import pytest
import subprocess
from typer.testing import CliRunner
from prescient.cli import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """
    Mocks logger and console for every test in this file.
    """
    mocker.patch("prescient.cli.logger")
    mocker.patch("prescient.cli.console")

@pytest.fixture(autouse=True)
def skip_ota_check(mocker):
    """
    Suppresses the global OTA check in app.callback() for every test.
    """
    mocker.patch("prescient.cli.check_for_updates", return_value=False)

# Checking for root (sudo)
def test_check_sudo_strict_exits_without_root(mocker):
    """
    strict=True exits with code 1 when not running as root.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)
    mocker.patch("prescient.cli.install")

    result = runner.invoke(app, ["install-hooks"])
    assert result.exit_code == 1

def test_check_sudo_non_strict_continues_without_root(mocker):
    """
    strict=False prints a hint but does not exit when not running as root.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=True)
    mocker.patch("prescient.cli.parse_and_sanitize_packages", return_value=[])
    mocker.patch("prescient.cli.CONFIG", {})

    result = runner.invoke(app, ["predict"])
    assert result.exit_code == 0

def test_check_sudo_strict_passes_as_root(mocker):
    """
    strict=True does not exit when running as root.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.install")

    result = runner.invoke(app, ["install-hooks"])
    assert result.exit_code == 0

# Predict
def test_predict_veto_on_failed_preflight(mocker):
    """
    Exits with code 1 when run_preflight_checks returns False (VETO).
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=False)

    result = runner.invoke(app, ["predict"])
    assert result.exit_code == 1

def test_predict_passes_on_healthy_system_no_stdin(mocker):
    """
    Exits with code 0 when preflight passes and no stdin is provided.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=True)
    mocker.patch("prescient.cli.CONFIG", {})

    result = runner.invoke(app, ["predict"])
    assert result.exit_code == 0

def test_predict_triggers_snapshot_on_scary_package(mocker):
    """
    Calls trigger_snapshot when blast radius assessment returns high-risk.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=True)
    mocker.patch(
        "prescient.cli.parse_and_sanitize_packages",
        return_value=["linux-image-6.8.0-45-generic"]
    )
    mocker.patch("prescient.cli.analyze_boot_health", return_value=True)
    mocker.patch("prescient.cli.analyze_security_risk", return_value=True)
    mocker.patch(
        "prescient.cli.assess_blast_radius",
        return_value=(True, "Critical System Component (Kernel)")
    )
    mocker.patch("prescient.cli.CONFIG", {"core": {"auto_snapshot": True}})
    mock_snapshot = mocker.patch("prescient.cli.trigger_snapshot")

    result = runner.invoke(app, ["predict"], input="linux-image-6.8.0-45-generic\n")
    assert result.exit_code == 0
    mock_snapshot.assert_called_once()

def test_predict_skips_snapshot_when_auto_snap_disabled(mocker):
    """
    Does not call trigger_snapshot when auto_snapshot is False in config.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=True)
    mocker.patch(
        "prescient.cli.parse_and_sanitize_packages",
        return_value=["linux-image-6.8.0-45-generic"]
    )
    mocker.patch("prescient.cli.analyze_boot_health", return_value=True)
    mocker.patch("prescient.cli.analyze_security_risk", return_value=True)
    mocker.patch(
        "prescient.cli.assess_blast_radius",
        return_value=(True, "Critical System Component (Kernel)")
    )
    mocker.patch("prescient.cli.CONFIG", {"core": {"auto_snapshot": False}})
    mock_snapshot = mocker.patch("prescient.cli.trigger_snapshot")

    result = runner.invoke(app, ["predict"], input="linux-image-6.8.0-45-generic\n")
    assert result.exit_code == 0
    mock_snapshot.assert_not_called()

def test_predict_skips_probes_when_no_input(mocker):
    """
    Does not call parse_and_sanitize_packages when no stdin is provided.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_preflight_checks", return_value=True)
    mocker.patch("prescient.cli.CONFIG", {})
    mock_parse = mocker.patch("prescient.cli.parse_and_sanitize_packages")

    result = runner.invoke(app, ["predict"])
    assert result.exit_code == 0
    mock_parse.assert_not_called()

# Diagnose
def test_diagnose_runs_without_flags(mocker):
    """
    Basic diagnose invocation exits with code 0.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_diagnostics", return_value=[])

    result = runner.invoke(app, ["diagnose"])
    assert result.exit_code == 0

def test_diagnose_previous_flag_passed_to_engine(mocker):
    """
    --previous flag is forwarded to run_diagnostics.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mock_diag = mocker.patch("prescient.cli.run_diagnostics", return_value=[])

    runner.invoke(app, ["diagnose", "--previous"])
    mock_diag.assert_called_once_with(previous=True)

