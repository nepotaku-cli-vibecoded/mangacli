import re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def natural_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(s))]


class Mangataro:
    name = "mangataro"
    API_BASE = "https://manga-scrape-api.vercel.app/api/scrape"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    CDN = "https://mangataro.yachts"
    _page_cache = {}

    def search(self, query):
        if not query:
            return []
        r = requests.get(f"{self.API_BASE}/search", params={"query": query, "provider": "mangataro"}, timeout=15)
        data = r.json()
        return [{"slug": item["id"], "title": item["title"], "source": self.name} for item in data.get("results", [])]

    def chapters(self, manga_slug):
        r = requests.get(f"{self.API_BASE}/chapters", params={"id": manga_slug, "provider": "mangataro"}, timeout=15)
        chapters_data = r.json().get("chapters", [])

        wp_base = "https://mangataro.org/wp-json/wp/v2/chapter"
        batch_size = 50
        num_to_url = {}
        unresolved = {}

        for i, ch in enumerate(chapters_data):
            num = str(ch["number"])
            unresolved[i] = (num, ch["url"])

        def query_slugs(slug_list):
            if not slug_list:
                return {}
            result = {}
            for start in range(0, len(slug_list), batch_size):
                batch = slug_list[start:start + batch_size]
                try:
                    resp = requests.get(
                        wp_base,
                        params={"slug": ",".join(batch), "_fields": "slug,link", "per_page": 100},
                        headers=self.HEADERS,
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        for item in resp.json():
                            result[item["slug"]] = item["link"]
                except Exception:
                    pass
            return result

        raw_slugs = []
        for idx, (num, _) in unresolved.items():
            raw = num.replace(".", "-")
            raw_slugs.append(f"{manga_slug}-chapter-{raw}")

        raw_results = query_slugs(raw_slugs)

        resolved_raw = set()
        for idx, (num, fallback) in unresolved.items():
            raw = num.replace(".", "-")
            slug = f"{manga_slug}-chapter-{raw}"
            if slug in raw_results:
                num_to_url[num] = raw_results[slug]
                resolved_raw.add(idx)

        alt_slugs = []
        for idx, (num, _) in unresolved.items():
            if idx in resolved_raw or "." in num:
                continue
            n = int(num)
            for fmt in [n, f"{n:03d}", f"{n:02d}"]:
                alt_slugs.append(f"{manga_slug}-chapter-{fmt}")
        alt_results = query_slugs(alt_slugs)

        for idx, (num, fallback) in unresolved.items():
            if idx in resolved_raw:
                continue
            if "." in num:
                num_to_url[num] = fallback
                continue
            n = int(num)
            for fmt in [str(n), f"{n:03d}", f"{n:02d}"]:
                slug = f"{manga_slug}-chapter-{fmt}"
                if slug in alt_results:
                    num_to_url[num] = alt_results[slug]
                    break
            else:
                num_to_url[num] = fallback

        out = [{"url": num_to_url.get(str(ch["number"]), ch["url"]), "num": str(ch["number"])} for ch in chapters_data]
        out.sort(key=lambda x: float(x["num"]))
        return out

    def pages(self, chapter_url):
        if chapter_url in self._page_cache:
            return self._page_cache[chapter_url]
        r = requests.get(chapter_url, headers=self.HEADERS, timeout=15)
        html = r.text
        hash_match = re.search(r'/storage/chapters/([a-f0-9]+)/\d+\.webp', html)
        if not hash_match:
            return []
        storage_hash = hash_match.group(1)
        base = f"{self.CDN}/storage/chapters/{storage_hash}"
        urls = []
        with ThreadPoolExecutor(max_workers=16) as ex:
            fut_map = {}
            for i in range(1, 101):
                url = f"{base}/{i:03d}.webp"
                fut = ex.submit(requests.get, url, headers=self.HEADERS, timeout=5)
                fut_map[fut] = (i, url)
            for fut in as_completed(fut_map):
                i, url = fut_map[fut]
                try:
                    if fut.result().status_code == 200:
                        urls.append((i, url))
                except:
                    pass
        urls.sort(key=lambda x: x[0])
        result = [u for _, u in urls]
        self._page_cache[chapter_url] = result
        return result


class SourceManager:
    def __init__(self):
        self.sources = [Mangataro()]

    def search(self, query):
        results = []
        for src in self.sources:
            try:
                for r in src.search(query):
                    results.append({
                        "title": r["title"],
                        "slugs": {src.name: r["slug"]},
                        "sources": [src],
                    })
            except Exception:
                pass
        return results

    def chapters_for_source(self, manga, source_name):
        for src in self.sources:
            if src.name == source_name:
                slug = manga["slugs"].get(source_name)
                if not slug:
                    return []
                try:
                    return [{"num": ch["num"], "sources": {source_name: ch["url"]}} for ch in src.chapters(slug)]
                except Exception:
                    return []
        return []

    def get_pages(self, chapter, source_name):
        for src in self.sources:
            if src.name != source_name:
                continue
            if src.name not in chapter["sources"]:
                return None, [], 0, {}
            try:
                urls = src.pages(chapter["sources"][src.name])
            except Exception:
                return None, [], 0, {}
            if urls:
                headers = getattr(src, "IMG_HEADERS", getattr(src, "HEADERS", {"User-Agent": "Mozilla/5.0"}))
                return src.name, urls, len(urls), headers
            return None, [], 0, {}
        return None, [], 0, {}
