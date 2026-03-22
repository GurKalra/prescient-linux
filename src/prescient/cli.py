import typer
from rich.console import Console 
import sys
import subprocess
import os
import time
import select
import shutil
import pwd
import platform
from datetime import datetime

from prescient.core.hooks import install
from prescient.core.logger import logger
from prescient.core.update_checker import check_for_updates, get_local_version
from prescient.vanguard.security import analyze_security_risk
from prescient.vanguard.boot import analyze_boot_health
from prescient.vanguard.system import run_preflight_checks, assess_blast_radius, parse_and_sanitize_packages
from prescient.recovery.snapshot import trigger_snapshot
from prescient.intelligence.diagnose import run_diagnostics, get_raw_journalctl_output
from prescient.intelligence.autoheal import run_autoheal_sequence
from prescient.recovery.undo import get_last_snapshot, verify_snapshot, execute_rollback, get_latest_system_snapshot
from prescient.intelligence.network import export_to_termbin

console = Console()
app = typer.Typer(help="Prescient Linux: Predict, Protect, Recover")

def check_sudo(command_name: str, strict: bool=False):
    """
    Checks for root privileges.
    """
    if os.geteuid() != 0:
        if strict:
            console.print(f"\n[bold red]Error: `{command_name}` requires root privileges to execute.[/bold red]")
            console.print(f"Try running: [bold yellow]sudo prescient {command_name}[/bold yellow]\n")
            raise typer.Exit(code=1)
        else:
            console.print(f"[dim yellow]Hint: You are running `{command_name}` without sudo. Some system files may be unreadable.[/dim yellow]\n")

@app.callback()
def main(ctx: typer.Context):
    """
    Global hook that runs before commands to check for OTA updates.
    """
    if ctx.invoked_subcommand not in ["predict", "update", "uninstall", "install-hooks", "tui"]:
        if check_for_updates():
            console.print("[bold yellow]!A new version of Prescient is available![/bold yellow]")
            console.print("[dim]Run `sudo prescient update` to install it securely.[/dim]\n")

def _format_relative_time(timestamp: float) -> str:
    """
    Helper function to convert UNIX time to human readable format.
    """
    diff = time.time() - timestamp
    if diff < 60:
        return "Just now"
    elif diff < 3600:
        return f"{int(diff // 60)} minutes ago"
    elif diff < 86400:
        return f"{int(diff // 3600)} hours ago" 
    return f"{int(diff // 86400)} days ago"

@app.command()
def tui():
    """
    Launch the interactive Prescient Terminal UI.
    """
    logger.info("Initializing Prescient TUI...")

    from prescient.tui.app import PrescientTUI
    ui = PrescientTUI()
    ui.run()

@app.command()
def install_hooks():
    """
    Install package manager hooks to run prescient automatically (Requires Root).
    """
    check_sudo("install-hooks", strict=True)
    logger.info("Installing package manager hooks.")
    install()

@app.command()
def predict():
    """
    Surgically analyze the incoming update for system and bootloader collisions.
    """
    check_sudo("predict", strict=False)
    input_data = ""

    #if nothing arrives, prescient will not freeze. It will keep going
    if not sys.stdin.isatty():
        input_data = sys.stdin.read()

    # 1. IMMEDIATE HARD STOP (Pre-flight health)
    if not run_preflight_checks():
        logger.error("VETO: System pre-flight health checks failed. Aborting transaction.")
        console.print("\n[bold red]!!!Prescient VETO: System health checks failed!!![/bold red]")
        console.print("[white]Aborting installation to prevent system breakage.[/white]")
        raise typer.Exit(code=1)  # This stops the APT transaction

    # 2. The Surgical Probes & Recovery Engine
    if input_data:
        # Sanitizing the list first
        safe_package_list = parse_and_sanitize_packages(input_data)

        analyze_boot_health(safe_package_list)
        analyze_security_risk(safe_package_list)

        #3. Assess the Blast Radius (The Recovery Engine)
        is_scary, risk_category = assess_blast_radius(safe_package_list)

        if is_scary:
            logger.warning(f"High-Risk Update Detected ({risk_category}). Triggering snapshot.")
            console.print(f"\n[bold cyan] High-Risk Update Detected: [white]{risk_category}[/white][/bold cyan]")
            console.print("  [cyan]Engaging Recovery Guardrails...[/cyan]")
            trigger_snapshot(input_data, risk_category)
        else:
            logger.info("No high-risk packages detected in transaction.")

    logger.info("Audit complete. Proceeding with installation.")    
    console.print("\n[bold green]Prescient Audit Complete. Proceeding with transaction...[/bold green]")

