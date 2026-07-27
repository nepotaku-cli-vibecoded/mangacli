import re, html, json, requests
import cloudscraper

class Comix:
    name = "comix"
    API_BASE = "https://comix-api.vercel.app"
    BASE = "https://comix.to"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    def search(self, query):
        out = []
        try:
            if not query:
                r = self._session.get(f"{self.API_BASE}/api/manga/home", timeout=15)
                if r.ok:
                    data = r.json()
                    popular = data.get("popular", []) + data.get("latest", [])
                    seen = set()
                    for item in popular:
                        sid = item.get("id") or (item.get("link", "").split("/")[-1] if item.get("link") else None)
                        title = item.get("title")
                        if sid and title and sid not in seen:
                            seen.add(sid)
                            out.append({"slug": sid, "title": title, "source": self.name})
            else:
                r = self._session.get(f"{self.API_BASE}/api/manga/search", params={"q": query}, timeout=15)
                if r.ok:
                    data = r.json()
                    results = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for item in results:
                        sid = item.get("id") or (item.get("link", "").split("/")[-1] if item.get("link") else None)
                        title = item.get("title")
                        if sid and title:
                            out.append({"slug": sid, "title": title, "source": self.name})
        except Exception:
            pass

        if not out and query:
            try:
                scraper = cloudscraper.create_scraper()
                r = scraper.get("https://comix.to/", timeout=20)
                if r.ok:
                    match = re.search(r'<script[^>]*id="initial-data"[^>]*>(.*?)</script>', r.text, re.DOTALL)
                    if match:
                        bdata = json.loads(match.group(1))
                        ql = query.lower()
                        seen = set()
                        for qk, qv in bdata.get("queries", {}).items():
                            if isinstance(qv, dict):
                                for sub in ([qv] if "items" in qv else [v for v in qv.values() if isinstance(v, dict) and "items" in v]):
                                    for item in sub.get("items", []):
                                        if isinstance(item, dict):
                                            title = item.get("title")
                                            hid = item.get("hid") or item.get("id")
                                            if title and hid and ql in title.lower() and hid not in seen:
                                                seen.add(hid)
                                                out.append({"slug": str(hid), "title": title, "source": self.name})
            except Exception:
                pass
        return out

    def chapters(self, slug):
        out = []
        try:
            r = self._session.get(f"{self.API_BASE}/api/manga/{slug}", timeout=15)
            if r.ok:
                data = r.json()
                chs = data.get("chapters", [])
                for ch in chs:
                    num = str(ch.get("number") or ch.get("num") or "0")
                    ch_id = ch.get("id") or ch.get("url")
                    if ch_id:
                        out.append({"url": str(ch_id), "num": num})
        except Exception:
            pass

        if not out:
            try:
                url = f"{self.BASE}/title/{slug}"
                r_html = self._session.get(url, timeout=15)
                if r_html.ok:
                    script_match = re.search(r'<script[^>]*>\s*(\{"page":.*?\})\s*</script>', r_html.text, re.DOTALL)
                    if script_match:
                        tdata = json.loads(script_match.group(1))
                        for qk, qv in tdata.get("queries", {}).items():
                            if isinstance(qv, dict) and "chapters" in qv:
                                for ch in qv["chapters"]:
                                    num = str(ch.get("number") or ch.get("num") or "0")
                                    ch_id = ch.get("id") or ch.get("hid") or ch.get("url")
                                    if ch_id:
                                        out.append({"url": str(ch_id), "num": num})
            except Exception:
                pass

        seen = set()
        cleaned = []
        for ch in out:
            num = ch["num"].replace("-", ".")
            if num not in seen:
                seen.add(num)
                try:
                    fnum = float(num)
                except ValueError:
                    fnum = 0.0
                cleaned.append((ch["url"], num, fnum))
        cleaned.sort(key=lambda x: x[2])
        return [{"url": u, "num": n} for u, n, _ in cleaned]

    def pages(self, chapter_url):
        try:
            r = self._session.get(f"{self.API_BASE}/api/manga/read", params={"chapterId": chapter_url}, timeout=15)
            if r.ok:
                data = r.json()
                pages = data.get("pages", []) or data.get("images", [])
                if isinstance(pages, list) and pages:
                    return [p if p.startswith("http") else f"{self.API_BASE}{p}" for p in pages]
        except Exception:
            pass

        try:
            if chapter_url.startswith("http"):
                r_html = self._session.get(chapter_url, timeout=15)
                if r_html.ok:
                    imgs = re.findall(r'<img[^>]*src=[\'"]([^\'"]+)[\'"]', r_html.text, re.DOTALL | re.IGNORECASE)
                    return [i.strip() for i in imgs if "static.comix.to" in i or "cdn" in i or "storage" in i]
        except Exception:
            pass
        return []


