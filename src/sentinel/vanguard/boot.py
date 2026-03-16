import os
import shutil
import shlex
from rich.console import Console
from sentinel.config import CONFIG
from sentinel.core.logger import logger

console = Console()

def check_boot_space(min_mb: int = 500) -> tuple[bool, float]:
    """
    Checks if /boot has enough space for a new kernel image and initramfs.
    """
    try:
        usage = shutil.disk_usage("/boot")
        free_mb = usage.free / (1024 * 1024)
        is_healthy = free_mb >= min_mb

        if not is_healthy:
            logger.warning(f"/boot partition space critically low: {free_mb:.0f} MB free.")
        
        return is_healthy, free_mb

    except FileNotFoundError:
        # If /boot doesn't exist as a distinct path, it's likely part of root.
        logger.info("/boot directory not found (likely unified with root). Bypassing boot space check.")
        return True, 0.0
    except Exception as e:
        logger.warning(f"Failed to read /boot disk space: {e}")
        return True, 0.0
    
def count_installed_kernels() -> int:
    """Counts the number of kernel images currently sitting in /boot."""
    try:
        kernels = [f for f in os.listdir("/boot") if f.startswith("vmlinuz")]
        count = len(kernels)
        logger.debug(f"Found {count} installed kernels in /boot.")
        return count
    except FileNotFoundError:
        logger.error("/boot directory not found during kernel count.")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error counting kernels: {e}")
        return 0

def analyze_boot_health(safe_package_list: list[str]) -> bool:
    """
    Dynamic Trigger: Reads the TOML configuration to determine what constitutes
    a kernel or bootloader update, preserving shlex injection security.
    """
    triggers = CONFIG.get("triggers", {})
    kernel_pkgs = triggers.get("high_risk", {}).get("kernel", [])
    boot_pkgs = triggers.get("high_risk", {}).get("bootloader", [])

    boot_triggers = kernel_pkgs + boot_pkgs 
    # Skip if it is a normal app update
    is_boot_update = False
    for trigger in boot_triggers:
        if any(pkg == trigger or pkg.startswith(trigger + "-") for pkg in safe_package_list):
            is_boot_update = True
            break
        
    if not is_boot_update:
        return True
    
    logger.info("Kernel/Bootloader update detected. Auditing /boot partition health.")
    console.print("[bold magenta]Kernel/Boot Update Detected. Auditing /boot partition...[/bold magenta]")

    is_safe = True

    #1. Check space
    space_ok, free_mb = check_boot_space()
    if space_ok:
        console.print(f"  /boot Partition Space: [bold green]{free_mb:.0f} MB free[/bold green]")
    else:
        logger.error(f"Boot Audit Failed: /boot space too low ({free_mb:.0f} MB).")
        console.print(f"  /boot Partition Space: [bold red]{free_mb:.0f} MB free[/bold red] (Minimum: 500 MB)")
        console.print("    [white]A kernel update with a full /boot partition will fail and break your bootloader.[/white]")
        is_safe = False

    # 2. Check Kernel Clutter
    kernel_count = count_installed_kernels()
    if kernel_count >= 3:
        logger.warning(f"Kernel clutter detected: {kernel_count} old kernels installed.")
        console.print(f"  Old Kernels Detected: [bold yellow]{kernel_count} installed[/bold yellow]")
        console.print("   [white]Run 'sudo apt autoremove' to clear old kernels and free up space.[/white]")

    if is_safe:
        logger.info("/boot partition audit passed.")
    
    return is_safe