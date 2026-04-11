# Testing

> Prescient uses a fully-mocked, zero-I/O test suite built with `pytest` and `pytest-mock`. No root access is required, no real packages are modified, and no network requests are made during the test run.

---

## The Problem With Testing System-Level Tools

Prescient intercepts package managers, triggers system snapshots, reads kernel logs, and inspects `/boot`. A naive test suite that let these operations run for real could call `timeshift --create` on a developer's laptop, fill `/boot` with test kernels, or accidentally run `dpkg --configure -a` mid-session. This is not acceptable.

The solution is a **Strict Zero-I/O Testing Philosophy** enforced across every test module. Every path that touches real hardware, real processes, or real network connections is intercepted and replaced with a controlled mock before it executes.

---

## The Zero-I/O Guarantee

When you run the test suite, four guarantees hold unconditionally:

**1. No root access required.** Every function that would ordinarily need root. It checks `/boot`, reading `/var/lib/prescient`, calling `mokutil` (is mocked at the boundary). `pytest` runs entirely as a normal user.

**2. No real subprocesses executed.** Every call to `subprocess.run` is replaced with a `subprocess.CompletedProcess` or `MagicMock` configured to return the exact `stdout`, `returncode`, or exception the test scenario requires. No `dpkg`, `snapper`, `timeshift`, `mokutil`, or `journalctl` binary is ever invoked.

**3. No filesystem pollution.** Any test that needs to read or write a real file uses `pytest`'s native `tmp_path` fixture, which creates an isolated temporary directory that is automatically wiped after each test session. The host's `/var/lib/prescient`, `/etc/apt`, and `/boot` are never touched.

**4. No network calls.** Mirror health checks mock their `audit_all_mirrors` results entirely. OTA update checks mock `urllib.request.urlopen`. No real HTTP or TCP connections are made during the test run.

---

## Running the Tests

Install the package in editable mode with development dependencies before running:

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run the full suite with verbose output
pytest tests/ -v

# Run a specific module
pytest tests/vanguard/test_security.py -v

