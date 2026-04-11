import pytest
import json
import subprocess
from pathlib import Path
from prescient.recovery.undo import get_last_snapshot, get_latest_system_snapshot, verify_snapshot, execute_rollback

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """
    Mocks logger and console for every test in this file.
    """
    mocker.patch("prescient.recovery.undo.logger")
    mocker.patch("prescient.recovery.undo.console")

# Helpers
TIMESHIFT_STATE = {
    "provider": "timeshift",
    "snapshot_name": "2026-03-24_01-15-00",
    "created_at": 1742778900.0,
    "trigger_reason": "Critical System Component (Kernel)"
}

SNAPPER_STATE = {
    "provider": "snapper",
    "snapshot_name": "42",
    "created_at": 1742778900.0,
    "trigger_reason": "Core Subsystem (Core Daemons)"
}

# Getting last snapshot
def test_get_last_snapshot_returns_state(mocker, tmp_path):
    """
    Returns parsed JSON dict when state file exists and is valid.
    """
    state_file = tmp_path / "last_snapshot.json"
    state_file.write_text(json.dumps(TIMESHIFT_STATE))
    mocker.patch("prescient.recovery.undo.STATE_FILE", state_file)

    result = get_last_snapshot()
    assert result["provider"] == "timeshift"
    assert result["snapshot_name"] == "2026-03-24_01-15-00"
    assert result["created_at"] == 1742778900.0

def test_get_last_snapshot_returns_none_when_missing(mocker, tmp_path):
    """
    Returns None when the state file does not exist.
    """
    mocker.patch("prescient.recovery.undo.STATE_FILE", tmp_path / "nonexistent.json")

    result = get_last_snapshot()
    assert result is None

def test_get_last_snapshot_returns_none_on_corrupt_json(mocker, tmp_path):
    """
    Returns None gracefully when state file contains invalid JSON.
    """
    state_file = tmp_path / "last_snapshot.json"
    state_file.write_text("not valid json {{{")
    mocker.patch("prescient.recovery.undo.STATE_FILE", state_file)

    result = get_last_snapshot()
    assert result is None

# Getting latest system snapshots
def test_get_latest_system_snapshot_returns_latest_timeshift(mocker, tmp_path):
    """
    Finds and returns the most recent Timeshift snapshot via filesystem scan.
    Sorted alphabetically so 2026-03-24 wins over 2026-03-22.
    """
    # Fake timeshift config
    config_dir = tmp_path / "etc" / "timeshift"
    config_dir.mkdir(parents=True)
    (config_dir / "timeshift.json").write_text("{}")

    # Fake snapshot directory with three snapshots
    snap_dir = tmp_path / "timeshift" / "snapshots"
    snap_dir.mkdir(parents=True)
    (snap_dir / "2026-03-22_10-00-00").mkdir()
    (snap_dir / "2026-03-23_12-00-00").mkdir()
    (snap_dir / "2026-03-24_01-15-00").mkdir()

    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = get_latest_system_snapshot()
    assert result is not None
    assert result["provider"] == "timeshift"
    assert result["snapshot_name"] == "2026-03-24_01-15-00"
    assert result["trigger_reason"] == "Rescue Scan (Filesystem Direct)"

def test_get_latest_system_snapshot_parses_timestamp(mocker, tmp_path):
    """
    Correctly parses the snapshot directory name as a UNIX timestamp.
    """
    config_dir = tmp_path / "etc" / "timeshift"
    config_dir.mkdir(parents=True)
    (config_dir / "timeshift.json").write_text("{}")

    snap_dir = tmp_path / "timeshift" / "snapshots"
    snap_dir.mkdir(parents=True)
    (snap_dir / "2026-03-24_01-15-00").mkdir()

    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = get_latest_system_snapshot()
    assert result is not None
    assert result["created_at"] > 0.0

def test_get_latest_system_snapshot_falls_back_to_snapper(mocker, tmp_path):
    """
    When no Timeshift config exists, falls back to Snapper directory scan.
    Returns the highest numeric snapshot ID.
    """
    # No timeshift config i.e snapper directory exists
    snapper_dir = tmp_path / ".snapshots"
    snapper_dir.mkdir()
    (snapper_dir / "40").mkdir()
    (snapper_dir / "41").mkdir()
    (snapper_dir / "42").mkdir()

    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = get_latest_system_snapshot()
    assert result is not None
    assert result["provider"] == "snapper"
    assert result["snapshot_name"] == "42"

def test_get_latest_system_snapshot_returns_none_when_nothing_found(mocker, tmp_path):
    """
    Returns None when neither Timeshift config nor Snapper directory exists.
    """
    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = get_latest_system_snapshot()
    assert result is None

