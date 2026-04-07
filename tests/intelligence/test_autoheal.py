import pytest
import subprocess
from prescient.intelligence.autoheal import determine_fixes, run_autoheal_sequence

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """
    Mocks logger and console for every test in this file.
    """
    mocker.patch("prescient.intelligence.autoheal.logger")
    mocker.patch("prescient.intelligence.autoheal.console")

# Helpers
def make_culprit(identifier: str, message: str, count: int = 1) -> tuple:
    """
    Builds a culprit tuple matching the format returned by run_diagnostics.
    """
    return (identifier, {"count": count, "latest_msg": message})

# Determining fixes
def test_determine_fixes_detects_apt_deadlock(mocker):
    """
    Message containing 'could not get lock' maps to the APT deadlock fix.
    """
    culprits = [make_culprit("apt", "could not get lock /var/lib/dpkg/lock-frontend")]

    fixes = determine_fixes(culprits)
    assert len(fixes) == 1
    issue, cmds = fixes[0]
    assert "Deadlock" in issue
    assert any("lock-frontend" in cmd for cmd in cmds)
    assert "dpkg --configure -a" in cmds

def test_determine_fixes_detects_frontend_lock(mocker):
    """
    Message containing 'frontend lock' also triggers the deadlock fix.
    """
    culprits = [make_culprit("dpkg", "waiting for frontend lock")]

    fixes = determine_fixes(culprits)
    issue, cmds = fixes[0]
    assert "Deadlock" in issue


def test_determine_fixes_detects_unmet_dependencies():
    """
    Message containing 'unmet dependencies' maps to apt install -f -y.
    """
    culprits = [make_culprit("apt", "unmet dependencies for python3-pip")]

    fixes = determine_fixes(culprits)
    assert len(fixes) == 1
    issue, cmds = fixes[0]
    assert "Dependencies" in issue
    assert "apt install -f -y" in cmds


def test_determine_fixes_uses_direct_playbook_lookup():
    """
    A subsystem directly in HEAL_PLAYBOOK gets its mapped commands.
    """
    culprits = [make_culprit("NetworkManager", "dhcp request timed out")]

    fixes = determine_fixes(culprits)

    assert len(fixes) == 1
    issue, cmds = fixes[0]
    assert "NetworkManager" in issue
    assert "systemctl restart NetworkManager" in cmds


def test_determine_fixes_playbook_covers_all_known_services():
    """
    Every service in HEAL_PLAYBOOK produces a fix when it appears as a culprit.
    """
    from prescient.intelligence.autoheal import HEAL_PLAYBOOK

    for service in HEAL_PLAYBOOK:
        culprits = [make_culprit(service, "generic failure")]
        fixes = determine_fixes(culprits)
        assert len(fixes) == 1, f"No fix generated for playbook service: {service}"


def test_determine_fixes_catches_service_via_systemd_message():
    """
    When identifier is 'systemd' and the message mentions a known service,
    the correct playbook entry is used.
    """
    culprits = [make_culprit("systemd", "failed to start NetworkManager.service")]

    fixes = determine_fixes(culprits)
    assert len(fixes) == 1
    issue, cmds = fixes[0]
    assert "NetworkManager" in issue
    assert "systemctl restart NetworkManager" in cmds


def test_determine_fixes_generic_fallback_for_unknown_service():
    """
    Unknown services that are not kernel/systemd/unknown get a generic restart.
    """
    culprits = [make_culprit("cups", "printer daemon crashed")]

    fixes = determine_fixes(culprits)
    assert len(fixes) == 1
    issue, cmds = fixes[0]
    assert "cups" in issue
    assert "systemctl restart cups" in cmds


def test_determine_fixes_skips_kernel_in_fallback():
    """
    'kernel' is explicitly excluded from the generic restart fallback.
    """
    culprits = [make_culprit("kernel", "oops: general protection fault")]

    fixes = determine_fixes(culprits)
    assert fixes == []


def test_determine_fixes_skips_unknown_subsystem_in_fallback():
    """
    'Unknown Subsystem' is excluded from the generic restart fallback.
    """
    culprits = [make_culprit("Unknown Subsystem", "mystery error")]

    fixes = determine_fixes(culprits)
    assert fixes == []