# Run a single test by name
pytest tests/vanguard/test_boot.py::test_analyze_boot_health_veto_on_low_boot_space -v
```

---

## Test Suite Structure

```
tests/
├── core/
│   ├── test_cache.py               # /dev/shm RAM cache TTL and permission logic
│   ├── test_mirror_checker.py      # Concurrent mirror health auditor
│   └── test_update_checker.py      # OTA version check and 24-hour cache logic
├── intelligence/
│   ├── test_autoheal.py            # Auto-heal decision tree and execution sequence
│   └── test_diagnose.py            # journalctl log parsing and culprit grouping
├── recovery/
│   ├── test_snapshot.py            # Timeshift/Snapper snapshot guardrails
│   └── test_undo.py                # Rollback state file, verification, and execution
├── vanguard/
│   ├── test_boot.py                # /boot partition and kernel clutter audits
│   ├── test_security.py            # Secure Boot + DKMS collision detection
│   └── test_system.py              # Pre-flight checks and input sanitization
└── test_cli.py                     # All user-facing CLI commands via CliRunner
```

---

## Current Coverage

### `tests/vanguard/test_boot.py`

**Module:** `prescient/vanguard/boot.py`

Validates the `/boot` partition health auditor. All `shutil.disk_usage` and `os.listdir` calls are mocked so no real disk reads occur.

**Key design validated:** The surgical trigger i.e the boot audit only wakes up for packages matching `kernel` or `bootloader` entries in `prescient.toml`. Normal app updates skip it entirely with zero overhead.

| Test                                                      | What it validates                                                                        |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `test_boot_space_safe`                                    | Returns `True` when `/boot` has more than 500 MB free                                    |
| `test_boot_space_critical`                                | Returns `False` (VETO) when `/boot` is below the threshold                               |
| `test_boot_space_exactly_at_threshold`                    | Boundary condition: exactly 500 MB is considered safe                                    |
| `test_boot_directory_missing_returns_safe`                | Fails open (`True`) when `/boot` does not exist as a separate partition                  |
| `test_boot_space_unexpected_exception_returns_safe`       | Any unexpected `OSError` also fails open                                                 |
| `test_count_installed_kernels_multiple`                   | Correctly counts only `vmlinuz-*` files, ignoring `initrd`, `grub`, and `efi` entries    |
| `test_count_installed_kernels_none`                       | Returns `0` when no kernel images are present                                            |
| `test_count_installed_kernels_boot_missing`               | Returns `0` gracefully when `/boot` is missing                                           |
| `test_analyze_boot_health_skips_non_boot_update`          | `htop`, `curl`, `vim` neither `check_boot_space` nor `count_installed_kernels` is called |
| `test_analyze_boot_health_passes_on_safe_kernel_update`   | A kernel update with sufficient space passes the audit                                   |
| `test_analyze_boot_health_veto_on_low_boot_space`         | A kernel update with critically low `/boot` space returns `False`                        |
| `test_analyze_boot_health_triggers_on_bootloader_package` | A `grub-efi-amd64` update also triggers the boot audit, not just `linux-image-*`         |

---

### `tests/vanguard/test_security.py`

**Module:** `prescient/vanguard/security.py`

Validates the Secure Boot and DKMS collision detector. Mocks `mokutil`, `dkms status`, and the `/dev/shm` RAM cache so no real hardware state is read.

**Key design validated:** The security engine never VETOs. It warns and educates. The tests confirm it correctly triggers on the three risk categories (kernel, bootloader, drivers) and fast-passes everything else. The RAM cache is confirmed to prevent redundant `mokutil` calls.

| Test                                                                   | What it validates                                                                                                                                       |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_secure_boot_returns_cached_value`                                | If `sb_enabled` is already in the RAM cache, `mokutil` is never called                                                                                  |
| `test_secure_boot_enabled_via_mokutil`                                 | Correctly parses `"SecureBoot enabled"` from `mokutil` stdout                                                                                           |
| `test_secure_boot_disabled_via_mokutil`                                | Correctly parses `"SecureBoot disabled"` from `mokutil` stdout                                                                                          |
| `test_secure_boot_mokutil_missing_returns_false`                       | If `mokutil` is not installed, fails open (permissive mode)                                                                                             |
| `test_secure_boot_mokutil_timeout_returns_false`                       | Any exception also fails open                                                                                                                           |
| `test_get_dkms_modules_returns_parsed_lines`                           | Correctly parses multi-line `dkms status` output into a list                                                                                            |
| `test_get_dkms_modules_returns_empty_when_none_installed`              | Returns empty list when `dkms status` has no output                                                                                                     |
| `test_get_dkms_modules_returns_empty_on_failure`                       | Returns empty list if `dkms` binary is not installed                                                                                                    |
| `test_analyze_security_risk_skips_boring_update`                       | `curl`, `vim`, `htop` neither probe is called                                                                                                           |
| `test_analyze_security_risk_kernel_update_secure_boot_off_no_dkms`     | Kernel update + Secure Boot disabled + no DKMS: safe                                                                                                    |
| `test_analyze_security_risk_kernel_update_secure_boot_on_no_dkms`      | Kernel update + Secure Boot enabled + no DKMS: safe (no unsigned modules to collide)                                                                    |
| `test_analyze_security_risk_collision_kernel_plus_dkms_secure_boot_on` | The critical collision path: Secure Boot ON + kernel update + active DKMS. Returns `True` (warns, does not VETO), but both probes must have been called |
| `test_analyze_security_risk_driver_update_triggers_audit`              | An `nvidia-driver-535` update triggers the full security audit                                                                                          |
| `test_analyze_security_risk_bootloader_update_triggers_audit`          | A `shim-signed` update triggers the security audit                                                                                                      |

---

### `tests/vanguard/test_system.py`

**Module:** `prescient/vanguard/system.py`

Validates the core pre-flight audit engine and the package name sanitizer. Tests are split across Ubuntu (dpkg) and Arch (pacman) paths.

**Key design validated:** The sanitizer is the security boundary between raw stdin from `apt`/`pacman` and any subprocess call. The injection tests confirm that characters outside `[a-zA-Z0-9\-_\.\+]` are dropped before any package name reaches a system command.

