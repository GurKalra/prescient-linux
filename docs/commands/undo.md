# `prescient undo`

> The Atomic Recovery Engine that reads prescient's last known-good snapshot, verifies it still exists on disk, and triggers a full system rollback via Timeshift or Snapper along with a hard confirmation gate before a single file is touched.

---

## Purpose

`undo` is the command you reach for when an update has already run and broken something. Where `predict` stops bad updates before they happen, `undo` fixes the aftermath. It restores your root filesystem to the exact state it was in the moment prescient took a pre-update snapshot before the breaking transaction was committed.

It is designed around one principle: **never touch your system without telling you exactly what it is about to do first.** Before any rollback executes, `undo` prints the snapshot provider, name, age, and the trigger reason that caused it to be created. Then it presents a hard `[y/N]` confirmation prompt. There is no `--yes` flag to skip it.

`undo` works in two contexts:

- **Live system (TTY or terminal):** Run directly after a bad update breaks your GUI or networking. Drop into a TTY with `Ctrl+Alt+F2`, log in, and run `sudo prescient undo`.
- **Rescue context (chroot from initramfs):** Called automatically by `prescient-rescue` when your system cannot boot at all. In this context it skips CLI tools and reads snapshot directories directly from the filesystem.

---

## Usage

```bash
sudo prescient undo
```

### Options

| Flag     | Description                                                    |
| -------- | -------------------------------------------------------------- |
| _(none)_ | No flags. All behaviour is driven by the saved snapshot state. |

> **!!Tip:** If your graphical environment is dead after an update, press `Ctrl+Alt+F2` (or `F3`, `F4`) to switch to a TTY, log in with your username and password, and run `sudo prescient undo`. You do not need a working desktop to use this command.

> **!!Tip:** If your system cannot boot at all and you are dropped to an `(initramfs)` prompt, do not run `prescient undo` manually. Use `prescient-rescue` instead (it sets up the correct chroot environment and calls `undo` for you automatically).

---

## Prerequisites

- [x] Requires `sudo` (root privileges)
- [x] A snapshot must have been created by `prescient predict` before the breaking update — metadata is stored at `/var/lib/prescient/last_snapshot.json`
- [x] `timeshift` or `snapper` must be installed and the snapshot must still exist on disk
- [ ] In rescue/chroot context: D-Bus and systemd are not required - `undo` falls back to filesystem-direct snapshot detection automatically

---

## Under the Hood

`undo` executes a strict, ordered sequence. Each stage must pass before the next begins.

### Stage 1 - State File Lookup

Reads `/var/lib/prescient/last_snapshot.json` — the metadata file written by `prescient predict` every time it creates a snapshot. This file contains four fields:

| Field            | Description                                                                              |
| ---------------- | ---------------------------------------------------------------------------------------- |
| `provider`       | `"timeshift"` or `"snapper"`                                                             |
| `snapshot_name`  | Timeshift timestamp (`2026-03-24_01-15-00`) or Snapper numeric ID (`42`)                 |
| `created_at`     | UNIX timestamp of when the snapshot was taken                                            |
| `trigger_reason` | The risk category that caused the snapshot (e.g. `"Critical System Component (Kernel)"`) |

If the state file does not exist (prescient was never triggered on this system, or the file was deleted), `undo` does not immediately fail.

### Stage 2 - Filesystem Fallback (Rescue Mode)

If Stage 1 returns nothing, `undo` falls back to `get_latest_system_snapshot()` which is a filesystem-direct scanner that works without calling any CLI tools. This is specifically designed for the chroot rescue context where D-Bus and systemd are unavailable.

**Timeshift fallback:** Checks if `/etc/timeshift/timeshift.json` exists, then scans two possible snapshot directories.

It sorts the snapshot directories alphabetically, takes the last one (the most recent), and attempts to parse its name as a `%Y-%m-%d_%H-%M-%S` timestamp to recover a `created_at` value.

**Snapper fallback:** Checks if `/.snapshots` exists, collects all subdirectories with purely numeric names, sorts them as integers, and takes the highest ID as the latest snapshot.

If both fallbacks return nothing, `undo` exits cleanly with a message explaining that no snapshot history exists and that one will be created automatically on the next high-risk update (if opted).

### Stage 3 - Snapshot Integrity Verification

Before showing anything to the user, `undo` verifies the snapshot still physically exists. It tries two methods in sequence:

**CLI verification (primary):**

- For Snapper: runs `snapper list` and checks if the snapshot ID appears in the output (10-second timeout)
- For Timeshift: runs `timeshift --list` and checks if the snapshot name appears in the output (10-second timeout)

**Filesystem verification (fallback):** If the CLI call fails or times out (common in chroot environments):

- Timeshift: checks for the snapshot directory at `/timeshift/snapshots/<name>` or `/run/timeshift/backup/timeshift/snapshots/<name>`
- Snapper: checks for `/.snapshots/<id>/snapshot`

If neither method confirms the snapshot exists, `undo` aborts with an error explaining the snapshot may have been manually deleted or purged by the backup provider's own cleanup rules.

### Stage 4 - Snapshot Summary Display

If the snapshot is verified, `undo` prints a human-readable summary before asking for confirmation:

