import json
import datetime
import requests

URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/refs/heads/main/provider_3/sports_channels.json"

def fetch_json(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def normalize_drm_key(drm_key: str) -> str:
    """Return drm_key as a single line string suitable for Kodi."""
    if not drm_key:
        return ""
    drm_key = drm_key.strip()
    if drm_key.startswith("{"):
        try:
            # Parse JSON and dump back as compact string
            parsed = json.loads(drm_key)
            return json.dumps(parsed, separators=(",", ":"))
        except Exception:
            # If parsing fails, just collapse whitespace
            return " ".join(drm_key.split())
    return drm_key

def create_m3u(data, filename="stv9.m3u"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write('#EXTM3U url-tvg="https://raw.githubusercontent.com/didikc/EPG3/main/epg.xml.gz"\n')
        for ch in data:
            tvg_id = str(ch.get("id", ""))
            name = ch.get("name", "Unknown Channel")
            logo = ch.get("logo", "")
            group = ch.get("group", "Sports")

            for stream in ch.get("streams", []):
                raw_link = stream.get("link", "")
                drm_key = stream.get("drm_key", "")
                drm_scheme = stream.get("drm_scheme", "")
                title = stream.get("name", name)
                if not raw_link:
                    continue

                # EXTINF line
                f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{title}" tvg-logo="{logo}" group-title="{group}",{title}\n')

                # DASH streams
                if ".mpd" in raw_link:
                    f.write("#KODIPROP:inputstream=inputstream.adaptive\n")
                    f.write("#KODIPROP:inputstream.adaptive.manifest_type=mpd\n")
                    if drm_scheme.lower() == "clearkey":
                        f.write("#KODIPROP:inputstream.adaptive.license_type=clearkey\n")
                        if drm_key:
                            f.write(f"#KODIPROP:inputstream.adaptive.license_key={normalize_drm_key(drm_key)}\n")

                # HLS streams
                elif ".m3u8" in raw_link:
                    f.write("#KODIPROP:inputstream=inputstream.ffmpeg\n")
                    f.write("#KODIPROP:inputstream.adaptive.manifest_type=hls\n")

                # Handle extra headers
                url = raw_link
                if "|" in raw_link:
                    url, headers = raw_link.split("|", 1)
                    for header in headers.split("&"):
                        if "=" not in header:
                            continue
                        key, val = header.split("=", 1)
                        key = key.lower()
                        if key == "user-agent":
                            f.write(f"#EXTVLCOPT:http-user-agent={val}\n")
                        elif key == "origin":
                            f.write(f"#EXTVLCOPT:http-origin={val}\n")
                        elif key == "referer":
                            f.write(f"#EXTVLCOPT:http-referrer={val}\n")

                f.write(f"{url}\n")

def create_log(data, filename="stv9.log"):
    with open(filename, "w", encoding="utf-8") as log:
        log.write(f"Generated on: {datetime.datetime.now()}\n")
        total_streams = sum(len(ch.get("streams", [])) for ch in data)
        log.write(f"Total channels: {len(data)}\n")
        log.write(f"Total streams: {total_streams}\n\n")

        for ch in data:
            name = ch.get("name", "Unknown Channel")
            log.write(f"Channel: {name}\n")
            for stream in ch.get("streams", []):
                title = stream.get("name", "")
                url = stream.get("link", "")
                drm_key = stream.get("drm_key", "")
                log.write(f"  {title} -> {url} | drm_key={normalize_drm_key(drm_key)}\n")
            log.write("\n")

def main():
    data = fetch_json(URL)
    create_m3u(data)
    create_log(data)
    print("stv9.m3u and stv9.log created successfully.")

if __name__ == "__main__":
    main()
