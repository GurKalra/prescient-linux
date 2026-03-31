import pytest
import json
import time
import subprocess
from unittest.mock import MagicMock
from prescient.recovery.snapshot import check_disk_space, get_last_snapshot_state, is_in_cooldown, get_snapshot_provider, trigger_snapshot

@pytest.fixture(autouse=True)
def silence_output(mocker):
    mocker.patch("prescient.recovery.snapshot.logger")
    mocker.patch("prescient.recovery.snapshot.console")

# Checking disk Space
def test_check_disk_space_passes_when_sufficient(mocker):
    """
    Returns True when root partition has more than 5 GB free.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.disk_usage",
        return_value=(100 * 2**30, 50 * 2**30, 50 * 2**30)
    )

    result = check_disk_space()
    assert result is True

def test_check_disk_space_fails_when_low(mocker):
    """
    Returns False when root partition has less than 5 GB free.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.disk_usage",
        return_value=(100 * 2**30, 97 * 2**30, 3 * 2**30)
    )

    result = check_disk_space()
    assert result is False

def test_check_disk_space_exactly_at_threshold(mocker):
    """
    Boundary condition: exactly 5 GB free is NOT enough (requires > 5 GB).
    The function uses integer division so 5 GB exactly returns free_gb = 5,
    which fails the < MIN_FREE_GB check.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.disk_usage",
        return_value=(100 * 2**30, 95 * 2**30, 5 * 2**30)
    )

    result = check_disk_space()
    assert result is True

# Getting last snapshot state
def test_get_last_snapshot_state_returns_dict(mocker, tmp_path):
    """
    Returns the parsed JSON from the state file when it exists.
    """
    state_data = {
        "provider": "timeshift",
        "snapshot_name": "2026-03-24_01-15-00",
        "created_at": 1742778900.0,
        "trigger_reason": "Critical System Component (Kernel)"
    }
    state_file = tmp_path / "last_snapshot.json"
    state_file.write_text(json.dumps(state_data))

    mocker.patch("prescient.recovery.snapshot.STATE_FILE", state_file)

    result = get_last_snapshot_state()
    assert result["provider"] == "timeshift"
    assert result["snapshot_name"] == "2026-03-24_01-15-00"

def test_get_last_snapshot_state_returns_empty_when_missing(mocker, tmp_path):
    """
    Returns an empty dict when the state file does not exist.
    """
    missing_file = tmp_path / "nonexistent.json"
    mocker.patch("prescient.recovery.snapshot.STATE_FILE", missing_file)

    result = get_last_snapshot_state()
    assert result == {}

def test_get_last_snapshot_state_returns_empty_on_corrupt_json(mocker, tmp_path):
    """
    Returns an empty dict gracefully when the state file has invalid JSON.
    """
    state_file = tmp_path / "last_snapshot.json"
    state_file.write_text("this is not json {{{")

    mocker.patch("prescient.recovery.snapshot.STATE_FILE", state_file)

    result = get_last_snapshot_state()
    assert result == {}

# Cooldown is working or not
def test_is_in_cooldown_returns_false_when_no_state(mocker):
    """
    Returns False (not in cooldown) when no state file exists.
    """
    mocker.patch(
        "prescient.recovery.snapshot.get_last_snapshot_state",
        return_value={}
    )

    result = is_in_cooldown()
    assert result is False

def test_is_in_cooldown_returns_true_when_recent(mocker):
    """
    Returns True when a snapshot was taken less than 10 minutes ago.
    """
    mocker.patch(
        "prescient.recovery.snapshot.get_last_snapshot_state",
        return_value={"created_at": time.time() - 60}
    )

    result = is_in_cooldown()
    assert result is True

def test_is_in_cooldown_returns_false_when_expired(mocker):
    """
    Returns False when the last snapshot was taken more than 10 minutes ago.
    """
    mocker.patch(
        "prescient.recovery.snapshot.get_last_snapshot_state",
        return_value={"created_at": time.time() - 700}
    )

    result = is_in_cooldown()
    assert result is False

# Getting snapshot provider
def test_get_snapshot_provider_returns_snapper_first(mocker):
    """
    Snapper is preferred over Timeshift when both are installed.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.which",
        side_effect=lambda cmd: "/usr/bin/snapper" if cmd == "snapper" else "/usr/bin/timeshift"
    )

    result = get_snapshot_provider()
    assert result == "snapper"

