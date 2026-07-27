import re, html, json, requests

class Mangataro:
    name = "mangataro"
    API_BASE = "https://manga-scrape-api.vercel.app/api/scrape"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def search(self, query):
        if not query:
            return []
        r = requests.get(f"{self.API_BASE}/search", params={"query": query, "provider": "mangataro"}, timeout=15)
        data = r.json()
        return [{"slug": item["id"], "title": item["title"], "source": self.name} for item in data.get("results", [])]

    def chapters(self, slug):
        r = requests.get(f"{self.API_BASE}/chapters", params={"id": slug, "provider": "mangataro"}, timeout=15)
        out = []
        for ch in r.json().get("chapters", []):
            num = str(ch["number"])
            out.append({"url": f"{slug}:{num}", "num": num})
        out.sort(key=lambda x: float(x["num"]))
        return out

    def pages(self, chapter_url):
        slug, num = chapter_url.split(":", 1)
        r = requests.get(f"{self.API_BASE}/pages", params={"id": slug, "chapterNumber": num, "provider": "mangataro"}, timeout=15)
        return [p["url"] for p in r.json().get("pages", [])]


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
        self.sources = [Weebcentral(), Mangataro(), Mangaread()]

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

    @staticmethod
    def _img_size(url, headers):
        try:
            r = requests.head(url, headers=headers, timeout=10)
            return int(r.headers.get("Content-Length", 0)) or 0
        except Exception:
            return 0

    def best_pages(self, chapter):
        candidates = []
        for src in self.sources:
            if src.name not in chapter["sources"]:
                continue
            ch_url = chapter["sources"][src.name]
            try:
                urls = src.pages(ch_url)
            except Exception:
                continue
            if not urls:
                continue
            headers = getattr(src, "IMG_HEADERS", getattr(src, "HEADERS", {"User-Agent": "Mozilla/5.0"}))
            size = self._img_size(urls[0], headers)
            candidates.append((src.name, urls, len(urls), headers, size))

        if not candidates:
            return None, [], 0, {}

        candidates.sort(key=lambda c: c[4], reverse=True)
        best = candidates[0]
        return best[0], best[1], best[2], best[3]

