"""Upload finished videos to your own YouTube channel with the YouTube Data API v3.

Free: you create a Google OAuth client ("Desktop app") in your own Google Cloud project, with the YouTube Data API
v3 enabled, and paste its client ID and secret into Settings > API keys (YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET).
Then "Connect YouTube" once on this PC. The refresh token stays in the studio's data folder (never logged, never
sent anywhere but Google).

Endpoints and fields follow Google's official discovery document for youtube v3: videos.insert (resumable upload
to /upload/youtube/v3/videos, scope youtube.upload), thumbnails.set (/upload/youtube/v3/thumbnails/set),
channels.list (youtube/v3/channels, scope youtube.readonly). status.publishAt can only be set while the video is
private (it goes public at that time).
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse

from . import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://youtube.googleapis.com"
UPLOAD_URL = API + "/upload/youtube/v3/videos"
THUMB_URL = API + "/upload/youtube/v3/thumbnails/set"
CHANNELS_URL = API + "/youtube/v3/channels"
SCOPES = ("https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly")
CHUNK = 8 * 1024 * 1024            # a multiple of 256 KB, as resumable uploads require
CATEGORY_EDUCATION = "27"

_pending = {}                      # OAuth state -> (code_verifier, redirect_uri, created)
_token = {"access": None, "exp": 0.0}
_lock = threading.Lock()


class YouTubeError(Exception):
    pass


def token_file():
    return os.path.join(config.DATA_DIR, "youtube_token.json")


def client():
    return config.secret("YOUTUBE_CLIENT_ID"), config.secret("YOUTUBE_CLIENT_SECRET")


def configured():
    cid, cs = client()
    return bool(cid and cs)


def _saved():
    try:
        with open(token_file(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def connected():
    return bool(_saved().get("refresh_token"))


def _save(data):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = token_file()
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def redirect_uri(port):
    # a loopback address on this PC (Google allows any port for "Desktop app" clients); the dashboard's front page
    # finishes the sign-in when it sees ?code=...&state=...
    return f"http://localhost:{int(port)}/"


def auth_url(port):
    """The Google sign-in page to open. Uses PKCE and a one-time state value."""
    if not configured():
        raise YouTubeError("add YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET under Settings > API keys first")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    with _lock:
        for k in [k for k, v in _pending.items() if time.time() - v[2] > 900]:
            _pending.pop(k, None)
        _pending[state] = (verifier, redirect_uri(port), time.time())
    q = dict(client_id=client()[0], redirect_uri=redirect_uri(port), response_type="code", scope=" ".join(SCOPES),
             access_type="offline", prompt="consent", include_granted_scopes="true", state=state,
             code_challenge=challenge, code_challenge_method="S256")
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def is_pending(state):
    with _lock:
        return state in _pending


def finish(code, state):
    """Trade the code from Google's redirect for tokens and remember the refresh token."""
    import httpx
    with _lock:
        item = _pending.pop(state, None)
    if not item:
        raise YouTubeError("this sign-in link expired; click Connect YouTube again")
    verifier, ruri, _ = item
    cid, cs = client()
    r = httpx.post(TOKEN_URL, data=dict(code=code, client_id=cid, client_secret=cs, redirect_uri=ruri,
                                        grant_type="authorization_code", code_verifier=verifier), timeout=30)
    if r.status_code != 200:
        raise YouTubeError(f"Google refused the sign-in ({r.status_code}): {r.text[:200]}")
    data = r.json()
    if not data.get("refresh_token"):
        raise YouTubeError("Google didn't return a refresh token; remove the app's access in your Google account "
                           "and connect again")
    _save(dict(refresh_token=data["refresh_token"], scope=data.get("scope", ""), at=time.time()))
    with _lock:
        _token.update(access=data.get("access_token"), exp=time.time() + float(data.get("expires_in", 3000)) - 60)
    try:
        ch = channel()
        if ch:
            s = _saved()
            s["channel"] = ch
            _save(s)
    except Exception:
        pass
    return True


def access_token():
    import httpx
    with _lock:
        if _token["access"] and time.time() < _token["exp"]:
            return _token["access"]
    rt = _saved().get("refresh_token")
    if not rt:
        raise YouTubeError("YouTube isn't connected yet")
    cid, cs = client()
    r = httpx.post(TOKEN_URL, data=dict(client_id=cid, client_secret=cs, refresh_token=rt, grant_type="refresh_token"),
                   timeout=30)
    if r.status_code != 200:
        raise YouTubeError(f"couldn't refresh the YouTube sign-in ({r.status_code}); connect YouTube again")
    data = r.json()
    with _lock:
        _token.update(access=data["access_token"], exp=time.time() + float(data.get("expires_in", 3000)) - 60)
        return _token["access"]


def channel():
    import httpx
    r = httpx.get(CHANNELS_URL, params=dict(part="snippet", mine="true"),
                  headers={"Authorization": f"Bearer {access_token()}"}, timeout=30)
    if r.status_code != 200:
        return None
    items = r.json().get("items") or []
    if not items:
        return None
    sn = items[0].get("snippet") or {}
    return dict(id=items[0].get("id"), title=sn.get("title"))


