import os
import sys
from pathlib import Path
from rich.console import Console

from prescient.core.utils import detect_package_manager
from prescient.core.logger import logger

console = Console()

def install():
    """Installs the prescient pre-transaction hooks."""
    logger.info("Initializing prescient Hook Installer.")
    console.print("[bold cyan]prescient Linux: Initializing Hook Installer...[/bold cyan]")
    
    # 1. Enforce Root Privileges
    if os.geteuid() != 0:
        logger.error("Hook installation failed: Root privileges required.")
        console.print("[bold red] Error: Installing system hooks requires root privileges!!![/bold red]")
        console.print("Try running: [bold yellow]sudo prescient install-hooks[/bold yellow]")
        sys.exit(1)

    # 2. Detect the Host OS Package Manager
    pm = detect_package_manager()
    
    if pm == "apt":
        logger.info("Detected APT package manager.")
        install_apt_hook()
    elif pm == "pacman":
        logger.info("Detected Pacman package manager.")
        install_pacman_hook()
    else:
        logger.error("Hook installation failed: Unsupported package manager detected.")
        console.print("[bold red] Error: Unsupported package manager. prescient currently supports apt and pacman.[/bold red]")
        sys.exit(1)

def install_apt_hook():
    """Installs the pre-invoke hook for Debian/Ubuntu (APT)."""
    prescient_bin = os.path.abspath(sys.argv[0])
    hook_path = Path("/etc/apt/apt.conf.d/99prescient-guardian")
    hook_content = f"""DPkg::Pre-Install-Pkgs {{"{prescient_bin} predict";}};
    DPkg::Tools::Options::{prescient_bin}::Version "3";"""
    
    try:
        hook_path.write_text(hook_content)
        logger.info(f"APT hook successfully installed at {hook_path}")
        console.print(f"[bold green] prescient APT hook installed successfully at {hook_path}[/bold green]")
        console.print(f"[dim]Hook wired to executable: {prescient_bin}[/dim]")
    except Exception as e:
        logger.error(f"Failed to write APT hook to {hook_path}: {e}")
        console.print(f"[bold red] Failed to write APT hook: {e}!!![/bold red]")
        sys.exit(1)

def install_pacman_hook():
    """Installs the pre-transaction hook for Arch Linux (Pacman)."""
    prescient_bin = os.path.abspath(sys.argv[0])
    hook_dir = Path("/etc/pacman.d/hooks")
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hook_dir / "99-prescient-guardian.hook"
    
    hook_content = f"""[Trigger]
Operation = Upgrade
Operation = Install
Type = Package
Target = *

[Action]
Description = prescient Linux: Analyzing blast radius...
When = PreTransaction
Exec = {prescient_bin} predict
NeedsTargets
AbortOnFail
"""
    try:
        hook_path.write_text(hook_content)
        logger.info(f"Pacman hook successfully installed at {hook_path}")
        console.print(f"[bold green]prescient Pacman hook installed successfully at {hook_path}[/bold green]")
        console.print(f"[dim]Hook wired to executable: {prescient_bin}[/dim]")
    except Exception as e:
        logger.error(f"Failed to write Pacman hook to {hook_path}: {e}")
        console.print(f"[bold red]Failed to write Pacman hook: {e}!!!![/bold red]")
        sys.exit(1)