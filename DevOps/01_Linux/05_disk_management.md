# Disk Management

**DevOps Track · Phase 1: Linux**

## Quick Concepts

- **Filesystem** = how data is organized on a block device (ext4, xfs, btrfs)
- **Mount point** = a directory that a filesystem/device is attached to (`/`, `/mnt/data`)
- **Block device** = a raw storage device the OS sees as fixed-size blocks (`/dev/sda`, `/dev/nvme0n1`)
- **Partition** = a subdivision of a disk (`/dev/sda1`)
- **inode** = metadata structure describing a file (permissions, owner, block pointers) — separate from the filename
- **Disk full vs inode full** — you can run out of inodes (too many small files) even with free space

---

## Why This Matters for Backend/DevOps Work

```
- "Disk is 100% full" is one of the most common 3am pages — logs,
  temp files, or a runaway process writing unbounded data
- Attaching/growing an EBS volume on an EC2 instance
- Diagnosing "No space left on device" when df shows free space
  (classic inode exhaustion, or a deleted-but-still-open file)
- Mounting a network share or an extra disk for backups
```

---

## df — Disk Free (filesystem-level)

```bash
df -h                       # human-readable sizes, all mounted filesystems
df -h /var                    # usage of the filesystem containing /var
df -i                            # INODE usage, not byte usage — critical second check
df -T                              # show filesystem type (ext4, xfs, tmpfs...) per mount
```

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1   50G   47G  2.1G  96% /
tmpfs           3.9G     0  3.9G   0% /dev/shm

96% on / is a page-worthy alert threshold in most setups.
```

---

## du — Disk Usage (directory/file-level)

```bash
du -sh /var/log                # summary, human-readable, one directory
du -sh /var/log/*                 # summary PER item inside (great for hunting)
du -h --max-depth=1 /var           # one level deep, human-readable
du -a /var/log | sort -rn | head -20  # every file, sorted by size, top 20
```

```bash
# Practical: which subdirectory of /var is eating space
du -h --max-depth=1 /var | sort -rh

# Practical: largest files anywhere on disk
find / -xdev -type f -size +100M -exec du -h {} \; 2>/dev/null | sort -rh | head -10
```

---

## Senior Walkthrough: Disk Full — Find What's Eating Space

```bash
# 1. Confirm the problem and WHERE
df -h                              # which filesystem is full?
df -i                                # rule out inode exhaustion too

# 2. Walk down from root of the full filesystem
du -h --max-depth=1 / 2>/dev/null | sort -rh
# → probably points at /var

du -h --max-depth=1 /var 2>/dev/null | sort -rh
# → probably points at /var/log

du -h --max-depth=1 /var/log 2>/dev/null | sort -rh
# → find the exact offending log file(s)

# 3. Common culprits
ls -lhS /var/log | head            # huge single log file (unrotated?)
find / -name "*.log" -size +500M 2>/dev/null   # oversized logs anywhere

# 4. A SNEAKY one — df shows full but du doesn't find it:
#    a deleted file still held open by a running process
lsof +L1 2>/dev/null | grep deleted
# → restart or truncate the offending process's log fd:
#    > /proc/<pid>/fd/<fd_number>

# 5. Fix
truncate -s 0 /var/log/huge.log          # zero out without deleting (keeps the fd/inode)
gzip /var/log/app/app.log.1               # compress old rotated logs
find /var/log -mtime +30 -delete            # delete very old logs
```

```
Why does `df` sometimes not match `du`'s findings?

If a process still has a file open, deleting it (rm) frees the
directory entry but the KERNEL keeps the disk blocks allocated until
the process closes the file descriptor. df sees it as used; du (which
walks the visible filesystem tree) does not, because the file no
longer has a name. This is the #1 "df and du disagree" cause.
```

---

## mount / umount

```bash
mount                              # list all currently mounted filesystems
mount | column -t                    # readable columns

sudo mount /dev/sdb1 /mnt/data          # mount a device to a directory
sudo mount -t nfs server:/share /mnt/nfs  # mount a network filesystem, specify type
sudo mount -o remount,rw /                  # remount root read-write (e.g. after fsck)

sudo umount /mnt/data                          # unmount
sudo umount -l /mnt/data                         # lazy unmount (detach now, cleanup when free — use if "device busy")

# persistent mounts on boot: /etc/fstab
# /dev/sdb1   /mnt/data   ext4   defaults   0   2
```

```bash
# "device is busy" troubleshooting
fuser -m /mnt/data                 # who's using this mount
lsof +D /mnt/data                    # list open files under this path
```

---

## fdisk / lsblk — Partitioning & Block Devices

```bash
lsblk                             # tree view of all block devices + partitions + mounts
lsblk -f                            # + filesystem type and UUID

sudo fdisk -l                          # list partition tables of all disks
sudo fdisk /dev/sdb                      # interactive partitioning (n=new, d=delete, p=print, w=write)

sudo mkfs.ext4 /dev/sdb1                    # format a new partition
sudo mkfs.xfs /dev/sdb1                       # xfs alternative

blkid                                          # show UUIDs of all devices (use in fstab, not /dev/sdX which can shift)
```

```
Typical "attach a new EBS volume on EC2" flow:
  1. Attach volume in AWS console/CLI
  2. lsblk                    → confirm it shows up as /dev/xvdf (unformatted)
  3. sudo mkfs.ext4 /dev/xvdf   → format it (SKIP if reattaching existing data!)
  4. sudo mkdir /data
  5. sudo mount /dev/xvdf /data
  6. blkid /dev/xvdf → add UUID entry to /etc/fstab for persistence across reboot
```

---

## Senior Tip

```
1. Alert at 80% disk usage, not 95% — logs can fill a disk fast
   between check intervals.
2. Always check `df -i` (inodes) too — a directory full of millions
   of tiny files (session caches, thumbnails) can exhaust inodes while
   df -h still shows plenty of free space.
3. Never `rm` a huge log file a live process has open if you need the
   space back immediately — use `truncate -s 0` instead, or the space
   won't be freed until the process closes/restarts.
4. Use UUIDs (blkid) in /etc/fstab, not /dev/sdX — device letters can
   shift between reboots depending on what's attached.
```

## Interview Angle

**Q: `df` shows 100% full but `du` can't find files adding up to that much — why?**
A process is holding a deleted file open. The kernel keeps disk blocks allocated until the last file descriptor referencing it is closed, even though the file has no name left in the directory tree that `du` walks. Find it with `lsof +L1 | grep deleted` and restart/truncate the offending process.

**Q: Difference between `du -sh dir` and `df -h`?**
`du` measures actual file/directory usage by walking the tree; `df` reports filesystem-level free/used space from the kernel's block allocation view. They can disagree (see above) or differ slightly due to reserved blocks and filesystem overhead.

**Q: Why use `blkid`/UUID in fstab instead of `/dev/sdb1`?**
Device names can be reassigned across reboots based on detection order, especially with multiple attached volumes. UUIDs are stable identifiers tied to the filesystem itself.
