import json
import datetime
import requests

URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/refs/heads/main/provider_3/sports_channels.json"


def fetch_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def validate_data(data):
    """Validate JSON structure before processing."""

    if not isinstance(data, list):
        raise ValueError("JSON root harus berupa array/list")

    for i, channel in enumerate(data):

        if not isinstance(channel, dict):
            raise ValueError(f"Item channel ke-{i} bukan object")

        if "name" not in channel:
            raise ValueError(f"Channel ke-{i} tidak memiliki field 'name'")

        if "streams" not in channel:
            raise ValueError(
                f"Channel '{channel.get('name', 'Unknown')}' tidak memiliki field 'streams'"
            )

        if not isinstance(channel["streams"], list):
            raise ValueError(
                f"Field streams pada '{channel['name']}' harus berupa array"
            )

        for j, stream in enumerate(channel["streams"]):

            if not isinstance(stream, dict):
                raise ValueError(
                    f"Stream ke-{j} pada channel '{channel['name']}' bukan object"
                )

            if "link" not in stream:
                raise ValueError(
                    f"Stream ke-{j} pada channel '{channel['name']}' "
                    f"tidak memiliki field 'link'"
                )

    return True


def normalize_drm_key(drm_key: str) -> str:
    """Return drm_key as a single-line string suitable for Kodi."""

    if not drm_key:
        return ""

    drm_key = drm_key.strip()

    if drm_key.startswith("{"):
        try:
            parsed = json.loads(drm_key)
            return json.dumps(parsed, separators=(",", ":"))
        except Exception:
            return " ".join(drm_key.split())

    return drm_key


def create_m3u(data, filename="stv9.m3u"):
    with open(filename, "w", encoding="utf-8") as f:

        f.write(
            '#EXTM3U url-tvg="https://raw.githubusercontent.com/buhtigd1/EPG3/main/epg.xml.gz"\n'
        )

        for ch in data:

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

                tvg_id = title

                f.write(
                    f'#EXTINF:-1 tvg-id="{tvg_id}" '
                    f'tvg-name="{title}" '
                    f'tvg-logo="{logo}" '
                    f'group-title="{group}",{title}\n'
                )

                # DASH
                if ".mpd" in raw_link:
                    f.write("#KODIPROP:inputstream=inputstream.adaptive\n")
                    f.write(
                        "#KODIPROP:inputstream.adaptive.manifest_type=mpd\n"
                    )

                    if drm_scheme.lower() == "clearkey":
                        f.write(
                            "#KODIPROP:inputstream.adaptive.license_type=clearkey\n"
                        )

                        if drm_key:
                            f.write(
                                "#KODIPROP:inputstream.adaptive.license_key="
                                f"{normalize_drm_key(drm_key)}\n"
                            )

                # HLS
                elif ".m3u8" in raw_link:
                    f.write("#KODIPROP:inputstream=inputstream.ffmpeg\n")
                    f.write(
                        "#KODIPROP:inputstream.adaptive.manifest_type=hls\n"
                    )

                url = raw_link

                # Handle extra headers
                if "|" in raw_link:
                    url, headers = raw_link.split("|", 1)

                    for header in headers.split("&"):

                        if "=" not in header:
                            continue

                        key, val = header.split("=", 1)
                        key = key.lower()

                        if key == "user-agent":
                            f.write(
                                f"#EXTVLCOPT:http-user-agent={val}\n"
                            )

                        elif key == "origin":
                            f.write(
                                f"#EXTVLCOPT:http-origin={val}\n"
                            )

                        elif key == "referer":
                            f.write(
                                f"#EXTVLCOPT:http-referrer={val}\n"
                            )

                f.write(f"{url}\n")


def create_log(data, filename="stv9.log"):
    with open(filename, "w", encoding="utf-8") as log:

        log.write(
            f"Generated on: "
            f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
        )

        total_streams = sum(
            len(ch.get("streams", []))
            for ch in data
        )

        log.write(f"Total channels: {len(data)}\n")
        log.write(f"Total streams: {total_streams}\n\n")

        for ch in data:

            name = ch.get("name", "Unknown Channel")

            log.write(f"Channel: {name}\n")

            for stream in ch.get("streams", []):

                title = stream.get("name", "")
                url = stream.get("link", "")
                drm_key = stream.get("drm_key", "")

                log.write(
                    f"  {title} -> {url} | "
                    f"drm_key={normalize_drm_key(drm_key)}\n"
                )

            log.write("\n")


def main():
    try:
        print("Downloading JSON...")

        data = fetch_json(URL)

        print("Validating JSON structure...")
        validate_data(data)

        print("Creating M3U...")
        create_m3u(data)

        print("Creating LOG...")
        create_log(data)

        total_channels = len(data)
        total_streams = sum(
            len(ch.get("streams", []))
            for ch in data
        )

        print(
            f"Done! {total_channels} channels "
            f"and {total_streams} streams processed."
        )

    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")

    except ValueError as e:
        print(f"Validation error: {e}")

    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