```
  Provider:       Timeshift
  Snapshot Name:  2026-03-24_01-15-00
  Created:        2 hours ago
  Trigger Reason: Critical System Component (Kernel)
```

The `Created` field uses a relative time helper that converts the raw UNIX timestamp into a human-readable string: `"Just now"`, `"X minutes ago"`, `"X hours ago"`, or `"X days ago"`.

### Stage 5 - Confirmation Gate

```
!!!!WARNING: This will overwrite your root filesystem and immediately reboot your machine.
Proceed with system rollback? [y/N]:
```

This prompt is **mandatory and cannot be bypassed.** Answering `n` or pressing Enter exits cleanly with no changes made. This gate exists because the rollback command overwrites the root filesystem (there is no undo for an undo).

### Stage 6 - Rollback Execution

If confirmed, `undo` calls the appropriate provider with a 300-second timeout:

**Snapper:**

```bash
snapper rollback <snapshot_id>
```

**Timeshift:**

```bash
timeshift --restore --snapshot <snapshot_name> --scripted --yes
```

Both calls use list-form `subprocess.run()` with no `shell=True`.

**Post-rollback behaviour differs by provider:**

- **Timeshift:** Handles the reboot itself as part of `--scripted` restore. The terminal prints `"Rollback complete. Your system will reboot shortly."` and the machine reboots automatically.
- **Snapper:** Does not reboot automatically. The terminal prints `"Rollback complete. Please reboot manually: sudo reboot"` and the user must reboot themselves to boot into the restored subvolume.

If the rollback command times out (300 seconds) or returns a non-zero exit code, `undo` prints an error and directs the user to `/var/log/prescient.log` for details.

---

## Example Output

**Successful rollback (Timeshift):**

```
~~~ Prescient Recovery Engine ~~~

Verifying snapshot integrity...
  Provider:       Timeshift
  Snapshot Name:  2026-03-24_01-15-00
  Created:        2 hours ago
  Trigger Reason: Critical System Component (Kernel)

!!!!WARNING: This will overwrite your root filesystem and immediately reboot your machine.
Proceed with system rollback? [y/N]: y

Initiating Timeshift restoration...
Rollback complete. Your system will reboot shortly.
```

**Successful rollback (Snapper):**

```
~~~ Prescient Recovery Engine ~~~

Verifying snapshot integrity...
  Provider:       Snapper
  Snapshot Name:  42
  Created:        47 minutes ago
  Trigger Reason: Core Subsystem (Core Daemons)

!!!!WARNING: This will overwrite your root filesystem and immediately reboot your machine.
Proceed with system rollback? [y/N]: y

Initiating Snapper restoration...
Rollback complete. Please reboot manually: sudo reboot
```

**User aborts at confirmation:**

```
!!!!WARNING: This will overwrite your root filesystem and immediately reboot your machine.
Proceed with system rollback? [y/N]: n
Rollback aborted by user.
```

**No snapshot found:**

```
~~~ Prescient Recovery Engine ~~~

No recent snapshots found on this system.
If you recently installed prescient, a snapshot will be created automatically on your next high-risk update.
```

**Snapshot deleted since creation:**

```
~~~ Prescient Recovery Engine ~~~

Verifying snapshot integrity...
Error: The snapshot '2026-03-24_01-15-00' could not be found.
It may have been manually deleted or cleared by your backup provider's cleanup rules.
```

**No root privileges:**

```
Error: `undo` requires root privileges to execute.
Try running: sudo prescient undo
```

---

## Warnings

> **Rollback overwrites your root filesystem.** Any files created or modified after the snapshot was taken (documents, configuration changes, installed packages) will be lost. This is intentional and irreversible. The confirmation prompt is the only safety gate.

> **Timeshift reboots automatically.** When using Timeshift, the machine will reboot without further warning after the restore command completes. Save any open work in other terminals before confirming the rollback.

> **Snapper requires a manual reboot.** The `snapper rollback` command marks the snapshot subvolume as the new default but does not reboot. You must run `sudo reboot` yourself for the rollback to take effect on the next boot.

> **The state file is root-only.** `/var/lib/prescient/last_snapshot.json` is written with `0o600` permissions and stored in a `0o700` directory. It can only be read and written by root. Running `prescient undo` without `sudo` will be blocked before any state file access is attempted.

> **`undo` only knows about the most recent snapshot.** prescient stores metadata for exactly one snapshot at a time. Each new high-risk update overwrites the previous state file entry. If you ran two high-risk updates in a row and want to roll back to the one before the last, you will need to use your backup provider's own interface (`timeshift-gtk`, `snapper list`, etc.) directly.

> **Do not run `undo` manually from an `(initramfs)` prompt.** The chroot environment set up by `prescient-rescue` is required for the snapshot partition to be mounted and accessible. Running `undo` raw at the initramfs shell without the chroot will fail to find any snapshot directories.

---

## Related Commands

- [`prescient predict`](./predict.md) - Creates the snapshot that this command rolls back to
- [`prescient-rescue`](./rescue.md) - Calls `undo` automatically from a chroot when the system cannot boot
- [`prescient diagnose`](./diagnose.md) - Identify what broke before deciding whether a full rollback is necessary
- [`prescient heal`](./heal.md) - For service-level failures that don't require a full filesystem rollback