@app.command()
def diagnose(
    share: bool = typer.Option(False, "--share", help="Export diagnostic logs to termbin.com or save locally.")
):
    """
    Analyze system logs from the current boot to identify critical failures.
    """
    check_sudo("diagnose", strict=False)
    logger.info("User initiated post-crash diagnostics.")
    console.print("\n[bold cyan]~~~ Prescient Post-Crash Diagnostics ~~~[/bold cyan]")
    culprits = run_diagnostics()

    if share:
        logger.info("User requested crash report export.")
        console.print("\n[dim yellow]Note: Logs will be uploaded publicly to termbin.com. Avoid sharing on sensitive systems.[/dim yellow]")
        console.print("[dim]Packaging crash report...[/dim]")

        # Building a report string for better readablity
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_text = f"=== PRESCIENT CRASH REPORT ===\n"
        report_text += f"Generated: {now}\n"
        report_text += f"Kernel: {platform.release()}\n"
        report_text += f"System: {platform.system()} {platform.version()}\n"
        report_text += f"{'='*30}\n\n"

        report_text += "IDENTIFIED CULPRITS (Failing Subsystems):\n"
        if culprits:
            for identifier, data in culprits:
                report_text += f"- {identifier}: {data['count']} errors (Latest: {data['latest_msg']})\n"
        else:
            report_text += "- No critical systemd errors found.\n"
        
        report_text += "\n=== RAW JOURNALCTL LOGS (Last 50) ===\n"
        report_text += get_raw_journalctl_output(50)

        # Trying termbin (requires internet)
        console.print("[dim]Attempting to upload to termbin.com...[/dim]")
        url = export_to_termbin(report_text)

        if url:
            logger.info(f"Crash report exported to termbin: {url}")
            console.print(f"[bold green]Report exported successfully![/bold green]")
            console.print(f"Share this URL for support: [bold cyan]{url}[/bold cyan]\n")
        else:
            # If not termbin, fallback to local saving
            fallback_path = "/tmp/prescient_crash_report.txt"
            logger.warning(f"Termbin upload failed. Saving report locally to {fallback_path}")
            try:
                with open(fallback_path, "w") as f:
                    f.write(report_text)
                
                os.chmod(fallback_path, 0o600)

                console.print("[bold red]Network upload failed (Are you offline?).[/bold red]")
                console.print(f"[bold yellow]✓ Saved crash report locally instead: {fallback_path}[/bold yellow]\n")
                console.print(f"[dim]You can read it with: cat {fallback_path}[/dim]\n")
            except Exception as e:
                logger.error(f"Failed to save local offline crash report: {e}")
                console.print(f"[bold red]Failed to save local report: {e}[/bold red]\n")

@app.command()
def undo():
    """
    Instantly revert the system to the last prescient-created snapshot.
    """
    check_sudo("undo", strict=True)
    logger.info("User requested atomic rollback (undo)")
    console.print("\n[bold cyan]~~~ Prescient Recovery Engine ~~~[/bold cyan]")

    # State check
    state = get_last_snapshot()
    if not state:
        logger.info("No Prescient state found. Scanning for manual system snapshots...")
        state = get_latest_system_snapshot()
    if not state:
        logger.warning("Undo aborted: No snapshot history found.")
        console.print("[yellow]No recent snapshots found on this system.[/yellow]")
        console.print("[dim white]If you recently installed prescient, a snapshot will be created automatically on your next high-risk update.[/dim white]\n")
        sys.exit(0)

    # Verification check
    console.print("[dim]Verifying snapshot integrity...[/dim]")
    if not verify_snapshot(state):
        logger.error(f"Undo aborted: Snapshot {state.get('snapshot_name')} no longer exists.")
        console.print(f"[bold red]Error: The snapshot '{state.get('snapshot_name')}' could not be found.[/bold red]")
        console.print("[white]It may have been manually deleted or cleared by your backup provider's cleanup rules.[/white]\n")
        raise typer.Exit(code=1)

    provider = str(state.get("provider", "unknown")).capitalize()
    snap_name = state.get("snapshot_name", "Unknown")
    reason = state.get("trigger_reason", "Unknown trigger")
    rel_time = _format_relative_time(state.get("created_at", time.time()))

    console.print(f"  [bold white]Provider:[/bold white]       {provider}")
    console.print(f"  [bold white]Snapshot Name:[/bold white]  [green]{snap_name}[/green]")
    console.print(f"  [bold white]Created:[/bold white]        {rel_time}")
    console.print(f"  [bold white]Trigger Reason:[/bold white] {reason}\n")
    
    console.print("[bold red]!!!!WARNING: This will overwrite your root filesystem and immediately reboot your machine.[/bold red]")

    confirm = typer.confirm("Proceed with system rollback?")

    if not confirm:
        logger.info("User aborted rollback at confirmation prompt.")
        console.print("[yellow]Rollback aborted by user.[/yellow]\n")
        sys.exit(0)

    # If confirmed, continue with the rollback
    console.print(f"\n[bold cyan]Initiating {provider} restoration...[/bold cyan]")
    success = execute_rollback(state)

    if success:
        if provider.lower() == "timeshift":
            console.print("[bold green]Rollback complete. Your system will reboot shortly.[/bold green]")
        else:
            console.print("[bold green]Rollback complete. Please reboot manually: [yellow]sudo reboot[/yellow][/bold green]")
    else:
        console.print("[bold red]Rollback failed. Check /var/log/prescient.log for details.[/bold red]\n")
        raise typer.Exit(code=1)

