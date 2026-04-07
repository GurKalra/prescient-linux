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

**2. No real subprocesses executed.** Every call to `subprocess.run` is replaced with a `MagicMock` configured to return the exact `stdout`, `returncode`, or exception the test scenario requires. No `dpkg`, `snapper`, `timeshift`, `mokutil`, or `journalctl` binary is ever invoked.

**3. No filesystem pollution.** Any test that needs to read or write a real file uses `pytest`'s native `tmp_path` fixture, which creates an isolated temporary directory that is automatically wiped after each test session. The host's `/var/lib/prescient`, `/etc/apt`, and `/boot` are never touched.

**4. No network calls.** Mirror health checks mock their `audit_all_mirrors` results entirely. No real HTTP HEAD requests or TCP connections are made during the test run.

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
│   └── test_mirror_checker.py      # Concurrent mirror health auditor
├── recovery/
│   └── test_snapshot.py            # Timeshift/Snapper snapshot guardrails
└── vanguard/
    ├── test_boot.py                 # /boot partition and kernel clutter audits
    ├── test_security.py             # Secure Boot + DKMS collision detection
    └── test_system.py               # Pre-flight checks and input sanitization
```

---

## Current Coverage

Phase 1 covers the five most safety-critical modules. These are:

- the engines that can VETO a transaction
- trigger a snapshot, or cause real damage if their logic is wrong.

### `tests/vanguard/test_boot.py`

**Module:** `prescient/vanguard/boot.py`

Validates the `/boot` partition health auditor. All `shutil.disk_usage` and `os.listdir` calls are mocked so no real disk reads occur.

**Key design validated:** The surgical trigger - the boot audit only wakes up for packages matching `kernel` or `bootloader` entries in `prescient.toml`. Normal app updates skip it entirely with zero overhead.

| Test                                                      | What it validates                                                                                                  |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `test_boot_space_safe`                                    | Returns `True` when `/boot` has more than 500 MB free                                                              |
| `test_boot_space_critical`                                | Returns `False` (VETO) when `/boot` is below the threshold                                                         |
| `test_boot_space_exactly_at_threshold`                    | Boundary condition: exactly 500 MB is considered safe                                                              |
| `test_boot_directory_missing_returns_safe`                | Fails open (`True`) when `/boot` does not exist as a separate partition - unified root systems must not be blocked |
| `test_boot_space_unexpected_exception_returns_safe`       | Any unexpected `OSError` also fails open                                                                           |
| `test_count_installed_kernels_multiple`                   | Correctly counts only `vmlinuz-*` files, ignoring `initrd`, `grub`, and `efi` entries                              |
| `test_count_installed_kernels_none`                       | Returns `0` when no kernel images are present                                                                      |
| `test_count_installed_kernels_boot_missing`               | Returns `0` gracefully when `/boot` is missing                                                                     |
| `test_analyze_boot_health_skips_non_boot_update`          | `htop`, `curl`, `vim` - neither `check_boot_space` nor `count_installed_kernels` is called                         |
| `test_analyze_boot_health_passes_on_safe_kernel_update`   | A kernel update with sufficient space passes the audit                                                             |
| `test_analyze_boot_health_veto_on_low_boot_space`         | A kernel update with critically low `/boot` space returns `False`                                                  |
| `test_analyze_boot_health_triggers_on_bootloader_package` | A `grub-efi-amd64` update also triggers the boot audit, not just `linux-image-*`                                   |

---

### `tests/vanguard/test_security.py`

**Module:** `prescient/vanguard/security.py`

Validates the Secure Boot and DKMS collision detector. Mocks `mokutil`, `dkms status`, and the `/dev/shm` RAM cache so no real hardware state is read.

**Key design validated:** The security engine never VETOs, all it does is warns and educates. The tests confirm it correctly triggers on the three risk categories (kernel, bootloader, drivers) and fast-passes everything else. The RAM cache is confirmed to prevent redundant `mokutil` calls.

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
| `test_analyze_security_risk_skips_boring_update`                       | `curl`, `vim`, `htop` (neither probe is called)                                                                                                         |
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

| Test                                                | What it validates                                                                                                                                                  |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_parse_and_sanitize_packages`                  | Accepts valid names (`htop`, `linux-image-6.8.0-45-generic`, `valid-package+1.2.3`) and drops shell injection attempts (`malicious-pkg; rm -rf /`, `broken\|pipe`) |
| `test_preflight_checks_pass_ubuntu`                 | Healthy Ubuntu system (dpkg clean, 50 GB free, mirrors alive) returns `True`                                                                                       |
| `test_preflight_checks_fail_on_locked_dpkg_ubuntu`  | Broken `dpkg` state returns `False` (VETO)                                                                                                                         |
| `test_preflight_checks_fail_on_low_disk_ubuntu`     | 500 MB free root partition returns `False` (VETO) as minimum is 2 GB                                                                                               |
| `test_preflight_checks_fail_on_dead_mirrors_ubuntu` | All APT mirrors unreachable returns `False` (VETO)                                                                                                                 |
| `test_preflight_checks_pass_arch`                   | Healthy Arch system (pacman present, no `db.lck`) returns `True`                                                                                                   |
| `test_preflight_checks_fail_on_locked_pacman_arch`  | Presence of `/var/lib/pacman/db.lck` returns `False` (VETO)                                                                                                        |
| `test_preflight_checks_fail_on_low_disk_arch`       | 500 MB free root partition on Arch also returns `False` (VETO)                                                                                                     |

