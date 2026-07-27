#!/usr/bin/env python3
import sys, io, os, re, tempfile, shutil, subprocess, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from mangacli import tracker

try:
    from mangacli import anilist
except ImportError:
    import anilist

if os.name == 'nt':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    from mangacli.sources import SourceManager
except ImportError:
    from sources import SourceManager
sm = SourceManager()


def _getch():
    if os.name == 'nt':
        import msvcrt
        k = msvcrt.getch()
        if k in (b'\x00', b'\xe0'):
            k2 = msvcrt.getch()
            if k2 == b'K': return 'LEFT'
            if k2 == b'M': return 'RIGHT'
            return None
        try:
            return k.decode('utf-8', errors='replace').lower()
        except Exception:
            return None
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            k = sys.stdin.read(1)
            if k == '\x1b':
                seq = sys.stdin.read(2)
                if seq == '[D': return 'LEFT'
                if seq == '[C': return 'RIGHT'
                return None
            return k.lower()
        except Exception:
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _clear():
    os.system("cls" if os.name == 'nt' else "clear")


def _mpv_view(files, title):
    conf = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
    conf.write("RIGHT playlist-next\nLEFT playlist-prev\nq quit\n")
    conf.close()
    subprocess.run(["mpv", "--image-display-duration=inf", "--fs",
                    "--really-quiet", f"--input-conf={conf.name}",
                    f"--title={title}"] + files,
                   timeout=86400)
    os.unlink(conf.name)


def menu(opts, prompt="Select: "):
    items = list(opts.items()) if isinstance(opts, dict) else list(opts)
    for i, (k, v) in enumerate(items, 1):
        title = v[:120] + "..." if len(v) > 123 else v
        print(f"  {i:>3}. {title}")
    print(f"    0. Back")
    try:
        c = int(input(prompt))
        if c == 0:
            return None
        return items[c - 1][0]
    except (ValueError, IndexError):
        return None


def _download_images(urls, tmp, headers):
    files = [None] * len(urls)
    print(f"  Downloading {len(urls)} pages...", end="", flush=True)

    def _dl(i, purl):
        try:
            img = requests.get(purl.strip(), headers=headers, timeout=15).content
            ext = os.path.splitext(purl.split("?")[0])[1] or ".jpg"
            fpath = os.path.join(tmp, f"page_{i+1:03d}{ext}")
            with open(fpath, "wb") as f:
                f.write(img)
            return i, fpath
        except Exception:
            return i, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(_dl, i, u) for i, u in enumerate(urls)]
        for f in as_completed(futures):
            i, path = f.result()
            files[i] = path
            print(".", end="", flush=True)

    valid = [f for f in files if f]
    print(f" done ({len(valid)}/{len(urls)})")
    return valid


MEME_FACTS = [
    "the author is definitely watching you read this",
    "reading manga in the terminal doesn't make you a hacker",
    "this was vibecoded in a single sitting (and it shows)",
    "mpv was not designed for this. we did it anyway",
    "no API keys were harmed in the making of this tool",
    "this reader runs on pure spite and pip install requests",
    "manga sites hate this one simple trick (it's web scraping)",
    "your terminal has seen things it cannot unsee",
    "this is peak performance. don't look at the code.",
    "this is not a hackathon project. it just looks like one.",
    "weebcentral is not a real place. you cannot be hurt there.",
    "50% of the code is regex. the other 50% is praying.",
    "the chapter you want is always on the source that's down.",
    "this tool has more sources than your average anime adaptation",
    "no pandas were imported in the making of this script",
    "pip install requests was the only dependency we needed",
    "this is fine. everything is fine. the site will never change its HTML.",
    "the author writes regex the way manga artists draw backgrounds",
    "this project has a 10:1 comment-to-commit ratio. the comments are all git blame artifacts.",
    "the dependency is requests. the dependency is also your patience.",
    "the only thing more unreliable than the sources is the author's testing methodology",
    "one day the sites will add cloudflare and this whole repo becomes a museum exhibit",
    "/tmp/manga_* is the modern equivalent of a stack of books under your bed",
    "broken? fix it yourself",
]

def meme_loading(percent, total):
    bar_len = 20
    filled = int(bar_len * percent / total) if total else 0
    bar = "▓" * filled + "░" * (bar_len - filled)
    fact = random.choice(MEME_FACTS) if percent == 1 else ""
    return f"  {bar} {percent}/{total} {fact}"