def status():
    s = _saved()
    return dict(configured=configured(), connected=bool(s.get("refresh_token")), channel=s.get("channel"))


def disconnect():
    import httpx
    rt = _saved().get("refresh_token")
    if rt:
        try:
            httpx.post(REVOKE_URL, params=dict(token=rt), timeout=15)
        except Exception:
            pass
    try:
        os.remove(token_file())
    except OSError:
        pass
    with _lock:
        _token.update(access=None, exp=0.0)


# ------------------------------------------------------------------ upload
def clean_text(s, limit):
    s = str(s or "").replace("<", "").replace(">", "")
    return s[:limit]


def video_resource(title, description, tags=(), privacy="private", publish_at=None, made_for_kids=False,
                   synthetic=False, category=CATEGORY_EDUCATION, language="en"):
    """The JSON body for videos.insert (part=snippet,status)."""
    tags = [clean_text(t, 60) for t in tags or [] if str(t).strip()]
    while tags and len(",".join(tags)) > 450:      # YouTube's limit is about 500 characters for all tags
        tags.pop()
    status = {"privacyStatus": privacy if privacy in ("private", "unlisted", "public") else "private",
              "selfDeclaredMadeForKids": bool(made_for_kids), "containsSyntheticMedia": bool(synthetic)}
    if publish_at:
        status["privacyStatus"] = "private"        # publishAt only works on private videos
        status["publishAt"] = publish_at
    return {"snippet": {"title": clean_text(title, 100) or "Untitled", "description": clean_text(description, 4900),
                        "tags": tags, "categoryId": str(category), "defaultLanguage": language,
                        "defaultAudioLanguage": language},
            "status": status}


def upload(video_path, resource, thumbnail=None, progress=None):
    """Resumable upload. progress(fraction, message). Returns the new video's id."""
    import httpx
    size = os.path.getsize(video_path)
    progress = progress or (lambda f, m: None)
    headers = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}
    r = httpx.post(UPLOAD_URL, params=dict(uploadType="resumable", part="snippet,status"), headers=headers,
                   content=json.dumps(resource).encode(), timeout=60)
    if r.status_code != 200 or not r.headers.get("location"):
        raise YouTubeError(f"YouTube didn't accept the upload ({r.status_code}): {_reason(r)}")
    session = r.headers["location"]
    sent = 0
    tries = 0
    video_id = None
    with open(video_path, "rb") as f:
        while video_id is None:
            f.seek(sent)
            chunk = f.read(CHUNK)
            end = sent + len(chunk) - 1
            try:
                r = httpx.put(session, content=chunk, timeout=300,
                              headers={"Authorization": f"Bearer {access_token()}",
                                       "Content-Range": f"bytes {sent}-{end}/{size}"})
            except httpx.HTTPError as e:
                r = None
                err = str(e)
            if r is not None and r.status_code in (200, 201):
                video_id = r.json().get("id")
                break
            if r is not None and r.status_code == 308:
                rng = r.headers.get("range")
                sent = int(rng.split("-")[1]) + 1 if rng else 0
                tries = 0
                progress(min(0.97, sent / size), f"uploading {sent / 1e6:.0f} of {size / 1e6:.0f} MB")
                continue
            if r is not None and r.status_code not in (500, 502, 503, 504):
                raise YouTubeError(f"YouTube stopped the upload ({r.status_code}): {_reason(r)}")
            tries += 1
            if tries > 6:
                raise YouTubeError(f"the upload kept failing: {err if r is None else r.status_code}")
            time.sleep(min(60, 2 ** tries))
            # ask how much arrived, then carry on from there
            try:
                q = httpx.put(session, content=b"", timeout=60, headers={"Authorization": f"Bearer {access_token()}",
                                                                         "Content-Range": f"bytes */{size}"})
                if q.status_code in (200, 201):
                    video_id = q.json().get("id")
                elif q.status_code == 308:
                    rng = q.headers.get("range")
                    sent = int(rng.split("-")[1]) + 1 if rng else 0
            except httpx.HTTPError:
                pass
    if not video_id:
        raise YouTubeError("YouTube didn't return a video id")
    progress(0.98, "setting the thumbnail")
    if thumbnail and os.path.exists(thumbnail):
        try:
            set_thumbnail(video_id, thumbnail)
        except YouTubeError as e:
            progress(0.99, f"video uploaded, but the thumbnail wasn't accepted: {e}")
    return video_id


def set_thumbnail(video_id, path):
    import httpx
    mt = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        r = httpx.post(THUMB_URL, params=dict(videoId=video_id, uploadType="media"), content=f.read(), timeout=120,
                       headers={"Authorization": f"Bearer {access_token()}", "Content-Type": mt})
    if r.status_code != 200:
        raise YouTubeError(f"{r.status_code}: {_reason(r)}")


def _reason(r):
    try:
        e = r.json().get("error") or {}
        reasons = ", ".join(x.get("reason", "") for x in e.get("errors") or [] if x.get("reason"))
        return (e.get("message") or "") + (f" [{reasons}]" if reasons else "")
    except Exception:
        return r.text[:200]
