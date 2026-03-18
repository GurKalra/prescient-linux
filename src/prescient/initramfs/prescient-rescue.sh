#!/bin/sh

echo "=========================================="
echo "    PRESCIENT EMERGENCY RESCUE SYSTEM     "
echo "=========================================="

# Checking for real root filesystem
if [ -d "/root/etc" ];then
    echo "[+] Real root filesystem detected at /root"
    echo "[+] Preparing to enter chroot environment..."

    # Bind critical virtual filesystems
    mount -t proc proc /root/proc
    mount -t sysfs sys /root/sys
    mount -o bind /dev /root/dev

    echo "[+] Waking up Prescient Rollback Engine...'
    chroot /root /bin/bash -c "prescient undo"

    echo "=========================================="
    echo "If the rollback was successful, type 'reboot' or press Ctrl+Alt+Del."
else
    echo "[-] ERROR: Root filesystem is not mounted at /root."
    echo "[-] Prescient cannot automatically locate your hard drive in this state."
    echo "[-] Please mount your root partition manually to /root, then run 'prescient-rescue'."
fi