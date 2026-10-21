import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


URL = (
    "https://raw.githubusercontent.com/"
    "darkbyteprojects/iptv_png/refs/heads/main/"
    "provider_3/sports_channels.json"
)

OUTPUT_M3U = "stv9.m3u"
OUTPUT_LOG = "stv9.log"
EPG_URL = (
    "https://raw.githubusercontent.com/"
    "buhtigd1/EPG3/main/epg.xml.gz"
)

TIMEOUT = 30


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# HTTP Session with Retry
# --------------------------------------------------

def create_session():
    session = requests.Session()

    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(max_retries=retries)

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# --------------------------------------------------
# Fetch JSON
# --------------------------------------------------

def fetch_json(url):
    session = create_session()

    logger.info("Downloading JSON...")

    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    try:
        return response.json()
    except Exception as exc:
        raise ValueError(
            "Response is not valid JSON"
        ) from exc


# --------------------------------------------------
# Validation
# --------------------------------------------------

def validate_data(data):

    if not isinstance(data, list):
        raise ValueError(
            "Root JSON must be a list"
        )

    for idx, channel in enumerate(data):

        if not isinstance(channel, dict):
            raise ValueError(
                f"Channel #{idx} must be object"
            )

        formats = channel.get("formats")

        if formats is None:
            raise ValueError(
                f"Channel #{idx} missing formats"
            )

        if not isinstance(formats, list):
            raise ValueError(
                f"formats in channel #{idx} "
                f"must be list"
            )

        for fidx, fmt in enumerate(formats):

            if not isinstance(fmt, dict):
                raise ValueError(
                    f"Format #{fidx} in "
                    f"channel #{idx} "
                    f"must be object"
                )

    return True


# --------------------------------------------------
# Clearkey
# --------------------------------------------------

def normalize_clearkey(api_value):

    if not api_value:
        return ""

    api_value = str(api_value).strip()

    if ":" not in api_value:
        return api_value

    kid, key = api_value.split(":", 1)

    kid = kid.strip()
    key = key.strip()

    if not kid or not key:
        return api_value

    return json.dumps(
        {
            "keys": [
                {
                    "kty": "oct",
                    "kid": kid,
                    "k": key,
                }
            ]
        },
        separators=(",", ":"),
    )


# --------------------------------------------------
# URL helpers
# --------------------------------------------------

def split_headers(url):

    if "|" not in url:
        return url, {}

    stream_url, header_string = url.split(
        "|",
        1,
    )

    headers = {}

    header_string = header_string.replace(
        "&amp;amp;",
        "&amp;",
    )

    for item in header_string.split("&amp;"):

        if "=" not in item:
            continue

        key, value = item.split("=", 1)

        headers[key.lower().strip()] = (
            value.strip()
        )

    return stream_url.strip(), headers


def detect_stream_type(url):

    parsed = urlparse(url)

    path = parsed.path.lower()

    if path.endswith(".mpd"):
        return "mpd"

    if path.endswith(".m3u8"):
        return "hls"

    return "unknown"


# --------------------------------------------------
# M3U Generator
# --------------------------------------------------

def create_m3u(data, filename):

    path = Path(filename)

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:

        f.write(
            f'#EXTM3U url-tvg="{EPG_URL}"\n'
        )

        stream_count = 0

        for channel in data:

            channel_name = (
                channel.get("title")
                or "Unknown Channel"
            )

            logo = channel.get("image", "")
            group = channel.get("cat", "Sports")

            for fmt in channel.get(
                "formats",
                [],
            ):

                title = (
                    fmt.get("title")
                    or channel_name
                )

                link = fmt.get("link", "")

                if not link:
                    continue

                api = fmt.get("api", "")

                stream_url, headers = (
                    split_headers(link)
                )

                full_name = (
                    f"{channel_name} - {title}"
                )

                f.write(
                    f'#EXTINF:-1 '
                    f'tvg-id="{full_name}" '
                    f'tvg-name="{full_name}" '
                    f'tvg-logo="{logo}" '
                    f'group-title="{group}",'
                    f'{full_name}\n'
                )

                stream_type = (
                    detect_stream_type(
                        stream_url
                    )
                )

                if stream_type == "mpd":

                    f.write(
                        "#KODIPROP:"
                        "inputstream="
                        "inputstream.adaptive\n"
                    )

                    f.write(
                        "#KODIPROP:"
                        "inputstream.adaptive."
                        "manifest_type=mpd\n"
                    )

                    if api:

                        f.write(
                            "#KODIPROP:"
                            "inputstream.adaptive."
                            "license_type=clearkey\n"
                        )

                        f.write(
                            "#KODIPROP:"
                            "inputstream.adaptive."
                            f"license_key="
                            f"{normalize_clearkey(api)}\n"
                        )

                elif stream_type == "hls":

                    f.write(
                        "#KODIPROP:"
                        "inputstream="
                        "inputstream.ffmpeg\n"
                    )

                    f.write(
                        "#KODIPROP:"
                        "inputstream.adaptive."
                        "manifest_type=hls\n"
                    )

                if "user-agent" in headers:
                    f.write(
                        "#EXTVLCOPT:"
                        f"http-user-agent="
                        f"{headers['user-agent']}\n"
                    )

                if "referer" in headers:
                    f.write(
                        "#EXTVLCOPT:"
                        f"http-referrer="
                        f"{headers['referer']}\n"
                    )

                if "origin" in headers:
                    f.write(
                        "#EXTVLCOPT:"
                        f"http-origin="
                        f"{headers['origin']}\n"
                    )

                f.write(
                    f"{stream_url}\n"
                )

                stream_count += 1

    logger.info(
        "Playlist saved: %s (%s streams)",
        filename,
        stream_count,
    )


# --------------------------------------------------
# Report Log
# --------------------------------------------------

def create_log(data, filename):

    path = Path(filename)

    total_streams = sum(
        len(ch.get("formats", []))
        for ch in data
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as log:

        from datetime import datetime

        log.write(
            f"Generated: {datetime.now()}\n"
        )

        log.write(
            f"Channels : {len(data)}\n"
        )

        log.write(
            f"Streams  : {total_streams}\n"
        )

        log.write("\n")

        for ch in data:

            log.write(
                f"[{ch.get('title','Unknown')}]\n"
            )

            for fmt in ch.get(
                "formats",
                [],
            ):

                log.write(
                    f"  {fmt.get('title','N/A')} "
                    f"-> "
                    f"{fmt.get('link','')}\n"
                )

            log.write("\n")

    logger.info(
        "Log saved: %s",
        filename,
    )


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    try:

        data = fetch_json(URL)

        validate_data(data)

        create_m3u(
            data,
            OUTPUT_M3U,
        )

        create_log(
            data,
            OUTPUT_LOG,
        )

        total_streams = sum(
            len(ch.get("formats", []))
            for ch in data
        )

        logger.info(
            "Done | Channels=%s | Streams=%s",
            len(data),
            total_streams,
        )

    except requests.HTTPError as exc:
        logger.error(
            "HTTP Error: %s",
            exc,
        )

    except requests.RequestException as exc:
        logger.error(
            "Network Error: %s",
            exc,
        )

    except Exception as exc:
        logger.exception(
            "Fatal Error: %s",
            exc,
        )


if __name__ == "__main__":
    main()
