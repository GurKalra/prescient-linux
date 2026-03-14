import json
import os
import time
from pathlib import Path

CACHE_FILE = Path("/dev/shm/sentinel_session.json")
CACHE_TTL_SECONDS = 1800

def get_cached_state():
    """Retrives the cached state if it's still fresh."""
    if not CACHE_FILE.exists():
        return {}

    if CACHE_FILE.exists():
        try:
            # Only trust if the cache is not expired
            if(time.time() - CACHE_FILE.stat().st_mtime) < CACHE_TTL_SECONDS:
                return json.loads(CACHE_FILE.read_text())
        except Exception:
            #if JSON is unreadable for some reason, fall back 
            pass
        return {}

def set_cached_state(data):
    """Updates the RAM cache with new state data."""
    current_cache = get_cached_state()
    current_cache.update(data)

    try:
        #Write to RAM
        CACHE_FILE.write_text(json.dumps(current_cache))
        # Lock down permissions so only root (who runs apt) can read/write it
        os.chmod(CACHE_FILE, 0o600)
    except Exception:
        # If cache writing fails for any reason, fail silently.
        pass