import subprocess
import shutil
import re
import time
import os
import json
from pathlib import Path
from rich.console import Console
from sentinel.core.logger import logger

console = Console()

COOLDOWN_SECONDS = 600
MIN_FREE_GB = 5
STATE_DIR = Path("/var/lib/sentinel")
STATE_FILE = STATE_DIR / "last_snapshot.json"

def check_disk_space() -> bool:
    """Ensures the root partition has enough free space for a snapshot."""
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)

    if free_gb < MIN_FREE_GB:
        logger.warning(f"Disk space low ({free_gb}GB free). Bypassing snapshot to prevent OS crash.")
        console.print(f"  [bold yellow] Low Disk Space ({free_gb}GB left). Bypassing snapshot.[/bold yellow]")
        return False
    return True

def get_last_snapshot_state() -> dict:
    """Safely reads the snapshot state JSON if it exists."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception as e:
        logger.error(f"Failed to read snapshot state: {e}")
        return {}

def is_in_cooldown() -> bool:
    """Checks if a snapshot was taken recently using the JSON state."""
    state = get_last_snapshot_state()
    if not state or "created_at" not in state:
        return False
    
    elapsed = time.time() - state["created_at"]
    if elapsed < COOLDOWN_SECONDS:
        mins_left = int((COOLDOWN_SECONDS - elapsed) / 60)
        logger.info(f"Snapshot skipped due to cooldown. ({mins_left}m remaining)")
        console.print(f"  [cyan]Recent snapshot detected. Skipping to save time (Cooldown: {mins_left}m left).[/cyan]")
        return True
    return False

def save_snapshot_state(provider: str, snap_id_or_name: str, reason: str):
    """
    Persists the snapshot metadata to disk.
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        state = {
            "provider": provider,
            "snapshot_name": snap_id_or_name,
            "created_at": time.time(),
            "trigger_reason": reason 
        }

        STATE_FILE.write_text(json.dumps(state, indent=4))

        if os.geteuid() == 0:
            os.chmod(STATE_FILE, 0o600)

        logger.debug(f"Saved snapshot state to {STATE_FILE}")
    except Exception as e:
        logger.error(f"Failed to save snapshot state: {e}")

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


def trigger_snapshot(package_data: str, trigger_reason: str = "Unknown Safety Trigger") -> bool:
    """
    Triggers an automated system snapshot using the available provider.
    Includes disk space guards, cooldown timers, and timeout protection.
    Returns True if successful, False otherwise.
    """
    provider = get_snapshot_provider()

    if not provider:
        logger.warning("No snapshot tool detected. Skipping guardrail.")
        console.print("  [yellow]No snapshot tool (Snapper/Timeshift) detected. Skipping recovery point.[/yellow]")
        return False
    
    if not check_disk_space():
        return False
    
    if is_in_cooldown():
        return False
    
    # Extract the first few characters of the update for the description
    preview = package_data[:25].replace('\n', ' ').strip()
    comment = f"Sentinel Pre-Update: {preview}..."
    logger.info(f"Triggering {provider} snapshot. Target: {comment}")

    with console.status (f"[bold cyan]Creating {provider.capitalize()} Snapshot (Do not close terminal (Max Wait: 120s))...[/bold cyan]", spinner="dots"):
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
                console.print(f"    [white]↳ To undo this update later, run:[/white] [bold yellow]sudo sentinel undo[/bold yellow]")
                
                save_snapshot_state(provider, snap_id, trigger_reason)
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
                console.print(f"    [white]↳ To undo this update later, run:[/white] [bold yellow]sudo sentinel undo[/bold yellow]")
                
                save_snapshot_state(provider, snap_name, trigger_reason)
                return True
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"CRITICAL: {provider.capitalize()} hung and timed out after 120s!")
            console.print(f"  [bold red] Snapshot Timed Out![/bold red]")
            console.print("  [white]The backup tool stopped responding. Proceeding to prevent system lock.[/white]")
            return False
        
        except subprocess.CalledProcessError as e:
            console.print(f"  [bold red]Snapshot Failed:[/bold red] {provider.capitalize()} returned an error.")
            # Exact error message for power users
            error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
            logger.error(f"{provider.capitalize()} returned an error: {error_msg}")
            if error_msg:
                console.print(f"    [dim white]Details: {error_msg}[/dim white]")
            return False