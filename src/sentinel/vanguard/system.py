import shutil
import os
import subprocess
import shlex
import re
from rich.console import Console
from sentinel.config import CONFIG
from sentinel.core.logger import logger
from sentinel.intelligence.heuristic import scan_transaction_heuristics

console = Console()

def parse_and_sanitize_packages(raw_input: str) -> list[str]:
    """
    Parses raw stdin from the package manager and neutralizes shell injection threats.
    Extracts the exact package names from APT cache paths
    Returns a clean list of safe package names.
    """
    clean_packages = []
    lines = raw_input.strip().splitlines()
    safe_pattern = re.compile(r"^[a-zA-Z0-9\-_\.\+]+$")

    in_packages = False
    if not lines or not lines[0].startswith("VERSION"):
        in_packages = True

    for line in lines:
        line = line.strip()
        
        if not line:
            in_packages = True
            continue

        if not in_packages:
            continue

        # Extract filename from path
        first_token = line.split()[0]
        basename = line.split('/')[-1]

        # Extract actual package name
        if basename.endswith(".deb"):
            pkg_name = basename.split('_')[0]
        else:
            pkg_name = basename

        # Apply strict shell-injection guards to the isolated name
        if safe_pattern.match(pkg_name):
            safe_pkg = shlex.quote(pkg_name)
            clean_packages.append(safe_pkg)
        else:
            logger.warning(f"SECURITY THREAT: Dropped malformed/malicious package input: '{pkg_name}'")
        
    return clean_packages

def check_root_space(min_gb=2.0) -> tuple[bool, float]:
    """
    Checks if the root partition has enough free space to safely run an upgrade.
    """
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3) #byte to gigabytes
        return free_gb >= min_gb, free_gb
    except Exception as e:
        # If we can't read the disk for some reason, fail open but log it
        logger.warning(f"Failed to read root disk space: {e}")
        console.print(f"[dim yellow]Warning: Could not read root disk space ({e})[/dim yellow]")
        return True, 0.0

def check_dpkg_health() -> tuple[bool, str]:
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
        logger.error("Health Check Failed: 'dpkg' command not found.")
        console.print("[dim red]Error: 'dpkg' command not found.[/dim red]")
        return False, "dpkg not found"
    except subprocess.TimeoutExpired:
        logger.error("Health Check Failed: 'dpkg --audit' timed out.")
        return False, "dpkg --audit timed out. dpkg might be locked."
    
def run_preflight_checks() -> bool:
    """
    Executes all system-level health checks.
    Returns True if safe to proceed, False if a Hard-Stop is required.
    """
    console.print("[bold cyan]~~~Sentinel Pre-Flight Audit...~~~[/bold cyan]")
    logger.info("Initiating pre-flight system health audit.")
    is_safe = True

    sudo_cmd = os.environ.get("SUDO_COMMAND", "").lower()
    is_removal = "remove" in sudo_cmd or "purge" in sudo_cmd or "autoremove" in sudo_cmd

    #1. DPKG Health Check
    dpkg_ok, dpkg_log = check_dpkg_health()
    if(dpkg_ok):
        console.print("  Package Manager State: [bold green]Healthy[/bold green]")
    else:
        logger.error(f"Pre-flight VETO: Package manager is broken. Reason: {dpkg_log.splitlines()[0] if dpkg_log else 'Unknown'}")
        console.print("  Package Manager State: [bold red]BROKEN[/bold red]")
        console.print(f"    [yellow]Reason:[/yellow] {dpkg_log.splitlines()[0] if dpkg_log else 'Unknown error'}")
        console.print("    [white]Run 'sudo apt install -f' to fix broken dependencies before updating.[/white]")
        is_safe = False

    #2. Root Disk Space Check
    space_ok, free_gb = check_root_space()
    if space_ok:
        console.print(f" Root Partition Space: [bold green]{free_gb:.2f} GB free[/bold green]")
    else:
        if is_removal:
            logger.warning(f"Root partition critically low on space ({free_gb:.2f} GB free), but permitting removal.")
            console.print(f" Root Partition Space: [bold yellow]{free_gb:.2f} GB free[/bold yellow] (Minimum required: 2.0 GB)")
            console.print("    [bold green]Removal detected. Bypassing space limit to allow disk cleanup.[/bold green]")
        else:
            logger.error(f"Pre-flight VETO: Root partition critically low on space ({free_gb:.2f} GB free).")
            console.print(f" Root Partition Space: [bold red]{free_gb:.2f} GB free[/bold red] (Minimum required: 2.0 GB)")
            console.print("    [white]Running an update with low disk space can corrupt your system. Please free up space.[/white]")
            is_safe = False

    if is_safe:
        logger.info("Pre-flight audit passed successfully.")

    return is_safe

def assess_blast_radius(safe_package_list: list[str]) -> tuple[bool, str]:
    """
    Determines if the update touches critical core system components
    by reading the extensible rules schema (sentinel.toml).
    """
    high_risk_triggers = CONFIG.get("triggers", {}).get("high_risk", {})
    medium_risk_triggers = CONFIG.get("triggers", {}).get("medium_risk", {})

    def is_match(pkg, trigger):
        return pkg == trigger or pkg.startswith(trigger + "-")

    # Checking high risk packages
    for category, packages in high_risk_triggers.items():
        for trigger in packages:
            if any(is_match(pkg, trigger) for pkg in safe_package_list):
                return True, f"Critical System Component ({category.capitalize()})"

    # Checking for medium risk
    for category, packages in medium_risk_triggers.items():
        for trigger in packages:
            if any(is_match(pkg, trigger) for pkg in safe_package_list):                                                
                return True, f"Core Subsystem ({category.replace('_', ' ').title()})"
    
    logger.info("Packages not found in static config. Deferring to Heuristic Engine.")
    is_scary, reason = scan_transaction_heuristics(safe_package_list)

    if is_scary:
        return True, reason
            
    return False, "Standard Package Update"