class Mangaread:
    name = "mangaread"
    BASE = "https://www.mangaread.org"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def _html(self, url):
        r = requests.get(url, headers=self.HEADERS, timeout=15)
        r.raise_for_status()
        return r.text

    def search(self, query):
        if not query:
            raw = self._html(f"{self.BASE}/manga/?m_orderby=views")
        else:
            raw = self._html(f"{self.BASE}/?s={requests.utils.quote(query)}&post_type=wp-manga")
        out = []
        for m in re.finditer(r'<div[^>]*class=["\'][^"\']*post-title[^"\']*["\'][^>]*>.*?<a[^>]*href=["\']([^"\']+/manga/([^"\'/]+)/?)["\'][^>]*>([^<]+)</a>', raw, re.DOTALL):
            slug, title = m.group(2), html.unescape(m.group(3).strip())
            if slug == "feed":
                continue
            out.append({"slug": slug, "title": title, "source": self.name})
        return out

    def chapters(self, slug):
        html = self._html(f"{self.BASE}/manga/{slug}/")
        links = re.findall(r'href=[\'"]([^\'"]+/manga/{}/chapter-(\d+(?:[\.-]\d+)?)[^/]*/)[\'"]'.format(re.escape(slug)), html)
        seen = set()
        out = []
        for url, num in links:
            num_norm = num.replace('-', '.')
            if num_norm not in seen:
                seen.add(num_norm)
                try:
                    fnum = float(num_norm)
                except ValueError:
                    fnum = 0
                out.append((url, num_norm, fnum))
        out.sort(key=lambda x: x[2])
        return [{"url": url, "num": num} for url, num, _ in out]

    def pages(self, chapter_url):
        if not chapter_url.startswith("http"):
            chapter_url = self.BASE + chapter_url
        html = self._html(chapter_url)
        imgs = re.findall(r'<img[^>]*src=[\'"]([^\'"]+)[\'"]', html, re.DOTALL | re.IGNORECASE)
        return [i.strip() for i in imgs if '/WP-manga/' in i]