| Test                                                | What it validates                                                                                  |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `test_parse_and_sanitize_packages`                  | Accepts valid names and drops shell injection attempts (`malicious-pkg; rm -rf /`, `broken\|pipe`) |
| `test_preflight_checks_pass_ubuntu`                 | Healthy Ubuntu system (dpkg clean, 50 GB free, mirrors alive) returns `True`                       |
| `test_preflight_checks_fail_on_locked_dpkg_ubuntu`  | Broken `dpkg` state returns `False` (VETO)                                                         |
| `test_preflight_checks_fail_on_low_disk_ubuntu`     | 500 MB free root partition returns `False` (VETO) as minimum is 2 GB                               |
| `test_preflight_checks_fail_on_dead_mirrors_ubuntu` | All APT mirrors unreachable returns `False` (VETO)                                                 |
| `test_preflight_checks_pass_arch`                   | Healthy Arch system (pacman present, no `db.lck`) returns `True`                                   |
| `test_preflight_checks_fail_on_locked_pacman_arch`  | Presence of `/var/lib/pacman/db.lck` returns `False` (VETO)                                        |
| `test_preflight_checks_fail_on_low_disk_arch`       | 500 MB free root partition on Arch also returns `False` (VETO)                                     |

---

### `tests/recovery/test_snapshot.py`

**Module:** `prescient/recovery/snapshot.py`

Validates the pre-transaction snapshot guardrails. All `subprocess.run`, `shutil.disk_usage`, and file I/O are mocked. The `tmp_path` fixture ensures state file reads and writes never touch the real `/var/lib/prescient`.

**Key design validated:** The guard chain: provider check → disk space → cooldown → subprocess. Each guard short-circuits and returns `False` before the next stage is reached, and critically, before any real subprocess is ever called.

| Test                                                         | What it validates                                                                                   |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `test_check_disk_space_passes_when_sufficient`               | Returns `True` when root has 50 GB free (above 5 GB minimum)                                        |
| `test_check_disk_space_fails_when_low`                       | Returns `False` when only 3 GB free                                                                 |
| `test_check_disk_space_exactly_at_threshold`                 | Boundary: exactly 5 GB free passes (check is `< MIN_FREE_GB`, not `<=`)                             |
| `test_get_last_snapshot_state_returns_dict`                  | Correctly parses a valid JSON state file via `tmp_path`                                             |
| `test_get_last_snapshot_state_returns_empty_when_missing`    | Returns `{}` when the state file does not exist                                                     |
| `test_get_last_snapshot_state_returns_empty_on_corrupt_json` | Returns `{}` gracefully on malformed JSON                                                           |
| `test_is_in_cooldown_returns_false_when_no_state`            | No state file = not in cooldown, allow snapshot                                                     |
| `test_is_in_cooldown_returns_true_when_recent`               | Snapshot taken 60 seconds ago = in cooldown (10-minute window)                                      |
| `test_is_in_cooldown_returns_false_when_expired`             | Snapshot taken 700 seconds ago = cooldown expired                                                   |
| `test_get_snapshot_provider_returns_snapper_first`           | Snapper is preferred over Timeshift when both are installed                                         |
| `test_get_snapshot_provider_returns_timeshift_as_fallback`   | Returns `"timeshift"` when only Timeshift is installed                                              |
| `test_get_snapshot_provider_returns_none_when_no_provider`   | Returns `None` when neither tool is installed                                                       |
| `test_trigger_snapshot_skips_when_no_provider`               | Returns `False` immediately. `check_disk_space` is never called if no provider exists               |
| `test_trigger_snapshot_skips_when_disk_space_low`            | Returns `False`. `subprocess.run` is never called if disk space fails                               |
| `test_trigger_snapshot_skips_when_in_cooldown`               | Returns `False`. `subprocess.run` is never called during cooldown                                   |
| `test_trigger_snapshot_succeeds_with_timeshift`              | Returns `True` and calls `save_snapshot_state` with the timestamp name parsed from Timeshift stdout |
| `test_trigger_snapshot_succeeds_with_snapper`                | Returns `True` and calls `save_snapshot_state` with the numeric ID parsed from Snapper stdout       |
| `test_trigger_snapshot_returns_false_on_timeout`             | Returns `False` when the snapshot tool hangs past the 120-second timeout                            |
| `test_trigger_snapshot_returns_false_on_proceess_error`      | Returns `False` when the snapshot tool exits with a non-zero code                                   |

