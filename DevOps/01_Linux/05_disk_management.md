# Disk Management

**DevOps Track · Phase 1: Linux**

## Quick Concepts

| Concept | One-line definition |
|----------------------------------|----------------------------------------------------------------------|
| **Filesystem** | How data is organized on a block device (ext4, xfs, btrfs, tmpfs) |
| **Mount point** | A directory that a filesystem is attached to (`/`, `/mnt/data`) |
| **Block device** | Raw storage the OS sees as fixed-size blocks (`/dev/sda`, `/dev/nvme0n1`) |
| **Partition** | A subdivision of a disk (`/dev/sda1`) |
| **inode** | Metadata structure: permissions, owner, timestamps, block pointers — NOT the filename |
| **Disk full vs inode full** | Can run out of inodes (too many small files) even with free byte space |

---

## Quick Concepts — In Depth

### Filesystem

```bash
# A filesystem translates "I want to read /var/log/app.log"
# into actual block locations on disk.

# Common Linux filesystems:
# ext4      → most common on Linux VMs, good all-rounder, journaled
# xfs       → preferred for large files, high throughput, default on RHEL/Amazon Linux
# btrfs     → copy-on-write, snapshots, checksums — still maturing
# tmpfs     → in-memory (RAM), dies on reboot → /run, /dev/shm
# nfs       → network filesystem, remote server mounted locally
# overlayfs → used by Docker for container layers

df -T   # show filesystem type for every mount
# /dev/nvme0n1p1  ext4   50G  47G  2.1G  96%  /
```

### Block Device

```bash
lsblk
# NAME          MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
# nvme0n1       259:0    0   50G  0 disk           ← raw disk
# └─nvme0n1p1   259:1    0   50G  0 part /         ← partition 1, mounted at /

# Device naming conventions:
# /dev/sda, /dev/sdb     → SATA/SCSI disks (physical or virtual)
# /dev/nvme0n1           → NVMe SSD (EC2 instance store)
# /dev/xvdf              → Xen virtual disk (EBS on older EC2)
# /dev/vda               → VirtIO disk (KVM/QEMU VMs)
```

### inode

```bash
# Every file has two parts:
# 1. Directory entry (the filename) → points to an inode number
# 2. inode → stores: permissions, owner, timestamps, size, data block pointers
#             NOT the filename itself

# This explains:
# - Hard links: multiple names → same inode → same data
# - Deleted file still held open: name removed, inode lives until refcount = 0
# - mv within same filesystem is instant: just renames the directory entry
# - cp is slow: new inode + full data copy

ls -li /var/log/
# 131072 -rw-r--r-- 1 syslog syslog /var/log/syslog
# ^inode number
```

### Disk Full vs Inode Full

```bash
# ALWAYS check both during "No space left on device" incidents:
df -h    # byte usage
df -i    # inode usage

df -i
# Filesystem      Inodes   IUsed  IFree  IUse% Mounted on
# /dev/nvme0n1p1  3276800  3276800    0   100% /var
# ← 100% inodes — bytes may be fine, but no new files can be created

# Classic cause: millions of tiny session/temp files
ls /var/lib/php/sessions/ | wc -l   # if millions, that's your culprit
```

---

## Why This Matters for Backend/DevOps Work

```
- "Disk is 100% full" is one of the most common 3am pages — logs,
  temp files, or a runaway process writing unbounded data
- Attaching/growing an EBS volume on an EC2 instance
- Diagnosing "No space left on device" when df shows free space
  (inode exhaustion, or a deleted-but-still-open file)
- Mounting a network share or an extra disk for backups
```

---

## df — Disk Free (filesystem-level)

```bash
df -h                   # human-readable sizes, all mounted filesystems
df -h /var               # just the filesystem that /var lives on
df -i                     # INODE usage — critical second check
df -T                      # show filesystem type per mount
df -hT                      # type + human-readable together
df -h --total                # add a total row at the bottom
```

**Reading `df -hT` output:**

```
Filesystem     Type    Size  Used Avail Use% Mounted on
/dev/nvme0n1p1 ext4     50G   47G  2.1G  96% /
tmpfs          tmpfs   3.9G     0  3.9G   0% /dev/shm
/dev/nvme0n2p1 ext4    200G  180G   20G  90% /data

- / at 96%   → alert — logs or app data growing fast
- tmpfs       → in-memory, dies on reboot (safe for /tmp)
- /data       → separate data volume (keep data off OS disk)
  If /data fills → DB/uploads at risk
  If / fills → OS may fail to write pid files, sockets, logs
```