def _read_manga(manga, jump_chapter=None):
    chs = sm.chapters(manga)
    if not chs:
        input("  No chapters available. Press Enter...")
        return

    total_ch = len(chs)
    page_size = 100
    ch_page = 0
    cur_idx = 0
    cur_ch = None

    if jump_chapter is not None:
        for i, ch in enumerate(chs):
            if ch["num"] == jump_chapter:
                cur_idx = i
                cur_ch = chs[cur_idx]
                break

    while True:
        if cur_ch is None:
            start = ch_page * page_size
            end = min(start + page_size, total_ch)
            page_chs = chs[start:end]

            ch_opts = {}
            for ch in page_chs:
                ch_opts[ch["num"]] = f"Ch.{ch['num']}"

            if end < total_ch:
                n = start + page_size + 1
                m = min(n + page_size - 1, total_ch)
                ch_opts["__more__"] = f"→ Next chapters ({n}-{m})"

            ch_num = menu(ch_opts, "Select chapter: ")
            if ch_num == "__more__":
                ch_page += 1
                continue
            if not ch_num:
                break

            cur_idx = next(i for i, ch in enumerate(chs) if ch["num"] == ch_num)
            cur_ch = chs[cur_idx]

        while True:
            print(f"  Fetching Ch.{cur_ch['num']}...")
            best_src, page_urls, count, dl_headers = sm.best_pages(cur_ch)
            if not page_urls:
                input("  No pages found. Press Enter...")
                break

            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_img_load")
            os.makedirs(cache_dir, exist_ok=True)
            tmp = tempfile.mkdtemp(prefix="manga_", dir=cache_dir)
            files = _download_images(page_urls, tmp, dl_headers)
            if not files:
                input("  Download failed. Press Enter...")
                break

            _mpv_view(files, f"Ch.{cur_ch['num']}")

            tracker.record(manga["title"], cur_ch["num"], best_src or "?")
            anilist_msg = anilist.on_chapter_read(manga["title"], cur_ch["num"])

            _clear()
            sys.stdout.write(f"\n  Chapter finished.\n\n")
            sys.stdout.write(f"  ➜ {random.choice(MEME_FACTS)}\n\n")
            if anilist_msg:
                sys.stdout.write(anilist_msg)
                sys.stdout.write("\n")
            if cur_idx < total_ch - 1:
                sys.stdout.write("    [n] Next chapter\n")
            if cur_idx > 0:
                sys.stdout.write("    [p] Previous chapter\n")
            sys.stdout.write("    [q] Back to chapter list\n")
            sys.stdout.write("\n  Choose: ")
            sys.stdout.flush()

            nav = _getch()
            shutil.rmtree(tmp, ignore_errors=True)

            if nav in ('n', 'RIGHT') and cur_idx < total_ch - 1:
                cur_idx += 1
                cur_ch = chs[cur_idx]
                continue
            elif nav in ('p', 'LEFT') and cur_idx > 0:
                cur_idx -= 1
                cur_ch = chs[cur_idx]
                continue
            else:
                break
        cur_ch = None


def _history_menu():
    all_titles = tracker.get_grouped()
    total = len(all_titles)
    if total == 0:
        input("  No reading history yet. Press Enter...")
        return

    page_size = 10
    page = 0

    while True:
        _clear()
        start = page * page_size
        end = min(start + page_size, total)
        page_titles = all_titles[start:end]
        total_pages = (total + page_size - 1) // page_size

        print(f"\n{'=' * 50}")
        print(f"  Reading History (Page {page + 1}/{total_pages})")
        print(f"{'=' * 50}")

        for i, t in enumerate(page_titles, 1):
            label = f"{t['title']} - {len(t['chapters'])} ch. - last: Ch.{t['last_chapter']} - highest: Ch.{t['highest_chapter']}"
            print(f"  {i:>3}. {label}")

        if end < total:
            print(f"  {page_size + 1:>3}. → Next 10")
        if page > 0:
            print(f"  {page_size + 2:>3}. ← Previous 10")

        print(f"    0. Back")
        c = input("Select: ").strip()

        if c == "0":
            return

        try:
            ci = int(c)
        except ValueError:
            continue

        if 1 <= ci <= len(page_titles):
            sel = page_titles[ci - 1]
            go = input(f"  Read {sel['title']}? [y/N]: ").strip().lower()
            if go == "y":
                print(f"\n    [Enter] Last read (Ch.{sel['last_chapter']})")
                print(f"    [h] Highest (Ch.{sel['highest_chapter']})")
                print(f"    [c] Pick from chapter list")
                pick = input("  Choose: ").strip().lower()
                if pick == "h":
                    return sel["title"], sel["source"], sel["highest_chapter"]
                elif pick == "c":
                    return sel["title"], sel["source"], None
                else:
                    return sel["title"], sel["source"], sel["last_chapter"]
            continue

        if ci == page_size + 1 and end < total:
            page += 1
            continue
        if ci == page_size + 2 and page > 0:
            page -= 1
            continue


