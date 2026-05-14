import requests
import sys
import re
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


def get_token():
    resp = requests.post("https://accounts.spotify.com/api/token", data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def extract_playlist_id(playlist_input):
    match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_input)
    if match:
        return match.group(1)
    return playlist_input.strip()


def get_playlist_tracks(token, playlist_id):
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {token}"}

    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        for item in data["items"]:
            track = item.get("track")
            if track is None:
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
