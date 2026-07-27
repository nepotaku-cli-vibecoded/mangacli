import json, os, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
import requests

CLIENT_ID = 47076
CLIENT_SECRET = "sj5lbVagYLXOhQ2alJA4BEViTRYcyqCdcUjox6Zu"
REDIRECT_URI = "http://localhost:8888"
TOKEN_URL = "https://anilist.co/api/v2/oauth/token"
AUTH_URL = "https://anilist.co/api/v2/oauth/authorize"
API_URL = "https://graphql.anilist.co"


def _base_path():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def _token_path():
    return os.path.join(_base_path(), 'anilist_token.json')


def _links_path():
    return os.path.join(_base_path(), 'anilist_links.json')


def _load_token():
    p = _token_path()
    if not os.path.isfile(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _save_token(token):
    token["_obtained_at"] = time.time()
    with open(_token_path(), 'w') as f:
        json.dump(token, f)


def _load_links():
    p = _links_path()
    if not os.path.isfile(p):
        return {"linked": {}, "not_found": []}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {"linked": {}, "not_found": []}


def _save_links(links):
    with open(_links_path(), 'w') as f:
        json.dump(links, f, ensure_ascii=False, indent=2)


def _refresh_token(token):
    try:
        r = requests.post(TOKEN_URL, json={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": token["refresh_token"],
            "redirect_uri": REDIRECT_URI,
        }, timeout=15)
        if r.ok:
            new = r.json()
            new["refresh_token"] = new.get("refresh_token", token["refresh_token"])
            _save_token(new)
            return new
    except Exception:
        pass
    return None


def _valid_token():
    token = _load_token()
    if not token:
        return None
    obtained = token.get("_obtained_at", 0)
    expires_in = token.get("expires_in", 3600)
    if time.time() - obtained > expires_in - 60:
        if "refresh_token" in token:
            new = _refresh_token(token)
            if new:
                return new["access_token"]
            return None
    return token.get("access_token")


def _graphql(query, variables, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        r = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=15)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


_oauth_code = []


class _AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _oauth_code.append(params["code"][0])
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this window.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed</h1><p>No code received.</p>")

    def log_message(self, format, *args):
        pass


def auth():
    _oauth_code.clear()
    try:
        server = HTTPServer(("localhost", 8888), _AuthHandler)
    except OSError:
        print("  Port 8888 is busy. Close other apps using it, or re-run.")
        return False
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    auth_url = f"{AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    print("  Opening browser for AniList authorization...")
    if not webbrowser.open(auth_url):
        print(f"  Visit this URL: {auth_url}")
    timeout = 120
    start = time.time()
    while not _oauth_code and time.time() - start < timeout:
        time.sleep(0.5)
    server.shutdown()
    if not _oauth_code:
        return False
    try:
        r = requests.post(TOKEN_URL, json={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": _oauth_code[0],
        }, timeout=15)
        if r.ok:
            _save_token(r.json())
            return True
    except Exception:
        pass
    return False


def is_authed():
    return _valid_token() is not None


def search_media(title):
    query = """
    query ($search: String) {
        Media(search: $search, type: MANGA) {
            id
            title { romaji english }
        }
    }
    """
    token = _valid_token()
    if not token:
        return None
    data = _graphql(query, {"search": title}, token)
    if data:
        media = data.get("data", {}).get("Media")
        if media:
            return {
                "media_id": media["id"],
                "title": media["title"].get("english") or media["title"].get("romaji") or title,
            }
    return None


def update_progress(media_id, chapter_num):
    query = """
    mutation ($mediaId: Int, $progress: Int) {
        SaveMediaListEntry(mediaId: $mediaId, progress: $progress) {
            id progress
        }
    }
    """
    token = _valid_token()
    if not token:
        return False
    data = _graphql(query, {"mediaId": media_id, "progress": int(float(str(chapter_num)))}, token)
    return data is not None


def get_linked():
    links = _load_links()
    return list(links.get("linked", {}).items())


def unlink(title):
    links = _load_links()
    links.get("linked", {}).pop(title, None)
    _save_links(links)


def forget_not_found(title):
    links = _load_links()
    if title in links.get("not_found", []):
        links["not_found"].remove(title)
        _save_links(links)


def forget_all_not_found():
    links = _load_links()
    links["not_found"] = []
    _save_links(links)


def get_stats():
    links = _load_links()
    return {
        "linked": len(links.get("linked", {})),
        "not_found": len(links.get("not_found", [])),
    }


def clear_auth():
    p = _token_path()
    if os.path.isfile(p):
        os.unlink(p)


def batch_link(title, chapter_num):
    token = _valid_token()
    if not token:
        return "no_auth"
    links = _load_links()
    if title in links.get("linked", {}):
        return "already_linked"
    if title in links.get("not_found", []):
        return "previously_not_found"
    result = search_media(title)
    if not result:
        links.setdefault("not_found", []).append(title)
        _save_links(links)
        return "not_found"
    links.setdefault("linked", {})[title] = {
        "media_id": result["media_id"],
        "media_title": result["title"],
    }
    _save_links(links)
    update_progress(result["media_id"], chapter_num)
    return "linked"


def on_chapter_read(title, chapter_num):
    token = _valid_token()
    if not token:
        return None
    links = _load_links()
    if title in links.get("linked", {}):
        mid = links["linked"][title]["media_id"]
        update_progress(mid, chapter_num)
        return None
    if title in links.get("not_found", []):
        return None
    result = search_media(title)
    if not result:
        links.setdefault("not_found", []).append(title)
        _save_links(links)
        return f"""

  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║   AniList: "{title}" not found                             ║
  ║                                                              ║
  ║   You can manually link it via the AniList menu.             ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝

"""
    links.setdefault("linked", {})[title] = {
        "media_id": result["media_id"],
        "media_title": result["title"],
    }
    _save_links(links)
    update_progress(result["media_id"], chapter_num)
    return None
