import time
import urllib.request
import re
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from prescient.core.logger import logger
from prescient.config import CONFIG, save_update_cache

def get_local_version() -> str:
    """
    Fetches the currently installed version from package metadata.
    """
    try:
        # Looking in pyproject.toml
        pyproject_path = Path(__file__).resolve().parent.parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            
            match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                local_ver = match.group(1).strip()
                logger.debug(f"Local version '{local_ver}' loaded from pyproject.toml")
                return local_ver
    except Exception as e:
        logger.debug(f"Failed to read local pyproject.toml: {e}")
        
    try:
        # Fallbacking to standard package metadata
        fallback_ver = version("prescient-linux")
        logger.debug(f"Local version '{fallback_ver}' loaded from package metadata fallback")
        return fallback_ver
    except PackageNotFoundError:
        logger.warning("Local version could not be determined (Package not found).")
        return "unknown"

def check_for_updates(force_network: bool = False) -> bool:
    """
    Pings the main GitHub repo's pyproject.toml to see if the remote version is newer.
    Uses a 24-hour cache to prevent network spam during routine package installations.
    """
    # Cache check
    if not force_network:
        update_data = CONFIG.get("update", {})
        last_checked = update_data.get("last_checked", 0.0)
        is_available = update_data.get("is_available", False)

        if (time.time() - last_checked) < 86400:
            logger.debug("OTA check: Using cached result (checked < 24h ago).")
            return is_available
    
    # Network Update check
    local_version_raw = get_local_version()
    if local_version_raw == "unknown":
        logger.debug("OTA update check aborted: Local version is unknown.")
        return False
    
    local_version = local_version_raw.lstrip("v").strip()
    update_found = False

    try:
        url = "https://raw.githubusercontent.com/GurKalra/prescient-linux/main/pyproject.toml"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=15.0) as response:
            content = response.read().decode("utf-8")

            match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                remote_version = match.group(1).lstrip("v").strip()
                if remote_version != local_version:
                    update_found = True
            else:
                logger.warning("OTA Check failed: Could not parse version from remote pyproject.toml")

    except Exception as e:
        logger.warning(f"OTA update check skipped or failed (offline/timeout): {e}")
    
    # Saving to cache
    logger.debug(f"OTA network check complete. Update found: {update_found}. Saving cache.")
    save_update_cache(time.time(), update_found)

    return update_found