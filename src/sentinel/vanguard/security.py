import subprocess
from rich.console import Console
from sentinel.core.cache import get_cached_state, set_cached_state
from sentinel.config import CONFIG
from sentinel.core.logger import logger

console = Console()

def get_secure_boot_status() -> bool:
    """Checks if Secure Boot is enabled, utilizing the RAM cache for speed."""
    cache = get_cached_state() or {}
    if "sb_enabled" in cache:
        logger.debug("Secure Boot status retrieved from cache.")
        return cache["sb_enabled"]
    
    try:
        #Timeout ensures sentinel never hangs the update process
        res = subprocess.run(
            ['mokutil', '--sb-state'], 
            capture_output=True,
            text=True,
            timeout=2
        ) 
        is_enabled = "enabled" in res.stdout.lower()
        set_cached_state({"sb_enabled": is_enabled})
        logger.debug(f"Secure Boot status verified via mokutil: {is_enabled}")
        return is_enabled
    except Exception as e:
        # If mokutil isn't installed or fails, assume permissive mode
        logger.warning(f"Failed to check Secure Boot status (assuming permissive): {e}")
        return False
    
def get_dkms_modules() -> list[str]:
    """Fetches currently installed DKMS modules."""
    try:
        res = subprocess.run(
            ['dkms', 'status'], 
            capture_output=True, 
            text=True, 
            timeout=3
        )
        # Returns a list of lines like "nvidia, 535.104.05, 6.8.0-40-generic, x86_64: installed"
        modules = res.stdout.strip().splitlines()
        logger.debug(f"Found {len(modules)} active DKMS modules.")
        return modules
    except Exception as e:
        logger.warning(f"Failed to fetch DKMS status: {e}")
        return []
    
def analyze_security_risk(safe_package_list: list[str]) -> bool:
    """
    Surgical Trigger: Only wakes up if DKMS, Kernel, or Bootloader are changing.
    """
    # Loading the list from the sentinel.toml
    triggers = CONFIG.get("triggers", {})
    kernel_pkgs = triggers.get("high_risk", {}).get("kernel", [])
    boot_pkgs = triggers.get("high_risk", {}).get("bootloader", [])
    driver_pkgs = triggers.get("medium_risk", {}).get("drivers", [])
    
    # Checking packages in the input matches
    kernel_changing = any(trigger in pkg for pkg in safe_package_list for trigger in kernel_pkgs)
    shim_changing = any(trigger in pkg for pkg in safe_package_list for trigger in boot_pkgs)
    dkms_changing = any(trigger in pkg for pkg in safe_package_list for trigger in driver_pkgs)

    # THE TRIGGER: Fast-pass if this is a boring update (like 'curl' or 'vlc')
    if not (kernel_changing or dkms_changing or shim_changing):
        return True

    console.print("[bold blue]Sentinel Security & Driver Audit...[/bold blue]")
    
    sb_active = get_secure_boot_status()
    dkms_modules = get_dkms_modules()
    
    if shim_changing:
        logger.warning("Bootloader/Shim update detected in transaction.")
        console.print("  Bootloader Update: [bold yellow]GRUB/Shim signatures are changing.[/bold yellow]")

    if sb_active:
        logger.info("Secure Boot is ENABLED.")
        console.print(f"  Secure Boot State: [bold green]ENABLED[/bold green]")
        
        # The ultimate collision: Secure Boot is ON, Kernel is updating, and we have DKMS modules.
        if kernel_changing and dkms_modules:
            logger.error("Collision Risk: Kernel update with active DKMS modules under Secure Boot.")
            console.print("  Driver Collision Risk: [bold red]Unsigned Modules vs. New Kernel[/bold red]")
            for mod in dkms_modules:
                mod_name = mod.split(',')[0] if ',' in mod else mod
                console.print(f"    - Found active DKMS module: [white]{mod_name}[/white]")
            console.print("    [yellow]Action Required:[/yellow] Ensure you have a MOK (Machine Owner Key) enrolled.")
            console.print("    [white]If these modules are not signed during the update, your system may boot to a black screen.[/white]")
    else:
        logger.info("Secure Boot is DISABLED (Permissive Mode).")
        console.print(f"  Secure Boot State: [bold yellow]DISABLED (Permissive Mode)[/bold yellow]")
        if kernel_changing and dkms_modules:
            logger.info("DKMS modules will rebuild safely (Secure Boot is off).")
            console.print("    [white]DKMS modules will rebuild automatically for the new kernel. No MOK signing required.[/white]")

    return True