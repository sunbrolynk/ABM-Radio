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

- Pick the default **Ubuntu Server** install (not minimized), with DHCP networking.
- **Use an entire disk** and pick the **40 GB** disk only. Leave the music disk alone; it's set
  up after the install.
- On the storage summary, check `ubuntu-lv`: the installer often sizes it to only half the
  disk. **Edit** it to the maximum size it offers.
- Server name `abm-radio`, your own user, and a strong password from a password manager.
- Tick **Install OpenSSH server**. Import your SSH key from GitHub if you use one there.
- Skip Ubuntu Pro and the optional snaps; Docker comes from AzuraCast's installer.

After the reboot, eject the ISO (**Hardware → CD/DVD Drive → Do not use any media**). Give the
VM a DHCP reservation on the router so its address never changes.

## 5. Updates and the guest agent

```
sudo apt update && sudo apt full-upgrade -y && sudo apt install -y qemu-guest-agent && sudo systemctl start qemu-guest-agent && sudo reboot
```

The guest agent lets Proxmox shut the VM down cleanly, freeze it for consistent backups, and
show its address. Ubuntu's automatic security updates (`unattended-upgrades`) are on by default.

## 6. Mount the music disk where Docker keeps its data

Everything AzuraCast stores (its database, settings and every station's media) lives in Docker's
data folder, so the music disk is mounted there before Docker is installed. The 40 GB disk then
holds only Ubuntu.

```
sudo mkfs.ext4 -L radio-data /dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1
sudo mkdir -p /var/lib/docker
echo 'LABEL=radio-data /var/lib/docker ext4 defaults,discard 0 2' | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount -a && df -h /var/lib/docker
```

The disk is picked by its permanent `scsi1` name, never `sdb`, so the system disk can't be
formatted by mistake. There's deliberately no `nofail`: if the music disk ever goes missing, the
VM stops at boot instead of quietly starting AzuraCast on the small system disk.

## 7. Install AzuraCast

AzuraCast's official installer, as [its docs](https://www.azuracast.com) give it:

```
sudo mkdir -p /var/azuracast && cd /var/azuracast
sudo curl -fsSL https://raw.githubusercontent.com/AzuraCast/AzuraCast/main/docker.sh -o docker.sh
sudo chmod a+x docker.sh && sudo ./docker.sh install
```

- Let it install Docker.
- Switch to the **Stable** release channel when asked. The script updates itself and stops, so
  run `sudo ./docker.sh install` again.
- Keep the default ports, skip any domain or certificate questions until launch, and say yes to
  blocking common bots and crawlers.

When it finishes it suggests the public IP; open the VM's LAN address over `http://` instead.
Create the super administrator with a password from a password manager, then turn on
**two-factor authentication** under the account's profile straight after the setup wizard.

**Administration → System Settings:**

| Setting | Value |
|---|---|
| Site Base URL | the LAN address for now; `https://stream.audiobookmanager.com` at launch |
| Instance Name | `ABM Radio` |
| Use Web Proxy for Radio | on (streams go through ports 80/443, nothing else opened) |
| Days of Playback History | 30 |
| Listener Analytics Collection | **Limited** (totals only, no per-listener IP tracking) |
| Always Use HTTPS | off until the stream domain has its certificate |
| API Access-Control-Allow-Origin | `https://radio.audiobookmanager.com` |
| Allow Raw Liquidsoap Configuration | off |
| Filter Local User-provided URLs | on |
| Allow Web Hooks | off until the Discord alerts exist |

## 8. Create the station

The first station is **ABM Lofi**, URL stub `lofi`, with its website set to
`https://radio.audiobookmanager.com/lofi`, public pages on and on-demand streaming off.

**Edit Station Settings → AutoDJ:** Liquidsoap, **Smart** crossfade at **2.5 s**, ReplayGain on,
**Master_me** post-processing with the **Music General** preset at **-16 LUFS**, and duplicate
prevention at **60 minutes** (raise it as the library grows; a window longer than the whole
library leaves AutoDJ nothing it's allowed to play). Song requests and streamers/DJs off.

**Playlists:** one playlist, `Lofi` (general rotation, no schedule). In **Media → Music Files**,
create a `lofi` folder and link it to the playlist (**Set Playlists**), plus an `incoming` folder
linked to nothing, where new tracks wait until they're approved.

**Holiday playlists** (Halloween first): a **General Rotation** playlist with a low weight (1, next to
LoFi's 3, so about one track in four), scheduled 00:00 to 23:59 across the holiday's date range,
and linked to its own folder. AutoDJ picks between general-rotation playlists at random by weight,
so holiday tracks mix into the lofi instead of taking over. Start and end times must differ (the
same time means "play once a day"), and the schedule's dates include the year, so move them
forward every year. Leave a holiday playlist disabled until it has approved tracks: an enabled,
scheduled, empty playlist stalls AutoDJ (see Troubleshooting).

**Mount Points:** `/radio.mp3` at **MP3 128 kbps** (the default mount, for compatibility) and
`/radio.aac` at **AAC 96 kbps** (better sound per bit, plays on Apple devices too).

## 9. Backups

- **AzuraCast (Administration → Backups):** nightly at 03:00, 7 copies, media excluded. It holds
  the settings, database, playlists and history.
- **Proxmox (Datacenter → Backup):** the whole VM, music disk included, nightly at 03:30 in
  snapshot mode with ZSTD, keeping 7 daily and 4 weekly copies. Run it once by hand to test it.

The music itself is also protected by the ZFS mirror, and the catalog records every track's
source and sha256, so any file can be fetched again and checked.

## 10. Updates and keeping it private until launch

*Written up as I do it.* AzuraCast updates through its own updater on the stable channel. The
admin pages stay on the local network or VPN only, and nothing is exposed to the internet until
the launch review.

## Troubleshooting

**The dashboard says "Station Offline" (playlist "default") while music plays, and "Record not
found" keeps popping up.** Liquidsoap's log shows `nextsong ... Queue is empty!` and `AutoDJ could
not be initialized`: Liquidsoap is playing its playlist file directly while AzuraCast's queue
builder has nothing to give it. Fix: delete empty playlists (including the default one), disable
any scheduled playlist that's still empty, clear the queue in **Administration → System
Debugger**, then **Restart Broadcasting**.

**A track moved out of a playlist folder still plays in that playlist.** A folder link only adds
files to its playlist; moving a file out doesn't remove it. Untick the old playlist under the
file's **Playlists** as well.

**FMA cover art shows as broken in the Liquidsoap log** (`No JPEG data found in image`). FMA's
resized image links serve WebP labelled as JPEG. The tagging scripts take covers from FMA's
original files and embed only real JPEG or PNG, so this only applies to files tagged some other
way.
