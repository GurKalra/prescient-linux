import pytest
import time
from unittest.mock import MagicMock
from prescient.core.update_checker import get_local_version, check_for_updates

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """
    Mocks logger for every test in this file.
    """
    mocker.patch("prescient.core.update_checker.logger")

# Helpers
PYPROJECT_WITH_VERSION = '[project]\nname = "prescient-linux"\nversion = "0.12.0"\n'
PYPROJECT_NO_VERSION = '[project]\nname = "prescient-linux"\n'
FROZEN_NOW = 1_000_000_000.0

def make_url_response(content: str) -> MagicMock:
    """
    Builds a MagicMock that correctly simulates urllib's context manager:
        with urllib.request.urlopen(req, timeout=...) as response:
            content = response.read().decode("utf-8")
    """
    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read.return_value = content.encode("utf-8")
    return mock_response

def patch_pyproject(mocker, content: str):
    """
    Correctly patches the full Path chaining sequence used in get_local_version:
        Path(__file__).resolve().parent.parent.parent.parent / "pyproject.toml"
    """
    mock_pyproject = MagicMock()
    mock_pyproject.exists.return_value = True
    mock_pyproject.read_text.return_value = content

    mock_path_cls = mocker.patch("prescient.core.update_checker.Path")
    (
        mock_path_cls.return_value
        .resolve.return_value
        .parent.parent.parent.parent
        .__truediv__.return_value
    ) = mock_pyproject

    return mock_pyproject

def patch_pyproject_missing(mocker):
    """
    Patches Path chain so the pyproject.toml is reported as not existing.
    """
    mock_pyproject = MagicMock()
    mock_pyproject.exists.return_value = False

    mock_path_cls = mocker.patch("prescient.core.update_checker.Path")
    (
        mock_path_cls.return_value
        .resolve.return_value
        .parent.parent.parent.parent
        .__truediv__.return_value
    ) = mock_pyproject

    return mock_pyproject

# Getting local version
def test_get_local_version_reads_from_pyproject_toml(mocker):
    """
    Returns version string parsed directly from pyproject.toml.
    """
    patch_pyproject(mocker, PYPROJECT_WITH_VERSION)

    result = get_local_version()
    assert result == "0.12.0"

def test_get_local_version_strips_whitespace(mocker):
    """
    Strips leading/trailing whitespace from the parsed version string.
    """
    patch_pyproject(mocker, '[project]\nversion = "  0.12.0  "\n')

    result = get_local_version()
    assert result == "0.12.0"

def test_get_local_version_falls_back_to_importlib_when_pyproject_missing(mocker):
    """
    Falls back to importlib.metadata when pyproject.toml does not exist.
    """
    patch_pyproject_missing(mocker)
    mocker.patch("prescient.core.update_checker.version", return_value="0.11.0")

    result = get_local_version()
    assert result == "0.11.0"

def test_get_local_version_falls_back_to_importlib_when_no_version_in_pyproject(mocker):
    """
    Falls back to importlib.metadata when pyproject.toml exists but has no version field.
    """
    patch_pyproject(mocker, PYPROJECT_NO_VERSION)
    mocker.patch("prescient.core.update_checker.version", return_value="0.11.0")

    result = get_local_version()
    assert result == "0.11.0"

def test_get_local_version_returns_unknown_when_both_sources_fail(mocker):
    """
    Returns 'unknown' when pyproject.toml is missing and the package
    is not installed (PackageNotFoundError from importlib).
    """
    from importlib.metadata import PackageNotFoundError

    patch_pyproject_missing(mocker)
    mocker.patch(
        "prescient.core.update_checker.version",
        side_effect=PackageNotFoundError("prescient-linux")
    )

    result = get_local_version()
    assert result == "unknown"

def test_get_local_version_falls_back_gracefully_on_read_exception(mocker):
    """
    Falls back to importlib when pyproject.toml read raises an unexpected exception.
    """
    mock_pyproject = MagicMock()
    mock_pyproject.exists.return_value = True
    mock_pyproject.read_text.side_effect = OSError("permission denied")

    mock_path_cls = mocker.patch("prescient.core.update_checker.Path")
    (
        mock_path_cls.return_value
        .resolve.return_value
        .parent.parent.parent.parent
        .__truediv__.return_value
    ) = mock_pyproject

    mocker.patch("prescient.core.update_checker.version", return_value="0.11.0")

    result = get_local_version()
    assert result == "0.11.0"

