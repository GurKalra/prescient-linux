import typer
from rich.console import Console 
import sys
import select

from sentinel.core.hooks import install
from sentinel.vanguard.security import analyze_security_risk
from sentinel.vanguard.boot import analyze_boot_health
from sentinel.vanguard.system import run_preflight_checks, assess_blast_radius
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
        console.print("\n[bold red]!!!SENTINEL VETO: System health checks failed!!![/bold red]")
        console.print("[white]Aborting installation to prevent system breakage.[/white]")
        sys.exit(1)  # This stops the APT transaction

    # 2. The Surgical Probes & Recovery Engine
    if input_data:
        analyze_boot_health(input_data)
        analyze_security_risk(input_data)

        #3. Assess the Blast Radius (The Recovery Engine)
        is_scary, risk_category = assess_blast_radius(input_data)

        if is_scary:
            console.print(f"\n[bold cyan] High-Risk Update Detected: [white]{risk_category}[/white][/bold cyan]")
            console.print("  [cyan]Engaging Recovery Guardrails...[/cyan]")
            trigger_snapshot(input_data)
        
    console.print("\n[bold green]Sentinel Audit Complete. Proceeding with transaction...[/bold green]")

@app.command()
def diagnose():
    """
    Analyze system logs from the current boot to identify critical failures.
    """
    console.print("\n[bold cyan]~~~ Sentinel Post-Crash Diagnostics ~~~[/bold cyan]")
    run_diagnostics()

@app.command()
def install_hooks():
    """
    Install package manager hooks to run sentinel automatically (Requires Root).
    """
    install()

@app.command()
def undo():
    """
    Instantly revert the system to the last Sentinel-created snapshot.
    """
    console.print("\n[bold yellow]🚧 The 'undo' engine is currently under construction.[/bold yellow]")
    console.print("[white]Soon, this will automatically restore your last Timeshift/Snapper backup.[/white]\n")

@app.command()
def heal():
    """
    Auto-restart crashed user-space services based on recent log diagnostics.
    """
    console.print("\n[bold yellow]🚧 The 'heal' engine is currently under construction.[/bold yellow]")
    console.print("[white]Soon, this will cross-reference diagnostics and restart broken daemons.[/white]\n")

if __name__=="__main__":
    app()