---

### `tests/recovery/test_snapshot.py`

**Module:** `prescient/recovery/snapshot.py`

Validates the pre-transaction snapshot guardrails. All `subprocess.run`, `shutil.disk_usage`, and file I/O are mocked. The `tmp_path` fixture ensures state file reads and writes never touch the real `/var/lib/prescient`.

**Key design validated:** The guard chain:

provider check → disk space → cooldown → subprocess. This is tested as a strict sequence. Each guard short-circuits and returns `False` before the next stage is reached, and critically, before any real subprocess is ever called.

| Test                                                         | What it validates                                                                                   |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `test_check_disk_space_passes_when_sufficient`               | Returns `True` when root has 50 GB free (above 5 GB minimum)                                        |
| `test_check_disk_space_fails_when_low`                       | Returns `False` when only 3 GB free                                                                 |
| `test_check_disk_space_exactly_at_threshold`                 | Boundary: exactly 5 GB free passes (check is `< MIN_FREE_GB`, not `<=`)                             |
| `test_get_last_snapshot_state_returns_dict`                  | Correctly parses a valid JSON state file via `tmp_path`                                             |
| `test_get_last_snapshot_state_returns_empty_when_missing`    | Returns `{}` when the state file does not exist                                                     |
| `test_get_last_snapshot_state_returns_empty_on_corrupt_json` | Returns `{}` gracefully on malformed JSON (never crashes)                                           |
| `test_is_in_cooldown_returns_false_when_no_state`            | No state file = not in cooldown, allow snapshot                                                     |
| `test_is_in_cooldown_returns_true_when_recent`               | Snapshot taken 60 seconds ago = in cooldown (10-minute window)                                      |
| `test_is_in_cooldown_returns_false_when_expired`             | Snapshot taken 700 seconds ago = cooldown expired, allow new snapshot                               |
| `test_get_snapshot_provider_returns_snapper_first`           | Snapper is preferred over Timeshift when both are installed                                         |
| `test_get_snapshot_provider_returns_timeshift_as_fallback`   | Returns `"timeshift"` when only Timeshift is installed                                              |
| `test_get_snapshot_provider_returns_none_when_no_provider`   | Returns `None` when neither tool is installed                                                       |
| `test_trigger_snapshot_skips_when_no_provider`               | Returns `False` immediately - `check_disk_space` is never called if no provider exists              |
| `test_trigger_snapshot_skips_when_disk_space_low`            | Returns `False` - `subprocess.run` is never called if disk space fails                              |
| `test_trigger_snapshot_skips_when_in_cooldown`               | Returns `False` - `subprocess.run` is never called during cooldown                                  |
| `test_trigger_snapshot_succeeds_with_timeshift`              | Returns `True` and calls `save_snapshot_state` with the timestamp name parsed from Timeshift stdout |
| `test_trigger_snapshot_succeeds_with_snapper`                | Returns `True` and calls `save_snapshot_state` with the numeric ID parsed from Snapper stdout       |
| `test_trigger_snapshot_returns_false_on_timeout`             | Returns `False` when the snapshot tool hangs past the 120-second timeout                            |
| `test_trigger_snapshot_returns_false_on_proceess_error`      | Returns `False` when the snapshot tool exits with a non-zero code                                   |

---

### `tests/core/test_mirror_checker.py`

**Module:** `prescient/core/mirror_checker.py`

