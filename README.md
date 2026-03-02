# Sentinel Linux

> **Predict. Protect. Recover.** > An intelligent, CLI-first system guardian that predicts update breakages, protects dependencies, and recovers Linux environments.

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

## Core Features (In Development)

- **Universal Pre-Transaction Hooks:** Injects native guardrails directly into `apt` (Debian/Ubuntu) and `pacman` (Arch Linux).
- **Surgical Prediction (`sentinel predict`):** Simulates incoming updates and catches exact module collisions with zero false positives.
- **Pattern Interpretation (`sentinel diagnose`):** Uses an extensible, JSON-based schema to parse `journalctl` boot errors and match them to specific, actionable terminal commands.

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

- [x] Phase 0: CLI Scaffolding and Environment Setup
- [ ] Phase 1: Universal Hook Installer ('apt' & 'pacman' interceptors)
- [ ] Phase 2: The Predict Engine (Subprocess simulation & blast radius analysis)
- [ ] Phase 3: Collision Logic (DKMS and Secure Boot cross-referencing)
- [ ] Phase 4: Diagnose Engine & Extensible Rules Schema

---

## License

This project is open-source and available under the **MIT License**. You are free to copy, modify, and distribute this software, as long as the original copyright and license notice are included.

See the [LICENSE](LICENSE) file for more details.
