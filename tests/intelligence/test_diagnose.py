import pytest
import json
import subprocess
from rich.table import Table
from prescient.intelligence.diagnose import get_structured_logs, run_diagnostics, get_raw_journalctl_output

@pytest.fixture(autouse=True)
def silence_output(mocker):
    """
    Mocks logger and console for every test.
    Returns the console mock so individual tests can inspect calls if needed.
    """
    mocker.patch("prescient.intelligence.diagnose.logger")
    return mocker.patch("prescient.intelligence.diagnose.console")

# Helpers
def make_log_entry(identifier: str, message: str) -> str:
    """
    Builds a minimal journalctl JSON line for a given subsystem.
    """
    return json.dumps({
        "SYSLOG_IDENTIFIER": identifier,
        "MESSAGE": message,
        "PRIORITY": "3"
    })

# Getting structured logs
def test_get_structured_logs_parses_current_boot(mocker):
    """
    Passes -b 0 to journalctl when previous=False.
    """
    mock_run = mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=make_log_entry("kernel", "some error") + "\n"
        )
    )

    result = get_structured_logs(previous=False)
    assert len(result) == 1
    cmd_used = mock_run.call_args[0][0]
    assert "-b" in cmd_used
    assert "0" in cmd_used

def test_get_structured_logs_passes_previous_flag(mocker):
    """
    Passes -b -1 to journalctl when previous=True.
    """
    mock_run = mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=make_log_entry("NetworkManager", "dhcp timed out") + "\n"
        )
    )

    result = get_structured_logs(previous=True)
    assert len(result) == 1
    cmd_used = mock_run.call_args[0][0]
    assert "-1" in cmd_used

def test_get_structured_logs_skips_invalid_json_lines(mocker):
    """
    Malformed JSON lines are silently skipped.
    """
    stdout = "\n".join([
        make_log_entry("kernel", "real error"),
        "this is not json at all",
        make_log_entry("dbus", "another error"),
        "",
    ])
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout
        )
    )

    result = get_structured_logs()
    assert len(result) == 2

def test_get_structured_logs_returns_empty_on_journalctl_failure(mocker):
    """
    Returns empty list when journalctl exits with a non-zero code.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        side_effect = subprocess.CalledProcessError(1, "journalctl")
    )

    result = get_structured_logs()
    assert result == []

def test_get_structured_logs_returns_empty_when_journalctl_missing(mocker):
    """
    Returns empty list when journalctl is not installed on the system.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        side_effect = FileNotFoundError
    )

    result = get_structured_logs()
    assert result == []

def test_get_structured_logs_returns_empty_on_no_output(mocker):
    """
    Returns empty list when journalctl runs but produces no log lines.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=""
        )
    )

    result = get_structured_logs()
    assert result == []

# Running diagnostics
def test_run_diagnostics_returns_empty_when_no_logs(mocker):
    """
    Returns empty list and prints clean message when no errors found.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=[]
    )

    result = run_diagnostics()
    assert result == []

def test_run_diagnostics_groups_errors_by_identifier(mocker):
    """
    Multiple log entries from the same subsystem are grouped under one culprit.
    """
    logs = [
        {"SYSLOG_IDENTIFIER": "NetworkManager", "MESSAGE": "dhcp timeout"},
        {"SYSLOG_IDENTIFIER": "NetworkManager", "MESSAGE": "interface down"},
        {"SYSLOG_IDENTIFIER": "kernel", "MESSAGE": "oom killer"},
    ]
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=logs
    )

    result = run_diagnostics()

    identifiers = [item[0] for item in result]
    assert "NetworkManager" in identifiers
    assert "kernel" in identifiers

    nm = next(item for item in result if item[0] == "NetworkManager")
    assert nm[1]["count"] == 2

def test_run_diagnostics_sorts_by_error_count_descending(mocker):
    """
    The subsystem with the most errors is listed first.
    """
    logs = [
        {"SYSLOG_IDENTIFIER": "kernel", "MESSAGE": "error 1"},
        {"SYSLOG_IDENTIFIER": "kernel", "MESSAGE": "error 2"},
        {"SYSLOG_IDENTIFIER": "kernel", "MESSAGE": "error 3"},
        {"SYSLOG_IDENTIFIER": "NetworkManager", "MESSAGE": "error 1"},
    ]
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value = logs
    )

    result = run_diagnostics()
    assert result[0][0] == "kernel"
    assert result[0][1]["count"] == 3

def test_run_diagnostics_strips_service_suffix(mocker):
    """
    .service suffix is stripped from _SYSTEMD_UNIT identifiers.
    """
    logs = [
        {"_SYSTEMD_UNIT": "gdm.service", "MESSAGE": "failed to start"},
    ]
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=logs
    )

    result = run_diagnostics()

    identifiers = [item[0] for item in result]
    assert "gdm" in identifiers
    assert "gdm.service" not in identifiers

def test_run_diagnostics_uses_fallback_identifier_chain(mocker):
    """
    Falls back to _SYSTEMD_UNIT, then _COMM, then 'Unknown Subsystem'
    when SYSLOG_IDENTIFIER is missing.
    """
    logs = [
        {"_SYSTEMD_UNIT": "bluetooth.service", "MESSAGE": "connection failed"},
        {"_COMM": "python3", "MESSAGE": "segfault"},
        {"MESSAGE": "mystery error"},
    ]
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=logs
    )

    result = run_diagnostics()

    identifiers = [item[0] for item in result]
    assert "bluetooth" in identifiers
    assert "python3" in identifiers
    assert "Unknown Subsystem" in identifiers

def test_run_diagnostics_table_renders_only_top_5(mocker, silence_output):
    """
    The function returns all culprits but the Rich table only displays
    the top 5. Verified by inspecting the Table object passed to console.print.
    """
    logs = [
        {"SYSLOG_IDENTIFIER": f"service-{i}", "MESSAGE": "error"}
        for i in range(10)
    ]
    mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=logs
    )

    result = run_diagnostics()

    # All 10 culprits are returned to the caller (for heal engine)
    assert len(result) == 10

    # But only 5 rows were added to the Rich table
    table_calls = [
        call for call in silence_output.print.call_args_list
        if call.args and isinstance(call.args[0], Table)
    ]
    assert len(table_calls) == 1
    assert table_calls[0].args[0].row_count == 5

def test_run_diagnostics_previous_boot_passes_flag(mocker):
    """
    When previous=True, get_structured_logs is called with previous=True.
    """
    mock_logs = mocker.patch(
        "prescient.intelligence.diagnose.get_structured_logs",
        return_value=[]
    )

    run_diagnostics(previous=True)

    mock_logs.assert_called_once_with(previous=True)

# Getting raw journalctl outputs
def test_get_raw_journalctl_output_returns_stdout(mocker):
    """
    Returns raw journalctl text output on success.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="Mar 24 01:15:00 kernel: error\n"
        )
    )

    result = get_raw_journalctl_output(lines=50)

    assert "kernel" in result

def test_get_raw_journalctl_output_uses_previous_flag(mocker):
    """
    Passes -b -1 when previous=True.
    """
    mock_run = mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="some output\n"
        )
    )

    get_raw_journalctl_output(lines=50, previous=True)

    cmd_used = mock_run.call_args[0][0]
    assert "-1" in cmd_used

def test_get_raw_journalctl_output_returns_error_string_on_failure(mocker):
    """
    Returns an error string (not an empty string or exception) on failure.
    """
    mocker.patch(
        "prescient.intelligence.diagnose.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "journalctl")
    )

    result = get_raw_journalctl_output()

    assert "Failed" in result
