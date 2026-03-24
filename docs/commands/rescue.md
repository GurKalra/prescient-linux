# `prescient-rescue`

> The Initramfs Emergency Rescue Hook that mounts your broken root filesystem, locates your last known-good snapshot, and triggers a full system rollback and that all from the `(initramfs)` prompt, before Linux has even finished booting.

---

## Purpose

`prescient-rescue` is the absolute last line of defense. It exists for the scenario where everything else has already failed. The update ran, the system tried to boot, and it couldn't. You are staring at an `(initramfs)` emergency shell with no graphical environment, no systemd, no D-Bus, and no way to run a normal `prescient undo`.

This script is a minimal, POSIX-compliant shell program embedded directly inside the kernel's RAM disk (initramfs) during `prescient install-hooks`. Because it lives in the RAM disk, it is available at boot time before your actual root filesystem is mounted. It doesn't need your broken system to be working (it works _around_ it).

It handles the entire rescue sequence automatically: probing block devices for your root partition, mounting the full virtual filesystem tree into a chroot jail, locating and mounting your Timeshift or Snapper snapshot partition, and handing off to `prescient undo` to perform the atomic rollback.

> **This command is only available at the `(initramfs)` emergency shell.** It is not callable from a running, booted system. For live system rollbacks, use [`prescient undo`](./undo.md) instead.

---

## Usage

```bash
# At the (initramfs) prompt - automatic root discovery
prescient-rescue

# If automatic discovery fails, mount manually first, then re-run
mount /dev/<your_partition> /root
prescient-rescue
```

### Options

| Flag     | Description                                                                    |
| -------- | ------------------------------------------------------------------------------ |
| _(none)_ | No flags. Root partition discovery and snapshot detection are fully automatic. |

> **!!Tip:** If you are unsure which block device is your root partition, run `blkid` at the `(initramfs)` prompt. Look for the partition with `TYPE="ext4"` or `TYPE="btrfs"` and a `LABEL` or path that matches your system's root. Then mount it manually and re-run `prescient-rescue`.

---

## Prerequisites

- [x] `prescient install-hooks` must have been run **before** the system broke — this embeds `prescient-rescue` into the initramfs image at install time
- [x] A working snapshot must exist - created by `prescient predict` (via Timeshift or Snapper) before the breaking update was applied
- [x] Access to the `(initramfs)` emergency shell - triggered automatically on boot failure, or by adding `break=bottom` to the kernel command line in GRUB
- [ ] `blkid` available in initramfs (standard on Ubuntu/Debian initramfs images; included by the prescient initramfs hook on Arch)

> **!!Important:** If `prescient install-hooks` was never run before the system broke, `prescient-rescue` will not be present in the RAM disk. In that case, you will need a live USB environment to perform recovery manually.

---

## Under the Hood

`prescient-rescue` executes a strict, ordered sequence. A `trap cleanup EXIT` is registered at startup so virtual mounts are always cleanly unmounted when the script exits, whether it succeeds, fails, or the user presses Ctrl+C.

### Stage 1 - Root Partition Discovery

Checks if `/root/etc` already exists (meaning the root filesystem is already mounted by the initramfs). If not, the script probes every available block device.

For each block device, it attempts two mount strategies:

1. **Standard mount** (`-o ro`) - looks for `/mnt/etc/os-release` to confirm it's a Linux root (covers ext4, XFS, and most standard filesystems)
2. **BTRFS subvolume mount** (`-o ro,subvol=@`) - covers systems using the standard BTRFS `@` root subvolume layout

On the first successful match, the partition is mounted read-write to `/root` and the probe loop exits.

If no partition is found automatically, the script prints manual recovery instructions and exits without attempting a rollback.

### Stage 2 - Virtual Filesystem Tree

Once the root partition is confirmed at `/root`, the script binds the full virtual filesystem tree into the chroot environment. This makes the broken system's hardware and kernel interfaces accessible from inside the chroot:

| Mount                       | Purpose                                                   |
| --------------------------- | --------------------------------------------------------- |
| `proc` → `/root/proc`       | Process and kernel info (required by many system tools)   |
| `sysfs` → `/root/sys`       | Hardware and driver interfaces                            |
| `/dev` → `/root/dev` (bind) | Block devices and input/output (required for disk access) |
| `tmpfs` → `/root/run`       | Runtime state directory (required by systemd tools)       |
| `devpts` → `/root/dev/pts`  | Terminal emulation (required for interactive chroot)      |
| `tmpfs` → `/root/tmp`       | Temporary file space inside chroot                        |

### Stage 3 - Snapshot Partition Detection

Before entering the chroot, the script locates and mounts the snapshot storage partition so `prescient undo` can find it from inside the chroot.

**Timeshift:** If `/root/etc/timeshift/timeshift.json` exists, the script reads the `backup_device_uuid` field directly using `awk`. It then resolves the UUID to a block device path using `blkid -U` and mounts it to `/root/run/timeshift/backup` (the exact path Timeshift expects).

