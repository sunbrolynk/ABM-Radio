# Server setup

How I build the ABM Radio server from nothing: a Proxmox VM running Ubuntu Server, with
AzuraCast installed by its official Docker installer. If the server ever has to be rebuilt,
this is the path. It's written for a Proxmox host, but everything from step 4 on works the same
on any machine running Ubuntu.

Nothing here names a real host, address or path on my network. Swap in your own.

## What it needs

AzuraCast's own guidance is 2 CPU cores and 2 GB of RAM at minimum, and 4 cores and 4 GB for
several stations. The VM below uses:

| | |
|---|---|
| CPU | 4 cores |
| RAM | 4 GB |
| System disk | 40 GB, on the host's fast VM storage |
| Music disk | 750 GB on a dedicated two-drive ZFS mirror |
| OS | Ubuntu Server 24.04 LTS |

## 1. Download the Ubuntu installer into Proxmox

In Proxmox, open the storage that holds ISO images (usually `local`), go to **ISO Images**, and
choose **Download from URL**:

- **URL:** `https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-live-server-amd64.iso`
- **Hash algorithm:** SHA-256
- **Checksum:** the value for `ubuntu-24.04.5-live-server-amd64.iso` in
  [Ubuntu's SHA256SUMS](https://releases.ubuntu.com/24.04/SHA256SUMS)

Proxmox checks the download against that checksum and fails the task if they don't match, so a
corrupted or tampered installer never gets used.

## 2. Give the music its own mirrored drives

The music gets two physical drives of its own, mirrored with ZFS: every block is on both, so one
drive can die without the station going quiet, and ZFS checksums catch and repair silent
corruption. No other VM can eat into it, and a full library can't fill the storage other VMs
live on.

**Check the drives before trusting them.** In Proxmox, open the host, then **Disks**, select
each candidate and choose **Show S.M.A.R.T. values**. "PASSED" isn't enough: on SATA drives,
`Reallocated_Sector_Ct`, `Current_Pending_Sector` and `Offline_Uncorrectable` should be 0, and on
SAS drives (`smartctl -a`) the grown defect list should be small and every uncorrected error
count 0. I found a drive that reported PASSED with over ten thousand pending sectors and couldn't
read its first block.

**Behind a Dell PERC in RAID mode** (such as the H730), a new drive stays hidden from Proxmox
until it's switched to pass-through. Dell's `perccli` (from Dell's support site, checked against
the SHA-256 Dell publishes) shows each slot and its state:

```
/opt/MegaRAID/perccli/perccli64 /c0/eall/sall show
/opt/MegaRAID/perccli/perccli64 /c0/e32/s<slot> set jbod
```

A drive in state `UGood` can be set to JBOD. A drive in state `UGUnsp` with a size of 0 KB is
almost always a pull from a storage array (NetApp `X425_…`, Hitachi `DKR5D-…` and the like),
formatted with 520-byte sectors; the PERC can't use it without a low-level reformat on a plain
SAS HBA. SMART for a drive still behind the PERC is readable with
`smartctl -a -d megaraid,<slot> /dev/sda`.

To find a drive's bay, read from it (`timeout 30 cat /dev/disk/by-id/<id> | wc -c`) and watch
for the bay whose activity light responds. A stuck failing drive shows a solid light instead of
a flicker.

Then build the mirror: **Disks → ZFS → Create: ZFS**, name `radio`, RAID level **Mirror**,
compression on, `ashift` 12, **Add Storage** ticked, and only the two music drives selected.

## 3. Create the VM

**Create VM** in Proxmox with **Advanced** ticked:

- **General:** name `ABM-Radio`; tick **Start at boot**.
- **OS:** the Ubuntu ISO from step 1.
- **System:** machine `q35`, SCSI controller `VirtIO SCSI single`, **Qemu Agent** ticked.
- **Disks:** 40 GB on the fast VM storage, with **Discard**, **SSD emulation** and
  **IO thread** ticked.
- **CPU:** 4 cores, type `host`.
- **Memory:** 4096 MiB.
- **Network:** the default bridge, model VirtIO.
- **Confirm:** leave **Start after created** unticked.

Then add the music disk: **Hardware → Add → Hard Disk**, `scsi1` on storage `radio`, 750 GB,
**Discard** and **IO thread** ticked. 750 GB leaves the roughly 900 GB mirror below 85% full,
where ZFS starts to slow down, and the disk can be grown later.

## 4. Install Ubuntu Server

Boot the VM and open the **Console**. In the installer:

- Pick the default **Ubuntu Server** install.
- Install on the 40 GB disk only. Leave the music disk alone; it's set up after the install.
- Tick **Install OpenSSH server**. Import your SSH key from GitHub if you use one there.
- Skip the optional snaps; Docker comes from AzuraCast's installer.

After the reboot, eject the ISO (**Hardware → CD/DVD Drive → Do not use any media**).

## 5. First login: updates, the guest agent and SSH

*Written up as I do it.*

## 6. Mount the music disk

*Written up as I do it.*

## 7. Install AzuraCast

*Written up as I do it,* using AzuraCast's official Docker installer from
[azuracast.com](https://www.azuracast.com).

## 8. Create the station

*Written up as I do it.* The first station is **ABM Lofi** (short name `lofi`): AutoDJ on with a
2-3 second crossfade, ReplayGain on, an MP3 128 kbps mount plus an efficient AAC or Opus mount,
and listener requests off.

## 9. Backups and updates

*Written up as I do it.* The plan: AzuraCast's built-in daily backup kept for 7 days, a scheduled
Proxmox backup of the whole VM (music disk included), and AzuraCast's own updater on the stable
channel.

## 10. Keeping it private until launch

*Written up as I do it.* The admin pages stay on the local network or VPN only. Nothing is
exposed to the internet until the launch review.
