import pytest
import subprocess
from pathlib import Path
from typer import Exit as TyperExit
from unittest.mock import MagicMock, call
from prescient.core.hooks import install, install_apt_hook, install_pacman_hook, install_ramdisk_hook

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """Mocks logger and console for every test in this file."""
    mocker.patch("prescient.core.hooks.logger")
    mocker.patch("prescient.core.hooks.console")

# Installing
def test_install_exits_without_root(mocker):
    """
    Exits with code 1 immediately when not running as root.
    Neither install_apt_hook nor install_pacman_hook should be called.
    """
    mocker.patch("prescient.core.hooks.os.geteuid", return_value=1000)
    mock_apt = mocker.patch("prescient.core.hooks.install_apt_hook")
    mock_pacman = mocker.patch("prescient.core.hooks.install_pacman_hook")

    with pytest.raises(TyperExit) as exc:
        install()

    assert exc.value.exit_code == 1
    mock_apt.assert_not_called()
    mock_pacman.assert_not_called()

def test_install_routes_to_apt_on_ubuntu(mocker):
    """
    Detects APT and calls install_apt_hook + install_ramdisk_hook("apt").
    """
    mocker.patch("prescient.core.hooks.os.geteuid", return_value=0)
    mocker.patch("prescient.core.hooks.detect_package_manager", return_value="apt")
    mock_apt = mocker.patch("prescient.core.hooks.install_apt_hook")
    mock_pacman = mocker.patch("prescient.core.hooks.install_pacman_hook")
    mock_ramdisk = mocker.patch("prescient.core.hooks.install_ramdisk_hook")

    install()
    mock_apt.assert_called_once()
    mock_pacman.assert_not_called()
    mock_ramdisk.assert_called_once_with("apt")

def test_install_routes_to_pacman_on_arch(mocker):
    """
    Detects Pacman and calls install_pacman_hook + install_ramdisk_hook("pacman").
    """
    mocker.patch("prescient.core.hooks.os.geteuid", return_value=0)
    mocker.patch("prescient.core.hooks.detect_package_manager", return_value="pacman")
    mock_apt = mocker.patch("prescient.core.hooks.install_apt_hook")
    mock_pacman = mocker.patch("prescient.core.hooks.install_pacman_hook")
    mock_ramdisk = mocker.patch("prescient.core.hooks.install_ramdisk_hook")

    install()
    mock_pacman.assert_called_once()
    mock_apt.assert_not_called()
    mock_ramdisk.assert_called_once_with("pacman")

def test_install_exits_on_unsupported_package_manager(mocker):
    """
    Exits with code 1 when neither apt nor pacman is detected.
    """
    mocker.patch("prescient.core.hooks.os.geteuid", return_value=0)
    mocker.patch("prescient.core.hooks.detect_package_manager", return_value=None)

    with pytest.raises(TyperExit) as exc:
        install()

    assert exc.value.exit_code == 1

# Installing apt hooks
def test_install_apt_hook_writes_correct_path(mocker):
    """
    Writes the hook file to /etc/apt/apt.conf.d/99prescient-guardian.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_file = MagicMock()
    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_file if str(p) == "/etc/apt/apt.conf.d/99prescient-guardian" else Path(p)
    )

    install_apt_hook()
    mock_hook_file.write_text.assert_called_once()

def test_install_apt_hook_content_contains_predict(mocker):
    """
    The written hook content must invoke 'prescient predict' and set Version 3.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_file = MagicMock()
    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_file if str(p) == "/etc/apt/apt.conf.d/99prescient-guardian" else Path(p)
    )

    install_apt_hook()
    written_content = mock_hook_file.write_text.call_args[0][0]
    assert "predict" in written_content
    assert 'Version "3"' in written_content
    assert "/usr/local/bin/prescient" in written_content

def test_install_apt_hook_exits_on_write_failure(mocker):
    """
    Exits with code 1 when writing the hook file raises a PermissionError.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_file = MagicMock()
    mock_hook_file.write_text.side_effect = PermissionError("permission denied")
    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_file if str(p) == "/etc/apt/apt.conf.d/99prescient-guardian" else Path(p)
    )
    with pytest.raises(TyperExit) as exc:
        install_apt_hook()

    assert exc.value.exit_code == 1

# Installing pacman hooks
def test_install_pacman_hook_creates_hook_directory(mocker):
    """
    Creates /etc/pacman.d/hooks/ with parents=True, exist_ok=True
    before writing the hook file.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_dir = MagicMock()
    mock_hook_file = MagicMock()
    mock_hook_dir.__truediv__ = MagicMock(return_value=mock_hook_file)

    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_dir if str(p) == "/etc/pacman.d/hooks" else Path(p)
    )

    install_pacman_hook()
    mock_hook_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