# Verification of snapshot
def test_verify_snapshot_returns_false_for_empty_state():
    """
    Returns False immediately when provider or snapshot_name is missing.
    """
    assert verify_snapshot({}) is False
    assert verify_snapshot({"provider": "timeshift"}) is False
    assert verify_snapshot({"snapshot_name": "42"}) is False

def test_verify_snapshot_timeshift_cli_success(mocker):
    """
    Returns True when timeshift --list output contains the snapshot name.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="  1  2026-03-24_01-15-00  O  Mon 24 Mar 2026\n"
        )
    )

    result = verify_snapshot(TIMESHIFT_STATE)
    assert result is True

def test_verify_snapshot_snapper_cli_success(mocker):
    """
    Returns True when snapper list output contains the snapshot ID.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="  42  | single | pre-update snapshot\n"
        )
    )

    result = verify_snapshot(SNAPPER_STATE)
    assert result is True

def test_verify_snapshot_cli_fails_falls_back_to_filesystem(mocker, tmp_path):
    """
    When CLI verification fails, falls back to checking filesystem paths.
    Returns True when the snapshot directory exists on disk.
    """
    # CLI raises an exception (e.g. D-Bus unavailable in chroot)
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        side_effect=Exception("D-Bus not available")
    )

    # Fake the filesystem path for timeshift snapshot
    snap_path = tmp_path / "timeshift" / "snapshots" / "2026-03-24_01-15-00"
    snap_path.mkdir(parents=True)

    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = verify_snapshot(TIMESHIFT_STATE)
    assert result is True

def test_verify_snapshot_snapper_filesystem_fallback(mocker, tmp_path):
    """
    Falls back to /.snapshots/<id>/snapshot path check for Snapper.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        side_effect=Exception("D-Bus not available")
    )

    snap_path = tmp_path / ".snapshots" / "42" / "snapshot"
    snap_path.mkdir(parents=True)

    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = verify_snapshot(SNAPPER_STATE)
    assert result is True

def test_verify_snapshot_returns_false_when_both_checks_fail(mocker, tmp_path):
    """
    Returns False when both CLI and filesystem verification fail.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        side_effect=Exception("unavailable")
    )
    mocker.patch(
        "prescient.recovery.undo.Path",
        side_effect=lambda p: _fake_path(str(p), tmp_path)
    )

    result = verify_snapshot(TIMESHIFT_STATE)
    assert result is False

def test_execute_rollback_snapper_success(mocker):
    """
    Returns True when snapper rollback exits with code 0.
    """
    mock_run = mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    result = execute_rollback(SNAPPER_STATE)
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert "snapper" in cmd
    assert "rollback" in cmd
    assert "42" in cmd

def test_execute_rollback_timeshift_success(mocker):
    """
    Returns True when timeshift --restore exits with code 0.
    """
    mock_run = mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    result = execute_rollback(TIMESHIFT_STATE)
    assert result is True
    cmd = mock_run.call_args[0][0]
    assert "timeshift" in cmd
    assert "--restore" in cmd
    assert "2026-03-24_01-15-00" in cmd

def test_execute_rollback_returns_false_on_timeout(mocker):
    """
    Returns False when the rollback tool hangs and times out after 300s.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="snapper", timeout=300)
    )

    result = execute_rollback(SNAPPER_STATE)
    assert result is False

def test_execute_rollback_returns_false_on_process_error(mocker):
    """
    Returns False when the rollback command exits with a non-zero code.
    """
    mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "timeshift", stderr="restore failed")
    )

    result = execute_rollback(TIMESHIFT_STATE)
    assert result is False

def test_execute_rollback_uses_300s_timeout(mocker):
    """
    Confirms the 300-second timeout is passed to subprocess.run.
    """
    mock_run = mocker.patch(
        "prescient.recovery.undo.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    execute_rollback(SNAPPER_STATE)
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs.get("timeout") == 300

def test_execute_rollback_returns_false_for_unknown_provider(mocker):
    """
    Returns False cleanly when provider is not snapper or timeshift.
    """
    mocker.patch("prescient.recovery.undo.subprocess.run")

    result = execute_rollback({"provider": "unknown", "snapshot_name": "1"})
    assert result is False

# Function for path remapping for filessytem tests
def _fake_path(p: str, tmp_path: Path) -> Path:
    remaps = {
        "/etc/timeshift/timeshift.json": str(tmp_path / "etc/timeshift/timeshift.json"),
        "/run/timeshift/backup/timeshift/snapshots": str(tmp_path / "run/timeshift/backup/timeshift/snapshots"),
        "/timeshift/snapshots": str(tmp_path / "timeshift/snapshots"),
        "/.snapshots": str(tmp_path / ".snapshots"),
    }
    for original, replacement in remaps.items():
        if p == original or p.startswith(original + "/"):
            suffix = p[len(original):]
            return Path(replacement + suffix)
    return Path(p)