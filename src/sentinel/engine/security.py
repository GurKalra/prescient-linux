import subprocess
from rich.console import Console
from sentinel.engine.cache import get_cached_state, set_cached_state

console = Console()

def get_secure_boot_status():
    """Checks if Secure Boot is enabled, utilizing the RAM cache for speed."""
    cache = get_cached_state()
    if "sb_enabled" in cache:
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
        return is_enabled
    except Exception:
        # If mokutil isn't installed or fails, assume permissive mode
        return False
    
def get_dkms_modules():
    """Fetches currently installed DKMS modules."""
    try:
        res = subprocess.run(
            ['dkms', 'status'], 
            capture_output=True, 
            text=True, 
            timeout=3
        )
        # Returns a list of lines like "nvidia, 535.104.05, 6.8.0-40-generic, x86_64: installed"
        return res.stdout.strip().splitlines()
    except Exception:
        return []
    
def analyze_security_risk(package_list):
    """
    Surgical Trigger: Only wakes up if DKMS, Kernel, or Bootloader are changing.
    """
    kernel_changing = "linux-image" in package_list or "linux-headers" in package_list
    dkms_changing = "dkms" in package_list or "nvidia" in package_list or "virtualbox" in package_list
    shim_changing = "shim" in package_list or "grub" in package_list
    
    # THE TRIGGER: Fast-pass if this is a boring update (like 'curl' or 'vlc')
    if not (kernel_changing or dkms_changing or shim_changing):
        return True

    console.print("[bold blue]🛡️  Sentinel Security & Driver Audit...[/bold blue]")
    
    sb_active = get_secure_boot_state()
    dkms_modules = get_dkms_modules()
    
    if shim_changing:
        console.print("  Bootloader Update: [bold yellow]GRUB/Shim signatures are changing.[/bold yellow]")

    if sb_active:
        console.print(f"  Secure Boot State: [bold green]ENABLED[/bold green]")
        
        # The ultimate collision: Secure Boot is ON, Kernel is updating, and we have DKMS modules.
        # This means the modules MUST be signed with a MOK key, or they will fail to load.
        if kernel_changing and dkms_modules:
            console.print("  Driver Collision Risk: [bold red]Unsigned Modules vs. New Kernel[/bold red]")
            for mod in dkms_modules:
                # Print just the module name, not the whole string
                mod_name = mod.split(',')[0] if ',' in mod else mod
                console.print(f"    - Found active DKMS module: [white]{mod_name}[/white]")
            console.print("    [yellow]Action Required:[/yellow] Ensure you have a MOK (Machine Owner Key) enrolled.")
            console.print("    [white]If these modules are not signed during the update, your system may boot to a black screen.[/white]")
    else:
        console.print(f"  Secure Boot State: [bold yellow]DISABLED (Permissive Mode)[/bold yellow]")
        if kernel_changing and dkms_modules:
            console.print("    [white]DKMS modules will rebuild automatically for the new kernel. No MOK signing required.[/white]")

    # We return True because we are warning the user, not forcing a hard-stop block.
    return True