import typer
from rich.console import Console 
import sys
import select

from sentinel.engine.security import analyze_security_risk
from sentinel.engine.boot import analyze_boot_health
from sentinel.engine.system import run_preflight_checks
from sentinel.hooks import install

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
        sys.exit(1)  # This LITERALLY stops the APT transaction

    # 2. The Surgical Probes (These will automatically skip if no danger keywords are found in input_data)
    analyze_boot_health(input_data)
    analyze_security_risk(input_data)

    console.print("\n[bold green]Sentinel Audit Complete. Proceeding with transaction...[/bold green]")

@app.command()
def diagnose():
    """To analyze system logs and suggest fixes"""
    print("Sentinel Diagnose: Analyzing system logs...")

@app.command()
def install_hooks():
    """
    Install package manager hooks to run sentinel automatically (Requires Root).
    """
    install()

if __name__=="__main__":
    app()
