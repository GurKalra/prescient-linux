import pytest
from unittest.mock import MagicMock
from prescient.vanguard.security import get_secure_boot_status, get_dkms_modules, analyze_security_risk

MOCK_CONFIG = {
    "triggers": {
        "high_risk": {
            "kernel": ["linux-image", "linux-headers"],
            "bootloader": ["grub", "shim"],
        },
        "medium_risk": {
            "drivers": ["nvidia", "dkms"],
        },
    }
}

@pytest.fixture(autouse=True)
def silence_output(mocker):
    mocker.patch("prescient.vanguard.security.logger")
    mocker.patch("prescient.vanguard.security.console")

# Getting Secure Boot Status
def test_secure_boot_returns_cached_value(mocker):
    """
    If the cache already has sb_enabled, mokutil should never be called.
    """
    mocker.patch(
        "prescient.vanguard.security.get_cached_state",
        return_value={"sb_enabled": True}
    )
    mock_run = mocker.patch("prescient.vanguard.security.subprocess.run")

    result = get_secure_boot_status()
    assert result is True
    mock_run.assert_not_called()

def test_secure_boot_enabled_via_mokutil(mocker):
    """
    Parses mokutil stdout and returns True when Secure Boot is enabled.
    """
    mocker.patch("prescient.vanguard.security.get_cached_state", return_value={})
    mocker.patch("prescient.vanguard.security.set_cached_state")
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        return_value=MagicMock(stdout="SecureBoot enabled\n")
    )
    
    result = get_secure_boot_status()
    assert result is True

def test_secure_boot_disabled_via_mokutil(mocker):
    """
    Parses mokutil stdout and returns False when Secure Boot is disabled.
    """
    mocker.patch("prescient.vanguard.security.get_cached_state", return_value={})
    mocker.patch("prescient.vanguard.security.set_cached_state")
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        return_value=MagicMock(stdout="SecureBoot disabled\n")
    )

    result = get_secure_boot_status()
    assert result is False

def test_secure_boot_mokutil_missing_returns_false(mocker):
    """
    If mokutil is not installed, fails open (returns False = permissive mode).
    """
    mocker.patch("prescient.vanguard.security.get_cached_state", return_value={})
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        side_effect=FileNotFoundError
    )

    result = get_secure_boot_status()
    assert result is False

def test_secure_boot_mokutil_timeout_returns_false(mocker):
    """
    If mokutil times out, fails open (returns False = permissive mode).
    """
    mocker.patch("prescient.vanguard.security.get_cached_state", return_value={})
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        side_effect=Exception("timed out")
    )

    result = get_secure_boot_status()
    assert result is False

# Gtting DKMS Modules
def test_get_dkms_modules_returns_parsed_lines(mocker):
    """
    Returns a list of lines from dkms status output.
    """
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        return_value=MagicMock(
            stdout="nvidia, 535.104.05, 6.8.0-45-generic, x86_64: installed\n"
                   "virtualbox, 7.0.12, 6.8.0-45-generic, x86_64: installed\n"
        )
    )

    modules = get_dkms_modules()
    assert len(modules) == 2
    assert "nvidia, 535.104.05, 6.8.0-45-generic, x86_64: installed" in modules

def test_get_dkms_modules_returns_empty_when_none_installed(mocker):
    """
    Returns an empty list when dkms runs but has no output.
    """
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        return_value=MagicMock(stdout="")
    )

    modules = get_dkms_modules()
    assert modules == []

def test_get_dkms_modules_returns_empty_on_failure(mocker):
    """
    Returns an empty list if dkms is not installed or times out.
    """
    mocker.patch(
        "prescient.vanguard.security.subprocess.run",
        side_effect=FileNotFoundError
    )

    modules = get_dkms_modules()
    assert modules == []

def test_analyze_security_risk_skips_boring_update(mocker):
    """
    A standard app update (curl, vim) should fast-pass without calling
    get_secure_boot_status or get_dkms_modules.
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mock_sb = mocker.patch("prescient.vanguard.security.get_secure_boot_status")
    mock_dkms = mocker.patch("prescient.vanguard.security.get_dkms_modules")

    result = analyze_security_risk(["curl", "vim", "htop"])

    assert result is True
    mock_sb.assert_not_called()
    mock_dkms.assert_not_called()

def test_analyze_security_risk_kernel_update_secure_boot_off_no_dkms(mocker):
    """
    Kernel update with Secure Boot disabled and no DKMS modules is safe.
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mocker.patch("prescient.vanguard.security.get_secure_boot_status", return_value=False)
    mocker.patch("prescient.vanguard.security.get_dkms_modules", return_value=[])

    result = analyze_security_risk(["linux-image-6.8.0-45-generic"])
    assert result is True

def test_analyze_security_risk_kernel_update_secure_boot_on_no_dkms(mocker):
    """
    Kernel update with Secure Boot enabled but no DKMS modules is safe
    (no collision risk without unsigned modules).
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mocker.patch("prescient.vanguard.security.get_secure_boot_status", return_value=True)
    mocker.patch("prescient.vanguard.security.get_dkms_modules", return_value=[])

    result = analyze_security_risk(["linux-image-6.8.0-45-generic"])
    assert result is True

def test_analyze_security_risk_collision_kernel_plus_dkms_secure_boot_on(mocker):
    """
    The critical collision: Secure Boot ON + kernel update + active DKMS modules.
    analyze_security_risk still returns True (it warns, does not VETO),
    but both probes must have been called.
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mock_sb = mocker.patch(
        "prescient.vanguard.security.get_secure_boot_status", return_value=True
    )
    mock_dkms = mocker.patch(
        "prescient.vanguard.security.get_dkms_modules",
        return_value=["nvidia, 535.104.05, 6.8.0-45-generic, x86_64: installed"]
    )

    result = analyze_security_risk(["linux-image-6.8.0-45-generic"])
    assert result is True
    mock_sb.assert_called_once()
    mock_dkms.assert_called_once()

def test_analyze_security_risk_driver_update_triggers_audit(mocker):
    """
    An nvidia/dkms driver update should trigger the security audit.
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mock_sb = mocker.patch(
        "prescient.vanguard.security.get_secure_boot_status", return_value=False
    )
    mock_dkms = mocker.patch(
        "prescient.vanguard.security.get_dkms_modules", return_value=[]
    )

    result = analyze_security_risk(["nvidia-driver-535"])
    assert result is True
    mock_sb.assert_called_once()
    mock_dkms.assert_called_once()

def test_analyze_security_risk_bootloader_update_triggers_audit(mocker):
    """
    A shim or grub update should trigger the security audit.
    """
    mocker.patch("prescient.vanguard.security.CONFIG", MOCK_CONFIG)
    mock_sb = mocker.patch(
        "prescient.vanguard.security.get_secure_boot_status", return_value=False
    )
    mocker.patch("prescient.vanguard.security.get_dkms_modules", return_value=[])

    result = analyze_security_risk(["shim-signed"])
    assert result is True
    mock_sb.assert_called_once()