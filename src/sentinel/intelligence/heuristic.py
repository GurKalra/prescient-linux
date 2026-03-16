import subprocess
import os
from rich.console import Console
from sentinel.core.logger import logger
from sentinel.core.utils import detect_package_manager
from sentinel.config import save_learned_package

console = Console()

# Current Tripwires
CRITICAL_PATHS = [
    "/boot/",    
    "/etc/grub.d/",    
    "/lib/modules/",    
    "/usr/lib/modules/",    
    "/usr/lib/shim/",   
    "/usr/lib/grub/",    
    "/etc/sudoers.d/",    
    "/etc/pam.d/", 
    "/etc/security/", 
    "/etc/polkit-1/", 
    "/etc/systemd/",         
    "/etc/init.d/", 
    "/usr/lib/systemd/", 
    "/etc/modprobe.d/",  
    "/etc/modules-load.d/", 
    "/etc/NetworkManager/",    
    "/etc/netplan/",    
    "/etc/network/",    
    "/lib/x86_64-linux-gnu/",    
    "/usr/lib/x86_64-linux-gnu/"
]

def get_package_files(pkg_name: str) -> list[str]:
    """
    Queries the host package manager for the full list of files a package contains.
    """
    pm = detect_package_manager()
    if not pm:
        logger.warning(f"Heuristics bypassed: Could not detect package manager for '{pkg_name}'")
        return []
    
    try:
        if pm == "apt":
            res = subprocess.run(
                ["dpkg", "-L", pkg_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                files = [os.path.normpath(line.strip()) for line in res.stdout.strip().splitlines() if line.strip()]
                logger.debug(f"Extracted {len(files)} paths from dpkg for '{pkg_name}'")
                return files
            
        elif pm == "pacman":
            res = subprocess.run(
                ["pacman", "-Ql", pkg_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                files = [os.path.normpath(line.split(" ", 1)[1]) for line in lines if " " in line]
                logger.debug(f"Extracted and normalized {len(files)} paths from pacman for '{pkg_name}'")
                return files
    except subprocess.TimeoutExpired:
        logger.warning(f"Heuristics timeout: Package manager hung while querying '{pkg_name}'")
    except Exception as e:
        logger.error(f"Heuristic query failed for '{pkg_name}': {e}")

    return []

def analyze_package_heuristics(pkg_name: str) -> tuple[bool, str]:
    """
    Scans a single package's normalized file list against the tripwires.
    """
    file_paths = get_package_files(pkg_name)

    if not file_paths:
        return False, ""
    
    # Pre-normalizing tripwires so we don't do it repeatedly inside the loop
    normalized_tripwires = [os.path.normpath(p) for p in CRITICAL_PATHS]

    for file_path in file_paths:
        for norm_crit in normalized_tripwires:
            if file_path == norm_crit or file_path.startswith(norm_crit + os.sep):
                reason = f"Modifies protected path ({norm_crit})"
                logger.warning(f"TRIPWIRE TRIGGERED: '{pkg_name}' -> {reason}")
                return True, reason
    
    return False, ""

def scan_transaction_heuristics(safe_package_list: list[str]) -> tuple[bool, str]:
    """
    The entry point for the Heuristic Engine.
    Scans the transaction, learns new threats, and returns the result.
    """
    if not safe_package_list:
        return False, "Standard Package Update"
    
    logger.info(f"Initiating deep heuristic scan on {len(safe_package_list)} packages...")

    pm = detect_package_manager()
    if pm:
        batch_cmd = ["dpkg", "-L"] + safe_package_list if pm == "apt" else ["pacman", "-Ql"] + safe_package_list
        try:
            logger.debug("Running batched heuristic pre-scan...")
            res = subprocess.run(
                batch_cmd, 
                capture_output=True,
                text=True,
                timeout=10
            )

            threat_detected = False
            for tripwire in CRITICAL_PATHS:
                norm_tripwire = os.path.normpath(tripwire)
                if norm_tripwire in res.stdout:
                    threat_detected = True
                    break
            
            # If the batched output is clean, we exit
            if not threat_detected:
                logger.info("Batched heuristic pre-scan clean. 0 threats found.")
                return False, "Standard Package Update"
                
            logger.info("Threat detected in batched scan. Falling back to isolation loop...")
        except subprocess.TimeoutExpired:
            logger.warning("Batched scan timed out. Falling back to isolation loop...")
        except Exception as e:
            logger.warning(f"Batched scan failed ({e}). Falling back to isolation loop...")

    findings = []

    for pkg in safe_package_list:
        is_dangerous, reason = analyze_package_heuristics(pkg)
        
        if is_dangerous:
            saved = save_learned_package(pkg, reason)

            if saved:
                console.print(f"  [bold magenta]Sentinel Intelligence learned a new threat:[/bold magenta] [white]{pkg}[/white]")
                console.print(f"    [dim white]↳ Reason: {reason}[/dim white]")
            findings.append((pkg,reason))

    if findings:
        # Report the highest-risk finding (first one) but all have been learned
        top_pkg, top_reason = findings[0]
        logger.info(f"Heuristic scan complete. {len(findings)} threat(s) found.")
        return True, f"Dynamic Heuristic Flag ({top_pkg})"
            
    logger.info("Heuristic scan complete. No critical paths modified by unknown packages.")
    return False, "Standard Package Update"