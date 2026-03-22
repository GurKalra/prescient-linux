import urllib.request
import re
from importlib.metadata import version, PackageNotFoundError
from prescient.core.logger import logger

def get_local_version() -> str:
    """
    Fetches the currently installed version from package metadata.
    """
    try:
        return version("prescient-linux")
    except PackageNotFoundError:
        return "unknown"

def check_for_updates() -> bool:
    """
    Pings the main GitHub repo's pyproject.toml to see if the remote version is newer.
    Fails silently and instantly if offline.
    """
    local_version_raw = get_local_version()
    if local_version_raw == "unknown":
        return False
    
    local_version = local_version_raw.lstrip("v").strip()
    
    try:
        url = "https://raw.githubusercontent.com/GurKalra/prescient-linux/main/pyproject.toml"
        req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=5.0) as response:
            content = response.read().decode("utf-8")
            
            match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                remote_version = match.group(1).lstrip("v").strip()
                if remote_version != local_version:
                    return True
    
    except Exception as e:
        logger.debug(f"Update check skipped or failed: {e}")

    return False