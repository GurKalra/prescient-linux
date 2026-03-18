import subprocess
import json
import re
import shutil
from pathlib import Path
from rich.console import Console
from prescient.core.logger import logger

console = Console()
STATE_FILE = Path("/var/lib/prescient/last_snapshot.json")

def get_last_snapshot() -> dict | None:
    """Reads the JSON state file to retrieve the last snapshot data."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception as e:
        logger.error(f"Failed to read undo state: {e}")
        return None

def get_latest_system_snapshot() -> dict | None:
    """
    Scans the system for the most recent Timeshift or Snapper snapshot if prescient's JSON is missing/not existing
    """
    # Timeshift checking
    if shutil.which("timeshift"):
        try:
            res = subprocess.run(
                ["timeshift", "--list"],
                capture_output=True,
                text=True
            )
            matches = re.findall(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", res.stdout)
            if matches:
                return{
                    "provider": "timeshift",
                    "snapshot_name": matches[-1], # Grab the very last one
                    "created_at": 0.0,
                    "trigger_reason": "Manual/System Snapshot (Non-Prescient)"
                }
        except Exception as e:
            logger.error(f"Failed to list timeshift snapshots: {e}")
    
    # Snapper checking
    if shutil.which("snapper"):
        try:
            res = subprocess.run(
                ["snapper", "list"],
                capture_output=True,
                text=True
            )
            lines = [line.strip() for line in res.stdout.splitline() if line.strip() and line.strip()[0].isdigit()]
            if lines:
                last_id = lines[-1].split()[0]
                return{
                    "provider": "snapper",
                    "snapshot_name": last_id,
                    "created_at": 0.0,
                    "trigger_reason": "Manual/System Snapshot (Non-Prescient)"
                }
        except Exception as e:
            logger.error(f"Failed to list snapper snapshots: {e}")
    
    return None
    
def verify_snapshot(state: dict) -> bool:
    """
    Asks the backup provider if the snapshot still exists on the disk.
    Prevents crashing if the user manually deleted the snapshot.
    """
    provider = state.get("provider")
    snap_target = str(state.get("snapshot_name", ""))

    if not provider or not snap_target:
        return False
    
    try:
        if provider == "snapper":
            res = subprocess.run(
                ["snapper", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return snap_target in res.stdout
        elif provider == "timeshift":
            res = subprocess.run(
                ["timeshift", "--list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return snap_target in res.stdout
    except Exception as e:
        logger.error(f"Snapshot verification failed for {provider}: {e}")
        return False

    return False

def execute_rollback(state: dict) -> bool:
    """Triggers the rollback command."""
    provider = state.get("provider")
    snap_target = str(state.get("snapshot_name", ""))

    try:
        if provider == "snapper":
            logger.info(f"Executing Snapper rollback to ID {snap_target}")
            subprocess.run(["snapper", "rollback", snap_target], check=True, timeout=300)
            return True
        
        elif provider == "timeshift":
            logger.info(f"Executing Timeshift rollback to {snap_target}")
            subprocess.run([
                "timeshift", "--restore", "--snapshot", snap_target, 
                "--scripted", "--yes"
            ], check=True, timeout=300)
            return True
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"CRITICAL: {provider.capitalize()} hung and timed out after 300s!")
        console.print(f"  [bold red] Snapshot Timed Out![/bold red]")
        console.print("  [white]The backup tool stopped responding. Proceeding to prevent system lock.[/white]")
        return False
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{provider.capitalize()} rollback command failed: {e}")
        return False
    
    return False