**Reserved blocks — why numbers don't add up to 100%:**

```bash
# ext4 reserves 5% of blocks for root by default
# At "100%" for regular users, root still has 5% headroom
# On a 50GB disk = 2.5GB reserved

sudo tune2fs -l /dev/nvme0n1p1 | grep "Reserved block"
sudo tune2fs -m 1 /dev/nvme0n1p1   # reduce to 1% (useful on data volumes)
```

---

## du — Disk Usage (directory/file-level)

```bash
du -sh /var/log                     # summary for the whole directory
du -sh /var/log/*                    # summary per item inside
du -h --max-depth=1 /var              # one level deep
du -h --max-depth=2 /var | sort -rh    # two levels, largest first

# Find ALL files over 100MB on root filesystem:
find / -xdev -type f -size +100M -exec du -h {} \; 2>/dev/null | sort -rh
# -xdev = don't cross filesystem boundaries
```

**Drill-down workflow — the right approach:**

```bash
# Start at /
du -h --max-depth=1 / 2>/dev/null | sort -rh
# → /var is 40GB

du -h --max-depth=1 /var | sort -rh
# → /var/log is 35GB

du -h --max-depth=1 /var/log | sort -rh
# → /var/log/nginx/access.log is 30GB (unrotated!)
```

**The `df` vs `du` disagreement — explained:**

```bash
# df says 48GB used. du of / says 30GB. Where's the missing 18GB?
#
# Answer: deleted files still held open by running processes.
# rm removes the directory entry (the name).
# But the kernel keeps disk blocks allocated until the last fd referencing
# the inode is closed — even after the file has no name.
# du walks the directory tree → can't see unnamed (deleted) files.
# df reports kernel-level block allocation → DOES count them.

# Find phantom deleted-but-open files:
lsof +L1 2>/dev/null
# +L1 = files with link count < 1 (deleted but still open)

# Example output:
# COMMAND  PID  USER  FD  TYPE  DEVICE    SIZE  NODE  NAME
# nginx   1234  root  3w  REG   8,1     2.1G   456   /var/log/nginx/access.log (deleted)
# ← 2.1GB log was deleted but nginx still has fd 3 pointing to it

# Fix WITHOUT restarting the process:
> /proc/1234/fd/3
# Redirects nothing into fd 3 → zeros the file → disk blocks freed immediately
# nginx keeps writing to the same fd with no error
```

---

## Senior Walkthrough: Disk Full — Find What's Eating Space

```bash
# 1. Confirm the problem and WHERE
df -h                              # which filesystem is full?
df -i                               # rule out inode exhaustion too

# 2. Walk down from root of the full filesystem
du -h --max-depth=1 / 2>/dev/null | sort -rh
# → probably points at /var

du -h --max-depth=1 /var 2>/dev/null | sort -rh
# → probably points at /var/log

du -h --max-depth=1 /var/log 2>/dev/null | sort -rh
# → find the exact offending file(s)

# 3. Common culprits
ls -lhS /var/log | head                         # huge unrotated log
find / -name "*.log" -size +500M 2>/dev/null     # oversized logs anywhere
find /tmp -size +100M 2>/dev/null                 # large temp files

# 4. Deleted-but-open file (df full, du doesn't explain it)
lsof +L1 2>/dev/null | grep deleted

# 5. Fix
truncate -s 0 /var/log/huge.log          # zero out WITHOUT deleting (keeps fd/inode)
gzip /var/log/app/app.log.1               # compress old rotated logs
find /var/log -mtime +30 -delete            # delete very old logs
> /proc/<pid>/fd/<fd_number>                  # free deleted-but-open file immediately
```

---

## truncate vs rm — When to Use Which

```bash
# rm big.log
# - Removes directory entry
# - Process has it open → disk NOT freed until process closes FD
# - No process has it open → disk freed immediately
# - File is gone — process gets write errors going forward

# truncate -s 0 big.log
# - File still exists, same path, same inode
# - Contents zeroed to 0 bytes immediately
# - Process keeps writing to the same fd — no error, no interruption
# - Disk blocks freed immediately even while process has it open

# USE truncate for: live log files any running process has open
# USE rm for:       old rotated logs no process is touching
```

