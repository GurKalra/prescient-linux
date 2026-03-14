import typer
from rich.console import Console 
import sys
import os
import time
import select

from sentinel.core.hooks import install
from sentinel.core.logger import logger
from sentinel.vanguard.security import analyze_security_risk
from sentinel.vanguard.boot import analyze_boot_health
from sentinel.vanguard.system import run_preflight_checks, assess_blast_radius, parse_and_sanitize_packages
from sentinel.recovery.snapshot import trigger_snapshot
from sentinel.intelligence.diagnose import run_diagnostics
from sentinel.intelligence.autoheal import run_autoheal_sequence
from sentinel.recovery.undo import get_last_snapshot, verify_snapshot, execute_rollback

console = Console()
app = typer.Typer(help="Sentinel Linux: Predict, Protect, Recover")

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
def install_hooks():
    """
    Install package manager hooks to run sentinel automatically (Requires Root).
    """
    logger.info("Installing package manager hooks.")
    install()

@app.command()
def predict():
    """
    Surgically analyze the incoming update for system and bootloader collisions.
    """
    input_data = ""

    #if nothing arrives, sentinel will not freeze. It will keep going
    if not sys.stdin.isatty():
        input_data = sys.stdin.read()

    # 1. IMMEDIATE HARD STOP (Pre-flight health)
    if not run_preflight_checks():
        logger.error("VETO: System pre-flight health checks failed. Aborting transaction.")
        console.print("\n[bold red]!!!SENTINEL VETO: System health checks failed!!![/bold red]")
        console.print("[white]Aborting installation to prevent system breakage.[/white]")
        sys.exit(1)  # This stops the APT transaction

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
    console.print("\n[bold green]Sentinel Audit Complete. Proceeding with transaction...[/bold green]")

@app.command()
def diagnose():
    """
    Analyze system logs from the current boot to identify critical failures.
    """
    logger.info("User initiated post-crash diagnostics.")
    console.print("\n[bold cyan]~~~ Sentinel Post-Crash Diagnostics ~~~[/bold cyan]")
    run_diagnostics()


@app.command()
def undo():
    """
    Instantly revert the system to the last Sentinel-created snapshot.
    """
    logger.info("User requested atomic rollback (undo)")

    # Root check
    if os.geteuid() != 0:
        logger.error("Undo failed: Root privileges required.")
        console.print("\n[bold red]Error: Restoring a root filesystem requires root privileges.[/bold red]")
        console.print("Try running: [bold yellow]sudo sentinel undo[/bold yellow]\n")
        sys.exit(1)

    console.print("\n[bold cyan]~~~ Sentinel Recovery Engine ~~~[/bold cyan]")

    # State check
    state = get_last_snapshot()
    if not state:
        logger.warning("Undo aborted: No snapshot history found.")
        console.print("[yellow]No recent Sentinel snapshots found on this system.[/yellow]")
        console.print("[dim white]If you recently installed Sentinel, a snapshot will be created automatically on your next high-risk update.[/dim white]\n")
        sys.exit(0)

    # Verification check
    console.print("[dim]Verifying snapshot integrity...[/dim]")
    if not verify_snapshot(state):
        logger.error(f"Undo aborted: Snapshot {state.get('snapshot_name')} no longer exists.")
        console.print(f"[bold red]Error: The snapshot '{state.get('snapshot_name')}' could not be found.[/bold red]")
        console.print("[white]It may have been manually deleted or cleared by your backup provider's cleanup rules.[/white]\n")
        sys.exit(1)

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
        console.print("[bold red]Rollback failed. Check /var/log/sentinel.log for details.[/bold red]\n")
        sys.exit(1)

@app.command()
def heal():
    """
    Transparently propose and execute fixes for crashed services based on log diagnostics.
    """
    logger.info("User requested heal. Feature under construction.")
    console.print("\n[bold cyan]~~~ Sentinel Diagnostics & Auto-Heal ~~~[/bold cyan]")

    culprits = run_diagnostics()
    run_autoheal_sequence(culprits)

if __name__=="__main__":
    app()
