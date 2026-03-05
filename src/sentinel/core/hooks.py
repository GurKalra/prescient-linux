import os
import shutil
import sys
from pathlib import Path
from rich.console import Console

console = Console()

def detect_package_manager():
    """Returns the name of the installed package manager."""
    if shutil.which("apt"):
        return "apt"
    elif shutil.which("pacman"):
        return "pacman"
    return None

def install():
    """Installs the Sentinel pre-transaction hooks."""
    console.print("[bold cyan]Sentinel Linux: Initializing Hook Installer...[/bold cyan]")
    
    # 1. Enforce Root Privileges
    if os.geteuid() != 0:
        console.print("[bold red] Error: Installing system hooks requires root privileges!!![/bold red]")
        console.print("Try running: [bold yellow]sudo sentinel install-hooks[/bold yellow]")
        sys.exit(1)

    # 2. Detect the Host OS Package Manager
    pm = detect_package_manager()
    
    if pm == "apt":
        install_apt_hook()
    elif pm == "pacman":
        install_pacman_hook()
    else:
        console.print("[bold red] Error: Unsupported package manager. Sentinel currently supports apt and pacman.[/bold red]")
        sys.exit(1)

def install_apt_hook():
    """Installs the pre-invoke hook for Debian/Ubuntu (APT)."""
    sentinel_bin = os.path.abspath(sys.argv[0])
    hook_path = Path("/etc/apt/apt.conf.d/99sentinel-guardian")
    hook_content = f'DPkg::Pre-Install-Pkgs {{"{sentinel_bin} predict";}};\n'
    
    try:
        hook_path.write_text(hook_content)
        console.print(f"[bold green] Sentinel APT hook installed successfully at {hook_path}[/bold green]")
        console.print(f"[dim]Hook wired to executable: {sentinel_bin}[/dim]")
    except Exception as e:
        console.print(f"[bold red] Failed to write APT hook: {e}!!![/bold red]")
        sys.exit(1)

def install_pacman_hook():
    """Installs the pre-transaction hook for Arch Linux (Pacman)."""
    sentinel_bin = os.path.abspath(sys.argv[0])
    hook_dir = Path("/etc/pacman.d/hooks")
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hook_dir / "99-sentinel-guardian.hook"
    
    hook_content = f"""[Trigger]
Operation = Upgrade
Operation = Install
Type = Package
Target = *

[Action]
Description = Sentinel Linux: Analyzing blast radius...
When = PreTransaction
Exec = {sentinel_bin} predict
AbortOnFail
"""
    try:
        hook_path.write_text(hook_content)
        console.print(f"[bold green]Sentinel Pacman hook installed successfully at {hook_path}[/bold green]")
        console.print("[dim]Hook wired to executable: {sentinel_bin}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Failed to write Pacman hook: {e}!!!![/bold red]")
        sys.exit(1)