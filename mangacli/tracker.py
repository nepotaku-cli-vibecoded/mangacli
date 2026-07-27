import gzip, json, os
from datetime import datetime, timezone


def _path():
    if os.name == 'nt':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    d = os.path.join(base, 'man-cli')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'history.gz')


def _load():
    p = _path()
    if not os.path.isfile(p):
        return []
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save(records):
    p = _path()
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        json.dump(records, f, separators=(',', ':'), ensure_ascii=False)


def record(manga_title, chapter_num, source):
    records = _load()
    ts = datetime.now(timezone.utc).isoformat()
    cn = str(chapter_num)
    for r in records:
        if r["t"] == manga_title:
            r["c"] = cn
            r["s"] = source
            r["ts"] = ts
            if cn not in r.get("chs", []):
                r.setdefault("chs", []).append(cn)
            if float(cn) > float(r.get("hc", "0")):
                r["hc"] = cn
            _save(records)
            return
    records.append({
        "t": manga_title, "c": cn, "s": source, "ts": ts,
        "hc": cn, "chs": [cn],
    })
    _save(records)


def get_grouped():
    records = _load()
    groups = {}
    for r in records:
        title = r["t"]
        if title not in groups:
            groups[title] = {
                "title": title,
                "source": r.get("s", "?"),
                "chapters": [],
                "last_ts": r["ts"],
                "last_chapter": r["c"],
                "highest_chapter": r.get("hc", r["c"]),
            }
        g = groups[title]
        for ch in r.get("chs", [r["c"]]):
            if ch not in g["chapters"]:
                g["chapters"].append(ch)
        if r["ts"] > g["last_ts"]:
            g["last_ts"] = r["ts"]
            g["last_chapter"] = r["c"]
        ghc = float(r.get("hc", r["c"]))
        if ghc > float(g["highest_chapter"]):
            g["highest_chapter"] = r.get("hc", r["c"])
    out = sorted(groups.values(), key=lambda x: x["last_ts"], reverse=True)
    return out


def get_raw():
    return _load()
