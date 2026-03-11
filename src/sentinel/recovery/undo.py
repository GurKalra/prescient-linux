import subprocess
import json
from pathlib import Path
from sentinel.core.logger import logger

STATE_FILE = Path("/var/lib/sentinel/last_snapshot.json")

def get_last_snapshot() -> dict | None:
    """Reads the JSON state file to retrieve the last snapshot data."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception as e:
        logger.error(f"Failed to read undo state: {e}")
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
            subprocess.run(["snapper", "rollback", snap_target], check=True)
            return True
        
        elif provider == "timeshift":
            logger.info(f"Executing Timeshift rollback to {snap_target}")
            subprocess.run([
                "timeshift", "--restore", "--snapshot", snap_target, 
                "--scripted", "--yes"
            ], check=True)
            return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{provider.capitalize()} rollback command failed: {e}")
        return False
    
    return False