---

### `tests/recovery/test_undo.py`

**Module:** `prescient/recovery/undo.py`

Validates the atomic rollback engine. The `_fake_path` helper remaps all absolute system paths (`/etc/timeshift`, `/.snapshots`) to `tmp_path` equivalents using prefix matching, so filesystem scan tests never touch real system directories.

**Key design validated:** The two-stage snapshot verification sequence, CLI check first, filesystem fallback second. This is specifically designed for the chroot rescue context where D-Bus is unavailable and CLI tools fail. Both stages are tested for Timeshift and Snapper independently.

| Test                                                              | What it validates                                                                       |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `test_get_last_snapshot_returns_state`                            | Returns parsed JSON dict when state file exists and is valid                            |
| `test_get_last_snapshot_returns_none_when_missing`                | Returns `None` when state file does not exist                                           |
| `test_get_last_snapshot_returns_none_on_corrupt_json`             | Returns `None` gracefully on malformed JSON                                             |
| `test_get_latest_system_snapshot_returns_latest_timeshift`        | Finds the most recent Timeshift snapshot via filesystem scan (sorted alphabetically)    |
| `test_get_latest_system_snapshot_parses_timestamp`                | Correctly parses snapshot directory name as a UNIX timestamp                            |
| `test_get_latest_system_snapshot_falls_back_to_snapper`           | Falls back to Snapper scan when no Timeshift config exists                              |
| `test_get_latest_system_snapshot_returns_none_when_nothing_found` | Returns `None` when neither tool has snapshots                                          |
| `test_verify_snapshot_returns_false_for_empty_state`              | Returns `False` immediately when provider or snapshot name is missing                   |
| `test_verify_snapshot_timeshift_cli_success`                      | Returns `True` when `timeshift --list` output contains the snapshot name                |
| `test_verify_snapshot_snapper_cli_success`                        | Returns `True` when `snapper list` output contains the snapshot ID                      |
| `test_verify_snapshot_cli_fails_falls_back_to_filesystem`         | Falls back to filesystem check when CLI raises (e.g. D-Bus unavailable in chroot)       |
| `test_verify_snapshot_snapper_filesystem_fallback`                | Falls back to `/.snapshots/<id>/snapshot` path check for Snapper                        |
| `test_verify_snapshot_returns_false_when_both_checks_fail`        | Returns `False` when both CLI and filesystem verification fail                          |
| `test_execute_rollback_snapper_success`                           | Returns `True` and calls `snapper rollback <id>` with correct arguments                 |
| `test_execute_rollback_timeshift_success`                         | Returns `True` and calls `timeshift --restore --snapshot <name>` with correct arguments |
| `test_execute_rollback_returns_false_on_timeout`                  | Returns `False` when rollback tool hangs past 300-second timeout                        |
| `test_execute_rollback_returns_false_on_process_error`            | Returns `False` when rollback command exits with non-zero code                          |
| `test_execute_rollback_uses_300s_timeout`                         | Confirms the 300-second timeout is explicitly passed to `subprocess.run`                |
| `test_execute_rollback_returns_false_for_unknown_provider`        | Returns `False` cleanly when provider is not `snapper` or `timeshift`                   |

---

### `tests/core/test_mirror_checker.py`

**Module:** `prescient/core/mirror_checker.py`

Validates the concurrent mirror pre-flight auditor. All file reads use `mock_open` and all network calls are mocked at the `audit_all_mirrors` level. The tests cover both APT (Ubuntu/Debian) and Pacman (Arch) parsing paths, and the `get_active_mirrors` router that picks between them.

**Key design validated:** Two fail-open behaviours, no mirrors configured at all, and a single dead PPA alongside a live mirror to ensure prescient never blocks a legitimate transaction due to an unconfigured or partially degraded mirror list.

