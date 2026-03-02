import shutil
import subprocess
from rich.console import Console

console = Console()

def check_root_space(min_gb=2.0):
    """
    Checks if the root partition has enough free space to safely run an upgrade.
    Returns (is_healthy, free_gb).
    """
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3) #byte to gigabytes
        return free_gb >= min_gb, free_gb
    except Exception as e:
        # If we can't read the disk for some reason, fail open but log it
        console.print(f"[dim yellow]Warning: Could not read root disk space ({e})[/dim yellow]")
        return True, 0.0

def check_dpkg_health():
    """
    Runs 'dpkg --audit' to check for half-installed or broken packages.
    Returns (is_healthy, audit_output).
    """
    try:
        result = subprocess.run(
            ['dpkg', '--audit'],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.strip()

        # If output is completely empty, dpkg is perfectly healthy
        if not output:
            return True, ""
        
        return False, output
    except FileNotFoundError:
        console.print("[dim red]Error: 'dpkg' command not found.[/dim red]")
        return False, "dpkg not found"
    except subprocess.TimeoutExpired:
        return False, "dpkg --audit timed out. dpkg might be locked."
    
def run_preflight_checks():
    """
    Executes all system-level health checks.
    Returns True if safe to proceed, False if a Hard-Stop is required.
    """
    console.print("[bold cyan]~~~Sentinel Pre-Flight Audit...~~~[/bold cyan]")
    is_safe = True

    #1. DPKG Health Check
    dpkg_ok, dpkg_log = check_dpkg_health()
    if(dpkg_ok):
        console.print("  [green]✓[/green] Package Manager State: [bold green]Healthy[/bold green]")
    else:
        console.print("  [red]✗[/red] Package Manager State: [bold red]BROKEN[/bold red]")
        console.print(f"    [yellow]Reason:[/yellow] {dpkg_log.splitlines()[0] if dpkg_log else 'Unknown error'}")
        console.print("    [white]Run 'sudo apt install -f' to fix broken dependencies before updating.[/white]")
        is_safe = False

    #2. Root Disk Space Check
    space_ok, free_gb = check_root_space()
    if space_ok:
        console.print(f" Root Partition Space: [bold green]{free_gb:.2f} GB free[/bold green]")
    else:
        console.print(f" Root Partition Space: [bold red]{free_gb:.2f} GB free[/bold red] (Minimum required: 2.0 GB)")
        console.print("    [white]Running an update with low disk space can corrupt your system. Please free up space.[/white]")
        is_safe = False
    
    return is_safe