Validates the concurrent mirror pre-flight auditor. All file reads use `mock_open` and all network calls are mocked at the `audit_all_mirrors` level. The tests cover both APT (Ubuntu/Debian) and Pacman (Arch) parsing paths, and the `get_active_mirrors` router that picks between them.

**Key design validated:** Two fail-open behaviours that are - no mirrors configured at all, and a single dead PPA alongside a live mirror so that it is ensured that prescient never blocks a legitimate transaction due to an unconfigured or partially degraded mirror list. Note that `get_active_mirrors` checks for `pacman` before `dpkg`, so on a system with both binaries present, Pacman takes priority.

| Test                                                      | What it validates                                                                                         |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `test_get_apt_mirrors_extracts_urls`                      | Correctly parses a standard `sources.list` `deb` line and extracts the base URL                           |
| `test_get_apt_mirrors_ignores_comments_and_cdrom`         | Commented lines (`#`) and `cdrom:` entries are skipped                                                    |
| `test_get_apt_mirrors_supports_deb822_format`             | Modern `URIs:` format (DEB822 `.sources` files) is also parsed correctly                                  |
| `test_get_pacman_mirrors_extracts_urls`                   | Correctly parses a standard Arch `mirrorlist` `Server =` line                                             |
| `test_get_pacman_mirrors_ignores_commented_servers`       | Commented `# Server =` lines are skipped                                                                  |
| `test_get_pacman_mirrors_strips_path_variables`           | Only the base domain is returned                                                                          |
| `test_get_pacman_mirrors_returns_empty_if_file_missing`   | Returns an empty set gracefully when `/etc/pacman.d/mirrorlist` does not exist                            |
| `test_get_active_mirrors_routes_to_apt_on_ubuntu`         | On Ubuntu (dpkg present, pacman absent), routes to `get_apt_mirrors`                                      |
| `test_get_active_mirrors_routes_to_pacman_on_arch`        | On Arch (pacman present), routes to `get_pacman_mirrors`                                                  |
| `test_get_active_mirrors_returns_empty_if_no_pm`          | Returns empty set when neither `dpkg` nor `pacman` is found                                               |
| `test_run_mirror_preflight_passes_when_all_mirrors_alive` | Returns `True` when all mirrors respond with OK                                                           |
| `test_run_mirror_preflight_passes_with_one_dead_mirror`   | Returns `True` when at least one mirror is alive so that a single dead PPA does not block the transaction |
| `test_run_mirror_preflight_veto_when_all_mirrors_dead`    | Returns `False` (VETO) only when every mirror is unreachable                                              |
| `test_run_mirror_preflight_passes_when_no_mirrors_found`  | Returns `True` (fail open) when no mirrors are configured                                                 |

---

## Post-Hackathon Roadmap

Phase 1 covers the protective engines. The following modules are targeted for comprehensive testing after the hackathon:

- [x] **`tests/intelligence/test_diagnose.py`** - Mock raw `journalctl` JSON output to validate culprit grouping, the fallback identifier chain (`SYSLOG_IDENTIFIER` → `_SYSTEMD_UNIT` → `_COMM`), and the top-5 table truncation.
- [x] **`tests/intelligence/test_autoheal.py`** - Validate the `determine_fixes` decision tree: message-pattern matching (lock files, unmet dependencies), direct playbook lookup, systemd message scan, and the generic service restart fallback. Confirm no `shell=True` is present in any proposed command.
- [ ] **`tests/recovery/test_undo.py`** - Validate the full rollback safety gate: state file missing → filesystem fallback → CLI verification → filesystem verification → confirmation prompt → `execute_rollback`. Mock both `snapper rollback` and `timeshift --restore` success and failure paths, including the 300-second timeout.
- [ ] **`tests/core/test_cache.py`** - Validate the `/dev/shm` RAM cache TTL logic: fresh cache returns stored value, expired cache (>30 minutes) returns empty, corrupt JSON falls back gracefully, and `0o600` permissions are applied on write.
- [ ] **`tests/core/test_hooks.py`** - Mock `shutil.copy`, `os.chmod`, and `subprocess.run` to validate that APT and Pacman hook files are written to the correct paths with the correct content, and that `update-initramfs -u` / `mkinitcpio -P` are called exactly once each.
- [ ] **`tests/test_cli.py`** - Use `typer.testing.CliRunner` to validate all user-facing command routes: `predict` with and without stdin, `diagnose` with and without `--share`, `undo` abort and confirm paths, `update` with and without `--force`, and the `check_sudo` root privilege guard for each command that requires it.
