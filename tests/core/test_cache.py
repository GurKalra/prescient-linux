import pytest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock
from prescient.core.cache import get_cached_state, set_cached_state

# Getting cached state
def test_get_cached_state_returns_empty_when_file_missing(mocker, tmp_path):
    """
    Returns empty dict when the cache file does not exist.
    """
    mocker.patch("prescient.core.cache.CACHE_FILE", tmp_path / "nonexistent.json")

    result = get_cached_state()
    assert result == {}

def test_get_cached_state_returns_data_when_fresh(mocker, tmp_path):
    """
    Returns parsed cache data when the file exists and is within the TTL window.
    """
    cache_file = tmp_path / "prescient_session.json"
    cache_data = {"sb_enabled": True}
    cache_file.write_text(json.dumps(cache_data))

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    # Fake current time to be 60 seconds after file was written (well within 1800s TTL)
    mocker.patch("prescient.core.cache.time.time", return_value=cache_file.stat().st_mtime + 60)

    result = get_cached_state()
    assert result == {"sb_enabled": True}

def test_get_cached_state_returns_empty_when_expired(mocker, tmp_path):
    """
    Returns empty dict when the cache file exists but is older than the TTL (1800s).
    """
    cache_file = tmp_path / "prescient_session.json"
    cache_file.write_text(json.dumps({"sb_enabled": True}))

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    # Fake current time to be 2000 seconds after the file was written (past TTL)
    mocker.patch(
        "prescient.core.cache.time.time",
        return_value=cache_file.stat().st_mtime + 2000
    )

    result = get_cached_state()
    assert result == {}

def test_get_cached_state_returns_empty_on_corrupt_json(mocker, tmp_path):
    """
    Returns empty dict gracefully when the cache file contains invalid JSON.
    """
    cache_file = tmp_path / "prescient_session.json"
    cache_file.write_text("this is not valid json {{{")

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    mocker.patch("prescient.core.cache.time.time", return_value=cache_file.stat().st_mtime + 60)

    result = get_cached_state()
    assert result == {}

def test_get_cached_state_returns_empty_at_exact_ttl_boundary(mocker, tmp_path):
    """
    Boundary condition: cache at exactly TTL seconds old should be expired.
    The check is strict less-than so exactly 1800s is expired.
    """
    cache_file = tmp_path / "prescient_session.json"
    cache_file.write_text(json.dumps({"sb_enabled": False}))

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    # Exactly at TTL boundary (1800 seconds)
    mocker.patch(
        "prescient.core.cache.time.time",
        return_value=cache_file.stat().st_mtime + 1800
    )

    result = get_cached_state()
    assert result == {}

# Setting cached state
def test_set_cached_state_writes_data_to_file(mocker, tmp_path):
    """
    Writes the new state to the cache file as valid JSON.
    """
    cache_file = tmp_path / "prescient_session.json"
    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    mocker.patch("prescient.core.cache.time.time", return_value=0)

    set_cached_state({"sb_enabled": True})

    written = json.loads(cache_file.read_text())
    assert written["sb_enabled"] is True

def test_set_cached_state_merges_with_existing_cache(mocker, tmp_path):
    """
    Merges new data with existing cache rather than overwriting it entirely.
    """
    cache_file = tmp_path / "prescient_session.json"
    existing = {"sb_enabled": True}
    cache_file.write_text(json.dumps(existing))

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    # Cache is fresh so get_cached_state returns existing data
    mocker.patch("prescient.core.cache.time.time", return_value=cache_file.stat().st_mtime + 60)

    set_cached_state({"another_key": "hello"})

    written = json.loads(cache_file.read_text())
    assert written["sb_enabled"] is True        # original key preserved
    assert written["another_key"] == "hello"    # new key added

def test_set_cached_state_overwrites_existing_key(mocker, tmp_path):
    """
    When the same key is set twice, the latest value wins.
    """
    cache_file = tmp_path / "prescient_session.json"
    cache_file.write_text(json.dumps({"sb_enabled": False}))

    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    mocker.patch("prescient.core.cache.time.time", return_value=cache_file.stat().st_mtime + 60)

    set_cached_state({"sb_enabled": True})

    written = json.loads(cache_file.read_text())
    assert written["sb_enabled"] is True

def test_set_cached_state_applies_0o600_permissions(mocker, tmp_path):
    """
    Sets 0o600 permissions on the cache file so only root can read/write it.
    """
    cache_file = tmp_path / "prescient_session.json"
    mocker.patch("prescient.core.cache.CACHE_FILE", cache_file)
    mocker.patch("prescient.core.cache.time.time", return_value=0)
    mock_chmod = mocker.patch("prescient.core.cache.os.chmod")

    set_cached_state({"sb_enabled": True})

    mock_chmod.assert_called_once_with(cache_file, 0o600)

def test_set_cached_state_fails_silently_on_write_error(mocker, tmp_path):
    """
    Does not raise an exception when the cache file cannot be written
    (e.g. /dev/shm is not available or permissions are wrong).
    """
    mock_file = MagicMock()
    mock_file.exists.return_value = False
    mock_file.write_text.side_effect = OSError("no space left on device")

    mocker.patch("prescient.core.cache.CACHE_FILE", mock_file)
    mocker.patch("prescient.core.cache.time.time", return_value=0)

    try:
        set_cached_state({"sb_enabled": True})
    except Exception as e:
        pytest.fail(f"set_cached_state raised unexpectedly: {e}")