def test_install_pacman_hook_content_contains_required_fields(mocker):
    """
    The written hook content must include NeedsTargets, AbortOnFail,
    PreTransaction trigger, and the prescient predict command.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_dir = MagicMock()
    mock_hook_file = MagicMock()
    mock_hook_dir.__truediv__ = MagicMock(return_value=mock_hook_file)

    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_dir if str(p) == "/etc/pacman.d/hooks" else Path(p)
    )

    install_pacman_hook()
    written_content = mock_hook_file.write_text.call_args[0][0]
    assert "NeedsTargets" in written_content
    assert "AbortOnFail" in written_content
    assert "PreTransaction" in written_content
    assert "predict" in written_content
    assert "/usr/local/bin/prescient" in written_content

def test_install_pacmaan_hook_exits_on_write_faliure(mocker):
    """
    Exits with code 1 when writing the hook file raises a PermissionError.
    """
    mocker.patch("prescient.core.hooks.os.path.abspath", return_value="/usr/local/bin/prescient")
    mock_hook_dir = MagicMock()
    mock_hook_file = MagicMock()
    mock_hook_file.write_text.side_effect = PermissionError("permission denied")
    mock_hook_dir.__truediv__ = MagicMock(return_value=mock_hook_file)

    mocker.patch(
        "prescient.core.hooks.Path",
        side_effect=lambda p: mock_hook_dir if str(p) == "/etc/pacman.d/hooks" else Path(p)
    )
    with pytest.raises(TyperExit) as exc:
        install_pacman_hook()

    assert exc.value.exit_code == 1

# Installing ramdisk hooks
def test_install_ramdisk_hook_apt_copies_rescue_binary(mocker):
    """
    First shutil.copy call must deliver the rescue binary
    to /usr/local/bin/prescient-rescue with 0o755 permissions.
    """
    mock_shutil_copy = mocker.patch("prescient.core.hooks.shutil.copy")
    mock_chmod = mocker.patch("prescient.core.hooks.os.chmod")
    mocker.patch(
        "prescient.core.hooks.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    install_ramdisk_hook("apt")
    first_dest = mock_shutil_copy.call_args_list[0][0][1]
    assert first_dest == Path("/usr/local/bin/prescient-rescue")
    first_chmod_args = mock_chmod.call_args_list[0][0]
    assert first_chmod_args[0] == Path("/usr/local/bin/prescient-rescue")
    assert first_chmod_args[1] == 0o755

def test_install_ramdisk_hook_apt_installs_ubuntu_hook(mocker):
    """
    Second shutil.copy call must deliver the Ubuntu hook
    to /etc/initramfs-tools/hooks/prescient-hook with 0o755 permissions.
    """
    mock_shutil_copy = mocker.patch("prescient.core.hooks.shutil.copy")
    mock_chmod = mocker.patch("prescient.core.hooks.os.chmod")
    mocker.patch(
        "prescient.core.hooks.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    install_ramdisk_hook("apt")
    second_dest = mock_shutil_copy.call_args_list[1][0][1]
    assert second_dest == Path("/etc/initramfs-tools/hooks/prescient-hook")
    second_chmod_args = mock_chmod.call_args_list[1][0]
    assert second_chmod_args[0] == Path("/etc/initramfs-tools/hooks/prescient-hook")
    assert second_chmod_args[1] == 0o755

def test_install_ramdisk_hook_apt_runs_update_initramfs(mocker):
    """
    Calls update-initramfs -u to rebuild the kernel RAM disk on Ubuntu/Debian.
    """
    mocker.patch("prescient.core.hooks.shutil.copy")
    mocker.patch("prescient.core.hooks.os.chmod")
    mock_run = mocker.patch(
        "prescient.core.hooks.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    install_ramdisk_hook("apt")
    cmd = mock_run.call_args[0][0]
    assert cmd == ["update-initramfs", "-u"]

def test_install_ramdisk_hook_pacman_installs_arch_hook(mocker):
    """
    Second shutil.copy call must deliver the Arch hook
    to /etc/initcpio/install/prescient-hook with 0o755 permissions.
    """
    mock_shutil_copy = mocker.patch("prescient.core.hooks.shutil.copy")
    mock_chmod = mocker.patch("prescient.core.hooks.os.chmod")
    mocker.patch(
        "prescient.core.hooks.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )
    mocker.patch("pathlib.Path.mkdir")

    install_ramdisk_hook("pacman")
    second_dest = mock_shutil_copy.call_args_list[1][0][1]
    assert second_dest == Path("/etc/initcpio/install/prescient-hook")
    second_chmod_args = mock_chmod.call_args_list[1][0]
    assert second_chmod_args[0] == Path("/etc/initcpio/install/prescient-hook")
    assert second_chmod_args[1] == 0o755

def test_install_ramdisk_hook_pacman_runs_mkinitcpio(mocker):
    """
    Calls mkinitcpio -P to rebuild all kernel presets on Arch Linux.
    """
    mocker.patch("prescient.core.hooks.shutil.copy")
    mocker.patch("prescient.core.hooks.os.chmod")
    mocker.patch("pathlib.Path.mkdir")
    mock_run = mocker.patch(
        "prescient.core.hooks.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    install_ramdisk_hook("pacman")
    cmd = mock_run.call_args[0][0]
    assert cmd == ["mkinitcpio", "-P"]

def test_install_ramdisk_hook_returns_early_on_rescue_copy_failure(mocker):
    """
    Returns early without installing the OS hook or rebuilding the RAM disk
    when copying the rescue binary fails.
    """
    mocker.patch(
        "prescient.core.hooks.shutil.copy",
        side_effect=OSError("no space left on device")
    )
    mocker.patch("prescient.core.hooks.os.chmod")
    mock_run = mocker.patch("prescient.core.hooks.subprocess.run")

    install_ramdisk_hook("apt")
    mock_run.assert_not_called()

def test_install_ramdisk_hook_handles_ramdisk_rebuild_failure_gracefully(mocker):
    """
    Does not raise when update-initramfs exits with a non-zero code.
    The failure is logged but the function completes without raising.
    """
    mocker.patch("prescient.core.hooks.shutil.copy")
    mocker.patch("prescient.core.hooks.os.chmod")
    mocker.patch(
        "prescient.core.hooks.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "update-initramfs")
    )

    try:
        install_ramdisk_hook("apt")
    except Exception as e:
        pytest.fail(f"install_ramdisk_hook raised unexpectedly: {e}")