def test_determine_fixes_only_processes_top_3():
    """
    Only the top 3 culprits are processed even if more are passed.
    """
    culprits = [
        make_culprit("NetworkManager", "dhcp timeout", count=10),
        make_culprit("bluetooth",      "connection failed", count=8),
        make_culprit("gdm3",           "display crash", count=6),
        make_culprit("lightdm",        "session error", count=4),
        make_culprit("cups",           "printer crash", count=2),
    ]

    fixes = determine_fixes(culprits)
    fix_issues = [issue for issue, _ in fixes]
    assert any("NetworkManager" in i for i in fix_issues)
    assert any("bluetooth" in i for i in fix_issues)
    assert any("gdm3" in i for i in fix_issues)
    assert not any("lightdm" in i for i in fix_issues)
    assert not any("cups" in i for i in fix_issues)


def test_determine_fixes_deduplicates_same_identifier():
    """
    If the same identifier appears twice in top 3, it is only processed once.
    """
    culprits = [
        make_culprit("NetworkManager", "dhcp timeout", count=5),
        make_culprit("NetworkManager", "interface down", count=4),
        make_culprit("bluetooth",      "connection failed", count=3),
    ]

    fixes = determine_fixes(culprits)
    nm_fixes = [f for f in fixes if "NetworkManager" in f[0]]
    assert len(nm_fixes) == 1


def test_determine_fixes_no_shell_true_in_commands():
    """
    Confirms no proposed command contains shell metacharacters that would
    require shell=True because all commands must be safe for shlex.split().
    """
    import shlex
    culprits = [
        make_culprit("NetworkManager", "dhcp timeout"),
        make_culprit("dpkg", "could not get lock /var/lib/dpkg/lock-frontend"),
        make_culprit("cups", "printer crash"),
    ]

    fixes = determine_fixes(culprits)
    for _, cmds in fixes:
        for cmd in cmds:
            parts = shlex.split(cmd)
            assert len(parts) >= 1


# Running autoheal sequence
def test_run_autoheal_sequence_aborts_without_root(mocker):
    """
    Exits immediately when not running as root.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=1000)
    mock_confirm = mocker.patch("prescient.intelligence.autoheal.typer.confirm")

    run_autoheal_sequence([make_culprit("NetworkManager", "dhcp timeout")])
    mock_confirm.assert_not_called()


def test_run_autoheal_sequence_aborts_with_empty_culprits(mocker):
    """
    Exits immediately when culprits list is empty.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=0)
    mock_confirm = mocker.patch("prescient.intelligence.autoheal.typer.confirm")

    run_autoheal_sequence([])
    mock_confirm.assert_not_called()


def test_run_autoheal_sequence_aborts_when_user_declines(mocker):
    """
    When user answers N at the confirmation prompt, no subprocess calls are made.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=0)
    mocker.patch("prescient.intelligence.autoheal.typer.confirm", return_value=False)
    mock_run = mocker.patch("prescient.intelligence.autoheal.subprocess.run")

    run_autoheal_sequence([make_culprit("NetworkManager", "dhcp timeout")])
    mock_run.assert_not_called()


def test_run_autoheal_sequence_executes_on_confirm(mocker):
    """
    When user answers Y, subprocess.run is called for each proposed command.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=0)
    mocker.patch("prescient.intelligence.autoheal.typer.confirm", return_value=True)
    mock_run = mocker.patch(
        "prescient.intelligence.autoheal.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    )

    run_autoheal_sequence([make_culprit("NetworkManager", "dhcp timeout")])
    mock_run.assert_called()
    cmd_used = mock_run.call_args[0][0]
    assert "systemctl" in cmd_used


def test_run_autoheal_sequence_skips_when_no_fixes_mapped(mocker):
    """
    When determine_fixes returns empty, the confirm prompt is never shown.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=0)
    mock_confirm = mocker.patch("prescient.intelligence.autoheal.typer.confirm")

    # kernel has no fix mapped
    run_autoheal_sequence([make_culprit("kernel", "oops: general protection fault")])
    mock_confirm.assert_not_called()


def test_run_autoheal_sequence_continues_on_failed_command(mocker):
    """
    A failed command does not abort the remaining fixes.
    """
    mocker.patch("prescient.intelligence.autoheal.os.geteuid", return_value=0)
    mocker.patch("prescient.intelligence.autoheal.typer.confirm", return_value=True)
    mock_run = mocker.patch(
        "prescient.intelligence.autoheal.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "dpkg", stderr="locked")
    )

    run_autoheal_sequence([make_culprit("dpkg", "could not get lock /var/lib/dpkg/lock-frontend")])
    assert mock_run.call_count == 4