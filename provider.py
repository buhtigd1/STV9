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
        for event in data:
            event_name = event.get("eventInfo", {}).get("eventName", "Unknown Event")
            event_cat = event.get("eventInfo", {}).get("eventCat", "General")
            logo = event.get("eventInfo", {}).get("eventLogo", "")
            tvg_id = str(event.get("id", ""))

            teamA = event.get("eventInfo", {}).get("teamA", "")
            teamB = event.get("eventInfo", {}).get("teamB", "")
            match_label = f"{event_name}: {teamA} vs {teamB}" if teamA and teamB else event_name

            for stream in event.get("resolved_streams", []):
                title = stream.get("title", "Unknown Stream")
                raw_link = stream.get("link", "")
                api = stream.get("api", "")
                if not raw_link:
                    continue

                tvg_name = f"{match_label} - {title}"
                f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{logo}" group-title="{event_cat}",{tvg_name}\n')

                # DASH streams
                if ".mpd" in raw_link:
                    f.write("#KODIPROP:inputstream=inputstream.adaptive\n")
                    f.write("#KODIPROP:inputstream.adaptive.manifest_type=mpd\n")
                    f.write("#KODIPROP:inputstream.adaptive.license_type=clearkey\n")
                    if api:
                        f.write(f"#KODIPROP:inputstream.adaptive.license_key={api}\n")

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
        total_streams = sum(len(event.get("resolved_streams", [])) for event in data)
        log.write(f"Total events: {len(data)}\n")
        log.write(f"Total streams: {total_streams}\n\n")
        for event in data:
            event_name = event.get("eventInfo", {}).get("eventName", "Unknown Event")
            teamA = event.get("eventInfo", {}).get("teamA", "")
            teamB = event.get("eventInfo", {}).get("teamB", "")
            match_label = f"{event_name}: {teamA} vs {teamB}" if teamA and teamB else event_name
            log.write(f"Event: {match_label}\n")
            for stream in event.get("resolved_streams", []):
                title = stream.get("title", "Unknown Stream")
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
