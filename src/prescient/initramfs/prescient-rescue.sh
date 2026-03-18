#!/bin/sh

echo "=========================================="
echo "    PRESCIENT EMERGENCY RESCUE SYSTEM     "
echo "=========================================="

# Trying to find the root partition if not mounted
if [ ! -d "/root/etc" ]; then
    echo "[*] Searching for root partition..."
    for part in /dev/sd* /dev/vd* /dev/nvme* /dev/mapper/*; do
        [ -b "$part" ] || continue
        mount -o ro "$part" /mnt >/dev/null 2>&1
        if [ -f "/mnt/etc/os-release" ]; then
            echo "[+] Found Root Partition at $part"
            umount /mnt
            mount "$part" /root
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

    echo "[+] Prescient Rollback Engine..."
    chroot /root /bin/bash -c "prescient undo"

    echo "=========================================="
    echo "If the rollback was successful, type 'exit'."
else
    echo "[-] CRITICAL: Could not find root partition automatically."
    echo "[-] Tip: Run 'blkid' to identify your Linux root partition (look for ext4 or btrfs)."
    echo "[-] Please mount manually: 'mount /dev/<your_partition> /root' then run 'prescient-rescue'"
fi