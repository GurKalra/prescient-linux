import pytest
from unittest.mock import MagicMock, mock_open
from prescient.core.mirror_checker import (
    get_apt_mirrors,
    get_pacman_mirrors,
    get_active_mirrors,
    run_mirror_preflight,
)

@pytest.fixture(autouse=True)
def silence_logger(mocker):
    """
    Automatically mocks the logger for every test in this file.
    """
    mocker.patch("prescient.core.mirror_checker.logger")

# Ubuntu / Apt paths
def test_get_apt_mirrors_extracts_urls(mocker):
    """
    Parses a standard Ubuntu sources.list and extracts the base URL.
    """
    fake_sources = "deb https://archive.ubuntu.com/ubuntu noble main restricted\n"

    mocker.patch("builtins.open", mock_open(read_data=fake_sources))
    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == "/etc/apt/sources.list"
    )

    mirrors = get_apt_mirrors()
    assert "https://archive.ubuntu.com" in mirrors

def test_get_apt_mirrors_ignores_comments_and_cdrom(mocker):
    """
    Commented lines and cdrom entries must be skipped entirely.
    """
    fake_sources = (
        "# deb https://should-be-ignored.com/ubuntu noble main\n"
        "deb cdrom:[Ubuntu 24.04]/ noble main\n"
        "deb https://real-mirror.ubuntu.com/ubuntu noble main\n"
    )
    
    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == "/etc/apt/sources.list"
    )
    mocker.patch("builtins.open", mock_open(read_data=fake_sources))

    mirrors = get_apt_mirrors()
    assert "https://real-mirror.ubuntu.com" in mirrors
    assert "https://should-be-ignored.com" not in mirrors

def test_get_apt_mirrors_supports_deb822_format(mocker):
    """
    Parses modern DEB822 .sources format
    """
    fake_sources = "URIs: https://ppa.launchpadcontent.net/example/ubuntu\n"

    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == '/etc/apt/sources.list'
    )
    mocker.patch("builtins.open", mock_open(read_data=fake_sources))

    mirrors = get_apt_mirrors()
    assert "https://ppa.launchpadcontent.net" in mirrors


# Arch / pacman path
def test_get_pacman_mirrors_extracts_urls(mocker):
    """
    Parses a standard Arch mirrorlist and extracts the base domain.
    """
    fake_mirrorlist = "Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch\n"

    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == "/etc/pacman.d/mirrorlist"
    )
    mocker.patch("builtins.open", mock_open(read_data=fake_mirrorlist))

    mirrors = get_pacman_mirrors()
    assert "https://mirror.rackspace.com" in mirrors


def test_get_pacman_mirrors_ignores_commented_servers(mocker):
    """
    Commented-out Server lines must be skipped.
    """
    fake_mirrorlist = (
        "# Server = https://commented-out.mirror.com/archlinux/$repo/os/$arch\n"
        "Server = https://active.mirror.com/archlinux/$repo/os/$arch\n"
    )

    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == "/etc/pacman.d/mirrorlist"
    )
    mocker.patch("builtins.open", mock_open(read_data=fake_mirrorlist))

    mirrors = get_pacman_mirrors()
    assert "https://active.mirror.com" in mirrors
    assert "https://commented-out.mirror.com" not in mirrors


def test_get_pacman_mirrors_strips_path_variables(mocker):
    """
    Only the base domain is extracted (not the $repo/$arch path variables).
    """
    fake_mirrorlist = "Server = https://geo.mirror.pkgbuild.com/archlinux/$repo/os/$arch\n"

    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        side_effect=lambda p: p == "/etc/pacman.d/mirrorlist"
    )
    mocker.patch("builtins.open", mock_open(read_data=fake_mirrorlist))

    mirrors = get_pacman_mirrors()
    assert "https://geo.mirror.pkgbuild.com" in mirrors
    assert "https://geo.mirror.pkgbuild.com/archlinux/$repo/os/$arch" not in mirrors


def test_get_pacman_mirrors_returns_empty_if_file_missing(mocker):
    """
    Returns an empty set gracefully if mirrorlist does not exist.
    """
    mocker.patch(
        "prescient.core.mirror_checker.os.path.exists",
        return_value=False
    )

    mirrors = get_pacman_mirrors()
    assert mirrors == set()

# Routers
def _ubuntu_which(cmd):
    return "/usr/bin/dpkg" if cmd == "dpkg" else None

def _arch_which(cmd):
    return "/usr/bin/pacman" if cmd == "pacman" else None

def test_get_active_mirrors_routes_to_apt_on_ubuntu(mocker):
    """
    On Ubuntu (dpkg present), routes to get_apt_mirrors.
    """
    mocker.patch("prescient.core.mirror_checker.shutil.which", side_effect=_ubuntu_which)
    mock_apt = mocker.patch(
        "prescient.core.mirror_checker.get_apt_mirrors",
        return_value={"https://archive.ubuntu.com"}
    )

    result = get_active_mirrors()
    mock_apt.assert_called_once()
    assert "https://archive.ubuntu.com" in result

def test_get_active_mirrors_routes_to_pacman_on_arch(mocker):
    """
    On Arch (pacman present), routes to get_pacman_mirrors.
    """
    mocker.patch("prescient.core.mirror_checker.shutil.which", side_effect=_arch_which)
    mock_pacman = mocker.patch(
        "prescient.core.mirror_checker.get_pacman_mirrors",
        return_value={"https://mirror.rackspace.com"}
    )

    result = get_active_mirrors()
    mock_pacman.assert_called_once()
    assert "https://mirror.rackspace.com" in result

def test_get_active_mirrors_returns_empty_if_no_pm(mocker):
    """
    Returns empty set if neither dpkg nor pacman is found.
    """
    mocker.patch("prescient.core.mirror_checker.shutil.which", return_value=None)

    result = get_active_mirrors()

    assert result == set()

# Entry points
def test_run_mirror_preflight_passes_when_all_mirrors_alive(mocker):
    """
    Returns True when at least one mirror is reachable.
    """
    mocker.patch(
        "prescient.core.mirror_checker.audit_all_mirrors",
        return_value=[
            ("https://archive.ubuntu.com", True, "OK"),
            ("https://ppa.launchpadcontent.net", True, "OK"),
        ]
    )

    result = run_mirror_preflight()
    assert result is True

def test_run_mirror_preflight_passes_with_one_dead_mirror(mocker):
    """
    Returns True when at least one mirror is alive (a single dead PPA should not block).
    """
    mocker.patch(
        "prescient.core.mirror_checker.audit_all_mirrors",
        return_value=[
            ("https://archive.ubuntu.com", True, "OK"),
            ("https://dead-ppa.example.com", False, "Connection refused"),
        ]
    )

    result = run_mirror_preflight()
    assert result is True


def test_run_mirror_preflight_veto_when_all_mirrors_dead(mocker):
    """
    Returns False (VETO) when every mirror is unreachable.
    """
    mocker.patch(
        "prescient.core.mirror_checker.audit_all_mirrors",
        return_value=[
            ("https://archive.ubuntu.com", False, "Connection refused"),
            ("https://mirror.rackspace.com", False, "timed out"),
        ]
    )

    result = run_mirror_preflight()
    assert result is False


def test_run_mirror_preflight_passes_when_no_mirrors_found(mocker):
    """Returns True (fail open) when no mirrors are found (avoids blocking on unconfigured systems).
    """
    mocker.patch(
        "prescient.core.mirror_checker.audit_all_mirrors",
        return_value=[]
    )

    result = run_mirror_preflight()
    assert result is True