| Test                                                      | What it validates                                                                  |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `test_get_apt_mirrors_extracts_urls`                      | Correctly parses a standard `sources.list` `deb` line and extracts the base URL    |
| `test_get_apt_mirrors_ignores_comments_and_cdrom`         | Commented lines (`#`) and `cdrom:` entries are skipped                             |
| `test_get_apt_mirrors_supports_deb822_format`             | Modern `URIs:` format (DEB822 `.sources` files) is also parsed correctly           |
| `test_get_pacman_mirrors_extracts_urls`                   | Correctly parses a standard Arch `mirrorlist` `Server =` line                      |
| `test_get_pacman_mirrors_ignores_commented_servers`       | Commented `# Server =` lines are skipped                                           |
| `test_get_pacman_mirrors_strips_path_variables`           | Only the base domain is returned, not `$repo/$arch` path variables                 |
| `test_get_pacman_mirrors_returns_empty_if_file_missing`   | Returns an empty set gracefully when `/etc/pacman.d/mirrorlist` does not exist     |
| `test_get_active_mirrors_routes_to_apt_on_ubuntu`         | On Ubuntu (dpkg present, pacman absent), routes to `get_apt_mirrors`               |
| `test_get_active_mirrors_routes_to_pacman_on_arch`        | On Arch (pacman present), routes to `get_pacman_mirrors`                           |
| `test_get_active_mirrors_returns_empty_if_no_pm`          | Returns empty set when neither `dpkg` nor `pacman` is found                        |
| `test_run_mirror_preflight_passes_when_all_mirrors_alive` | Returns `True` when all mirrors respond with OK                                    |
| `test_run_mirror_preflight_passes_with_one_dead_mirror`   | Returns `True` when at least one mirror is alive. A single dead PPA does not block |
| `test_run_mirror_preflight_veto_when_all_mirrors_dead`    | Returns `False` (VETO) only when every mirror is unreachable                       |
| `test_run_mirror_preflight_passes_when_no_mirrors_found`  | Returns `True` (fail open) when no mirrors are configured                          |

---

### `tests/core/test_cache.py`

**Module:** `prescient/core/cache.py`

Validates the `/dev/shm` RAM cache used to persist the Secure Boot status between `prescient predict` invocations. All file I/O uses `tmp_path`. The `write_text` failure test uses a `MagicMock` as `CACHE_FILE` to avoid Python 3.12's read-only `PosixPath` slot restriction.

**Key design validated:** The cache is the performance guarantee that `mokutil` is only called once per boot session rather than on every `apt upgrade`. The TTL boundary test uses a frozen clock (`FROZEN_NOW`) to eliminate time drift flakiness.

| Test                                                        | What it validates                                                                                                      |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `test_get_cached_state_returns_empty_when_file_missing`     | Returns `{}` when the cache file does not exist                                                                        |
| `test_get_cached_state_returns_data_when_fresh`             | Returns parsed data when file exists and is within the 1800-second TTL                                                 |
| `test_get_cached_state_returns_empty_when_expired`          | Returns `{}` when the file is older than 1800 seconds                                                                  |
| `test_get_cached_state_returns_empty_on_corrupt_json`       | Returns `{}` gracefully on malformed JSON                                                                              |
| `test_get_cached_state_returns_empty_at_exact_ttl_boundary` | Boundary: exactly 1800 seconds old is expired (strict `<`, not `<=`)                                                   |
| `test_set_cached_state_writes_data_to_file`                 | Writes new state as valid JSON                                                                                         |
| `test_set_cached_state_merges_with_existing_cache`          | Merges new keys with existing cache, it does not overwrite unrelated keys                                              |
| `test_set_cached_state_overwrites_existing_key`             | Latest value wins when the same key is set twice                                                                       |
| `test_set_cached_state_applies_0o600_permissions`           | Sets `0o600` permissions so only root can read/write the cache                                                         |
| `test_set_cached_state_fails_silently_on_write_error`       | Does not raise when `/dev/shm` write fails. It uses `MagicMock` as `CACHE_FILE` to avoid Python 3.12 slot restrictions |

---

### `tests/core/test_update_checker.py`

**Module:** `prescient/core/update_checker.py`

