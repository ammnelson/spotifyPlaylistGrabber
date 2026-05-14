import requests
import sys
import re
import os
import json
import time
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-read-private playlist-read-collaborative"
TOKEN_CACHE = os.path.join(os.path.dirname(__file__), ".token_cache.json")


def load_cached_token():
    if not os.path.exists(TOKEN_CACHE):
        return None
    with open(TOKEN_CACHE) as f:
        data = json.load(f)
    if data.get("expires_at", 0) > time.time() + 60:
        return data["access_token"]
    if data.get("refresh_token"):
        return refresh_access_token(data["refresh_token"])
    return None


def save_token(token_data):
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
    with open(TOKEN_CACHE, "w") as f:
        json.dump(token_data, f)


def refresh_access_token(refresh_token):
    resp = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    if resp.status_code != 200:
        return None
    data = resp.json()
    if "refresh_token" not in data:
        data["refresh_token"] = refresh_token
    save_token(data)
    return data["access_token"]


def get_token_via_oauth():
    state = secrets.token_urlsafe(16)
    auth_url = "https://accounts.spotify.com/authorize?" + urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })

    auth_code = [None]

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if params.get("state", [None])[0] == state:
                auth_code[0] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Auth complete. You can close this tab.</h2>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    print(f"Opening browser for Spotify login...")
    webbrowser.open(auth_url)
    server.handle_request()

    if not auth_code[0]:
        print("Error: did not receive auth code from Spotify.")
        sys.exit(1)

    resp = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "authorization_code",
        "code": auth_code[0],
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    data = resp.json()
    save_token(data)
    return data["access_token"]


def get_token():
    token = load_cached_token()
    if token:
        return token
    return get_token_via_oauth()


def extract_playlist_id(playlist_input):
    match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_input)
    if match:
        return match.group(1)
    return playlist_input.strip()


def get_playlist_tracks(token, playlist_id):
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/items"
    headers = {"Authorization": f"Bearer {token}"}

    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        for item in data["items"]:
            track = item.get("track") or item.get("item")
            if track is None or track.get("type") != "track":
                continue
            name = track["name"]
            artists = ", ".join(a["name"] for a in track["artists"])
            tracks.append(f"{name} — {artists}")
        url = data.get("next")

    return tracks


def get_playlist_name(token, playlist_id):
    resp = requests.get(f"https://api.spotify.com/v1/playlists/{playlist_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"fields": "name"})
    resp.raise_for_status()
    return resp.json()["name"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python spotifyPlaylistGrabber.py <playlist_url_or_id>")
        sys.exit(1)

    playlist_input = sys.argv[1]
    playlist_id = extract_playlist_id(playlist_input)

    token = get_token()
    playlist_name = get_playlist_name(token, playlist_id)
    tracks = get_playlist_tracks(token, playlist_id)

    safe_name = re.sub(r'[^\w\s-]', '', playlist_name).strip().replace(' ', '_')
    filename = f"{safe_name}.txt"

    with open(filename, "w") as f:
        f.write(f"Playlist: {playlist_name}\n")
        f.write(f"Total tracks: {len(tracks)}\n")
        f.write("-" * 40 + "\n")
        for i, track in enumerate(tracks, 1):
            f.write(f"{i}. {track}\n")

    print(f"Saved {len(tracks)} tracks to {filename}")


if __name__ == "__main__":
    main()
