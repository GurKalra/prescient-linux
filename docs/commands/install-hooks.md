# `prescient install-hooks`

> Wires Prescient directly into your package manager and injects an emergency rescue environment into your kernel's RAM disk. This is handled automatically during first-time setup via the TUI onboarding screen.

---

## Purpose

`install-hooks` is the setup operation that transforms Prescient from a tool you run manually into a **Guardrail by Default**. After hooks are installed, `prescient predict` fires automatically on every `sudo apt upgrade` or `pacman -Syu`.

> **You do not need to run this command manually.** It is called automatically when you first run `prescient tui` and press Enter on the onboarding screen. The `install.sh` script also handles this flow end-to-end. This page documents what the operation does under the hood.

If you need to re-run it manually (e.g. after moving the binary or reinstalling), the command is:

```bash
sudo prescient install-hooks
```

---

## Usage

```bash
# Manual use only — normally handled by the TUI onboarding screen
sudo prescient install-hooks
```

### Options

| Flag     | Description                                 |
| -------- | ------------------------------------------- |
| _(none)_ | No flags. Package manager is auto-detected. |

---

## Prerequisites

- [x] Requires `sudo` (root privileges)
- [x] Requires `apt` (Debian/Ubuntu) or `pacman` (Arch Linux)
- [x] Ubuntu/Debian: requires `initramfs-tools` and `update-initramfs`
- [x] Arch Linux: requires `mkinitcpio`

---

## Under the Hood

The operation runs in two sequential stages.

### Stage 1 - Package Manager Hook

Prescient detects your package manager and installs the appropriate native hook.

**On Debian/Ubuntu (APT):**

Creates `/etc/apt/apt.conf.d/99prescient-guardian`:

```
DPkg::Pre-Install-Pkgs {"/path/to/prescient predict";};
DPkg::Tools::Options::/path/to/prescient::Version "3";
```

`DPkg::Pre-Install-Pkgs` tells APT to pipe the full incoming package list to `prescient predict` via stdin before committing any changes to disk. `Version "3"` enables the package file path format that Prescient's input sanitizer expects.

**On Arch Linux (Pacman):**

Creates `/etc/pacman.d/hooks/99-prescient-guardian.hook`:

```ini
[Trigger]
Operation = Upgrade
Operation = Install
Type = Package
Target = *

[Action]
Description = prescient Linux: Analyzing blast radius...
When = PreTransaction
Exec = /path/to/prescient predict
NeedsTargets
AbortOnFail
```

`NeedsTargets` passes the target package names to `prescient predict`. `AbortOnFail` means if Prescient exits with a non-zero code (a VETO), the entire transaction is cancelled. `When = PreTransaction` guarantees the hook fires before any package is extracted or installed.

Both hooks resolve the binary path dynamically at install time using `os.path.abspath(sys.argv[0])`.

### Stage 2 - Initramfs Rescue Injection

After the package manager hook is installed, the emergency rescue environment is injected into the kernel's RAM disk. This is the safety net for worst-case scenarios where an update breaks the entire boot sequence.

**Step 1 - Install rescue binary:**
Copies `prescient-rescue.sh` to `/usr/local/bin/prescient-rescue` with `0o755` permissions.

**Step 2 - Install OS-specific initramfs hook:**

On Ubuntu/Debian: copies `prescient-ubuntu-hook` to `/etc/initramfs-tools/hooks/prescient-hook` (`0o755`). Uses `copy_exec` to bundle the rescue binary into the initramfs image.

On Arch Linux: copies `prescient-arch-hook` to `/etc/initcpio/install/prescient-hook` (`0o755`). Uses `add_binary` to include the rescue binary in the mkinitcpio image.

**Step 3 - Rebuild the RAM disk:**

On Ubuntu/Debian: runs `update-initramfs -u` to rebuild the initramfs for the running kernel.

On Arch Linux: runs `mkinitcpio -P` to rebuild all kernel presets.

This embeds `prescient-rescue` at `/bin/prescient-rescue` inside the kernel's boot image. If a future update completely breaks the boot sequence, the rescue binary is available at the `(initramfs)` prompt without needing a working root filesystem, D-Bus, or systemd.

### Files Created

| File                                             | Purpose                                  |
| ------------------------------------------------ | ---------------------------------------- |
| `/etc/apt/apt.conf.d/99prescient-guardian`       | APT pre-transaction hook (Debian/Ubuntu) |
| `/etc/pacman.d/hooks/99-prescient-guardian.hook` | Pacman pre-transaction hook (Arch)       |
| `/usr/local/bin/prescient-rescue`                | Universal emergency rescue script        |
| `/etc/initramfs-tools/hooks/prescient-hook`      | Ubuntu initramfs hook                    |
| `/etc/initcpio/install/prescient-hook`           | Arch mkinitcpio hook                     |

---

## Example Output

```
prescient Linux: Initializing Hook Installer...
 prescient APT hook installed successfully at /etc/apt/apt.conf.d/99prescient-guardian
 Hook wired to executable: /usr/local/bin/prescient

Injecting Emergency Rescue Environment into Kernel RAM Disk...
  Universal Rescue Script installed to '/usr/local/bin/prescient-rescue'
  Ubuntu Initramfs Hook installed.
  Rebuilding initramfs image... (This may take a minute)
  Kernel RAM Disk rebuilt successfully!
```

---

## Warnings

> The initramfs rebuild step (`update-initramfs -u` or `mkinitcpio -P`) modifies your kernel boot image. This is a standard, safe operation performed by every kernel update. If the rebuild fails, Prescient logs the error and continues, the package manager hook will still work, but the rescue environment will not be available in the RAM disk until the rebuild succeeds.

> If you move the `prescient` binary after installing hooks (e.g. by reinstalling to a different path), the hooks will point to the old path and stop working. Re-run `sudo prescient install-hooks` to update them.

> To completely remove all hooks and files created by this command, use `sudo prescient uninstall`.

---

## Related Commands

- [`prescient predict`](./predict.md) - The command this hook calls automatically on every transaction
- [`prescient uninstall`](./uninstall.md) - Removes all hooks and files installed by this command
- [`prescient tui`](./tui.md) - The onboarding screen that calls this automatically on first launch
