import gzip, json, os
from datetime import datetime, timezone


def _path():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
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


def record(manga_title, chapter_num, source, volume=None):
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
            if volume is not None:
                vn = str(volume)
                r["v"] = vn
                vols = r.setdefault("vols", {})
                vdata = vols.setdefault(vn, {"c": "0", "hc": "0"})
                vdata["c"] = cn
                if float(cn) > float(vdata.get("hc", "0")):
                    vdata["hc"] = cn
            _save(records)
            return
    entry = {"t": manga_title, "c": cn, "s": source, "ts": ts, "hc": cn, "chs": [cn]}
    if volume is not None:
        vn = str(volume)
        entry["v"] = vn
        entry["vols"] = {vn: {"c": cn, "hc": cn}}
    records.append(entry)
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
                "last_volume": r.get("v"),
                "vols": {},
            }
        g = groups[title]
        for ch in r.get("chs", [r["c"]]):
            if ch not in g["chapters"]:
                g["chapters"].append(ch)
        if r["ts"] > g["last_ts"]:
            g["last_ts"] = r["ts"]
            g["last_chapter"] = r["c"]
            g["last_volume"] = r.get("v")
        ghc = float(r.get("hc", r["c"]))
        if ghc > float(g["highest_chapter"]):
            g["highest_chapter"] = r.get("hc", r["c"])
        for vn, vd in r.get("vols", {}).items():
            g["vols"][vn] = {"c": vd["c"], "hc": vd.get("hc", vd["c"])}
    out = sorted(groups.values(), key=lambda x: x["last_ts"], reverse=True)
    return out


def get_raw():
    return _load()