Validates the OTA version checker and its 24-hour cache. All `urllib.request.urlopen` calls are mocked with a correctly configured context manager mock. The `Path` chaining issue (`Path(__file__).resolve().parent...parent / "pyproject.toml"`) is handled via explicit `__truediv__` patching through helper functions. All time-sensitive tests use a frozen clock (`FROZEN_NOW = 1_000_000_000.0`).

**Key design validated:** The `v` prefix normalisation regression. `v0.12.0` and `0.12.0` must compare as equal. The 24-hour cache boundary is verified with a frozen clock to eliminate drift.

| Test                                                                          | What it validates                                                                                     |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `test_get_local_version_reads_from_pyproject_toml`                            | Returns version parsed directly from `pyproject.toml`. The primary path, bypasses `importlib` caching |
| `test_get_local_version_strips_whitespace`                                    | Strips leading/trailing whitespace from the parsed version string                                     |
| `test_get_local_version_falls_back_to_importlib_when_pyproject_missing`       | Falls back to `importlib.metadata` when `pyproject.toml` does not exist                               |
| `test_get_local_version_falls_back_to_importlib_when_no_version_in_pyproject` | Falls back when `pyproject.toml` exists but has no `version` field                                    |
| `test_get_local_version_returns_unknown_when_both_sources_fail`               | Returns `"unknown"` when both `pyproject.toml` and `importlib` fail                                   |
| `test_get_local_version_falls_back_gracefully_on_read_exception`              | Falls back to `importlib` when `pyproject.toml` read raises `OSError`                                 |
| `test_check_for_updates_returns_cached_result_within_24h`                     | Returns cached `is_available` without a network request when last checked < 24h ago                   |
| `test_check_for_updates_skips_cache_when_force_network`                       | `force_network=True` bypasses the cache even if it is fresh                                           |
| `test_check_for_updates_returns_true_when_remote_is_newer`                    | Returns `True` when remote version differs from local                                                 |
| `test_check_for_updates_returns_false_when_already_up_to_date`                | Returns `False` when local and remote versions match                                                  |
| `test_check_for_updates_normalises_v_prefix`                                  | `v0.12.0` and `0.12.0` are treated as equal                                                           |
| `test_check_for_updates_returns_false_when_local_version_unknown`             | Returns `False` immediately without a network request when local version is `"unknown"`               |
| `test_check_for_updates_returns_false_on_network_failure`                     | Returns `False` silently when the network request fails                                               |
| `test_check_for_updates_returns_false_when_remote_has_no_version`             | Returns `False` when remote `pyproject.toml` has no version field                                     |
| `test_check_for_updates_saves_result_to_cache_after_network_check`            | Calls `save_update_cache` with a float timestamp and boolean result after every network check         |
| `test_check_for_updates_cache_boundary_exactly_24h`                           | Boundary: exactly 86400 seconds old is expired . It is verified with frozen clock                     |

---

### `tests/intelligence/test_diagnose.py`

**Module:** `prescient/intelligence/diagnose.py`

Validates the `journalctl` log parser and culprit grouping engine. All `subprocess.run` calls are mocked with `subprocess.CompletedProcess`. The `silence_output` fixture returns the console mock so the table row count can be inspected directly.