def _anilist_menu():
    while True:
        _clear()
        print(f"\n{'=' * 50}")
        authed = anilist.is_authed()
        print(f"  AniList ({'Connected' if authed else 'Not connected'})")
        print(f"{'=' * 50}")
        if authed:
            stats = anilist.get_stats()
            print(f"  Linked manga: {stats['linked']}")
            print(f"  Not found (won't retry): {stats['not_found']}")
            print()
            print(f"  1. Re-authorize")
            print(f"  2. View linked manga")
            print(f"  3. Unlink a manga")
            print(f"  4. Retry 'not found' titles")
            print(f"  5. Link all history to AniList")
            print(f"  6. Disconnect")
        else:
            print()
            print(f"  1. Authorize with AniList")
            print(f"     (requires redirect URL http://localhost:8888 in developer settings)")
        print(f"  0. Back")
        choice = input("Choose: ").strip()
        if choice == "0":
            return
        if choice == "1":
            print("  Opening browser...")
            if anilist.auth():
                print("  Authorization successful!")
            else:
                print("  Authorization failed.")
            input("  Press Enter...")
            continue
        if not authed:
            continue
        if choice == "2":
            linked = anilist.get_linked()
            if not linked:
                print("  No linked manga.")
            else:
                print(f"\n  Linked manga ({len(linked)}):")
                for t, info in linked:
                    print(f"    - {t} → AniList: {info.get('media_title', info['media_id'])}")
            input("  Press Enter...")
            continue
        if choice == "3":
            linked = anilist.get_linked()
            if not linked:
                print("  No linked manga to unlink.")
                input("  Press Enter...")
                continue
            print()
            for i, (t, info) in enumerate(linked, 1):
                print(f"  {i}. {t}")
            try:
                ci = int(input("  Number to unlink: ").strip())
                if 1 <= ci <= len(linked):
                    anilist.unlink(linked[ci - 1][0])
                    print("  Unlinked.")
            except ValueError:
                pass
            input("  Press Enter...")
            continue
        if choice == "4":
            anilist.forget_all_not_found()
            print("  'Not found' titles will be retried on next read.")
            input("  Press Enter...")
            continue
        if choice == "5":
            all_titles = tracker.get_grouped()
            if not all_titles:
                print("  No reading history to link.")
                input("  Press Enter...")
                continue
            print(f"\n  Linking {len(all_titles)} titles from history...")
            results = {"linked": 0, "already_linked": 0, "not_found": 0, "previously_not_found": 0}
            for i, t in enumerate(all_titles, 1):
                sys.stdout.write(f"  [{i}/{len(all_titles)}] {t['title']}... ")
                sys.stdout.flush()
                res = anilist.batch_link(t["title"], t["highest_chapter"])
                results[res] = results.get(res, 0) + 1
                labels = {"linked": "linked!", "already_linked": "already linked", "not_found": "not found on AniList", "previously_not_found": "already marked not found", "no_auth": "not connected"}
                print(labels.get(res, res))
            print(f"\n  Done: {results['linked']} linked, {results['already_linked']} already linked, {results['not_found']} not found")
            input("  Press Enter...")
            continue
        if choice == "6":
            anilist.clear_auth()
            print("  Disconnected.")
            input("  Press Enter...")
            continue


def main():
    while True:
        _clear()
        print(f"\n{'=' * 50}")
        print(f"  man-cli - Manga Reader")
        print(f"  \"trust me bro, it's for educational purposes\"")
        print(f"{'=' * 50}")
        print(f"  1. Search manga")
        print(f"  2. Popular")
        print(f"  3. History")
        print(f"  4. AniList")
        print(f"  5. Exit")
        choice = input("Choose: ").strip()

        if choice in ("5", "q", "exit", "quit"):
            break

        mangas = []
        if choice == "2":
            mangas = sm.search("")
        elif choice == "1":
            q = input("Search: ").strip()
            if not q:
                continue
            mangas = sm.search(q)
        elif choice == "3":
            result = _history_menu()
            if result is None:
                continue
            title, source, last_ch = result
            mangas = sm.search(title)
            for m in mangas:
                if source in m.get("slugs", {}):
                    _read_manga(m, jump_chapter=last_ch)
                    break
            continue

        elif choice == "4":
            _anilist_menu()
            continue

        if not mangas:
            input("No results. Press Enter...")
            continue

        while True:
            opts = {i: m["title"] for i, m in enumerate(mangas)}
            idx = menu(opts, "Select manga: ")
            if idx is None:
                break
            _read_manga(mangas[idx])

    print("Bye! (read a physical book once in a while)")


if __name__ == "__main__":
    main()
