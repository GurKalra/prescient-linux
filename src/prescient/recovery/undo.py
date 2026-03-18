import subprocess
import json
import re
import shutil
from datetime import datetime
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
    In rescue context, reads Timeshift/Snapper directories directly instead of 
    calling their CLIs (which need D-Bus/systemd and fail in chroot). 
    """
    # Timeshift filesystem scan
    timeshift_config_path = Path("/etc/timeshift/timeshift.json")
    if timeshift_config_path.exists():
        try:
            snapshot_dirs = [
                Path("/run/timeshift/backup/timeshift/snapshots"),
                Path("/timeshift/snapshots"),
            ]

            for snap_dir in snapshot_dirs:
                if snap_dir.exists():
                    snaps = sorted([d for d in snap_dir.iterdir() if d.is_dir()])
                    if snaps:
                        latest = snaps[-1].name
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(latest, "%Y-%m-%d_%H-%M-%S")
                            ts = dt.timestamp()
                        except ValueError:
                            ts = 0.0
                        
                        logger.info(f"Found Timeshift snapshot via filesystem scan: {latest}")
                        return {
                            "provider": "timeshift",
                            "snapshot_name": latest,
                            "created_at": ts,
                            "trigger_reason": "Rescue Scan (Filesystem Direct)"
                        }
        except Exception as e:
                logger.error(f"Failed to scan Timeshift snapshots directly: {e}")

    # Snapper filesystem scan
    snapper_dir = Path("/.snapshots")
    if snapper_dir.exists():
        try:
            snap_ids = sorted([
                int(d.name) for d in snapper_dir.iterdir()
                if d.is_dir() and d.name.isdigit()
            ])
            if snap_ids:
                last_id = str(snap_ids[-1])
                logger.info(f"Found Snapper snapshot via filesystem scan: {last_id}")
                return {
                    "provider": "snapper",
                    "snapshot_name": last_id,
                    "created_at": 0.0,
                    "trigger_reason": "Rescue Scan (Filesystem Direct)"
                }
        except Exception as e:
            logger.error(f"Failed to scan Snapper snapshots: {e}")
        
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