**Key design validated:** The four-level identifier fallback chain (`SYSLOG_IDENTIFIER` → `_SYSTEMD_UNIT` → `_COMM` → `"Unknown Subsystem"`), the top-5 display cap (verified by inspecting the Rich `Table` object's `row_count`), and the `--previous` flag propagation through all three functions.

| Test                                                             | What it validates                                                      |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `test_get_structured_logs_parses_current_boot`                   | Passes `-b 0` to `journalctl` when `previous=False`                    |
| `test_get_structured_logs_passes_previous_flag`                  | Passes `-b -1` to `journalctl` when `previous=True`                    |
| `test_get_structured_logs_skips_invalid_json_lines`              | Malformed JSON lines are silently skipped but valid lines still parsed |
| `test_get_structured_logs_returns_empty_on_journalctl_failure`   | Returns `[]` when `journalctl` exits with non-zero code                |
| `test_get_structured_logs_returns_empty_when_journalctl_missing` | Returns `[]` when `journalctl` is not installed                        |
| `test_get_structured_logs_returns_empty_on_no_output`            | Returns `[]` when `journalctl` runs but produces no log lines          |
| `test_run_diagnostics_returns_empty_when_no_logs`                | Returns `[]` and prints clean message when no errors found             |
| `test_run_diagnostics_groups_errors_by_identifier`               | Multiple entries from the same subsystem are grouped and counted       |
| `test_run_diagnostics_sorts_by_error_count_descending`           | The subsystem with the most errors is listed first                     |
| `test_run_diagnostics_strips_service_suffix`                     | `.service` suffix is stripped from `_SYSTEMD_UNIT` identifiers         |
| `test_run_diagnostics_uses_fallback_identifier_chain`            | All four fallback levels verified in a single test                     |
| `test_run_diagnostics_table_renders_only_top_5`                  | Returns all 10 culprits but Rich table `row_count == 5`                |
| `test_run_diagnostics_previous_boot_passes_flag`                 | `previous=True` is forwarded to `get_structured_logs`                  |
| `test_get_raw_journalctl_output_returns_stdout`                  | Returns raw `journalctl` text output on success                        |
| `test_get_raw_journalctl_output_uses_previous_flag`              | Passes `-b -1` when `previous=True`                                    |
| `test_get_raw_journalctl_output_returns_error_string_on_failure` | Returns an error string (not an exception) on failure                  |

---

### `tests/intelligence/test_autoheal.py`

**Module:** `prescient/intelligence/autoheal.py`

Validates the auto-heal decision tree and interactive execution sequence. `os.geteuid` and `typer.confirm` are mocked so tests never require root or block on user input.

**Key design validated:** The four-level decision tree priority order (message pattern → direct playbook → systemd message scan → generic fallback), the top-3 culprit limit, deduplication, and the safety guarantee that no command uses `shell=True` (verified by running `shlex.split()` on every proposed command).

| Test                                                        | What it validates                                                                           |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `test_determine_fixes_detects_apt_deadlock`                 | `"could not get lock"` in message maps to the four-command APT deadlock fix                 |
| `test_determine_fixes_detects_frontend_lock`                | `"frontend lock"` also triggers the deadlock fix                                            |
| `test_determine_fixes_detects_unmet_dependencies`           | `"unmet dependencies"` maps to `apt install -f -y`                                          |
| `test_determine_fixes_uses_direct_playbook_lookup`          | A subsystem directly in `HEAL_PLAYBOOK` gets its mapped commands                            |
| `test_determine_fixes_playbook_covers_all_known_services`   | Loops over every `HEAL_PLAYBOOK` entry. It automatically covers new entries added in future |
| `test_determine_fixes_catches_service_via_systemd_message`  | `systemd` identifier + message mentioning `NetworkManager` → correct playbook used          |
| `test_determine_fixes_generic_fallback_for_unknown_service` | Unknown services get `systemctl restart <service>`                                          |
| `test_determine_fixes_skips_kernel_in_fallback`             | `"kernel"` is excluded from the generic restart fallback                                    |
| `test_determine_fixes_skips_unknown_subsystem_in_fallback`  | `"Unknown Subsystem"` is excluded from the generic restart fallback                         |
| `test_determine_fixes_only_processes_top_3`                 | 4th and 5th culprits are ignored                                                            |
| `test_determine_fixes_deduplicates_same_identifier`         | Same identifier appearing twice in top 3 is only processed once                             |
| `test_determine_fixes_no_shell_true_in_commands`            | Every proposed command passes `shlex.split()`                                               |
| `test_run_autoheal_sequence_aborts_without_root`            | Exits immediately when not running as root. The confirm prompt never shown                  |
| `test_run_autoheal_sequence_aborts_with_empty_culprits`     | Exits immediately when culprits list is empty                                               |
| `test_run_autoheal_sequence_aborts_when_user_declines`      | No `subprocess.run` calls when user answers N                                               |
| `test_run_autoheal_sequence_executes_on_confirm`            | `subprocess.run` called with correct command when user answers Y                            |
| `test_run_autoheal_sequence_continues_on_failed_command`    | A failed command does not abort the remaining fixes. All 4 deadlock commands run            |
| `test_run_autoheal_sequence_skips_when_no_fixes_mapped`     | Confirm prompt never shown when `determine_fixes` returns empty                             |

---

### `tests/test_cli.py`

**Module:** `prescient/cli.py`

Validates all user-facing CLI commands using `typer.testing.CliRunner`. Two `autouse` fixtures apply globally: `silence_output` mocks logger and console, and `skip_ota_check` suppresses the `app.callback()` network request that would otherwise fire before every command.

**Key design validated:** Every command's root privilege guard (`check_sudo`), the `predict` VETO exit code, the `auto_snapshot` config flag, the `diagnose --previous --share` flag combination, the `undo` confirmation gate, the `update --force` bypass, and the `uninstall` two-file removal covering both APT and Pacman hook paths.

| Test                                                   | What it validates                                                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `test_check_sudo_strict_exits_without_root`            | `strict=True` exits with code 1 when not root                                                           |
| `test_check_sudo_non_strict_continues_without_root`    | `strict=False` prints a hint but does not exit                                                          |
| `test_check_sudo_strict_passes_as_root`                | `strict=True` does not exit when running as root                                                        |
| `test_predict_veto_on_failed_preflight`                | Exits with code 1 when `run_preflight_checks` returns `False`                                           |
| `test_predict_passes_on_healthy_system_no_stdin`       | Exits with code 0 when preflight passes and no stdin is provided                                        |
| `test_predict_triggers_snapshot_on_scary_package`      | Calls `trigger_snapshot` when blast radius returns high-risk                                            |
| `test_predict_skips_snapshot_when_auto_snap_disabled`  | Does not call `trigger_snapshot` when `auto_snapshot = false` in config                                 |
| `test_predict_skips_probes_when_no_input`              | `parse_and_sanitize_packages` is never called when no stdin is provided                                 |
| `test_diagnose_runs_without_flags`                     | Basic `diagnose` invocation exits with code 0                                                           |
| `test_diagnose_previous_flag_passed_to_engine`         | `--previous` is forwarded to `run_diagnostics(previous=True)`                                           |
| `test_diagnose_share_calls_termbin`                    | `--share` triggers `export_to_termbin`                                                                  |
| `test_diagnose_share_saves_locally_on_termbin_failure` | Falls back to local file save when termbin returns `None`                                               |
| `test_diagnose_previous_and_share_combined`            | Both flags can be combined freely                                                                       |
| `test_undo_exits_without_root`                         | Exits with code 1 when not root                                                                         |
| `test_undo_exits_cleanly_when_no_snapshot`             | Exits with code 0 when no snapshot exists                                                               |
| `test_undo_aborts_when_snapshot_not_verified`          | Exits with code 1 when snapshot is not found on disk                                                    |
| `test_undo_aborts_at_user_confirmation`                | `execute_rollback` is never called when user answers N                                                  |
| `test_undo_executes_rollback_on_confirm`               | `execute_rollback` called once when user confirms                                                       |
| `test_undo_exits_with_error_on_failed_rollback`        | Exits with code 1 when `execute_rollback` returns `False`                                               |
| `test_update_exits_without_root`                       | Exits with code 1 when not root                                                                         |
| `test_update_exits_cleanly_when_already_up_to_date`    | Exits with code 0 and skips `git pull` when already on latest                                           |
| `test_update_force_bypasses_version_check`             | `--force` skips version check and calls `subprocess.run` (driven by real `tmp_path` filesystem)         |
| `test_update_exits_when_install_dir_missing`           | Exits with code 1 when `~/.prescient/.git` is missing                                                   |
| `test_heal_exits_without_root`                         | Exits with code 1 when not root                                                                         |
| `test_heal_runs_diagnose_then_autoheal`                | Calls `run_diagnostics` then `run_autoheal_sequence` in order                                           |
| `test_uninstall_exits_without_root`                    | Exits with code 1 when not root                                                                         |
| `test_uninstall_aborts_at_confirmation`                | Neither `os.remove` nor `shutil.rmtree` called when user answers N                                      |
| `test_uninstall_removes_files_on_confirm`              | `os.remove` called for both APT hook and Pacman hook paths (`shutil.rmtree` mocked as safety guardrail) |
