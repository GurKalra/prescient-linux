import pytest
from unittest.mock import MagicMock
from prescient.vanguard.boot import check_boot_space, count_installed_kernels, analyze_boot_health

@pytest.fixture(autouse=True)
def silence_logger(mocker):
    mocker.patch("prescient.vanguard.boot.logger")
    mocker.patch("prescient.vanguard.boot.console")

# Checking boot space
def test_boot_space_safe(mocker):
    """
    Test that check_boot_space returns True when /boot has more free space
    than the minimum threshold.
    """
    mocker.patch(
        "prescient.vanguard.boot.shutil.disk_usage",
        return_value=MagicMock(free=800 * 1024 * 1024)
    )

    is_safe, free_mb = check_boot_space(min_mb=500)
    assert is_safe is True
    assert free_mb > 500

def test_boot_space_critical(mocker):
    """
    Test that check_boot_space returns False when /boot is below the threshold.
    """
    mocker.patch(
        "prescient.vanguard.boot.shutil.disk_usage",
        return_value=MagicMock(free=50 * 1024 * 1024)
    )

    is_safe, free_mb = check_boot_space(min_mb=500)
    assert is_safe is False
    assert free_mb < 500

def test_boot_space_exactly_at_threshold(mocker):
    """
    Test the boundary condition: exactly at 500 MB should be considered safe.
    """
    mocker.patch(
        "prescient.vanguard.boot.shutil.disk_usage",
        return_value=MagicMock(free=500 * 1024 * 1024)
    ) 

    is_safe, free_mb = check_boot_space(min_mb=500)
    assert is_safe is True

def test_boot_directory_missing_returns_safe(mocker):
    """
    Test that a missing /boot directory (unified root filesystem) fails
    open and returns True (the update should not be blocked).
    """
    mocker.patch(
        "prescient.vanguard.boot.shutil.disk_usage",
        side_effect=FileNotFoundError
    )

    is_safe, free_mb = check_boot_space()
    assert is_safe is True
    assert free_mb == 0.0

def test_boot_space_unexpected_exception_returns_safe(mocker):
    """
    Test that any unexpected OS error also fails open.
    It is same as missing /boot.
    """
    mocker.patch(
        "prescient.vanguard.boot.shutil.disk_usage",
        side_effect=OSError("permission denied")
    )

    is_safe, free_mb = check_boot_space()
    assert is_safe is True
    assert free_mb == 0.0

# Counting Installed Kernels
def test_count_installed_kernels_multiple(mocker):
    """
    Test that kernel counting correctly identifies vmlinuz files only.
    """
    mocker.patch(
        "prescient.vanguard.boot.os.listdir",
        return_value=[
            "vmlinuz-6.8.0-45-generic",
            "vmlinuz-6.8.0-41-generic",
            "vmlinuz-6.5.0-35-generic",
            "initrd.img-6.8.0-45-generic",
            "grub",
        ]
    )

    count = count_installed_kernels()
    assert count == 3

def test_count_installed_kernels_none(mocker):
    """
    Test that zero is returned when no kernel images exist.
    """
    mocker.patch(
        "prescient.vanguard.boot.os.listdir",
        return_value=["initrd.img", "grub", "efi"]
    )

    count = count_installed_kernels()
    assert count == 0

def test_count_installed_kernels_boot_missing(mocker):
    """
    Test that a missing /boot directory returns 0 without crashing.
    """
    mocker.patch(
        "prescient.vanguard.boot.os.listdir",
        side_effect=FileNotFoundError
    )

    count = count_installed_kernels()
    assert count == 0

# Analyse Boot Health
MOCK_CONFIG = {
    "triggers": {
        "high_risk": {
            "kernel": ["linux-image", "linux-headers"],
            "bootloader": ["grub"]
        }
    }
}

def test_analyze_boot_health_skips_non_boot_update(mocker):
    """
    Test that analyze_boot_health returns True immediately and skips all
    checks for a normal (non-boot) package list.
    """
    mocker.patch("prescient.vanguard.boot.CONFIG", MOCK_CONFIG)
    mock_space = mocker.patch("prescient.vanguard.boot.check_boot_space", return_value=(True, 800.0))
    mock_kernels = mocker.patch("prescient.vanguard.boot.count_installed_kernels", return_value=1)

    result = analyze_boot_health(["htop", "curl", "vim"])

    assert result is True
    mock_space.assert_not_called()
    mock_kernels.assert_not_called()

def test_analyze_boot_health_passes_on_safe_kernel_update(mocker):
    """
    Test that a kernel update with plenty of /boot space passes the audit.
    """
    mocker.patch("prescient.vanguard.boot.CONFIG", MOCK_CONFIG)
    mock_space = mocker.patch("prescient.vanguard.boot.check_boot_space", return_value=(True, 800.0))
    mocker.patch("prescient.vanguard.boot.count_installed_kernels", return_value=1)

    result = analyze_boot_health(["linux-image-6.8.0-45-generic"])

    assert result is True
    mock_space.assert_called_once()

def test_analyze_boot_health_veto_on_low_boot_space(mocker):
    """
    Test that a kernel update with critically low /boot space returns False (VETO).
    """
    mocker.patch("prescient.vanguard.boot.CONFIG", MOCK_CONFIG)
    mocker.patch("prescient.vanguard.boot.check_boot_space", return_value=(False, 50.0))
    mocker.patch("prescient.vanguard.boot.count_installed_kernels", return_value=1)

    result = analyze_boot_health(["linux-image-6.8.0-45-generic"])

    assert result is False

def test_analyze_boot_health_triggers_on_bootloader_package(mocker):
    """
    Test that a bootloader update (grub) also triggers the boot audit.
    """
    mocker.patch("prescient.vanguard.boot.CONFIG", MOCK_CONFIG)
    mock_space = mocker.patch("prescient.vanguard.boot.check_boot_space", return_value=(True, 800.0))
    mocker.patch("prescient.vanguard.boot.count_installed_kernels", return_value=1)

    result = analyze_boot_health(["grub-efi-amd64"])

    assert result is True
    mock_space.assert_called_once()
