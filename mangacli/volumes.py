from mangacli.sources import natural_key


def lookup(title, chapters=None):
    if not chapters:
        return None
    per_vol = 10
    vol_map = {}
    for i in range(0, len(chapters), per_vol):
        group = chapters[i:i + per_vol]
        vol_map[str(len(vol_map) + 1)] = [ch["num"] for ch in group]
    return vol_map


def get_volume_for_chapter(vol_map, chapter_num):
    cn = str(chapter_num)
    for vn in sorted(vol_map.keys(), key=natural_key):
        if cn in vol_map[vn]:
            return vn
    return None