class Weebcentral:
    name = "weebcentral"
    BASE = "https://weebcentral.com"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    IMG_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                   "Referer": "https://weebcentral.com/"}

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    def _get(self, path, params=None, htmx_target=None, referer=None):
        headers = {}
        if htmx_target:
            headers["HX-Request"] = "true"
            headers["HX-Target"] = htmx_target
        if referer:
            headers["Referer"] = referer
            headers["HX-Current-URL"] = referer
        r = self._session.get(f"{self.BASE}{path}", params=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text

    def search(self, query):
        if not query:
            return []
        params = {
            "text": query, "sort": "Best Match", "order": "Descending",
            "official": "Any", "anime": "Any", "adult": "Any",
            "display_mode": "Full Display", "author": "",
        }
        raw = self._get("/search/data", params=params, htmx_target="search-results",
                        referer=f"{self.BASE}/search?search={requests.utils.quote(query)}")
        seen = set()
        out = []
        for a_match in re.finditer(r'<a\s+href="https://weebcentral\.com/series/([^/"]+)/([^/"]+)"[^>]*>.*?</a>', raw, re.DOTALL):
            sid, slug = a_match.group(1), a_match.group(2)
            if sid in seen:
                continue
            seen.add(sid)
            inner = a_match.group(0)
            img = re.search(r'<img[^>]*alt="([^"]+)"', inner)
            if img:
                title = html.unescape(img.group(1))
                if title.endswith(" cover"):
                    title = title[:-6].strip()
            else:
                title = slug.replace("-", " ").title()
            out.append({"slug": sid, "title": title, "source": self.name})
        return out

    def chapters(self, series_id):
        html = self._get(f"/series/{series_id}/full-chapter-list",
                         htmx_target="chapter-list",
                         referer=f"{self.BASE}/series/{series_id}/dummy")
        entries = re.findall(r'<a[^>]*href=[\'"]([^\'"]+/chapters/[^\'"]+)[\'"][^>]*>(.*?)</a>', html, re.DOTALL)
        seen = set()
        out = []
        for url, inner in entries:
            text = re.sub(r'<[^>]+>', '', inner).strip()
            num_match = re.search(r'#?\s*([\d.]+)', text)
            if num_match:
                num = num_match.group(1)
                if num not in seen:
                    seen.add(num)
                    try:
                        fnum = float(num)
                    except ValueError:
                        fnum = 0
                    out.append((url, num, fnum))
        out.sort(key=lambda x: x[2])
        return [{"url": url, "num": num} for url, num, _ in out]

    def pages(self, chapter_url):
        ch_id = chapter_url.rstrip('/').split('/')[-1]
        params = {"is_prev": "False", "current_page": "1"}
        html = self._get(f"/chapters/{ch_id}/images", params=params,
                         htmx_target="image-container",
                         referer=f"{self.BASE}/chapters/{ch_id}")
        imgs = re.findall(r'src="([^"]+)"', html)
        return [i.strip() for i in imgs if i.startswith("http") and not any(x in i for x in ("/static/images/", "avatar", "logo", "icon"))]


class SourceManager:
    def __init__(self):
        self.sources = [Weebcentral(), Comix(), Mangaread()]

    @staticmethod
    def _normalize(title):
        s = title.lower()
        s = re.sub(r"\s*[\(\[\{].*?[\)\]\}]", "", s)
        s = re.sub(r"\s+-\s+manga$", "", s)
        s = re.sub(r"[^a-z0-9\s]", "", s)
        return re.sub(r"\s+", " ", s).strip()

    def search(self, query):
        results = {}
        for src in self.sources:
            try:
                for r in src.search(query):
                    key = self._normalize(r["title"])
                    if key not in results:
                        results[key] = {
                            "title": r["title"],
                            "slugs": {},
                            "sources": [],
                        }
                    results[key]["slugs"][src.name] = r["slug"]
                    if src not in results[key]["sources"]:
                        results[key]["sources"].append(src)
            except Exception:
                pass
        return list(results.values())

    def chapters(self, manga):
        merged = {}
        for src in manga["sources"]:
            slug = manga["slugs"].get(src.name)
            if not slug:
                continue
            try:
                chs = src.chapters(slug)
                for ch in chs:
                    num = ch["num"]
                    if num not in merged:
                        merged[num] = {"num": num, "sources": {}}
                    merged[num]["sources"][src.name] = ch["url"]
            except Exception:
                pass
        return [merged[k] for k in sorted(merged.keys(), key=lambda x: float(x.replace("-", ".")) if x.replace("-", "").replace(".", "").isdigit() else 0)]

    def _count_pages(self, chapter_url, source):
        try:
            pages = source.pages(chapter_url)
            return len(pages), pages
        except Exception:
            return 0, []

    def best_pages(self, chapter):
        # 1. Weebcentral as primary source
        if "weebcentral" in chapter["sources"]:
            src = next((s for s in self.sources if s.name == "weebcentral"), None)
            if src:
                ch_url = chapter["sources"]["weebcentral"]
                count, urls = self._count_pages(ch_url, src)
                if count > 0:
                    headers = getattr(src, "IMG_HEADERS", getattr(src, "HEADERS", {"User-Agent": "Mozilla/5.0"}))
                    return "weebcentral", urls, count, headers

        # 2. Fall back to secondary sources
        candidates = []
        for src_name in ("comix", "mangaread"):
            if src_name not in chapter["sources"]:
                continue
            src = next((s for s in self.sources if s.name == src_name), None)
            if not src:
                continue
            ch_url = chapter["sources"][src_name]
            count, urls = self._count_pages(ch_url, src)
            if count > 0:
                headers = getattr(src, "IMG_HEADERS", getattr(src, "HEADERS", {"User-Agent": "Mozilla/5.0"}))
                png_count = sum(1 for u in urls if ".png" in u.lower() or ".png?" in u.lower())
                candidates.append((src_name, urls, count, headers, png_count))

        if not candidates:
            return None, [], 0, {}

        candidates.sort(key=lambda c: (c[2], c[4]), reverse=True)
        best = candidates[0]
        return best[0], best[1], best[2], best[3]