**Snapper:** If `/.snapshots` exists on the root partition, the script identifies the root device from `/proc/mounts` and mounts the `@snapshots` BTRFS subvolume into `/root/.snapshots` (the path Snapper uses for its snapshot directory).

If neither snapshot tool's configuration is found, the script proceeds to the chroot anyway. `prescient undo` will handle the "no snapshot found" case from inside.

### Stage 4 - Chroot and Rollback Handoff

The script executes a chroot into `/root` and runs:

```sh
chroot /root /bin/bash -c "export PATH=/usr/local/bin:/usr/bin:/bin:\$PATH && prescient undo"
```

The `PATH` is explicitly set inside the chroot because the broken system's environment variables may be missing or corrupted. Control is handed to `prescient undo`, which performs the atomic, safety-gated rollback using the snapshot metadata from `/var/lib/prescient/last_snapshot.json`.

In rescue context, `prescient undo` uses filesystem-direct snapshot detection (reading Timeshift snapshot directories and Snapper `/.snapshots` directly) rather than calling their CLIs because D-Bus and systemd are/might not be not available inside a chroot.

### Stage 5 - Cleanup

The `trap cleanup EXIT` handler fires on exit regardless of outcome. It unmounts all virtual filesystems in reverse dependency order:

All unmount errors are suppressed (`2>/dev/null`) to prevent the cleanup itself from hanging in a partial state.

---

## Example Output

**Successful automatic recovery:**

```
==========================================
    PRESCIENT EMERGENCY RESCUE SYSTEM
==========================================
[*] Searching for root partition...
[+] Found Root Partition at /dev/sda2
[+] System root prepared at /root
[*] Timeshift config found. Ensuring snapshot partition is accessible...
[*] Target UUID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
[+] Mounting /dev/sda3 for Timeshift...
[+] Prescient Rollback Engine...

[prescient undo output appears here — snapshot selection and rollback]

==========================================
If the rollback was successful, type 'exit'.
[*] Cleaning up virtual mounts...
[+] Cleanup complete.
```

**BTRFS root with Snapper:**

```
==========================================
    PRESCIENT EMERGENCY RESCUE SYSTEM
==========================================
[*] Searching for root partition...
[+] Found BTRFS Root Subvolume at /dev/nvme0n1p2
[+] System root prepared at /root
[*] Snapper directory detected. Checking BTRFS subvolumes...
[+] Snapper BTRFS subvolume linked.
[+] Prescient Rollback Engine...
```

**Automatic discovery failed - manual mount required:**

```
==========================================
    PRESCIENT EMERGENCY RESCUE SYSTEM
==========================================
[*] Searching for root partition...
[-] CRITICAL: Could not find root partition automatically.
[-] Tip: Run 'blkid' to identify your Linux root partition (look for ext4 or btrfs).
[-] Please mount manually: 'mount /dev/<your_partition> /root' then run 'prescient-rescue'
[*] Cleaning up virtual mounts...
[+] Cleanup complete.
```

**After manual mount - re-run succeeds:**

```
(initramfs) mount /dev/nvme0n1p2 /root
(initramfs) prescient-rescue
==========================================
    PRESCIENT EMERGENCY RESCUE SYSTEM
==========================================
[+] System root prepared at /root
...
```

---

## Warnings

> `prescient-rescue` must be embedded in the initramfs **before** the system breaks. It is injected during `prescient install-hooks` via `update-initramfs -u` (Ubuntu/Debian) or `mkinitcpio -P` (Arch). If the hooks were never installed, the binary will not be present at the `(initramfs)` prompt. Use a live USB in that case.

> Snapshot partition mounting (Stage 3) requires that the snapshot device was configured and used at least once by `prescient predict` before the breakage. If no snapshot exists, `prescient undo` will report this from inside the chroot and no rollback will occur.

> The chroot environment has no active systemd or D-Bus session. `prescient undo` is specifically designed for this - it uses direct filesystem scanning to find snapshots rather than calling Timeshift or Snapper CLIs (which require D-Bus). Other system tools that depend on a running init system may not work correctly from inside this chroot.

> Do not interrupt the cleanup phase (`trap cleanup EXIT`). If virtual filesystems like `/root/proc` or `/root/dev` are left mounted, your next boot attempt may behave erratically. The cleanup trap handles this automatically on normal exit or Ctrl+C.

> LUKS-encrypted root partitions on `/dev/mapper/*` are probed, but the script does not handle decryption. You must unlock your LUKS volume manually at the `(initramfs)` prompt (`cryptsetup open /dev/sdXY root`) before running `prescient-rescue`.

---

## Related Commands

- [`prescient install-hooks`](./install-hooks.md) - Embeds `prescient-rescue` into the initramfs (must be done before a breakage occurs)
- [`prescient undo`](./undo.md) - The live-system rollback command called internally by this script
- [`prescient diagnose`](./diagnose.md) - If the system boots but is unstable, diagnose before reaching for rescue
- [`prescient predict`](./predict.md) - Creates the pre-update snapshot that `prescient-rescue` rolls back to
