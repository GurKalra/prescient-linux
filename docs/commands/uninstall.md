# `prescient uninstall`

> The Complete Self-Destruct Sequence that permanently removes every file prescient has ever written to your system: package manager hooks, initramfs rescue binaries, logs, state files, the CLI symlink, and the source directory itself.

---

## Purpose

`uninstall` is a clean, total purge. When you run it, prescient removes its own footprint from your system in its entirety and returns your package manager to its default, unguarded state. No hooks will fire on future updates. No residual files are left in `/etc`, `/var`, or `/usr`.

It is designed around the same philosophy as every other prescient command: **never do anything destructive without telling you exactly what it is about to do first.** Before a single file is touched, you are shown what will be removed and asked to confirm. Answering `n` leaves your system completely unchanged.

---

## Usage

```bash
sudo prescient uninstall
```

### Options

| Flag     | Description                            |
| -------- | -------------------------------------- |
| _(none)_ | No flags. The purge is all-or-nothing. |

> **!!Warning:** There is no `--dry-run` or partial removal flag. `uninstall` is a complete purge. If you only want to temporarily disable prescient without removing it, you can manually delete the APT or Pacman hook file and re-run `sudo prescient install-hooks` later to restore it.

---

## Prerequisites

- [x] Requires `sudo` (root privileges) - needed to remove system files from `/etc`, `/usr`, `/var`, and `/var/log`

---

## Under the Hood

`uninstall` executes in three stages.

### Stage 1 - Confirmation Gate

Before anything is deleted, prescient prints a warning and presents a single `[y/N]` confirmation prompt:

```
!!! INITIATING PRESCIENT SELF-DESTRUCT !!!
This will permanently remove all hooks, logs, configs, and source files.
Are you sure you want to purge prescient from this system? [y/N]:
```

Answering `n` exits immediately. Nothing is touched. There is no `--yes` flag to bypass this gate.

### Stage 2 - Purge Execution

If confirmed, prescient iterates through every file and directory it has ever created and removes them in sequence. Files are removed with `os.remove()`, directories with `shutil.rmtree()`. Each target is reported individually - either as removed, failed, or skipped (not found). A failed removal does not abort the sequence; all remaining targets continue.

### Files and Directories Removed

| Target Name           | Path                                        | What It Is                                       |
| --------------------- | ------------------------------------------- | ------------------------------------------------ |
| APT Hook              | `/etc/apt/apt.conf.d/99prescient-guardian`  | The `DPkg::Pre-Install-Pkgs` interceptor for apt |
| Pacman Hook           | `/etc/pacman.d/hooks/99-prescient.hook`     | The `PreTransaction` interceptor for pacman      |
| Initramfs Hook        | `/etc/initramfs-tools/hooks/prescient-hook` | Ubuntu/Debian initramfs hook script              |
| Mkinitcpio Hook       | `/etc/initcpio/install/prescient-hook`      | Arch mkinitcpio hook script                      |
| Rescue Binary         | `/usr/local/bin/prescient-rescue`           | The emergency initramfs rescue binary            |
| System Configs        | `/etc/prescient/`                           | System-wide configuration directory              |
| Logs Data             | `/var/log/prescient.log`                    | The persistent audit log                         |
| State Directory       | `/var/lib/prescient/`                       | Snapshot state JSON (`last_snapshot.json`)       |
| CLI Symlink           | `/usr/local/bin/prescient`                  | The global `prescient` command symlink           |
| Core Source Directory | `~/.prescient/`                             | The full cloned source repository and venv       |

> **Note:** The home directory (`~/.prescient`) is resolved correctly when running under `sudo`. prescient reads `$SUDO_USER` to locate the real user's home directory, preventing the source from being searched in `/root/.prescient` by mistake.

### Stage 3 - Completion

After all targets are processed, prescient prints a confirmation that the purge is complete and that update control has been fully returned to the native package manager.

**Important:** `uninstall` does **not** rebuild the initramfs after removing the initramfs hook files. The rescue binary (`prescient-rescue`) will remain embedded in the current kernel's RAM disk until the next time `update-initramfs -u` or `mkinitcpio -P` is run (e.g. on the next kernel update). This is safe (a dormant binary in the RAM disk causes no harm) but if you want to remove it immediately, run the appropriate rebuild command manually after uninstalling.

---

## Example Output

**Standard uninstall:**

```
!!! INITIATING PRESCIENT SELF-DESTRUCT !!!
This will permanently remove all hooks, logs, configs, and source files.
Are you sure you want to purge prescient from this system? [y/N]: y

Purging system footprint...
  Removed APT Hook (/etc/apt/apt.conf.d/99prescient-guardian)
  Removed Initramfs Hook (/etc/initramfs-tools/hooks/prescient-hook)
  Removed Rescue Binary (/usr/local/bin/prescient-rescue)
  Removed Logs Data (/var/log/prescient.log)
  Removed State Directory (/var/lib/prescient)
  Removed CLI Symlink (/usr/local/bin/prescient)
  Removed Core Source Directory (/home/user/.prescient)
  ~ Skipped Pacman Hook (Not found)
  ~ Skipped Mkinitcpio Hook (Not found)
  ~ Skipped System Configs (Not found)

Prescient has been completely erased from the system.
Update lifecycle returned to standard package manager control.
```

**User aborts at confirmation:**

```
!!! INITIATING PRESCIENT SELF-DESTRUCT !!!
This will permanently remove all hooks, logs, configs, and source files.
Are you sure you want to purge prescient from this system? [y/N]: n
Uninstall aborted. Prescient remains active.
```

**No root privileges:**

```
Error: `uninstall` requires root privileges to execute.
Try running: sudo prescient uninstall
```

---

## Warnings

> **Uninstall is permanent and irreversible.** The source directory (`~/.prescient`), virtual environment, all logs, and all state files are deleted. Your prescient configuration (including any packages learned by the Heuristic Engine and saved to `prescient.toml`) is also destroyed. There is no undo for an uninstall.

> **Snapshot state is deleted, but your actual snapshots are not.** Removing `/var/lib/prescient/last_snapshot.json` means `prescient undo` will no longer know about your last pre-update snapshot. However, your Timeshift or Snapper snapshots themselves are **not touched**. They live in the backup provider's own directories and can still be accessed directly via `timeshift-gtk` or `snapper list`.

> **The initramfs is not rebuilt automatically.** After uninstall, the `prescient-rescue` binary may still be present inside the currently running kernel's RAM disk. It is inert without a running prescient installation and will be flushed naturally on your next kernel update.

> **The APT hook is removed immediately.** From the moment uninstall completes, future `apt upgrade` runs will no longer be intercepted. No pre-flight audit, no snapshot guardrail, no DKMS collision detection. You are back to the default package manager behavior.

---

## Related Commands

- [`prescient install-hooks`](./install-hooks.md) — Re-install hooks if you change your mind after uninstalling
- [`prescient predict`](./predict.md) — The core engine that is disabled when the hooks are removed
- [`prescient undo`](./undo.md) — Use this before uninstalling if you have a pending rollback to perform
