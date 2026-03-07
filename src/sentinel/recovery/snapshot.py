import subprocess
import shutil
import re
from rich.console import Console
from sentinel.core.logger import logger

console = Console()

def get_snapshot_provider():
    """
    Detects if a supported system snapshot tool is installed.
    Prioritizes Snapper (BTRFS native), falls back to Timeshift.
    """

    if shutil.which("snapper"):
        return "snapper"
    if shutil.which("timeshift"):
        return "timeshift"
    return None

def trigger_snapshot(package_data: str):
    """
    Triggers an automated system snapshot using the available provider.
    Includes a 120-second circuit breaker to prevent blocking package managers.
    Returns True if successful, False otherwise.
    """
    provider = get_snapshot_provider()

    if not provider:
        logger.warning("No snapshot tool detected. Skipping guardrail.")
        console.print("  [yellow]No snapshot tool (Snapper/Timeshift) detected. Skipping recovery point.[/yellow]")
        return False
    
    # Extract the first few characters of the update for the description
    preview = package_data[:25].replace('\n', ' ').strip()
    comment = f"Sentinel Pre-Update: {preview}..."
    logger.info(f"Triggering {provider} snapshot. Target: {comment}")

    # We use console.status to show a loading spinner (Timeshift takes time, Snapper is instant)
    with console.status (f"[bold cyan]Creating {provider.capitalize()} Snapshot (Do not close terminal)...[/bold cyan]", spinner="dots"):
        try:
            if provider == "snapper":
                cmd = [
                    "snapper",
                    "create",
                    "--description", comment,
                    "--cleanup-algorithm", "number",
                    "--print-number"
                ]                        
                res = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
                snap_id = res.stdout.strip()
                
                logger.info(f"Snapper snapshot created successfully. ID: {snap_id}")
                console.print(f"  [bold green]Snapper Snapshot Created:[/bold green] ID [bold white]{snap_id}[/bold white]")
                console.print(f"    [white]↳ To undo this update later, run:[/white] [bold yellow]sudo snapper rollback {snap_id}[/bold yellow]")
                return True

            elif provider == "timeshift":
                cmd = [
                    "timeshift",
                    "--create",
                    "--comments", comment,
                    "--scripted",
                    "--yes"
                ]
                res = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
                
                match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", res.stdout)
                snap_name = match.group(1) if match else "latest"
                
                logger.info(f"Timeshift snapshot created successfully. Name: {snap_name}")
                console.print(f"  [bold green]Timeshift Snapshot Created:[/bold green] [bold white]{snap_name}[/bold white]")
                console.print(f"    [white]↳ To undo this update later, run:[/white] [bold yellow]sudo timeshift --restore --snapshot '{snap_name}'[/bold yellow]")
                return True
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"CRITICAL: {provider.capitalize()} hung and timed out after 120s!")
            console.print(f"  [bold red] Snapshot Timed Out![/bold red]")
            console.print("  [white]The backup tool stopped responding. Proceeding with update to prevent system lock.[/white]")
            return False
        
        except subprocess.CalledProcessError as e:
            console.print(f"  [bold red]Snapshot Failed:[/bold red] {provider.capitalize()} returned an error.")
            # Exact error message for power users
            error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
            logger.error(f"{provider.capitalize()} returned an error: {error_msg}")
            if error_msg:
                console.print(f"    [dim white]Details: {error_msg}[/dim white]")
            return False