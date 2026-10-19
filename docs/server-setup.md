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
| Music disk | a dedicated drive (about 1 TB), reserved for the stations |
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

## 2. Give the music its own drive

The music gets a whole physical drive instead of a slice of the shared VM storage, so no other VM
can ever eat into it, and a full music library can't fill up the storage other VMs live on.

1. In Proxmox, open the host, then **Disks**, and find the unused drive. Check the model and
   size twice: the next step erases it.
2. Select it and choose **Wipe Disk**.
3. Under **Disks → LVM-Thin**, choose **Create: Thinpool** on that drive and name the storage
   `radio`.

A 1 TB drive shows as about 930 GB here, because drive makers count in decimal and Proxmox
counts in binary.

It's a single drive with no redundancy. The VM's scheduled backup (step 9) is what protects the
music.

## 3. Create the VM

**Create VM** in Proxmox, with:

- **General:** name `abm-radio`; tick **Start at boot**.
- **OS:** the Ubuntu ISO from step 1.
- **System:** tick **Qemu Agent**.
- **Disks:** 40 GB on the fast VM storage, with **Discard** and **SSD emulation** ticked.
- **CPU:** 4 cores, type `host`.
- **Memory:** 4096 MB.
- **Network:** the default bridge, model VirtIO.

Before the first boot, add the music disk: **Hardware → Add → Hard Disk**, storage `radio`, with
nearly the whole drive (leave a few GB of headroom in the thin pool), **Discard** ticked.

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
