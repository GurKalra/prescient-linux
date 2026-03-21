# Prescient

> **Predict. Protect. Recover.**
> An intelligent, CLI-first system guardian that predicts update breakages, protects dependencies, and recovers Linux environments.

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Active_Development-orange)
![FOSS Hack 2026](https://img.shields.io/badge/FOSS_Hack-2026-purple)

---

## The Problem: Linux Instability Anxiety

Every Linux user knows the anxiety of running `sudo apt upgrade`. Updates silently break kernel modules, NVIDIA driver versions mismatch, and Secure Boot complicates everything. Linux fails predictably, but no one checks the engine before hitting the gas.

## The Solution: An Active Interceptor

Prescient Linux is a proactive system guardian that acts like a stability anti-cheat. Instead of a tool you have to remember to run, prescient hooks directly into your native package manager (`apt`, `pacman`).

When you initiate an update, prescient intercepts the command, simulates the transaction in the background, and cross-references incoming kernel versions against your current `dkms` dependencies and `mokutil` states. If an update will brick your graphical interface or network drivers, prescient completely halts the installation and warns you.

Prescient does not replace your package manager. It performs deterministic pre-flight audits and optional recovery orchestration.

## Core Features

- **The Vanguard Engine (`prescient predict`):** _(Live)_ A blazing-fast, RAM-cached (`/dev/shm`) transaction auditor. It evaluates incoming packages in under 200ms, pulling the emergency brake (`sys.exit(1)`) if it detects `/boot` partition saturation, a locked `dpkg` state, or a collision between new kernels and unsigned DKMS modules while Secure Boot is active.

- **Universal Pre-Transaction Hooks:** _(Live)_ Native interceptors injected directly into package managers (using `DPkg::Pre-Install-Pkgs` for `apt`, with `pacman` support planned). prescient doesn't need to be run manually—it wakes up automatically at the point of no return.

- **Autonomous Heuristic Engine:** _(Live)_ prescient doesn't just rely on static blacklists. It dynamically queries the package manager to analyze the exact paths an unknown package intends to modify. If a package touches critical tripwires (like `/etc/pam.d` or `/boot`), prescient flags it, learns the threat, and saves it to its configuration memory.

- **Automated Recovery Guardrails:** _(Live)_ Context-aware integration with `timeshift` and native `btrfs` (`snapper`). prescient will only trigger a pre-transaction system snapshot when core boot-chain or critical services are actively threatened, keeping overhead to an absolute minimum and persisting the state to `/var/lib/prescient`.

- **Atomic Local Rollbacks (`prescient undo`):** _(Live)_ Strict, dependency-safe transaction reversals. If an update breaks your system's GUI or networking, drop into a TTY terminal and instantly restore your root filesystem to the exact moment before the crash with an interactive, safety-gated rollback UI.

- **Pattern Interpretation (`prescient diagnose`):** _(Live)_ A post-crash logic engine that parses the `journalctl -p 3 -b -1` errors. It translates cryptic kernel panics from a failed boot into human-readable English and highly specific, actionable terminal commands.

- **Transparent Auto-Healer (`prescient heal`):** _(Live)_ An interactive execution engine that maps critical `journalctl` failures to known the remediation playbooks. It transparently proposes exact bash fixes for crashed services and waits for user confirmation before safely executing them.

- **Initramfs Rescue Hook (`prescient-rescue`):** _(Live)_ A minimal, POSIX-compliant shell hook injected into the initramfs boot stage. This allows for absolute worst-case emergency recovery. If an update completely breaks your boot sequence, you can trigger a raw filesystem rollback directly from the initramfs prompt, bypassing the need for D-Bus or systemd.

- **TTY Pastebin Exporter (`prescient diagnose --share`):** _(Live)_ A frictionless log-sharing mechanism designed for headless or broken GUI states. It securely pipes anonymized crash traces and `journalctl` outputs directly to a CLI-friendly pastebin (`termbin.com`) using native Python sockets (bypassing the need for external tools like `netcat`), generating a short URL for remote debugging. It includes a secured, local offline fallback mechanism if the system's network drivers are completely broken.

- **Network & Mirror Pre-Flight:** _(Live)_ An active, concurrent network health auditor that pings your configured package mirrors (supporting both legacy `.list` and modern DEB822 `.sources`) before a transaction begins. It prevents broken or partial updates caused by dead repository servers or 404 errors, taking milliseconds to run using thread pools, and smartly bypasses itself during local package removals.

- **Interactive TUI Control Center:** _(Planned)_ A comprehensive Terminal User Interface. Moving beyond a read-only status screen, this dashboard acts as a visual command center. Users can navigate graphical buttons with their keyboard to execute core commands (`undo`, `heal`, `diagnose`), view system health metrics, seamlessly pull OTA updates directly from the main repository, or cleanly trigger the system uninstall sequence.

## The North Stars of prescient

Prescient Linux is built on four uncompromising principles:

1. **Low Latency:** Intercepts and audits must take milliseconds. No bloated execution.
2. **Low False Positives:** Only wake up the heavy probes when the boot-chain or critical services are genuinely threatened.
3. **Clear Explanations:** Don't just throw errors. Tell the user exactly _why_ it's dangerous and _how_ to fix it.
4. **Reliability > Feature Count:** A half-broken rollback is worse than no rollback. Every recovery feature must be atomic, safe, and functional—even from a dead, unbootable state.

---

## Installation & Setup

Prescient is built entirely on native open-source binaries with zero proprietary APIs.

Run this single command to securely deploy prescient to your system:

```bash
curl -sSL https://raw.githubusercontent.com/GurKalra/prescient-linux/main/install.sh | bash
```

---

## Usage

Once the hooks are installed, prescient runs automatically in the background whenever you use your package manager (e.g., `sudo apt upgrade`). However, you can still use the native Linux commands manually:

- To install the background package manager hooks (Require root):

```bash
sudo prescient install-hooks
```

- To see the help menu and avaliable commands:

```bash
prescient --help
```

- To run a system update simulatoin and risk analysis:

```bash
prescient predict
```

- To diagnose critical system logs from the current boot:

```bash
prescient diagnose
```

- To export diagnostic logs to a public URL for remote support:

```bash
prescient diagnose --share
```

- To safely rollback the system to the last pre-update snapshot (Requires root):

```bash
sudo prescient undo
```

- To recover a completely unbootable system from the `(initramfs)` prompt:

```bash
prescient-rescue
```

- To transparently auto-recover crashed services based on log diagnostics (Requires root):

```bash
sudo prescient heal
```

- To securely pull and install the latest Over-The-Air (OTA) update directly from GitHub (Requires root):

```bash
sudo prescient update
```

- To completely remove prescient, its hooks, and all system files (Requires root):

```bash
sudo prescient uninstall
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
- [x] **Phase 6:** Atomic Local Rollback (`prescient undo` via local cache simulation)
- [x] **Phase 7:** Transparent Auto-Healer (prescient heal with interactive command proposals).
- [x] **Phase 8:** Initramfs Rescue Hook (Minimal POSIX shell failsafe for broken boots)
- [x] **Phase 9:** TTY Pastebin Exporter (prescient diagnose --share via termbin).
- [x] **Phase 10:** Network & Mirror Pre-Flight (Checking repo health before APT runs).
- [ ] **Phase 11:** Interactive TUI Control Center (Visual execution, OTA updates, and metrics)

---

## License

This project is open-source and available under the **MIT License**. You are free to copy, modify, and distribute this software, as long as the original copyright and license notice are included.

See the [LICENSE](LICENSE) file for more details.
