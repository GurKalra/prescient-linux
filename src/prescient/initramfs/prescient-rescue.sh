#!/bin/sh

echo "=========================================="
echo "    PRESCIENT EMERGENCY RESCUE SYSTEM     "
echo "=========================================="

# Cleanup trap to prevent lockups
cleanup() {
    echo  "[*] Cleaning up virtual mounts..."
    umount /root/run/timeshift/backup 2>/dev/null
    umount /root/dev/pts 2>/dev/null
    umount /root/dev     2>/dev/null
    umount /root/run     2>/dev/null
    umount /root/tmp     2>/dev/null
    umount /root/proc    2>/dev/null
    umount /root/sys     2>/dev/null
    echo "[+] Cleanup complete."
}
trap cleanup EXIT

# Trying to find the root partition if not mounted
if [ ! -d "/root/etc" ]; then
    echo "[*] Searching for root partition..."
    mkdir -p /mnt

    for part in /dev/sd* /dev/vd* /dev/nvme* /dev/mapper/*; do
        [ -b "$part" ] || continue
        # EXT4/XFS
        mount -o ro "$part" /mnt >/dev/null 2>&1
        if [ -f "/mnt/etc/os-release" ]; then
            echo "[+] Found Root Partition at $part"
            umount /mnt
            mount "$part" /root
            break
        fi
        umount /mnt >/dev/null 2>&1

        # BTRFS subvolumes
        mount -o ro,subvol=@ "$part" /mnt >/dev/null 2>&1
        if [ -f "/mnt/etc/os-release" ]; then
            echo "[+] Found BTRFS Root Subvolume at $part"
            umount /mnt
            mount -o subvol=@ "$part" /root
            break
        fi
        umount /mnt >/dev/null 2>&1
    done
fi

# Checking for real root filesystem
if [ -d "/root/etc" ];then
    echo "[+] System root prepared at /root"
    mount -t proc proc /root/proc
    mount -t sysfs sys /root/sys
    mount -o bind /dev /root/dev

    mount -t tmpfs tmpfs /root/run
    chmod 755 /root/run
    mount -t devpts devpts /root/dev/pts
    mount -t tmpfs tmpfs /root/tmp

    # Timeshift filesystem reading
    TIMESHIFT_CONFIG="/root/etc/timeshift/timeshift.json"
    if [ -f "$TIMESHIFT_CONFIG" ]; then
        echo "[*] Timeshift config found. Ensuring snapshot partition is accessible..."
        mkdir -p /root/run/timeshift/backup

        BACKUP_UUID=$(awk -F'"' '/backup_device_uuid/ {print $4}' "$TIMESHIFT_CONFIG")

        if [ -n "$BACKUP_UUID" ]; then
            echo "[*] Target UUID: $BACKUP_UUID"
            BACKUP_DEV=$(blkid -U "$BACKUP_UUID" 2>/dev/null)

            if [ -n "$BACKUP_DEV" ]; then
                echo "[+] Mounting $BACKUP_DEV for Timeshift..."
                mount "$BACKUP_DEV" /root/run/timeshift/backup
            else
                echo "[-] Warning: blkid could not find device for UUID $BACKUP_UUID"
            fi
        fi
    fi

    # Snapper filesystem reading
    if [ -d "root/.snapshots" ]; then
        echo "[*] Snapper directory detected. Checking BTRFS subvolumes..."
        ROOT_DEV=$(awk '$2 == "/root" {print $1}' /proc/mounts)
        if [ -n "$ROOT_DEV" ]; then
            mount -o subvol=@snapshots "$ROOT_DEV" /root/.snapshots >/dev/null 2>&1
            echo "[+] Snapper BTRFS subvolume linked."
        fi
    fi

    echo "[+] Prescient Rollback Engine..."
    chroot /root /bin/bash -c "export PATH=/usr/local/bin:/usr/bin:/bin:\$PATH && prescient undo"

    echo "=========================================="
    echo "If the rollback was successful, type 'exit'."
else
    echo "[-] CRITICAL: Could not find root partition automatically."
    echo "[-] Tip: Run 'blkid' to identify your Linux root partition (look for ext4 or btrfs)."
    echo "[-] Please mount manually: 'mount /dev/<your_partition> /root' then run 'prescient-rescue'"
fi