# Checking for updates
def test_check_for_updates_returns_cached_result_within_24h(mocker):
    """
    Returns cached is_available without making a network request
    when last_checked is within the 24-hour TTL.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {
        "update": {
            "last_checked": FROZEN_NOW - 3600,  # 1 hour ago — within TTL
            "is_available": True
        }
    })
    mock_urlopen = mocker.patch("prescient.core.update_checker.urllib.request.urlopen")

    result = check_for_updates(force_network=False)
    assert result is True
    mock_urlopen.assert_not_called()

def test_check_for_updates_skips_cache_when_force_network(mocker):
    """
    Bypasses the 24-hour cache and makes a network request
    when force_network=True, even if cache is fresh.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {
        "update": {
            "last_checked": FROZEN_NOW - 60,
            "is_available": False
        }
    })
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.11.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    result = check_for_updates(force_network=True)
    assert result is True

def test_check_for_updates_returns_true_when_remote_is_newer(mocker):
    """
    Returns True when remote version differs from local version.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.11.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    result = check_for_updates(force_network=True)
    assert result is True

def test_check_for_updates_returns_false_when_already_up_to_date(mocker):
    """
    Returns False when local and remote versions match.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.12.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    result = check_for_updates(force_network=True)
    assert result is False

def test_check_for_updates_normalises_v_prefix(mocker):
    """
    Strips leading 'v' from both local and remote versions before comparing.
    v0.12.0 and 0.12.0 must be treated as equal.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="v0.12.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    result = check_for_updates(force_network=True)
    assert result is False

def test_check_for_updates_returns_false_when_local_version_unknown(mocker):
    """
    Returns False immediately without a network request when
    local version cannot be determined.
    """
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="unknown")
    mock_urlopen = mocker.patch("prescient.core.update_checker.urllib.request.urlopen")

    result = check_for_updates(force_network=True)
    assert result is False
    mock_urlopen.assert_not_called()

def test_check_for_updates_returns_false_on_network_failure(mocker):
    """
    Returns False silently when the network request fails (offline, timeout).
    Must not raise an exception.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.11.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        side_effect=Exception("connection timed out")
    )

    result = check_for_updates(force_network=True)
    assert result is False

def test_check_for_updates_returns_false_when_remote_has_no_version(mocker):
    """
    Returns False when remote pyproject.toml exists but has no version field.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.11.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('[project]\nname = "prescient-linux"\n')
    )

    result = check_for_updates(force_network=True)
    assert result is False

def test_check_for_updates_saves_result_to_cache_after_network_check(mocker):
    """
    Calls save_update_cache with a float timestamp and a boolean result
    after every network check, regardless of whether an update was found.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {})
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.12.0")
    mock_save = mocker.patch("prescient.core.update_checker.save_update_cache")
    mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    check_for_updates(force_network=True)

    mock_save.assert_called_once()
    args = mock_save.call_args[0]
    assert args[0] == FROZEN_NOW
    assert args[1] is False

def test_check_for_updates_cache_boundary_exactly_24h(mocker):
    """
    Boundary condition: a cache that is exactly 86400 seconds old must be
    treated as expired and trigger a network check.
    The TTL condition is strict less-than so exactly 86400s is expired.
    Clock is frozen to eliminate any time drift between test setup and execution.
    """
    mocker.patch("prescient.core.update_checker.time.time", return_value=FROZEN_NOW)
    mocker.patch("prescient.core.update_checker.CONFIG", {
        "update": {
            "last_checked": FROZEN_NOW - 86400,  # exactly at boundary
            "is_available": True
        }
    })
    mocker.patch("prescient.core.update_checker.get_local_version", return_value="0.12.0")
    mocker.patch("prescient.core.update_checker.save_update_cache")

    mock_urlopen = mocker.patch(
        "prescient.core.update_checker.urllib.request.urlopen",
        return_value=make_url_response('version = "0.12.0"')
    )

    check_for_updates(force_network=False)
    mock_urlopen.assert_called_once()