---

## Inode Exhaustion — Deep Dive

```bash
# Symptom: "No space left on device" but df -h shows 20% free
df -i
# Filesystem      Inodes  IUsed   IFree IUse% Mounted on
# /dev/nvme0n1p1  3276800 3276800     0  100% /var
# ← 0 inodes left

# Find which directory has millions of files:
find / -xdev -printf '%h\n' 2>/dev/null | sort | uniq -c | sort -rn | head -5
# Counts files per directory — highest = culprit

# Common causes:
# /var/spool/postfix/maildrop  → stuck mail queue
# /var/lib/php/sessions         → old PHP sessions never cleaned
# /tmp                           → temp files from runaway process

# Fix PHP sessions:
find /var/lib/php/sessions -mtime +1 -delete

# Fix mail queue (verify first!):
postqueue -p | wc -l
sudo postsuper -d ALL
```

---

## mount / umount

### What Mounting Actually Does

```
A filesystem lives on a block device — it's just data in a specific format.
Mounting tells the kernel: "attach this filesystem at this directory path."
After mount, any path under /mnt/data transparently goes to that device.

The VFS (Virtual File System) layer provides a unified interface —
whether you're reading ext4, xfs, nfs, or tmpfs, the read() syscall
looks identical to your program.
```

```bash
mount                              # list all currently mounted filesystems
mount | column -t                    # readable aligned columns
cat /proc/mounts                      # kernel's authoritative view

sudo mount /dev/sdb1 /mnt/data              # auto-detect filesystem type
sudo mount -t ext4 /dev/sdb1 /mnt/data       # explicit type
sudo mount -t nfs server:/share /mnt/nfs       # NFS mount
sudo mount -o ro /dev/sdb1 /mnt/data            # read-only
sudo mount -o remount,rw /                       # remount with different options

sudo umount /mnt/data              # normal unmount
sudo umount -l /mnt/data            # lazy: detach now, clean up when last FD released
sudo umount -f /mnt/nfs              # force (for hung NFS — use carefully)
```

**`/etc/fstab` — persistent mounts across reboots:**

```bash
# Format: device  mountpoint  fstype  options  dump  fsck-order
UUID=abc123  /data  ext4  defaults,noatime,nofail  0  2
#                          │               │        │  └── fsck order: 0=skip, 1=root, 2=others
#                          │               │        └── dump: 0=skip
#                          │               └── nofail: don't halt boot if volume missing
#                          └── noatime: skip updating access timestamps (faster reads)

# Always use UUID — device letters (/dev/sdb) can shift between reboots
blkid /dev/sdb1
# /dev/sdb1: UUID="abc123-..." TYPE="ext4"

# Test fstab before rebooting:
sudo mount -a       # mount everything in fstab not yet mounted
# If no error: your fstab entry is syntactically valid
```

**"Device is busy" — umount fails:**

```bash
fuser -m /mnt/data              # which processes have files open here?
lsof +D /mnt/data                # detailed list of open files under this mount
cd /                             # move your shell out of the mount first
sudo umount /mnt/data
```

---

## fdisk / lsblk — Partitioning & Block Devices

```bash
lsblk                                    # tree: disk → partition → mountpoint
lsblk -f                                  # + filesystem type and UUID
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT,UUID  # custom columns

sudo fdisk -l                    # list partition tables of all disks
sudo fdisk -l /dev/sdb            # specific disk only
sudo parted -l                     # GPT-aware alternative (fdisk = MBR only)

# Create partition (interactive):
sudo fdisk /dev/sdb
# n = new, p = primary, w = write and exit

# Format:
sudo mkfs.ext4 /dev/sdb1         # ext4
sudo mkfs.xfs /dev/sdb1           # xfs (better for large files / databases)

blkid                              # UUIDs of all devices — use in fstab, not /dev/sdX
```

**Full EBS Volume Attach Workflow on EC2:**

