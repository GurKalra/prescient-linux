import tomlkit
import os
from pathlib import Path
from prescient.core.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

CONFIG_PATHS = [
    PROJECT_ROOT / "prescient.toml", #Local dev folder
    Path("/etc/prescient/prescient.toml")  # System-wide install
]

CONFIG = {}

def get_active_config_path() -> Path | None:
    """Detects which config file prescient is currently using."""
    for path in CONFIG_PATHS:
        if path.exists():
            return path
    return None

def reload_config():
    """Reads the TOML schema and refreshes the in-memory CONFIG."""
    global CONFIG
    path  = get_active_config_path()

    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                CONFIG = tomlkit.parse(f.read())
                logger.debug(f"Config reloaded from {path}")
            return
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
        
    # Fallback Structure if the file is missing or corrupt
    CONFIG = {"triggers": {"high_risk" : {}, "medium_risk": {}}}

def save_learned_package(pkg_name: str, reason: str) -> bool:
    """Surgically injects a dynamically learned package into the TOML file.
    Preserves all user comments and automatically reloads the RAM config."""
    path = get_active_config_path()
    if not path:
        logger.warning("No prescient.toml found. Cannot persist learned package.")
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
        
        if "triggers" not in doc:
            doc.add("triggers", tomlkit.table())
        if "high_risk" not in doc["triggers"]:
            doc["triggers"]["high_risk"] = tomlkit.table()

        high_risk_table = doc["triggers"]["high_risk"]
        if "heuristics" not in high_risk_table:
            heuristics_array = tomlkit.array()
            high_risk_table.add("heuristics", heuristics_array)
            high_risk_table["heuristics"].comment("Packages dynamically flagged by prescient's Intelligence Engine")

        heuristics_list = high_risk_table["heuristics"]

        # Preventing duplicates
        if pkg_name in heuristics_list:
            logger.debug(f"Package '{pkg_name}' is already known to prescient.")
            return True
        
        logger.info(f"prescient learned new threat: '{pkg_name}' ({reason})")
        heuristics_list.append(pkg_name)

        with open(path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

        if os.geteuid() == 0:
            os.chmod(path, 0o644)

        reload_config()
        return True
    except Exception as e:
        logger.error(f"Intelligence persistence failed via tomlkit: {e}")
        return False

def save_auto_snapshot_config(enabled: bool) -> bool:
    """
    Saves the user's automated snapshot preference.
    """
    path = get_active_config_path()

    if not path:
        path = PROJECT_ROOT / "prescient.toml"
        if not path.exists():
            path.touch()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            doc = tomlkit.parse(content) if content else tomlkit.document()
        
        # Adding core table in toml file
        if "core" not in doc:
            doc.add("core", tomlkit.table())
        
        doc["core"]["auto_snapshot"] = enabled

        with open(path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        
        if os.geteuid() == 0:
            os.chmod(path, 0o644)
        
        reload_config()
        return True
    except Exception as e:
        logger.error(f"Failed to save snapshot config: {e}")
        return False

def save_update_cache(last_checked: float, is_available: bool) -> bool:
    """
    Saves the timestamp and result of the last OTA update check.
    """
    path = get_active_config_path()

    if not path:
        path = PROJECT_ROOT / "prescient.toml"
        if not path.exists():
            path.touch()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            doc = tomlkit.parse(content) if content else tomlkit.document()

        # Adding update table in toml file
        if "update" not in doc:
            doc.add("update", tomlkit.table())
        
        doc["update"]["last_checked"] = last_checked
        doc["update"]["is_available"] = is_available

        with open(path, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        
        if os.geteuid() == 0:
            os.chmod(path, 0o644)
        
        reload_config()
        return True
    except Exception as e:
        logger.error(f"Failed to save update cache: {e}")
        return False


reload_config()
