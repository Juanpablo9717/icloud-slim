# icloud-slim

[Español](README.es.md)

Frees up **iCloud Photos** storage by re-compressing the videos, photos, screen recordings and screenshots that take far more space than they need. It keeps the **date, order, location, albums, favorites and people**, and the quality loss isn't visible in normal viewing.

Everything runs on your Mac. Nothing is uploaded anywhere except back to your own iCloud Photos.

**Real result:** 61 iPhone and Android videos went from 51.5 GB to 12.8 GB (−75 %), with an average VMAF of 97.7. VMAF is a 0–100 visual quality score where anything above 93 looks identical to the original.

---

## Contents

- [What it does](#what-it-does)
- [Setup (step by step)](#setup-step-by-step)
- [Usage](#usage)
- [Stopping and resuming](#stopping-and-resuming)
- [Settings](#settings)
- [Help and troubleshooting](#help-and-troubleshooting)
- [Technical details](#technical-details)
- [Uninstall](#uninstall)

---

## What it does

Phones record video in real time, so they store it in a very wasteful way: one minute of iPhone 4K can weigh 400 MB. icloud-slim takes each heavy video and re-packs it calmly and efficiently. It's like re-folding the clothes in a suitcase: same clothes, less space.

For each item it:

1. **downloads** the original from iCloud,
2. **compresses** it on the Mac's video chip and checks the result (duration, date and location must match the original),
3. **saves** the compressed copy to Photos, in the same albums and with the same date, place, favorite and keywords,
4. **keeps a copy of the original** on your Mac in `~/icloud-slim/originals-backup/<year>/<month>/`, under its original name,
5. **moves the original to Recently Deleted**, in batches of about 20 GB. macOS asks you to confirm each batch, and processing keeps going while the dialog waits.

Items in Recently Deleted [don't count toward iCloud storage](https://support.apple.com/en-us/108922), so the space is freed as soon as you confirm. Originals stay recoverable there for 30 days, and the local backup is yours to keep or delete.

**What does NOT change**

| | |
|---|---|
| Resolution, frame rate, sound | Identical (4K stays 4K; the audio is copied as is) |
| HDR | Kept (10-bit HLG) |
| Date, time and order in the library | Identical |
| Location | Identical: shows on the map and in place search |
| Albums, favorite, title, description, keywords | Copied over |
| People and pets | Their names are added as keywords, so searching by name works right away. Photos also recognizes the faces again on its own after a while |

**What DOES change**

- **Less fine detail** in very busy scenes (leaves, water, confetti, dark scenes). You'd notice it only by pausing and zooming in.
- **Dolby Vision becomes standard HDR (HLG).** Bright highlights may look slightly different on Dolby Vision screens.
- **Edits and Memories** made on the original don't carry over.
- **Cinematic mode** videos lose the ability to change focus afterwards.
- **Screenshots** go from PNG/JPEG to HEIC, Apple's modern format. They look the same and weigh about half as much.
- **Heavy JPEG photos** (from a camera, an Android phone, an old iPhone…) also become HEIC, at a higher quality than screenshots. Each one is compared with its original and left as it was if it would look worse. Light ones, like WhatsApp photos, aren't touched: they're already compressed and redoing them would only lose quality.

**What it never touches:** photos already in HEIC (what iPhones take today), Live Photos, Android motion photos, bursts, RAW, photos edited in Photos, slow-motion videos, hidden items, shared albums, the iCloud Shared Library, and anything that is already light enough.

---

## Setup (step by step)

**You need:** a Mac with Apple silicon (M1 or later), [Homebrew](https://brew.sh), and iCloud Photos turned on in the Photos app. Tested on an M1 Max with macOS 15 Sequoia.

### 1. Download it and open a terminal in it

Use **Terminal** or **iTerm2**. The macOS permission prompts only show up there; terminals embedded in other apps (VS Code, the Claude app, …) don't get them.

```bash
git clone https://github.com/Juanpablo9717/icloud-slim.git
cd icloud-slim
```

### 2. Install the tools (once)

```bash
./icloud-slim install
```

This installs ffmpeg, exiftool and osxphotos, all free and open source. It takes a few minutes.

### 3. Grant the permissions (once)

```bash
./icloud-slim permissions
```

macOS will show two prompts. Accept both:

| Prompt | Choose |
|---|---|
| **"Terminal" would like to access your Photos** | **Allow Full Access** (not "Limit Access") |
| **"Terminal" wants access to control "Photos"** | **Allow** / **OK** |

It shows a 3-step checklist with what to do at each step (the macOS windows may open behind other windows). It should end with ✓ on all three and "All set". If a step fails it stops and tells you how to fix it.

**If no prompt appears, or it says FAILED:**

1. Open **System Settings → Privacy & Security → Photos** and set your terminal to **Full Access**.
2. Open **System Settings → Privacy & Security → Automation**, find your terminal and turn on **Photos**.
3. If your terminal isn't listed, reset the permission and try again:
   ```bash
   tccutil reset Photos com.apple.Terminal        # Terminal
   tccutil reset Photos com.googlecode.iterm2     # iTerm2
   ```
   Then quit the terminal completely (⌘Q), reopen it, and run `./icloud-slim permissions` again.

### 4. While it runs

- **Keep the Mac plugged in, and the lid open** (or use an external display). icloud-slim stops the Mac from going to sleep on its own, but closing the lid still puts it to sleep.
- **Leave Photos alone.** It may open by itself; that's expected.
- **Watch for the "delete" dialog** every ~20 GB. Confirm it to free the iCloud space.

---

## Usage

### The menu (easiest)

```bash
./icloud-slim
```

Opens an arcade-style menu: pick with ↑↓, Enter to choose, Esc to go back, q to quit.

| Item | What it does |
|---|---|
| VIDEOS, PHOTOS, SCREEN RECORDINGS, SCREENSHOTS, EVERYTHING | Shows how many are left and how much you'd save; then START, START WITH ONLY THE 10 BIGGEST, or SHOW THE LIST (dry run) |
| ANALYZE LIBRARY · STATS & ERRORS · DEMO | The `analyze`, `status` and `demo` commands |
| SETUP | A checklist (tools, Photos access, control of Photos, right terminal). Press Enter on any ✗ to fix it |
| SETTINGS | Language (English/Español) and the options below, saved for next time |
| HOW IT WORKS | Tabs: in short (what you gain and what changes), videos, photos, safety net, technical details, problems, keys |

The HI-SCORE is the space saved so far. The runs stay greyed out until SETUP is all ✓.

### Commands

Everything in the menu also works as a command, handy for scripts:

```bash
./icloud-slim --help        # all commands
./icloud-slim <command> --help
```

### 1. See what you'd save (changes nothing)

```bash
./icloud-slim analyze
```

Shows what takes space (by type, source, resolution and year), what can be compressed, the estimated savings and the 15 largest videos. The report is saved to `~/icloud-slim/reports/`.

### 2. Try it on a few

```bash
./icloud-slim process --batch 3
```

Processes the 3 heaviest videos. Open Photos and compare them: quality, date, place, album.

### 3. Process everything

```bash
./icloud-slim process                       # all videos
./icloud-slim process --type photos         # heavy JPEG photos → HEIC
./icloud-slim process --type recordings     # screen recordings
./icloud-slim process --type screenshots    # screenshots
./icloud-slim process --type all            # everything
./icloud-slim process --dry-run             # list what would be processed, touch nothing
```

It always starts with whatever saves the most. While it runs you'll see a live panel with:

- the overall progress and the time left,
- the iCloud space saved, split into what's already freed and what will be freed at the next deletion,
- the items in progress (up to 2 compressing and 1 downloading at once),
- the network speed,
- failures, which stay pinned so they don't scroll away,
- the recent items, each with its time, result, duration and how long ago it finished.

The panel adapts to the window size. To preview it without touching your library, run `./icloud-slim demo`.

### 4. Check the results

```bash
./icloud-slim status
```

Shows the space saved, the time spent, the state of every item and any errors. It's also saved to `~/icloud-slim/metrics.md`.

---

## Stopping and resuming

Press **Ctrl+C** at any time, then run **the same command** again to continue where it left off.

- Every step of every item is recorded as soon as it finishes, so nothing is downloaded, compressed or imported twice.
- The item that was downloading when you stopped is downloaded again from scratch. An item that was already downloaded is reused.
- Failed items are retried automatically on the next run, up to 3 times. After that, use `--retry`.
- Compressed copies carry an invisible marker (XMP metadata), so they're never compressed again, not even from another Mac.

---

## Settings

The menu's **SETTINGS** screen changes these and saves them to `~/icloud-slim/settings.json`: language (English by default, or Español), videos compressing at once, deletion batch size, backup, VMAF and animation. Command-line flags override them for a single run.

### Command options (`process`)

| Option | Default | What it does |
|---|---|---|
| `--type videos\|photos\|recordings\|screenshots\|all` | `videos` | What to process |
| `--batch N` | all | Only the N largest items |
| `--uuid ID …` | | Only these items |
| `--dry-run` | | List what would be processed, change nothing |
| `--parallel N` | `2` | Videos compressing at once. Use `1` on an older or busy Mac. More than 2 rarely helps: most Macs have 1 or 2 video encoders |
| `--delete-every GB` | `20` | Ask to delete originals every this many GB (also every 500 items) |
| `--no-backup` | | Don't keep a local copy of the originals |
| `--vmaf` | | Measure the visual quality of every video (much slower) |
| `--retry` | | Retry items that already failed 3 times |
| `--no-fun` | | Plain panel, without the space animation |

### Work folder

Everything lives in `~/icloud-slim`. To use another location, e.g. an external drive, set `ICLOUD_SLIM_DIR`:

```bash
ICLOUD_SLIM_DIR=/Volumes/Backup/icloud-slim ./icloud-slim process
```

| Path | What it is |
|---|---|
| `originals-backup/<year>/<month>/` | **Your originals.** Delete them when you're happy with the results |
| `state.db` | Progress of every item (SQLite). Don't delete it while you're still processing |
| `settings.json` | Your SETTINGS from the menu |
| `logs/` | Detailed log of every run |
| `reports/`, `metrics.md` | Output of `analyze` and `status` |
| `originals/`, `compressed/` | Temporary, cleaned up after each item |

### Quality (in `icloud_slim.py`)

| Constant | Default | Meaning |
|---|---|---|
| `BITRATE` | 4K → 20 Mbps, 1080p → 8 Mbps, smaller → 4 Mbps | Target bitrate by the video's long side. Raise it for more quality and less savings |
| `MARGIN` | `1.2` | Only compress videos at least 20 % above their target |
| `HEIC_QUALITY` | `80` | Screenshot quality (0–100) |
| `PHOTO_QUALITY` | `90` | Photo quality (0–100) |
| `PHOTO_BPP` | `1.2` | Expected bits per pixel of a photo at `PHOTO_QUALITY`. A JPEG is a candidate above `MARGIN` × this |
| `PHOTO_MIN_VMAF` | `93` | A photo scoring below this is left as it was |
| `DELETE_EVERY_GB`, `DELETE_EVERY_ITEMS` | `20`, `500` | Deletion batch size |
| `MAX_ATTEMPTS` | `3` | Automatic retries per item |

---

## Help and troubleshooting

**`permissions` says FAILED, or no prompt appears.** See step 3 of [Setup](#3-grant-the-permissions-once). Make sure you're in Terminal or iTerm2, not in a terminal inside another app.

**"iCloud download failed … Could not get video for asset".** iCloud refused to hand over that original right now (it shows the real reason and how long it tried). When that happens icloud-slim automatically retries through the Photos app itself, which usually works. If it still fails it's usually temporary, or the item is still syncing from another device. It's retried on the next run. If an item keeps failing, open it in Photos and play it once; that forces the download. VPNs can slow iCloud down a lot.

**Many "Can't import 1 item … Unknown error" windows in Photos.** Photos gets stuck after a few thousand imports in one session and starts rejecting every file, even good ones. icloud-slim restarts Photos on its own every 1,000 imports, and right away if it rejects 3 files in a row (that also closes those windows). If it still rejects files after restarting, the run stops instead of failing everything. Nothing is lost: originals are only deleted after their compressed copy is saved, and whatever was left is imported on the next run without downloading again.

**I clicked "Don't Allow" in the delete dialog.** Nothing is lost: those originals stay in your library and you'll be asked again at the next batch, or at the next run.

**I see an item twice in Photos.** Your library probably had a duplicate before; each copy gets processed. Check the **Duplicates** album in Photos (sidebar → Utilities) to merge them.

**"already compressed · skipped".** That file was already made by icloud-slim (it carries the marker). This only happens if `state.db` was deleted or you're running on another Mac.

**"skipped: saves less than 10 %".** That video was already efficient, so it's left untouched.

**Does Recently Deleted use my iCloud space?** No. Per Apple, it doesn't count toward iCloud storage. It does take space on your Mac and iPhone until you empty it or the 30 days pass.

**Can I use my Mac while it runs?** Yes. If it feels slow, stop it and restart with `--parallel 1`.

**Where's the detailed log?** In `~/icloud-slim/logs/`. The path of the current one is shown when the run starts and ends.

---

## Technical details

### Pipeline

```
iCloud ──PhotoKit export (child process)──▶ originals/<uuid>/         one download at a time, one item ahead
  ──ffmpeg (VideoToolbox) / sips → HEIC──▶ compressed/<uuid>/         up to --parallel at once
  ──exiftool: copy metadata + XMP marker──▶ verify
  ──photoscript import + albums/keywords/favorite──▶ Photos            main thread
  ──move original to originals-backup/──▶ PhotoKit delete in batches  child process, non-blocking
```

States in `state.db`: `pending → exported → compressed → imported → replaced → done`, plus `skipped`. `imported` is written right after the import, along with the new item's id, so an item is never imported twice. Worker threads download and compress (each with its own SQLite connection); the main thread imports, because AppleScript and the live panel run there. Ctrl+C sets a stop flag, so interrupted work isn't counted as a failure.

### Selection

| Type | Rule |
|---|---|
| `videos` | Real bitrate (`size × 8 / duration`) > `MARGIN` × target |
| `recordings` | Same rule, for screen recordings |
| `photos` | JPEG with bits per pixel (`size × 8 / (width × height)`) > `MARGIN` × `PHOTO_BPP`. Skips Live Photos, bursts, RAW pairs and edited photos (only originals are exported, so edits would be lost) |
| `screenshots` | PNG or JPEG screenshots |

Photos are chosen by how compressed they are, not by where they came from, so the same rule works for any library. After downloading, a JPEG with an MP4 inside (Android motion photos: `MVIMG_`, `PXL_…MP`, Samsung) is skipped: HEIC would drop the video.

Screen captures are detected with osxphotos' `screenshot`/`screen_recording` flags plus the `ZASSET.ZISDETECTEDSCREENSHOT` column of the Photos database. That column also catches Android and WhatsApp screenshots, which osxphotos doesn't expose.

### Video encoding

```
ffmpeg -hwaccel videotoolbox -hwaccel_output_format videotoolbox_vld -i in
       -map 0:v:0 -map 0:a? -c:v hevc_videotoolbox -b:v T -maxrate 1.5T -bufsize 2T [-profile:v main10]
       -c:a copy -tag:v hvc1 -map_metadata 0 -movflags use_metadata_tags+faststart out
```

- Decoding and encoding both run on Apple silicon's media engine. A 30-second 4K clip uses about 1 s of CPU instead of about 200 s, which is what makes running several encodes at once worthwhile.
- If hardware decoding fails, it falls back to software decoding. If the container rejects the audio as is (some Android codecs), the audio is re-encoded to AAC at 192 kbps.
- `hvc1` is required for Photos, QuickTime and iOS to play the file. 10-bit sources keep Main 10 with their HLG/BT.2020 color.
- **What's lost:** the Dolby Vision RPU (the result is still HDR, as HLG) and Apple's timed-metadata tracks (`mebx`: stabilization and Cinematic mode data).

### Metadata and verification

- `exiftool -tagsFromFile original -all:all`, plus `Keys:CreationDate` (with time zone), `Keys:GPSCoordinates`, `QuickTime:CreateDate` and `FileModifyDate` set explicitly, using `-api QuickTimeUTC`.
- **Checked before importing:** duration within ±0.5 s, the same dimensions for photos and screenshots, identical date and GPS tags (including EXIF GPS), VMAF ≥ `PHOTO_MIN_VMAF` for photos (always measured: about a second each; the HEIC is decoded with `sips` first because ffmpeg only reads its first tile), and a size at least 10 % smaller.
- **Applied after importing:** the original's albums, favorite, title and description, plus keywords made of the original's keywords and people's names. The date and location are also set if Photos didn't take them from the file.
- **XMP marker:** `xmp:CreatorTool=icloud-slim 1.0`, `xmpMM:PreservedFileName`, `xmpMM:DerivedFromDocumentID` (the original's id) and an `xmpMM:History` entry with JSON parameters (before/after, settings, original SHA-1, VMAF). It's invisible in Photos; read it with `exiftool -XMP:all file`.

### Deletion

Replaced originals are deleted with `PHAssetChangeRequest.deleteAssets` in a child process, once 20 GB or 500 items pile up. macOS always shows its own confirmation, and no API skips it. The run keeps processing while the dialog is open, and only waits for the last one at the end.

### Dependencies

[osxphotos](https://github.com/RhetTbull/osxphotos) (includes photoscript and rich), [ffmpeg](https://ffmpeg.org) and [exiftool](https://exiftool.org), plus `sips`, `caffeinate` and `nettop`, which come with macOS. The script runs inside osxphotos' environment (`osxphotos run`).

### Known limitations

- It exports the **unedited original**, so edits made in Photos don't carry over.
- Faces can't be assigned from outside Photos. Photos re-detects them in the background, and the names are added as keywords in the meantime.
- If the process dies in the milliseconds between an import and the state write, that item could be imported twice. You'd see it as a duplicate.

---

## Uninstall

```bash
pipx uninstall osxphotos && brew uninstall ffmpeg exiftool
rm -rf ~/icloud-slim        # ⚠️ also deletes originals-backup: move anything you want to keep first
```

## License

MIT. See [LICENSE](LICENSE).
