import pytest
from unittest.mock import MagicMock
from prescient.vanguard.system import parse_and_sanitize_packages, run_preflight_checks

@pytest.fixture(autouse=True)
def silence_logger(mocker):
    mocker.patch("prescient.vanguard.system.logger")

def test_parse_and_sanitize_packages():
    raw_input = "\n".join([
        "linux-image-6.8.0-45-generic",
        "htop",
        "malicious-pkg; rm -rf /",
        "broken|pipe",
        "valid-package+1.2.3"
    ])

    clean_packages = parse_and_sanitize_packages(raw_input)

    # Clean names
    assert "linux-image-6.8.0-45-generic" in clean_packages
    assert "htop" in clean_packages
    assert "valid-package+1.2.3" in clean_packages

    # Malicious inputs
    assert "malicious-pkg; rm -rf /" not in clean_packages
    assert "broken|pipe" not in clean_packages

# Tests for ubuntu

def test_preflight_checks_pass_ubuntu(mocker):
    """
    Simulates a healthy Ubuntu system (dpkg present, no issues).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", return_value="/usr/bin/dpkg")
    mocker.patch("prescient.vanguard.system.subprocess.run", return_value=MagicMock(returncode=0, stdout=""))
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=50 * 1024**3))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    result = run_preflight_checks()
    assert result is True

def test_preflight_checks_fail_on_locked_dpkg_ubuntu(mocker):
    """
    Simulates a broken dpkg state on Ubuntu (should VETO).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", return_value="/usr/bin/dpkg")
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=50 * 1024**3))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    mock_sub = mocker.patch("prescient.vanguard.system.subprocess.run")
    mock_sub.return_value.returncode = 1
    mock_sub.return_value.stdout = "dpkg was interrupted, you must manually run 'sudo dpkg --configure -a'"

    result = run_preflight_checks()
    assert result is False

def test_preflight_checks_fail_on_low_disk_ubuntu(mocker):
    """
    Simulates critically low root disk space on Ubuntu (should VETO).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", return_value="/usr/bin/dpkg")
    mocker.patch("prescient.vanguard.system.subprocess.run", return_value=MagicMock(returncode=0, stdout=""))
    # 500 MB free which is below the 2 GB minimum limit
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=500 * 1024**2))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    result = run_preflight_checks()
    assert result is False

def test_preflight_checks_fail_on_dead_mirrors_ubuntu(mocker):
    """
    Simulates all APT mirrors being unreachable on Ubuntu (should VETO).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", return_value="/usr/bin/dpkg")
    mocker.patch("prescient.vanguard.system.subprocess.run", return_value=MagicMock(returncode=0, stdout=""))
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=50 * 1024**3))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=False)

    result = run_preflight_checks()

    assert result is False

# Tests for arch
def _arch_which(cmd):
    return "/usr/bin/pacman" if cmd == "pacman" else None

def test_preflight_checks_pass_arch(mocker):
    """
    Simulates a healthy Arch system (pacman present, no db.lck).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", side_effect=_arch_which)
    mocker.patch("prescient.vanguard.system.os.path.exists",
                 side_effect=lambda p: False if p == "/var/lib/pacman/db.lck" else True)
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=50 * 1024**3))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    result = run_preflight_checks()
    assert result is True

def test_preflight_checks_fail_on_locked_pacman_arch(mocker):
    """
    Simulates a locked pacman database on Arch (should VETO).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", side_effect=_arch_which)
    mocker.patch("prescient.vanguard.system.os.path.exists",
                 side_effect=lambda p: True if p == "/var/lib/pacman/db.lck" else False)
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=50 * 1024**3))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    result = run_preflight_checks()
    assert result is False

def test_preflight_checks_fail_on_low_disk_arch(mocker):
    """
    Simulates critically low root disk space on Arch (should VET0).
    """
    mocker.patch("prescient.vanguard.system.shutil.which", side_effect=_arch_which)
    mocker.patch("prescient.vanguard.system.os.path.exists",
                 side_effect=lambda p: False if p == "/var/lib/pacman/db.lck" else True)
    mocker.patch("prescient.vanguard.system.shutil.disk_usage", return_value=MagicMock(free=500 * 1024**2))
    mocker.patch("prescient.vanguard.system.run_mirror_preflight", return_value=True)

    result = run_preflight_checks()
    assert result is False