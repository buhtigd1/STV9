import json
import datetime
import requests

URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/refs/heads/main/provider_3/sports_channels.json"

def fetch_json(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def create_m3u(data, filename="stv9.m3u"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in data:
            tvg_id = str(ch.get("id", ""))
            name = ch.get("name") or ch.get("title") or "Unknown Channel"
            logo = ch.get("logo") or ch.get("image") or ""
            group = ch.get("group") or ch.get("category") or "Sports"

            for stream in ch.get("resolved_streams", []):
                url = stream.get("link", "")
                api = stream.get("api", "")
                title = stream.get("title", name)

                # EXTINF line
                f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{title}" tvg-logo="{logo}" group-title="{group}",{title}\n')

                # DASH streams
                if ".mpd" in url:
                    f.write("#KODIPROP:inputstream=inputstream.adaptive\n")
                    f.write("#KODIPROP:inputstream.adaptive.manifest_type=mpd\n")
                    f.write("#KODIPROP:inputstream.adaptive.license_type=clearkey\n")
                    if api:
                        f.write(f"#KODIPROP:inputstream.adaptive.license_key={api}\n")

                # HLS streams
                elif ".m3u8" in url:
                    f.write("#KODIPROP:inputstream=inputstream.ffmpeg\n")
                    f.write("#KODIPROP:inputstream.adaptive.manifest_type=hls\n")

                # Handle extra headers
                clean_url = url
                if "|" in url:
                    clean_url, headers = url.split("|", 1)
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

                f.write(f"{clean_url}\n")

def create_log(data, filename="stv9.log"):
    with open(filename, "w", encoding="utf-8") as log:
        log.write(f"Generated on: {datetime.datetime.now()}\n")
        total_streams = sum(len(ch.get("resolved_streams", [])) for ch in data)
        log.write(f"Total channels: {len(data)}\n")
        log.write(f"Total streams: {total_streams}\n\n")

        for ch in data:
            name = ch.get("name") or ch.get("title") or "Unknown Channel"
            log.write(f"Channel: {name}\n")
            for stream in ch.get("resolved_streams", []):
                title = stream.get("title", "")
                url = stream.get("link", "")
                api = stream.get("api", "")
                log.write(f"  {title} -> {url} | license_key={api}\n")
            log.write("\n")

def main():
    data = fetch_json(URL)
    create_m3u(data)
    create_log(data)
    print("stv9.m3u and stv9.log created successfully.")

if __name__ == "__main__":
    main()
