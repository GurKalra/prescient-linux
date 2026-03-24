# `prescient predict`

> The Vanguard Engine that intercepts your package manager mid-transaction and audits every incoming package before a single file touches your disk.

---

## Purpose

`predict` is the core command of Prescient. It runs a deterministic, multi-stage pre-flight audit on every incoming package transaction and pulls the emergency brake if it detects a condition that would break your system.

It is designed to run automatically as it's wired directly into your package manager via `prescient install-hooks` (so you never have to remember to run it). When it fires, it either silently passes and lets the transaction continue, or halts it entirely with a clear explanation of what would have gone wrong and how to fix it.

---

## Usage

```bash
# Manual run (no packages — runs pre-flight checks only)
sudo prescient predict

# Automatic (triggered by apt/pacman via hooks — receives package list on stdin)
sudo apt upgrade
```

### Options

| Flag     | Description                                                                         |
| -------- | ----------------------------------------------------------------------------------- |
| _(none)_ | `predict` has no user-facing flags. All configuration is done via `prescient.toml`. |

> **!!!Tip:** You almost never need to run `predict` manually. Its real power is as a background interceptor. Run `sudo prescient install-hooks` once to wire it into your package manager permanently.

---

## Prerequisites

- [x] Requires `sudo` (root privileges)
- [x] Requires a supported package manager (`apt` or `pacman`)
- [ ] `mokutil` recommended for Secure Boot detection (falls back to permissive mode if missing)
- [ ] `dkms` required for driver collision detection (skipped silently if not installed)
- [ ] `timeshift` or `snapper` required for automated snapshot guardrails (skipped if neither is found)

---

## Under the Hood

When `predict` fires, either manually or via a package manager hook. It executes a strict, ordered sequence of checks. **Any stage marked VETO will immediately abort the transaction** with exit code 1, blocking `apt`/`pacman` from proceeding.

### Stage 1 - Pre-Flight System Health (VETO-capable)

Three checks run unconditionally before any package analysis:

1. **Package Manager Integrity** - Runs `dpkg --audit` (Debian) or checks for `/var/lib/pacman/db.lck` (Arch). A broken or locked package manager is an immediate VETO. Fix: `sudo apt install -f`
2. **Root Partition Space** - Requires at least **2.0 GB free** on `/`. If running low, the transaction is blocked to prevent a mid-update filesystem full condition. Exception: removal operations (`apt remove`, `autoremove`, `purge`) bypass this check since they free space.
3. **Mirror Health** - Concurrently pings all configured APT/pacman mirrors using thread pools. If **all** mirrors are unreachable, the transaction is blocked to prevent a partial update. A single dead PPA warns but does not block. Skipped during removal operations.

### Stage 2 - Package List Sanitization

The raw stdin from `apt`/`pacman` is parsed and sanitized. Package names are extracted from `.deb` cache paths, stripped down to their base names, and validated against a strict regex (`^[a-zA-Z0-9\-_\.\+]+$`). Any malformed input is dropped and logged as a security threat.

### Stage 3 - Surgical Probes (triggered only when relevant)

These probes only wake up if the incoming packages match their specific triggers. They add near-zero latency to normal `curl` or `vlc` updates.

**Boot Partition Audit** (triggers on: `linux-image`, `linux-headers`, `grub`, `shim`, `initramfs-tools`, etc.)

- Checks `/boot` has at least **500 MB free**
- Warns if **3 or more** old kernel images are sitting in `/boot`

**Security & Driver Collision Audit** (triggers on: kernel packages, bootloader packages, `nvidia`, `dkms`, `amdgpu`, etc.)

- Checks Secure Boot state via `mokutil --sb-state` (result is RAM-cached in `/dev/shm` for speed)
- If Secure Boot is **ENABLED** and a kernel update is incoming alongside active DKMS modules (e.g. `nvidia`), prescient raises a **collision warning** - unsigned modules will fail to load on the new kernel, causing a black screen on next boot
- If Secure Boot is **DISABLED**, DKMS modules will rebuild automatically and no action is needed

### Stage 4 - Blast Radius Assessment + Recovery Guardrails

Every package is cross-referenced against the rules in `prescient.toml`:

It has two types of risks 'triggers':

- **High Risk** (triggers automated snapshot):
  - Special flag: `heuristics`: Packages previously flagged by the Intelligence Engine

- **Medium Risk** (triggers automated snapshot)

