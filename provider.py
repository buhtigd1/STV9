import json
import datetime
import requests

URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/refs/heads/main/provider_3/sports_channels.json"


def fetch_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def normalize_clearkey(api_value):
    """
    Convert:
    kid:key

    menjadi format Kodi:
    {"keys":[{"kty":"oct","kid":"...","k":"..."}]}
    jika diperlukan.
    """

    if not api_value:
        return ""

    return api_value.strip()


def validate_data(data):

    if not isinstance(data, list):
        raise ValueError("JSON root must be a list")

    for idx, channel in enumerate(data):

        if not isinstance(channel, dict):
            raise ValueError(f"Channel #{idx} is not an object")

        if "formats" not in channel:
            raise ValueError(
                f"Channel '{channel.get('title', 'unknown')}' has no formats field"
            )

        if not isinstance(channel["formats"], list):
            raise ValueError(
                f"formats of '{channel.get('title')}' must be a list"
            )

    return True


def create_m3u(data, filename="stv9.m3u"):

    with open(filename, "w", encoding="utf-8") as f:

        f.write(
            '#EXTM3U url-tvg="https://raw.githubusercontent.com/buhtigd1/EPG3/main/epg.xml.gz"\n'
        )

        for ch in data:

            channel_name = ch.get("title", "Unknown Channel")
            logo = ch.get("image", "")
            group = ch.get("cat", "Sports")

            for fmt in ch.get("formats", []):

                title = fmt.get("title", channel_name)
                link = fmt.get("link", "")
                api = fmt.get("api", "")
                stream_type = str(fmt.get("type", ""))

                if not link:
                    continue

                full_name = f"{channel_name} - {title}"

                f.write(
                    f'#EXTINF:-1 tvg-id="{full_name}" '
                    f'tvg-name="{full_name}" '
                    f'tvg-logo="{logo}" '
                    f'group-title="{group}",{full_name}\n'
                )

                # DASH
                if ".mpd" in link:

                    f.write(
                        "#KODIPROP:inputstream=inputstream.adaptive\n"
                    )

                    f.write(
                        "#KODIPROP:inputstream.adaptive.manifest_type=mpd\n"
                    )

                    # type 7 biasanya DRM
                    if api:

                        f.write(
                            "#KODIPROP:inputstream.adaptive.license_type=clearkey\n"
                        )

                        f.write(
                            "#KODIPROP:inputstream.adaptive.license_key="
                            f"{normalize_clearkey(api)}\n"
                        )

                # HLS
                elif ".m3u8" in link:

                    f.write(
                        "#KODIPROP:inputstream=inputstream.ffmpeg\n"
                    )

                    f.write(
                        "#KODIPROP:inputstream.adaptive.manifest_type=hls\n"
                    )

                url = link

                if "|" in url:

                    url, headers = url.split("|", 1)

                    headers = headers.replace("&amp;", "&")

                    for header in headers.split("&"):

                        if "=" not in header:
                            continue

                        key, value = header.split("=", 1)

                        key = key.lower()

                        if key == "user-agent":
                            f.write(
                                f"#EXTVLCOPT:http-user-agent={value}\n"
                            )

                        elif key == "referer":
                            f.write(
                                f"#EXTVLCOPT:http-referrer={value}\n"
                            )

                        elif key == "origin":
                            f.write(
                                f"#EXTVLCOPT:http-origin={value}\n"
                            )

                f.write(f"{url}\n")


def create_log(data, filename="stv9.log"):

    with open(filename, "w", encoding="utf-8") as log:

        total_streams = sum(
            len(ch.get("formats", []))
            for ch in data
        )

        log.write(
            f"Generated on: {datetime.datetime.now()}\n"
        )

        log.write(f"Total channels: {len(data)}\n")
        log.write(f"Total streams: {total_streams}\n\n")

        for ch in data:

            log.write(
                f"Channel: {ch.get('title', 'Unknown')}\n"
            )

            for fmt in ch.get("formats", []):

                log.write(
                    f"  {fmt.get('title')} -> "
                    f"{fmt.get('link')}\n"
                )

            log.write("\n")


def main():

    data = fetch_json(URL)

    validate_data(data)

    create_m3u(data)
    create_log(data)

    print(
        f"Done. Channels={len(data)}, "
        f"Streams={sum(len(c.get('formats', [])) for c in data)}"
    )


if __name__ == "__main__":
    main()
