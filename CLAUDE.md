# CLAUDE.md — guide for AI assistants

You were probably asked something like "clone this repo, tell me what it does and set it up". This file tells you how.
**Talk to the user in their own language, without jargon.** Most users are not developers.

## What it is (explain this first, in 3–4 lines)

icloud-slim frees iCloud space by re-compressing the user's own videos, photos, screen recordings and screenshots
inside Apple Photos. It keeps date, place, people, albums and search. Originals are backed up locally
(`~/icloud-slim/originals-backup/`) and moved to Recently Deleted only after macOS asks the user to confirm.
Full details: `README.md` (English) and `README.es.md` (Spanish), same content.

## Setup (do these in order)

1. **Check the Mac:** `uname -m` must be `arm64` (Apple silicon) and macOS 14 or later (`sw_vers`). Otherwise stop and tell the user.
2. **Homebrew:** `command -v brew`. If missing, the user must install it from https://brew.sh (it asks for their password: don't do it for them).
3. **Install:** `./icloud-slim install` (ffmpeg, exiftool, pipx, osxphotos). Takes a few minutes.
4. **Permissions — the user must do this themselves.** macOS only shows the Photos prompts to Terminal or iTerm2, never to
   terminals inside other apps (VS Code, the Claude desktop app, …), and you can't click them. Ask the user to open
   Terminal or iTerm2 in this folder and run `./icloud-slim permissions`, then accept both prompts
   ("Allow Full Access" and "OK"). Troubleshooting: README → "Grant the permissions".
5. **Let them try it safely,** in Terminal/iTerm2:
   - `./icloud-slim` opens the menu (easiest).
   - `./icloud-slim analyze` shows what they'd save. Changes nothing.
   - `./icloud-slim demo` shows the progress screen with fake data. Changes nothing.
   - `./icloud-slim process --batch 3` processes the 3 heaviest videos so they can compare them in Photos.

## Rules for you

- **Never run `process` without `--dry-run`** unless the user explicitly asks. It changes their Photos library.
- Never run the internal commands `_delete` or `_export` yourself.
- Commands that touch Photos fail when run from your shell if it's not Terminal/iTerm2 (no permission). Hand them to the user instead.
- Long runs: Mac plugged in, lid open, confirm the "delete" dialog when it appears (every ~20 GB or 500 items).
- State and logs live in `~/icloud-slim/` (`state.db`, `logs/`, `metrics.md`). Read the latest log to diagnose a failed run.

## If you change the code

- `icloud_slim.py` (core, progress panel, commands), `menu.py` (arcade menu), `logo.py`, `i18n.py`. Runs inside osxphotos' Python (`osxphotos run`).
- Code, comments and logs in English. Every user-facing string in English and Spanish (`tr("key")` / `t("key")`).
- `README.md` and `README.es.md` must stay in sync.
- Self-checks: `"$HOME/Library/Application Support/pipx/venvs/osxphotos/bin/python" menu.py` and `python3 logo.py`.
  `icloud_slim.py` calls `main()` at import: to test functions, import a copy without its last line.