def test_diagnose_share_calls_termbin(mocker):
    """
    --share flag triggers export_to_termbin with the crash report.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_diagnostics", return_value=[])
    mocker.patch("prescient.cli.get_raw_journalctl_output", return_value="some logs\n")
    mock_termbin = mocker.patch(
        "prescient.cli.export_to_termbin",
        return_value="https://termbin.com/abc123"
    )

    result = runner.invoke(app, ["diagnose", "--share"])
    assert result.exit_code == 0
    mock_termbin.assert_called_once()

def test_diagnose_share_saves_locally_on_termbin_failure(mocker):
    """
    Falls back to local file save when termbin upload returns None.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.run_diagnostics", return_value=[])
    mocker.patch("prescient.cli.get_raw_journalctl_output", return_value="some logs\n")
    mocker.patch("prescient.cli.export_to_termbin", return_value=None)
    mock_open = mocker.patch("builtins.open", mocker.mock_open())

    result = runner.invoke(app, ["diagnose", "--share"])
    assert result.exit_code == 0
    mock_open.assert_called_once()

def test_diagnose_previous_and_share_combined(mocker):
    """
    --previous and --share flags can be combined freely.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mock_diag = mocker.patch("prescient.cli.run_diagnostics", return_value=[])
    mocker.patch("prescient.cli.get_raw_journalctl_output", return_value="logs\n")
    mocker.patch("prescient.cli.export_to_termbin", return_value="https://termbin.com/xyz")

    result = runner.invoke(app, ["diagnose", "--previous", "--share"])
    assert result.exit_code == 0
    mock_diag.assert_called_once_with(previous=True)

# Undo
def test_undo_exits_without_root(mocker):
    """
    Exits with code 1 when not running as root (strict=True).
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)

    result = runner.invoke(app, ["undo"])
    assert result.exit_code == 1

def test_undo_exits_cleanly_when_no_snapshot(mocker):
    """
    Exits with code 0 and prints a message when no snapshot exists.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.get_last_snapshot", return_value=None)
    mocker.patch("prescient.cli.get_latest_system_snapshot", return_value=None)

    result = runner.invoke(app, ["undo"])
    assert result.exit_code == 0

def test_undo_aborts_when_snapshot_not_verified(mocker):
    """
    Exits with code 1 when snapshot exists in state but not on disk.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.get_last_snapshot", return_value={
        "provider": "timeshift",
        "snapshot_name": "2026-03-24_01-15-00",
        "created_at": 1742778900.0,
        "trigger_reason": "Kernel"
    })
    mocker.patch("prescient.cli.verify_snapshot", return_value=False)

    result = runner.invoke(app, ["undo"])
    assert result.exit_code == 1

def test_undo_aborts_at_user_confirmation(mocker):
    """
    Does not call execute_rollback when user answers N at the prompt.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.get_last_snapshot", return_value={
        "provider": "timeshift",
        "snapshot_name": "2026-03-24_01-15-00",
        "created_at": 1742778900.0,
        "trigger_reason": "Kernel"
    })
    mocker.patch("prescient.cli.verify_snapshot", return_value=True)
    mock_rollback = mocker.patch("prescient.cli.execute_rollback")

    result = runner.invoke(app, ["undo"], input="n\n")
    assert result.exit_code == 0
    mock_rollback.assert_not_called()

def test_undo_executes_rollback_on_confirm(mocker):
    """
    Calls execute_rollback when user confirms with Y.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.get_last_snapshot", return_value={
        "provider": "snapper",
        "snapshot_name": "42",
        "created_at": 1742778900.0,
        "trigger_reason": "Kernel"
    })
    mocker.patch("prescient.cli.verify_snapshot", return_value=True)
    mock_rollback = mocker.patch("prescient.cli.execute_rollback", return_value=True)

    result = runner.invoke(app, ["undo"], input="y\n")
    assert result.exit_code == 0
    mock_rollback.assert_called_once()

def test_undo_exits_with_error_on_failed_rollback(mocker):
    """
    Exits with code 1 when execute_rollback returns False.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.get_last_snapshot", return_value={
        "provider": "timeshift",
        "snapshot_name": "2026-03-24_01-15-00",
        "created_at": 1742778900.0,
        "trigger_reason": "Kernel"
    })
    mocker.patch("prescient.cli.verify_snapshot", return_value=True)
    mocker.patch("prescient.cli.execute_rollback", return_value=False)

    result = runner.invoke(app, ["undo"], input="y\n")
    assert result.exit_code == 1

# Update
def test_update_exits_without_root(mocker):
    """
    Exits with code 1 when not running as root.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)

    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1