```bash
# 1. Attach in AWS console/CLI, note device name (/dev/xvdf or /dev/nvme1n1)

# 2. Confirm it appeared
lsblk                            # /dev/xvdf with no MOUNTPOINT = success

# 3. Check if already formatted
sudo file -s /dev/xvdf
# "data"                → raw/unformatted → safe to mkfs
# "ext4 filesystem data" → already has data → DO NOT mkfs (would wipe it)

# 4. Format ONLY if new volume
sudo mkfs.ext4 /dev/xvdf

# 5. Mount
sudo mkdir -p /data
sudo mount /dev/xvdf /data

# 6. Persist in fstab
blkid /dev/xvdf
# UUID="a1b2c3-..."
echo 'UUID=a1b2c3-...  /data  ext4  defaults,nofail  0  2' | sudo tee -a /etc/fstab

# 7. Verify
sudo mount -a && echo "fstab OK"

# 8. Fix permissions
sudo chown deploy:deploy /data
```

---

## Senior Tips

```
1. Alert at 80% disk usage, not 95% — logs fill fast between check intervals.

2. Always check df -i too — inode exhaustion looks identical to disk-full
   errors but requires a completely different fix.

3. Never rm a live log file to free space — the process still has it open,
   so disk blocks stay allocated. Use truncate -s 0 instead.

4. Use UUIDs in /etc/fstab, not /dev/sdX — device letters shift between
   reboots when multiple disks are attached.

5. Add nofail to fstab options for cloud volumes — without it, if the volume
   is not attached at boot (e.g. EBS not yet propagated), the instance hangs
   at boot waiting for the mount, making it unreachable via SSH.
```

---

## Interview Angle

**Q: `df` shows 100% full but `du` can't find files adding up to that much — why?**

```
Deleted files still held open by running processes.

rm removes the directory entry (the name). But the kernel keeps disk
blocks allocated as long as any process has an open file descriptor
pointing to that inode. du walks the visible directory tree → can't see
these unnamed files. df reports kernel-level block allocation → does count them.

Find them:
  lsof +L1 2>/dev/null | grep deleted

Fix without restarting:
  > /proc/<pid>/fd/<fd_number>   ← truncates via fd, frees blocks immediately
```

**Q: "No space left on device" but df shows 20% free — what do you check?**

```
Two possibilities:

1. df -i — inode exhaustion
   100% inodes = no new files can be created, even with byte space free
   Fix: find directory with millions of tiny files, clean them up

2. lsof +L1 — deleted-but-open files
   Blocks allocated but invisible to du
   Fix: > /proc/<pid>/fd/<fd_number> or restart the process
```

**Q: Difference between `du -sh dir` and `df -h`?**

```
du: measures actual file/directory usage by walking the directory tree.
df: reports filesystem-level free/used space from kernel block allocation.

They can disagree:
- Deleted-but-open files: counted by df, invisible to du
- Filesystem overhead (metadata, reserved blocks): counted by df, not du
```

**Q: Why UUID in `/etc/fstab` instead of `/dev/sdb1`?**

```
Device names are assigned by the kernel at boot based on detection order.
Attach a new disk → /dev/sdb might become /dev/sdc on next reboot.
Your fstab entry would try to mount the wrong device (or fail entirely).

UUIDs are embedded in filesystem metadata at format time.
They follow the filesystem wherever it goes, regardless of device name.

blkid /dev/sdb1   # get the UUID
```

**Q: ext4 vs xfs — when would you choose each?**

```
ext4:
  - Most mature, safest general-purpose choice
  - Handles many small files well
  - Can be shrunk (xfs cannot)
  - Default on Debian/Ubuntu
  - Good for: OS partitions, general application data

xfs:
  - Better for large files and parallel I/O
  - Scales to 500TB+ filesystems
  - Better sustained throughput on NVMe
  - Cannot be shrunk, only grown
  - Default on RHEL/CentOS/Amazon Linux
  - Good for: /data volumes, database storage, log aggregation
```

**Q: What is `nofail` in fstab and why does it matter on EC2?**

```
Without nofail: if a volume listed in fstab is not available at boot,
the system halts at the mount step and waits — the instance becomes
unreachable via SSH.

On EC2, EBS volumes can take a moment to attach, or a volume might not
be attached at all (e.g. dev environment). nofail tells the kernel:
"if this mount fails, continue booting without it."

Always add nofail to non-root volume fstab entries on cloud instances.
```