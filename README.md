# Sentinel Linux

> **Predict. Protect. Recover.**
> An intelligent, CLI-first system guardian that predicts update breakages, protects dependencies, and recovers Linux environments.

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Active_Development-orange)
![FOSS Hack 2026](https://img.shields.io/badge/FOSS_Hack-2026-purple)

---

## The Problem: Linux Instability Anxiety

Every Linux user knows the anxiety of running `sudo apt upgrade`. Updates silently break kernel modules, NVIDIA driver versions mismatch, and Secure Boot complicates everything. Linux fails predictably, but no one checks the engine before hitting the gas.

## The Solution: An Active Interceptor

Sentinel Linux is a proactive system guardian that acts like a stability anti-cheat. Instead of a tool you have to remember to run, Sentinel hooks directly into your native package manager (`apt`, `pacman`).

When you initiate an update, Sentinel intercepts the command, simulates the transaction in the background, and cross-references incoming kernel versions against your current `dkms` dependencies and `mokutil` states. If an update will brick your graphical interface or network drivers, Sentinel completely halts the installation and warns you.

Sentinel does not replace your package manager. It performs deterministic pre-flight audits and optional recovery orchestration.

## Core Features

- **The Vanguard Engine (`sentinel predict`):** _(Live)_ A blazing-fast, RAM-cached (`/dev/shm`) transaction auditor. It evaluates incoming packages in under 200ms, pulling the emergency brake (`sys.exit(1)`) if it detects `/boot` partition saturation, a locked `dpkg` state, or a collision between new kernels and unsigned DKMS modules while Secure Boot is active.

- **Universal Pre-Transaction Hooks:** _(Live)_ Native interceptors injected directly into package managers (using `DPkg::Pre-Install-Pkgs` for `apt`, with `pacman` support planned). Sentinel doesn't need to be run manually—it wakes up automatically at the point of no return.

- **Automated Recovery Guardrails:** _(In Development)_ Context-aware integration with `timeshift` and native `btrfs`. Sentinel will only trigger a pre-transaction system snapshot when core boot-chain or critical services are actively threatened, keeping overhead to an absolute minimum.

- **Pattern Interpretation (`sentinel diagnose`):** _(In Development)_ A post-crash logic engine that parses `journalctl -p 3 -b -1` errors. It translates cryptic kernel panics from a failed boot into human-readable English and highly specific, actionable terminal commands.

- **Atomic Local Rollbacks & Rescue:** _(Planned)_ Strict, dependency-safe transaction reversals (`sentinel undo`) using the local `apt` cache, paired with a minimal, POSIX-compliant shell hook injected into `initramfs` for absolute worst-case emergency recovery.

## The North Stars of Sentinel

Sentinel Linux is built on four uncompromising principles:

1. **Low Latency:** Intercepts and audits must take milliseconds. No bloated execution.
2. **Low False Positives:** Only wake up the heavy probes when the boot-chain or critical services are genuinely threatened.
3. **Clear Explanations:** Don't just throw errors. Tell the user exactly _why_ it's dangerous and _how_ to fix it.
4. **Reliability > Feature Count:** A half-broken rollback is worse than no rollback. Every feature must be atomic and safe.

---

## Installation & Setup

Sentinel is built entirely on native open-source binaries with zero proprietary APIs.

**1. Clone the repository**

```bash
git clone https://github.com/GurKalra/sentinel-linux.git
cd sentinel-linux
```

**\*for ssh**

```bash
git clone git@github.com:GurKalra/sentinel-linux.git
cd sentinel-linux
```

**2. Create a virtual enviroment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install the CLI locally.**

```bash
pip install -e .
```

---

## Usage

Once the hooks are installed, Sentinel runs automatically in the background whenever you use your package manager (e.g., `sudo apt upgrade`). However, you can still use the native Linux commands manually:

- To install the background package manager hooks (Require root):

```bash
sudo sentinel install-hooks
```

- To see the help menu and avaliable commands:

```bash
sentinel --help
```

- To run a system update simulatoin and risk analysis:

```bash
sentinel predict
```

- To diagnose critical system logs from the current boot:

```bash
sentinel diagnose
```

---

## FOSSHack 2026 Roadmap

This project is actively being built for FOSS Hack 2026.

- [x] **Phase 0:** CLI Scaffolding and Environment Setup
- [x] **Phase 1:** Universal Hook Interceptor (`apt` & `pacman` integration)
- [x] **Phase 2:** The Vanguard Engine (Predict Engine, DKMS Collision Logic, /boot Audits)
- [x] **Phase 3:** The Recovery Engine (Pre-Transaction Snapshots via Timeshift/BTRFS)
- [x] **Phase 4:** The Diagnose Engine (Post-Crash `journalctl` Analysis)
- [x] **Phase 5:** Extensible Rules Schema (Custom `.toml` triggers for power users)
- [ ] **Phase 6:** Atomic Local Rollback (`sentinel undo` via local cache simulation)
- [ ] **Phase 7:** Transparent Auto-Healer (sentinel heal with interactive command proposals).
- [ ] **Phase 8:** Initramfs Rescue Hook (Minimal POSIX shell failsafe for broken boots)
- [ ] **Phase 9:** TTY Pastebin Exporter (sentinel diagnose --share via termbin).
- [ ] **Phase 10:** Network & Mirror Pre-Flight (Checking repo health before APT runs).
- [ ] **Phase 11:** Interactive TUI Dashboard (Read-only visual system overview)

---

## License

This project is open-source and available under the **MIT License**. You are free to copy, modify, and distribute this software, as long as the original copyright and license notice are included.

See the [LICENSE](LICENSE) file for more details.
