import os
import shutil
from rich.console import Console

console = Console()

def check_boot_space(min_mb=500):
    """
    Checks if /boot has enough space for a new kernel image and initramfs.
    Returns (is_healthy, free_mb).
    """
    try:
        usage = shutil.disk_usage("/boot")
        free_mb = usage.free / (1024 * 1024)
        return free_mb >= min_mb, free_mb
    except FileNotFoundError:
        # If /boot doesn't exist as a distinct path, it's likely part of root.
        return True, 0.0
    
def count_installed_kernels():
    """Counts the number of kernel images currently sitting in /boot."""
    try:
        kernels = [f for f in os.listdir("/boot") if f.startswith("vmlinuz")]
        return len(kernels)
    except FileNotFoundError:
        return 0

def analyze_boot_health(package_list):
    """
    Surgical Trigger: Only runs if kernel or initramfs packages are in the transaction.
    """
    # THE TRIGGER: Skip entirely if this is just a normal app update
    if not("linux-image" in package_list or "initramfs" in package_list):
        return True
    
    console.print("[bold magenta]Kernel/Boot Update Detected. Auditing /boot partition...[/bold magenta]")

    is_safe = True

    #1. Check space
    space_ok, free_mb = check_boot_space()
    if space_ok:
        console.print(f"  /boot Partition Space: [bold green]{free_mb:.0f} MB free[/bold green]")
    else:
        console.print(f"  /boot Partition Space: [bold red]{free_mb:.0f} MB free[/bold red] (Minimum: 500 MB)")
        console.print("    [white]A kernel update with a full /boot partition will fail and break your bootloader.[/white]")
        is_safe = False

    # 2. Check Kernel Clutter
    kernel_count = count_installed_kernels()
    if kernel_count >= 3:
        console.print(f"  Old Kernels Detected: [bold yellow]{kernel_count} installed[/bold yellow]")
        console.print("   Run 'sudo apt autoremove' to clear old kernels and free up space.[/white]")

    return is_safe