If no match is found in the static config, the **Heuristic Engine** takes over.

### Stage 5 - Heuristic Intelligence Engine (unknown packages only)

For packages not found in `prescient.toml`, prescient runs a dynamic deep scan:

1. Runs `dpkg -L <package>` (or `pacman -Ql`) to get the full file list the package intends to install
2. Checks every file path against 20 critical system tripwires including `/boot/`, `/etc/pam.d/`, `/etc/systemd/`, `/lib/modules/`, `/etc/sudoers.d/`, `/etc/NetworkManager/`, and more
3. If a tripwire is hit, the package is flagged, the reason is logged, and the package name is **permanently saved to `prescient.toml`** under `[triggers.high_risk.heuristics]` so future scans skip this step
4. A batched pre-scan runs first for performance — individual package isolation only runs if the batch scan finds a potential threat

### Stage 6 - Snapshot Guardrails

If any high or medium risk package is detected (or a heuristic flag fires), prescient:

- Checks disk space (requires **5 GB free** to proceed with snapshot)
- Checks cooldown (skips if a snapshot was taken in the last **10 minutes**)
- Creates a pre-transaction snapshot via `timeshift` or `snapper` with a 120-second timeout
- Saves snapshot metadata (name, provider, timestamp, trigger reason) to `/var/lib/prescient/last_snapshot.json` for use by `prescient undo`

> **!!Security note:** All subprocess calls use list-form arguments (no `shell=True`). Package name inputs are validated with a strict regex before being passed to any system command.

---

## Example Output

**Clean transaction (standard app update):**

```
~~~Prescient Pre-Flight Audit...~~~
  Package Manager State: Healthy
  Root Partition Space: 47.23 GB free
  Mirror Health: Healthy

Prescient Audit Complete. Proceeding with transaction...
```

**High-risk kernel update with snapshot:**

```
~~~Prescient Pre-Flight Audit...~~~
  Package Manager State: Healthy
  Root Partition Space: 47.23 GB free
  Mirror Health: Healthy

Kernel/Boot Update Detected. Auditing /boot partition...
  /boot Partition Space: 892 MB free

prescient Security & Driver Audit...
  Secure Boot State: ENABLED
  Driver Collision Risk: Unsigned Modules vs. New Kernel
    - Found active DKMS module: nvidia
    Action Required: Ensure you have a MOK (Machine Owner Key) enrolled.

High-Risk Update Detected: Critical System Component (Kernel)
  Engaging Recovery Guardrails...
  Creating Timeshift Snapshot (Do not close terminal (Max Wait: 120s))...
  Timeshift Snapshot Created: 2026-03-24_01-15-00
    ↳ To undo this update later, run: sudo prescient undo

Prescient Audit Complete. Proceeding with transaction...
```

**VETO — broken package manager:**

```
~~~Prescient Pre-Flight Audit...~~~
  Package Manager State: BROKEN
    Reason: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a'
    Please fix broken dependencies or remove stale lockfiles before updating.

!!!Prescient VETO: System health checks failed!!!
Aborting installation to prevent system breakage.
```

**VETO — all mirrors unreachable:**

```
~~~Prescient Pre-Flight Audit...~~~
  Package Manager State: Healthy
  Root Partition Space: 47.23 GB free
  Mirror unreachable: https://archive.ubuntu.com (Connection refused)
  Mirror unreachable: https://ppa.launchpadcontent.net (timed out)
  All mirrors unreachable. Blocking transaction to prevent partial update.

!!!Prescient VETO: System health checks failed!!!
Aborting installation to prevent system breakage.
```

---

## Warnings

> If `predict` issues a VETO and exits with code 1, the entire `apt`/`pacman` transaction is cancelled. No packages are installed or upgraded. This is intentional — a partial update on a broken system is worse than no update.

> The Heuristic Engine runs `dpkg -L` on unknown packages as root. This queries already-installed package metadata and does **not** execute any package code.

> Snapshot creation adds time to high-risk updates (typically 30–90 seconds for Timeshift). The cooldown timer (10 minutes) prevents multiple snapshots in rapid succession.

---

## Related Commands

- [`prescient install-hooks`](./install-hooks.md) - Wire `predict` into your package manager so it runs automatically
- [`prescient undo`](./undo.md) - Roll back to the snapshot created by this command
- [`prescient diagnose`](./diagnose.md) - If `predict` passed but the update broke something anyway
