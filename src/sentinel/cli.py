import typer
from rich.console import Console 
import sys
import select

from sentinel.core.hooks import install
from sentinel.core.logger import logger
from sentinel.vanguard.security import analyze_security_risk
from sentinel.vanguard.boot import analyze_boot_health
from sentinel.vanguard.system import run_preflight_checks, assess_blast_radius, parse_and_sanitize_packages
from sentinel.recovery.snapshot import trigger_snapshot
from sentinel.intelligence.diagnose import run_diagnostics

console = Console()
app = typer.Typer(help="Sentinel Linux: Predict, Protect, Recover")

@app.command()
def predict():
    """
    Surgically analyze the incoming update for system and bootloader collisions.
    """
    input_data = ""

    #if nothing arrives, sentinel will not freeze. It will keep going
    ready, _, _ = select.select([sys.stdin], [], [], 0.1)
    if ready:
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
            trigger_snapshot(input_data)
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
def install_hooks():
    """
    Install package manager hooks to run sentinel automatically (Requires Root).
    """
    logger.info("Installing package manager hooks.")
    install()

@app.command()
def undo():
    """
    Instantly revert the system to the last Sentinel-created snapshot.
    """
    logger.info("User requested undo. Feature under construction.")
    console.print("\n[bold yellow]🚧 The 'undo' engine is currently under construction.[/bold yellow]")
    console.print("[white]Soon, this will automatically restore your last Timeshift/Snapper backup.[/white]\n")

@app.command()
def heal():
    """
    Auto-restart crashed user-space services based on recent log diagnostics.
    """
    logger.info("User requested heal. Feature under construction.")
    console.print("\n[bold yellow]🚧 The 'heal' engine is currently under construction.[/bold yellow]")
    console.print("[white]Soon, this will cross-reference diagnostics and restart broken daemons.[/white]\n")

if __name__=="__main__":
    app()
