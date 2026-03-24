# `prescient heal`

> The Transparent Auto-Healer that reads your current boot's error logs, maps failing services to known remediation playbooks, and proposes exact bash fixes for your explicit approval before executing anything.

---

## Purpose

`heal` is the action step after `diagnose`. Where `diagnose` tells you _what_ broke, `heal` tells you _how to fix it_ and then does it for you.

It is designed around a core philosophy: **never execute a command on your system without showing it to you first.** Every single fix is printed to the terminal before a confirmation prompt. You see exactly what will run, in what order, before a single command touches your system. If you decline, nothing happens.

It is most useful for post-update service failures. Things like NetworkManager not restarting, a display manager crashing, or dpkg getting stuck in a broken state. For catastrophic failures where the root filesystem itself is corrupted, use `prescient undo` instead.

---

## Usage

```bash
sudo prescient heal
```

### Options

| Flag     | Description                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------- |
| _(none)_ | `heal` has no flags. It always runs `diagnose` first, then proposes fixes based on what it finds. |

> **!!Tip:** `heal` runs `prescient diagnose` internally as its first step. You do not need to run `diagnose` separately beforehand. Running `heal` gives you both the diagnostic table and the fix proposals in one command.

---

## Prerequisites

- [x] Requires `sudo` (root privileges) — needed to restart system services and reconfigure dpkg
- [x] Requires `systemd` and `journalctl` — the diagnostic step reads from the journal
- [ ] `apt`/`dpkg` required for package-related fixes (skipped on non-Debian systems)

---

## Under the Hood

`heal` executes in two distinct phases: **Diagnosis** and **Remediation**.

### Phase 1 - Diagnosis

Internally calls `run_diagnostics()` from the diagnose engine. This runs `journalctl -p 3 -b -o json`, groups errors by subsystem, and returns the ranked culprit list. The same diagnostic table shown by `prescient diagnose` is printed here.

If no errors are found, `heal` exits cleanly with no further action.

### Phase 2 - Fix Formulation

The top **3** worst offending subsystems are passed to the remediation engine. For each culprit, the engine works through a priority-ordered decision tree:

**1. Message-based pattern matching (highest priority)**

The latest error message is scanned for known failure signatures:

| Pattern in message                          | Proposed fix                                       |
| ------------------------------------------- | -------------------------------------------------- |
| `"could not get lock"` or `"frontend lock"` | Remove APT/dpkg lock files + `dpkg --configure -a` |
| `"unmet dependencies"`                      | `apt install -f -y`                                |

**2. Direct playbook lookup**

If the subsystem identifier matches a known entry in the built-in remediation playbook:

| Failing Subsystem  | Proposed Commands                           |
| ------------------ | ------------------------------------------- |
| `NetworkManager`   | `systemctl restart NetworkManager`          |
| `systemd-resolved` | `systemctl restart systemd-resolved`        |
| `bluetooth`        | `systemctl restart bluetooth`               |
| `gdm3`             | `systemctl restart gdm3`                    |
| `lightdm`          | `systemctl restart lightdm`                 |
| `dpkg`             | `dpkg --configure -a` → `apt install -f -y` |
| `apt`              | `dpkg --configure -a` → `apt install -f -y` |

**3. systemd message scan**

If the failing identifier is `systemd` itself, the latest error message is scanned for the names of known services (e.g. if systemd reports a `NetworkManager` failure, the NetworkManager playbook is used).

**4. Generic fallback**

For any unknown service not in the playbook, prescient proposes `systemctl restart <service-name>`. The service name is sanitized with a strict character filter (`[a-zA-Z0-9\-_\.]` only) before being passed to the command. Kernel panics, unknown subsystems, and bare `systemd` entries without a matched service are skipped entirely. No generic restart is proposed for them (yet).

**Deduplication:** Each subsystem is only processed once even if it appears multiple times across the top 3 culprits.

### Phase 3 - Confirmation Gate

All proposed fixes are printed to the terminal:

- the issue name and every command that will run
- before a single `[Y/n]` confirmation prompt.
- This is **not** skippable and there is no `--yes` flag by design.
- If you answer `n`, the session exits cleanly. Nothing is executed.

### Phase 4 - Execution

If confirmed, each command is executed in order using `subprocess.run` with `shlex.split()` (no `shell=True`). Each command reports its own success or failure individually. A failed command does not abort the remaining fixes (all proposed fixes run to completion).

---

## Example Output

**Successful heal session:**

```
~~~ Prescient Diagnostics & Auto-Heal ~~~

 prescient is dynamically analyzing current boot logs...

!!!!! System Instability Detected (13 total errors)

 Failing Subsystem          Error Count   Latest Error Message
 ──────────────────────────────────────────────────────────────────────────────
 NetworkManager                   9        <e> [1742673901.3241] dhcp4 (enp0s3): request timed out
 gdm3                             3        Failed to start service: org.gnome.DisplayManager
 bluetooth                        1        Failed to connect to bluetooth daemon

prescient Auto-Heal Engine: Formulating Plan...

Proposed Remediation Actions:

  Issue: NetworkManager Crash
    ↳ Run: systemctl restart NetworkManager

  Issue: gdm3 Crash
    ↳ Run: systemctl restart gdm3

  Issue: bluetooth Crash
    ↳ Run: systemctl restart bluetooth

Execute these commands automatically? [y/N]: y

Executing Fixes...
  Resolving NetworkManager Crash...
    Success: systemctl restart NetworkManager
  Resolving gdm3 Crash...
    Success: systemctl restart gdm3
  Resolving bluetooth Crash...
    Success: systemctl restart bluetooth

Auto-Heal sequence complete. Verify system stability.
```

**APT deadlock fix:**

```
prescient Auto-Heal Engine: Formulating Plan...

Proposed Remediation Actions:

  Issue: APT/DPkg Deadlock Detected
    ↳ Run: rm -f /var/lib/apt/lists/lock
    ↳ Run: rm -f /var/cache/apt/archives/lock
    ↳ Run: rm -f /var/lib/dpkg/lock-frontend
    ↳ Run: dpkg --configure -a

Execute these commands automatically? [y/N]: y
```

**No fixes mapped:**

```
prescient Auto-Heal Engine: Formulating Plan...
No automated fixes available (yet) for current issues.
```

**User declines:**

```
Execute these commands automatically? [y/N]: n
Auto-Heal aborted by user.
```

**No root:**

```
Error: Auto-Heal requires root privileges to restart services.
Try running: sudo prescient heal
```

---

## Warnings

> `heal` proposes `rm -f` commands to remove APT/dpkg lock files when a deadlock is detected. Only run this if you are certain no other `apt` or `dpkg` process is currently running. Removing a lock file while an active process holds it can corrupt your package database. The fix is only proposed to you see it before confirming.

> `heal` targets **the top 3 culprits only**. If your system has more than 3 failing subsystems, the lower-ranked ones will not receive fix proposals in this run. Run `heal` again after resolving the top issues.

> `heal` is designed for **user-space service failures**. It cannot recover a broken kernel, corrupted root filesystem, or failed initramfs. For those scenarios, use `prescient undo` (live system) or `prescient-rescue` (unbootable system).

> All commands use `shlex.split()` and list-form `subprocess.run()`. No `shell=True` is ever used.

---

## Related Commands

- [`prescient diagnose`](./diagnose.md) — Run diagnostics without executing any fixes
- [`prescient undo`](./undo.md) — Roll back the entire system if service-level fixes are not enough
- [`prescient predict`](./predict.md) — Prevent update-caused failures before they happen
