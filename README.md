# man-cli

> "legally distinct from ani-cli" — the author, probably

A multi-source terminal manga reader — search, browse, and read manga directly in your terminal using mpv.

## Features

- **Multiple sources** — searches and merges results from Weebcentral, Comix, and Mangaread (no duplicates)
- **Auto quality preference** — picks the source with more PNG images (higher quality)
- **Parallel downloads** — downloads chapter pages concurrently (8 workers) for faster loading
- **Fullscreen viewer** — opens mpv in fullscreen with arrow key navigation
- **Reading history** — tracks last and highest chapter read per manga
- **AniList integration** — auto-links manga and updates chapter progress to your AniList list
- **Cross-platform** — works on Windows, Linux, and macOS
- **One-click launcher** — `Manga.exe` opens a fullscreen terminal with man-cli ready

## Dependencies

| What | How to install |
|------|---------------|
| **Python 3.8+** | [python.org](https://python.org) or system package |
| **mpv** | `winget install mpv` (Windows) / `sudo apt install mpv` (Debian) / `sudo pacman -S mpv` (Arch) / `brew install mpv` (macOS) |
| **requests** | `pip install requests` |
| **cloudscraper** | `pip install cloudscraper` |

## Install

### Windows — One-click launcher

Clone or download the repo, then double-click `app_of_cli\Manga.exe` — it launches a fullscreen terminal and starts man-cli automatically.

### Manual install

```powershell
git clone https://github.com/nepotaku-cli-vibecoded/mangacli
cd mangacli
pip install requests cloudscraper
pip install .
man-cli
```

If `man-cli` isn't found, add Python Scripts to PATH:
```powershell
%APPDATA%\Python\Scripts\
# or
%LOCALAPPDATA%\Programs\Python\Python313\Scripts\
```

### Linux / macOS

```bash
git clone https://github.com/nepotaku-cli-vibecoded/mangacli
cd mangacli
pip install requests cloudscraper
pip install .
man-cli
```

If `man-cli` isn't found, add `~/.local/bin/` to PATH, or run directly:
```bash
python mangacli/main.py
```

### Run without installing

```bash
cd mangacli
python mangacli/main.py
```

## Usage

```
  1. Search manga
  2. Popular
  3. History
  4. AniList
  5. Exit
```

- **Search** — type any title to find manga across all sources
- **Popular** — browse trending manga
- **History** — shows all manga you've read, with last and highest chapter
- **AniList** — one-time setup, then auto-track every chapter

Select a manga → pick a chapter → reads automatically in **mpv** fullscreen.  
**Arrow keys:** `→` next page, `←` previous page, `q` quit fullscreen.  
After a chapter: `n` next, `p` previous, `q` back to list.

Chapters are paginated (100 per page) with a "Next" option.

## AniList Integration

man-cli can automatically update your AniList manga list after every chapter.

### First-time setup

1. Go to **AniList** > **Settings** > **Developer**
2. Create a new client with redirect URL `http://localhost:8888`
3. Replace the Client ID and Secret in `mangacli/anilist.py` with yours
4. Run man-cli, go to `4. AniList` > `1. Authorize`
5. Browser opens — click "Authorize"

After that, every chapter you read is silently synced to your AniList list. If a manga isn't found on AniList, you'll be told once with no further prompts.

## How it works

1. **Search** queries multiple sources simultaneously
2. Results are merged by normalized title — no duplicates if multiple sources have the same manga
3. When reading a chapter, all available sources are checked for page availability
4. The source with more **PNG** images is preferred (higher quality)
5. Pages are downloaded in parallel (8 threads) for speed
6. mpv displays the images in fullscreen with keyboard navigation
7. Downloaded images are cleaned up after you finish the chapter
8. Your reading history is saved locally; AniList is updated automatically if linked

## Notes

- Images are cached to `temp_img_load/` and cleaned up after reading
- The reader uses mpv for full-resolution image viewing (not ASCII/block art)
- AniList requires browser authorization once — no passwords stored
- Reading history is stored in `%APPDATA%/man-cli/history.gz`

## Disclaimer

This tool does not host, store, or distribute any copyrighted material.
It only provides a terminal interface to access content hosted by
third-party websites. All manga content is served
directly from those sites. Any DMCA or copyright complaints
should be directed to the host site, not to this tool, its developers,
or contributors.

## Meme Disclaimer

This project was vibecoded in record time. The code quality has been
described as "aggressively functional." We apologize to anyone who
has to read the source.

## Space Fact

Did you know? A day on Venus is longer than a year on Venus — it takes 243 Earth days to rotate once, but only 225 Earth days to orbit the Sun.
