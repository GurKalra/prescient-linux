import subprocess
import json
from rich.console import Console
from rich.table import Table
from prescient.core.logger import logger

console = Console()

def get_structured_logs(previous: bool = False) -> list:
    """
    Fetches high-priority errors from the current boot as structured JSON.
    Priority 3 = Errors, 2 = Critical, 1 = Alerts, 0 = Emergencies.
    """
    boot_flag = "-1" if previous else "0"
    try:
        logger.debug(f"Executing journalctl to fetch structured logs. (boot: {boot_flag}).")
        cmd = ["journalctl", "-p", "3", "-b", boot_flag, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        logs=[]
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return logs
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to read system journals: {e}")
        console.print(f"[yellow] Unable to read system journals for {boot_flag}. Are you running as root?[/yellow]")
        return []
    except FileNotFoundError:
        logger.error("journalctl command not found on host.")
        console.print("[bold red]!!! journalctl command not found. Is systemd installed?[/bold red]")
        return []
    
def run_diagnostics(previous: bool = False) -> list:
    """
    Dynamically analyzes logs to find the root cause of system instability
    Also provides the sorted list for autoheal engine
    """
    boot_str = "previous" if previous else "current"
    logger.info(f"Starting diagnostic scan of {boot_str} boot logs.")
    with console.status(f"[bold cyan] prescient is dynamically analyzing {boot_str} boot logs...[/bold cyan]", spinner="bouncingBar"):
        logs = get_structured_logs(previous=previous)

    if not logs:
        logger.info(f"Diagnostic scan clean. No critical errors found in {boot_str} boot.")
        console.print(f"[bold green] No critical errors found in the {boot_str} boot log![/bold green]")
        return []
    
    # Dyanmically grouping errors by program/service
    culprits = {}
    for log in logs:
        # Current Fallback order: SYSLOG_IDENTIFIER -> _SYSTEMD_UNIT -> _COMM -> Unknown
        identifier = log.get("SYSLOG_IDENTIFIER") or log.get("_SYSTEMD_UNIT") or log.get("_COMM") or "Unknown Subsystem"
        message = log.get("MESSAGE", "No error message provided.")

        identifier = str(identifier).replace(".service", "")

        if identifier not in culprits:
            culprits[identifier] = {"count":1, "latest_msg":message}
        else:
            culprits[identifier]["count"] += 1
            culprits[identifier]["latest_msg"] = message
    
    # Sorting culprits by no of errors they throw
    sorted_culprits = sorted(culprits.items(), key=lambda item: item[1]["count"], reverse=True)

    logger.warning(f"System instability detected: {len(logs)} total errors across {len(sorted_culprits)} subsystems.")
    console.print(f"\n[bold red]!!!!! System Instability Detected ({len(logs)} total errors in {boot_str} boot)[/bold red]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Failing Subsystem", style="bold yellow", width=25)
    table.add_column("Error Count", justify="right", style="red")
    table.add_column("Latest Error Message", style="dim white")

    for identifier, data in sorted_culprits[:5]:
        sample = str(data["latest_msg"])
        if len(sample) > 70:
            sample = sample[:67] + "..."
        
        table.add_row(identifier, str(data["count"]), sample)

    console.print(table)
    console.print("\n[bold cyan] Tip: If you are stuck in a TTY, identify the failing subsystem above.[/bold cyan]")
    console.print("[bold cyan]   If an update caused this, run your Timeshift/Snapper restore command.[/bold cyan]\n")

    return sorted_culprits

def get_raw_journalctl_output(lines: int = 50, previous: bool = False) -> str:
    """
    Fetches the raw text output of recent journalctl errors for the crash report.
    """
    boot_flag = "-1" if previous else "0"
    try:
        cmd = ["journalctl", "-p", "3", "-b", boot_flag, "-n", str(lines)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except Exception as e:
        logger.error(f"Failed to fetch raw journalctl logs: {e}")
        return f"Failed to fetch raw journalctl logs: {e}\n"