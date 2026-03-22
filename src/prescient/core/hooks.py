import os
import sys
import typer
import shutil
import subprocess
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
        raise typer.Exit(code=1)

    # 2. Detect the Host OS Package Manager
    pm = detect_package_manager()
    
    if pm == "apt":
        logger.info("Detected APT package manager.")
        install_apt_hook()
        install_ramdisk_hook("apt")
    elif pm == "pacman":
        logger.info("Detected Pacman package manager.")
        install_pacman_hook()
        install_ramdisk_hook("pacman")
    else:
        logger.error("Hook installation failed: Unsupported package manager detected.")
        console.print("[bold red] Error: Unsupported package manager. prescient currently supports apt and pacman.[/bold red]")
        raise typer.Exit(code=1)

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
        raise typer.Exit(code=1)

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
        raise typer.Exit(code=1)

def install_ramdisk_hook(pm_type: str):
    """
    Installs the emergency rescue environment into the kernel RAM disk.
    """
    logger.info("Installing RAM disk rescue hooks...")
    console.print("\n[bold cyan]Injecting Emergency Rescue Environment into Kernel RAM Disk...[/bold cyan]")

    # Resolve the path to scripts(dynamically)
    core_dir = Path(__file__).parent
    initramfs_dir = core_dir.parent / "initramfs"

    rescue_src = initramfs_dir / "prescient-rescue.sh"
    ubuntu_hook_src = initramfs_dir / "prescient-ubuntu-hook"
    arch_hook_src = initramfs_dir / "prescient-arch-hook"

    rescue_dest = Path("/usr/local/bin/prescient-rescue")

    try:
        shutil.copy(rescue_src, rescue_dest)
        os.chmod(rescue_dest, 0o755)
        console.print("  [green]Universal Rescue Script installed to '/usr/local/bin/prescient-rescue'[/green]")
    except Exception as e:
        logger.error(f"Failed to install rescue script: {e}")
        console.print(f"  [red]!!!Failed to install rescue script: {e}[/red]")
        return
    
    # Install OS specific hook and rebuild the kernel
    try:
        if pm_type == "apt":
            hook_dest = Path("/etc/initramfs-tools/hooks/prescient-hook")
            shutil.copy(ubuntu_hook_src, hook_dest)
            os.chmod(hook_dest, 0o755)
            console.print("  [green]Ubuntu Initramfs Hook installed.[/green]")
            
            console.print("  [cyan]Rebuilding initramfs image... (This may take a minute)[/cyan]")
            subprocess.run(
                ["update-initramfs", "-u"],
                check=True
            )
            console.print("  [bold green]Kernel RAM Disk rebuilt successfully![/bold green]")

        elif pm_type == "pacman":
            hook_dir = Path("/etc/initcpio/install")
            hook_dir.mkdir(parents=True, exist_ok=True)
            hook_dest = hook_dir / "prescient-hook"

            shutil.copy(arch_hook_src, hook_dest)
            os.chmod(hook_dest, 0o755)
            console.print("  [green]✓ Arch mkinitcpio Hook installed.[/green]")
            
            console.print("  [cyan]Rebuilding mkinitcpio image... (This may take a minute)[/cyan]")
            subprocess.run(
                ["mkinitcpio", "-P"],
                check=True
            )
            console.print("  [bold green]Kernel RAM Disk rebuilt successfully![/bold green]")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to rebuild RAM disk: {e}")
        console.print(f"  [bold red]!!Failed to rebuild RAM disk. Rescue hook may not be active!![/bold red]")
    except Exception as e:
        logger.error(f"Failed to install RAM disk hook: {e}")
        console.print(f"  [red]!!Failed to install RAM disk hook: {e}!![/red]")