@app.command()
def heal():
    """
    Transparently propose and execute fixes for crashed services based on log diagnostics.
    """
    check_sudo("heal", strict=True)
    logger.info("User initiated Auto-Heal sequence.")
    console.print("\n[bold cyan]~~~ Prescient Diagnostics & Auto-Heal ~~~[/bold cyan]")

    culprits = run_diagnostics()
    run_autoheal_sequence(culprits)

@app.command()
def update(
    force: bool = typer.Option(False, "--force", help="Force reinstall even if up to date")
):
    """
    Securely pull and install the latest OTA update directly from GitHub.
    """
    check_sudo("update", strict=True)
    logger.info("User initiated secure OTA update.")    
    console.print("[bold cyan]Verifying system state and fetching latest updates...[/bold cyan]")

    # Checking for an actual update before pulling
    if not force:
        if not check_for_updates():
            console.print("[bold green]System is already up to date. No new OTA releases found.[/bold green]")
            console.print("[dim](Use 'sudo prescient update --force' to reinstall anyway)[/dim]\n")
            logger.info("OTA update skipped: System is already at the latest version.")
            raise typer.Exit()
    else:
        logger.info("OTA update forced by user (--force flag).")

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        real_home = pwd.getpwnam(sudo_user).pw_dir
    else:
        real_home = os.path.expanduser("~")
    
    install_dir = os.path.join(real_home, ".prescient")

    if not os.path.exists(install_dir) or not os.path.exists(os.path.join(install_dir, ".git")):
        console.print("[bold red]Error: Core installation directory (~/.prescient) or Git repository not found.[/bold red]")
        console.print("[white]Please re-run the initial installation script to repair the local repository.[/white]")
        raise typer.Exit(code=1)
    
    try:
        # Pull the latest code
        console.print("[dim]Pulling verified source code via git...[/dim]")
        subprocess.run(
            ["git", "-C", install_dir, "pull", "origin", "main"],
            check=True,
            capture_output=True,
            text=True
        )

        # Reinstall via pip (locally)
        console.print("[dim]Applying updates to isolated enviroment...[/dim]")
        python_path = os.path.join(install_dir, ".venv", "bin", "python")

        if not os.path.exists(python_path):
            console.print("[bold red]Error: Virtual environment not found in ~/.prescient/.venv[/bold red]")
            console.print("[white]Please re-run the installation script to repair it.[/white]")
            raise typer.Exit(code=1)
        
        pip_cmd = [python_path, "-m", "pip", "install", "--upgrade", "-e", "."]
        subprocess.run(
            pip_cmd,
            cwd=install_dir,
            check=True,
            capture_output=True,
            text=True
        )

        console.print("\n[bold green]Prescient updated successfully![/bold green]")
        logger.info(f"OTA update complete. Installed version: {get_local_version()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"OTA update failed during execution: {e.stderr if e.stderr else e}")
        console.print("\n[bold red]Update failed. Please check your network connection or repository state.[/bold red]")

@app.command()
def uninstall():
    """
    Complete self-destruct sequence. Removes all hooks, logs, binaries, and source files.
    """
    check_sudo("uninstall", strict=True)
    logger.info("User initiated self-destruct sequence (uninstall).")
    console.print("\n[bold red]!!! INITIATING PRESCIENT SELF-DESTRUCT !!![/bold red]")
    console.print("[white]This will permanently remove all hooks, logs, configs, and source files.[/white]")

    # Confirmation
    confirm = typer.confirm("Are you sure you want to purge prescient from this system?")
    if not confirm:
        logger.info("Uninstall aborted by user.")
        console.print("[yellow]Uninstall aborted. Prescient remains active.[/yellow]\n")
        sys.exit(0)

    console.print("\n[cyan]Purging system footprint...[/cyan]")

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        real_home = pwd.getpwnam(sudo_user).pw_dir
    else:
        real_home = os.path.expanduser("~")
    
    install_dir = os.path.join(real_home, ".prescient")

    # Defining the purge targets
    targets = {
        "APT Hook": "/etc/apt/apt.conf.d/99prescient-guardian",
        "Pacman Hook": "/etc/pacman.d/hooks/99-prescient.hook",
        "Initramfs Hook": "/etc/initramfs-tools/hooks/prescient-hook",
        "Mkinitcpio Hook": "/etc/initcpio/install/prescient-hook",
        "Rescue Binary": "/usr/local/bin/prescient-rescue",
        "System Configs": "/etc/prescient",
        "Logs Data": "/var/log/prescient.log",
        "State Directory": "/var/lib/prescient",
        "CLI Symlink": "/usr/local/bin/prescient",
        "Core Source Directory": install_dir
    }

    # Execute
    for name, path in targets.items():
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                console.print(f"  [green]Removed {name}[/green] ([dim]{path}[/dim])")
            
            except Exception as e:
                console.print(f"  [red]!!Failed to remove {name}[/red] ([dim]{e}[/dim])")
        else:
            console.print(f"  [dim]~ Skipped {name} (Not found)[/dim]")

    console.print("\n[bold green]Prescient has been completely erased from the system.[/bold green]")
    console.print("[white]Update lifecycle returned to standard package manager control.[/white]\n")


if __name__=="__main__":
    app()