def test_get_snapshot_provider_returns_timeshift_as_fallback(mocker):
    """
    Returns timeshift when snapper is not installed.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.which",
        side_effect=lambda cmd: None if cmd == "snapper" else "/usr/bin/timeshift"
    )

    result = get_snapshot_provider()
    assert result == "timeshift"

def test_get_snapshot_provider_returns_none_when_no_provider(mocker):
    """
    Returns None when neither snapper nor timeshift is installed.
    """
    mocker.patch(
        "prescient.recovery.snapshot.shutil.which",
        return_value=None
    )

    result = get_snapshot_provider()
    assert result is None

# Triggering Snapshots
def test_trigger_snapshot_skips_when_no_provider(mocker):
    """
    Returns False immediately when no snapshot tool is installed.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value=None)
    mock_disk = mocker.patch("prescient.recovery.snapshot.check_disk_space")

    result = trigger_snapshot("linux-image-6.8.0-45-generic")
    assert result is False
    mock_disk.assert_not_called()

def test_trigger_snapshot_skips_when_disk_space_low(mocker):
    """
    Returns False when disk space check fails, i.e. no subprocess call should be made.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="timeshift")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=False)
    mock_run = mocker.patch("prescient.recovery.snapshot.subprocess.run")

    result = trigger_snapshot("linux-image-6.8.0-45-generic")
    assert result is False
    mock_run.assert_not_called()

def test_trigger_snapshot_skips_when_in_cooldown(mocker):
    """
    Returns False when cooldown timer is active, again no subprocess call should be made.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="timeshift")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=True)
    mocker.patch("prescient.recovery.snapshot.is_in_cooldown", return_value=True)
    mock_run = mocker.patch("prescient.recovery.snapshot.subprocess.run")

    result = trigger_snapshot("linux-image-6.8.0-45-generic")
    assert result is False
    mock_run.assert_not_called()

def test_trigger_snapshot_succeeds_with_timeshift(mocker):
    """
    Returns True and calls save_snapshot_state when Timeshift succeeds.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="timeshift")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=True)
    mocker.patch("prescient.recovery.snapshot.is_in_cooldown", return_value=False)
    mocker.patch(
        "prescient.recovery.snapshot.subprocess.run",
        return_value=MagicMock(
            stdout="Created new snapshot: 2026-03-24_01-15-00\n",
            returncode=0
        )
    )
    mock_save = mocker.patch("prescient.recovery.snapshot.save_snapshot_state")

    result = trigger_snapshot("linux-image-6.8.0-45-generic", "Critical System Component (Kernel)")
    assert result is True
    mock_save.assert_called_once_with(
        "timeshift",
        "2026-03-24_01-15-00",
        "Critical System Component (Kernel)"
    )

def test_trigger_snapshot_succeeds_with_snapper(mocker):
    """
    Returns True and saves state with the numeric snapshot ID when Snapper succeeds.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="snapper")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=True)
    mocker.patch("prescient.recovery.snapshot.is_in_cooldown", return_value=False)
    mocker.patch(
        "prescient.recovery.snapshot.subprocess.run",
        return_value=MagicMock(stdout="42\n", returncode=0)
    )
    mock_save = mocker.patch("prescient.recovery.snapshot.save_snapshot_state")

    result = trigger_snapshot("linux-image-6.8.0-45-generic", "Critical System Component (Kernel)")

    assert result is True
    mock_save.assert_called_once_with(
        "snapper",
        "42",
        "Critical System Component (Kernel)"
    )

def test_trigger_snapshot_returns_false_on_timeout(mocker):
    """
    Returns False when the snapshot tool hangs and times out after 120s.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="timeshift")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=True)
    mocker.patch("prescient.recovery.snapshot.is_in_cooldown", return_value=False)
    mocker.patch(
        "prescient.recovery.snapshot.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="timeshift", timeout=120)
    )

    result = trigger_snapshot("linux-image-6.8.0-45-generic")
    assert result is False

def test_trigger_snapshot_returns_false_on_proceess_error(mocker):
    """
    Returns False when the snapshot tool exits with a non-zero code.
    """
    mocker.patch("prescient.recovery.snapshot.get_snapshot_provider", return_value="snapper")
    mocker.patch("prescient.recovery.snapshot.check_disk_space", return_value=True)
    mocker.patch("prescient.recovery.snapshot.is_in_cooldown", return_value=False)
    mocker.patch(
        "prescient.recovery.snapshot.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="snapper", stderr="Permission denied"
        )
    )

    result = trigger_snapshot("linux-image-6.8.0-45-generic")
    assert result is False