def test_update_exits_cleanly_when_already_up_to_date(mocker):
    """
    Exits with code 0 and skips git pull when already on latest version.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.check_for_updates", return_value=False)
    mock_run = mocker.patch("prescient.cli.subprocess.run")

    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    mock_run.assert_not_called()

def test_update_force_bypasses_version_check(mocker, tmp_path):
    """
    --force flag skips the version check and proceeds to git pull.
    Uses a real tmp_path filesystem so os.path.exists checks are driven
    by actual files, not a blanket mock.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.os.environ.get", return_value=None)
    mocker.patch("prescient.cli.os.path.expanduser", return_value=str(tmp_path))

    # Build the real directory structure that cli.py checks for
    install_dir = tmp_path / ".prescient"
    install_dir.mkdir()
    (install_dir / ".git").mkdir()
    venv_bin = install_dir / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()

    # Use side_effect so only the paths we actually created return True
    real_install_dir = str(install_dir)
    real_git_dir = str(install_dir / ".git")
    real_python = str(venv_bin / "python")

    mocker.patch(
        "prescient.cli.os.path.exists",
        side_effect=lambda p: str(p) in [real_install_dir, real_git_dir, real_python]
    )

    mock_run = mocker.patch(
        "prescient.cli.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    result = runner.invoke(app, ["update", "--force"])
    assert result.exit_code == 0
    mock_run.assert_called()

def test_update_exits_when_install_dir_missing(mocker):
    """
    Exits with code 1 when ~/.prescient or .git directory is missing.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.check_for_updates", return_value=True)
    mocker.patch("prescient.cli.os.environ.get", return_value=None)
    mocker.patch("prescient.cli.os.path.expanduser", return_value="/nonexistent")
    mocker.patch("prescient.cli.os.path.exists", return_value=False)

    result = runner.invoke(app, ["update"])
    assert result.exit_code == 1

# Heal
def test_heal_exits_without_root(mocker):
    """
    Exits with code 1 when not running as root (strict=True).
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)

    result = runner.invoke(app, ["heal"])
    assert result.exit_code == 1

def test_heal_runs_diagnose_then_autoheal(mocker):
    """
    Calls run_diagnostics then run_autoheal_sequence with its results.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mock_diag = mocker.patch(
        "prescient.cli.run_diagnostics",
        return_value=[("NetworkManager", {"count": 3, "latest_msg": "dhcp timeout"})]
    )
    mock_heal = mocker.patch("prescient.cli.run_autoheal_sequence")

    result = runner.invoke(app, ["heal"])
    assert result.exit_code == 0
    mock_diag.assert_called_once()
    mock_heal.assert_called_once()

# Uninstall
def test_uninstall_exits_without_root(mocker):
    """
    Exits with code 1 when not running as root.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=1000)

    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 1

def test_uninstall_aborts_at_confirmation(mocker):
    """
    Does not remove any files when user answers N at the prompt.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mock_remove = mocker.patch("prescient.cli.os.remove")
    mock_rmtree = mocker.patch("prescient.cli.shutil.rmtree")

    result = runner.invoke(app, ["uninstall"], input="n\n")
    assert result.exit_code == 0
    mock_remove.assert_not_called()
    mock_rmtree.assert_not_called()

def test_uninstall_removes_files_on_confirm(mocker, tmp_path):
    """
    Calls os.remove for file targets that exist when user confirms.
    shutil.rmtree is mocked as a safety guardrail.
    """
    mocker.patch("prescient.cli.os.geteuid", return_value=0)
    mocker.patch("prescient.cli.os.environ.get", return_value=None)
    mocker.patch("prescient.cli.os.path.expanduser", return_value="/home/testuser")

    APT_HOOK    = "/etc/apt/apt.conf.d/99prescient-guardian"
    PACMAN_HOOK = "/etc/pacman.d/hooks/99-prescient.hook"
    EXISTING    = {APT_HOOK, PACMAN_HOOK}

    mocker.patch(
        "prescient.cli.os.path.exists",
        side_effect=lambda p: str(p) in EXISTING
    )
    mocker.patch("prescient.cli.os.path.isdir", return_value=False)
    mock_remove = mocker.patch("prescient.cli.os.remove")
    mock_rmtree = mocker.patch("prescient.cli.shutil.rmtree")

    result = runner.invoke(app, ["uninstall"], input="y\n")

    assert result.exit_code == 0
    assert mock_remove.call_count == 2
    mock_remove.assert_any_call(APT_HOOK)
    mock_remove.assert_any_call(PACMAN_HOOK)
    mock_rmtree.assert_not_called()