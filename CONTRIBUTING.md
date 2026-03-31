# Contributing to Prescient

First off, thank you for taking the time to contribute. Prescient is a solo FOSS project built for real Linux users, and every bug report, fix, and idea makes it more reliable for everyone.

This document covers everything you need to get a working dev environment, understand the codebase layout, and submit changes that will actually get merged.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Before You Start](#before-you-start)
- [Project Structure](#project-structure)
- [Setting Up a Dev Environment](#setting-up-a-dev-environment)
- [The North Star Philosophy](#the-north-star-philosophy)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting a Pull Request](#submitting-a-pull-request)
- [Coding Standards](#coding-standards)
- [Testing Your Changes](#testing-your-changes)
- [Areas That Need Help](#areas-that-need-help)

---

## Code of Conduct

Be respectful. Prescient is built by and for the Linux community. Constructive criticism is welcome personal attacks are not :(. Issues and PRs that are hostile will be closed without comment.

---

## Before You Start

- Check the [open issues](https://github.com/GurKalra/prescient-linux/issues) before filing a new one (your bug or idea may already be tracked).
- For large features or architectural changes, **open an issue first** and discuss it before writing code. This prevents wasted effort if the direction doesn't fit the project.
- For small fixes (typos, doc corrections, obvious bugs), go ahead and open a PR directly.

---

## Project Structure

```
prescient-linux/
├── .gitignore
├── CONTRIBUTING.md                 # Guide for contributing and manual testing
├── install.sh                      # One-command bootstrap script
├── LICENSE
├── Makefile                        # Symlink installer (used by install.sh)
├── prescient.toml                  # Extensible rules schema (triggers, config, cache)
├── pyproject.toml                  # Package metadata and dependencies
├── README.md                       # Project overview and architecture
├── TESTING.md                      # Zero-I/O testing philosophy and instructions
├── docs/
│   └── commands/                   # One .md file per CLI command (the TUI reads these)
│       ├── diagnose.md
│       ├── heal.md
│       ├── install-hooks.md
│       ├── predict.md
│       ├── rescue.md
│       ├── tui.md
│       ├── undo.md
│       ├── uninstall.md
│       └── update.md
├── src/
│   └── prescient/
│       ├── __init__.py
│       ├── cli.py                  # Typer app - all command entry points
│       ├── config.py               # TOML config loader, saver, and hot-reloader
│       ├── core/
│       │   ├── __init__.py
│       │   ├── cache.py            # RAM-backed session cache (/dev/shm)
│       │   ├── hooks.py            # install-hooks logic (APT + Pacman + initramfs)
│       │   ├── logger.py           # Secure file logger (root vs user-space)
│       │   ├── mirror_checker.py   # Concurrent APT/Pacman mirror health auditor
│       │   ├── update_checker.py   # OTA version check against GitHub
│       │   └── utils.py            # Shared utilities (package manager detection)
│       ├── initramfs/
│       │   ├── prescient-arch-hook     # Arch mkinitcpio hook
│       │   ├── prescient-rescue.sh     # POSIX rescue script (embedded in initramfs)
│       │   └── prescient-ubuntu-hook   # Ubuntu initramfs-tools hook
│       ├── intelligence/
│       │   ├── __init__.py
│       │   ├── autoheal.py         # Remediation playbook and execution engine
│       │   ├── diagnose.py         # journalctl log parser and culprit ranker
│       │   ├── heuristic.py        # Dynamic tripwire scanner and threat learner
│       │   └── network.py          # termbin.com TCP socket exporter
│       ├── recovery/
│       │   ├── __init__.py
│       │   ├── snapshot.py         # Timeshift/Snapper snapshot trigger + state
│       │   └── undo.py             # Atomic rollback engine
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py              # Textual TUI application and screen logic
│       │   └── widgets.py          # DuneWave animation widget
│       └── vanguard/
│           ├── __init__.py
│           ├── boot.py             # /boot partition and kernel clutter audits
│           ├── security.py         # Secure Boot + DKMS collision detection
│           └── system.py           # Pre-flight checks, blast radius assessment
└── tests/                          # 100% Mocked Zero-I/O test suite
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   └── test_mirror_checker.py  # Tests concurrent network health pings
    ├── recovery/
    │   ├── __init__.py
    │   └── test_snapshot.py        # Tests snapshot guardrails and disk space logic
    └── vanguard/
        ├── __init__.py
        ├── test_boot.py            # Tests /boot space saturation logic
        ├── test_security.py        # Tests DKMS and Secure Boot VETO matrices
        └── test_system.py          # Tests pre-flight system state constraints
```

---

## Setting Up a Dev Environment

Prescient requires **Python 3.11+**, `git`, and `make`. You also need a Debian/Ubuntu or Arch Linux system to test hook installation (it will not work on macOS or Windows).

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/prescient-linux.git
cd prescient-linux

# 2. Create and activate an isolated virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install in editable mode so your changes take effect immediately
pip install -e .

# 4. Verify the install
prescient --help
```

> The `prescient` command is now wired to your local source. Any change you make to a `.py` file is live immediately. There is no reinstall needed.

For TUI development specifically, your terminal emulator must support at least 80×24 characters and a 256-color palette for the Gruvbox theme to render correctly.

---

## The North Star Philosophy

Every contribution should be measured against these four principles. They are not optional guidelines. Call them the design constraints of the project.

1. **Low Latency** - The predict engine intercepts every `apt upgrade`. If your change adds blocking I/O or a slow subprocess call to the hot path, it needs a timeout and a fast-fail fallback. No exceptions.
2. **Low False Positives** - Prescient should only raise alarms when something is genuinely threatening. A veto that blocks a safe `curl` update is worse than no veto at all.
3. **Clear Explanations** - Every error, warning, and veto must tell the user exactly what went wrong and what command to run next. No cryptic codes, no silent failures.
4. **Reliability > Feature Count** - A half-broken rollback is worse than no rollback. Do not add recovery features unless they are fully functional from a dead, unbootable state.

---

## How to Contribute

### Reporting Bugs

Open a [GitHub Issue](https://github.com/GurKalra/prescient-linux/issues/new) and include:

- Your OS and version (`lsb_release -a` or `cat /etc/os-release`)
- Your Python version (`python3 --version`)
- The exact command you ran
- The full terminal output (use `prescient diagnose --share` if the system is unstable and paste the URL)
- The contents of `/var/log/prescient.log` or `/tmp/prescient-user.log` if relevant

The more specific you are, the faster the fix.

### Suggesting Features

Open a [GitHub Issue](https://github.com/GurKalra/prescient-linux/issues/new) with the `enhancement`/`feature` label. Describe:

- The problem you are trying to solve (not just the feature itself)
- How it fits the North Star philosophy above
- Whether it affects the hot path (`predict`) or is a standalone command

### Submitting a Pull Request

```bash
# 1. Create a focused branch - one concern per branch
git checkout -b fix/boot-space-false-positive
# or
git checkout -b feat/pacman-mirror-checker

# 2. Make your changes

# 3. Test manually (see Testing section below)

# 4. Commit with a clear message
git commit -m "fix(boot): skip /boot check when partition is unified with root"

# 5. Push and open a PR against the main branch
git push origin fix/boot-space-false-positive
```

**PR checklist before submitting:**

- [ ] Tested manually on a real Linux system (VM is fine)
- [ ] No `shell=True` in any new `subprocess` call
- [ ] New user-facing output uses `rich` formatting, not bare `print()`
- [ ] New log lines go through `logger`, not `console` or `print()`
- [ ] Docs updated if you added or changed a command's behavior (edit the relevant file in `docs/commands/`)
- [ ] `prescient.toml` schema is unchanged unless the PR specifically extends it

---

## Coding Standards

**No `shell=True` ever.** All subprocess calls must use list-form arguments and `shlex.split()` where dynamic input is involved. This is a hard security requirement, not a style preference.

```python
# Correct
subprocess.run(["systemctl", "restart", service_name], check=True)

# Never do this
subprocess.run(f"systemctl restart {service_name}", shell=True)
```

**All timeouts must be explicit.** Any subprocess that talks to a package manager, network, or backup provider must have a timeout. Prescient runs inside `apt`. Remember a hung subprocess hangs the entire terminal.

**User-facing output goes through `rich` + `console`.** Raw `print()` calls are only acceptable inside `prescient-rescue.sh` (which is a POSIX shell script and has no access to Python).

**Logging goes through `logger`.** Use `logger.info()`, `logger.warning()`, and `logger.error()` for all background events. The logger writes to `/var/log/prescient.log` (root) or `/tmp/prescient-user.log` (user) automatically. Never log sensitive user data or full file paths from user input without sanitizing them first.

**Input sanitization is mandatory.** Any package name or path received from stdin or a subprocess must be validated against the strict regex (`^[a-zA-Z0-9\-_\.\+]+$`) before being passed to any system command. See `parse_and_sanitize_packages()` in `system.py` for the reference implementation.

**Style:** Follow the existing code style. No external linters are enforced yet, but keep line length reasonable, use descriptive variable names, and add a docstring to every new function.

---

## Testing Your Changes

Prescient has no automated test suite yet. All testing is currently manual. Here is how to test the most critical paths:

**Testing `predict` (the hot path):**

```bash
# Simulate an APT hook call with a fake package list
echo -e "VERSION 3\n\n/var/cache/apt/archives/linux-image-6.8.0-45-generic_6.8.0-45.45_amd64.deb" | sudo prescient predict
```

**Testing `diagnose`:**

```bash
# Run on any system - reads the live journal
prescient diagnose

# Test the share flag (requires internet)
prescient diagnose --share
```

**Testing `heal`:**

```bash
# Best tested on a VM where you can intentionally stop a service first
sudo systemctl stop NetworkManager
sudo prescient heal
```

**Testing `undo`:**

```bash
# Requires timeshift or snapper to be installed and a snapshot to exist
sudo prescient undo
```

**Testing the TUI:**

```bash
# Run without hooks installed to see the onboarding screen
prescient tui
```

**Testing hook installation (use a VM):**

```bash
sudo prescient install-hooks
# Then verify the hook file exists:
cat /etc/apt/apt.conf.d/99prescient-guardian
```

> Always test destructive operations (`undo`, `uninstall`, hook installation) inside a **virtual machine** first. A VM snapshot before testing is strongly recommended.

---

## Areas That Need Help

These are the highest-priority open contributions that would have real impact:

- **`pacman` mirror checker** - `mirror_checker.py` currently only parses APT sources. A parallel implementation for `/etc/pacman.d/mirrorlist` is needed.
- **Automated test suite** — Even a basic `pytest` suite that mocks `subprocess` calls for the `predict` pipeline would be a huge step forward.
- **`--previous-boot` flag for `diagnose`** - ([Issue #94](https://github.com/GurKalra/prescient-linux/issues/94)) — Currently `diagnose` only reads `-b 0`. If a user hard-reboots after a crash, the crash logs are in the previous boot and `diagnose` misses them entirely. Adding a `--previous-boot` flag to switch to `journalctl -b -1` is a small, self-contained change with a real impact.
- **LUKS support in `prescient-rescue`** - The rescue script currently skips encrypted partitions. Adding a `cryptsetup open` prompt before the block device probe would make rescue viable for LUKS users.
- **Expanded `HEAL_PLAYBOOK`** - ([Issue #93](https://github.com/GurKalra/prescient-linux/issues/93) _(good first issue)_) - `autoheal.py` has a small remediation playbook that currently covers basic networking, display managers, and APT/dpkg locks. We need more mappings: audio subsystems (Pipewire, PulseAudio, ALSA), display servers (X11, Wayland, SDDM, GDM edge cases), and networking daemons (UFW, Firewalld, DNSmasq) etc. Open `src/prescient/intelligence/autoheal.py`, find the `HEAL_PLAYBOOK` dictionary, and add a new key-value pair - or add a new `if "my error" in msg` block inside `determine_fixes()` for message-matched fixes.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE) that covers this project.
