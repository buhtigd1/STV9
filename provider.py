import json
import logging
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# --------------------------------------------------
# Config
# --------------------------------------------------

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
CHECK_TIMEOUT = 10
MAX_WORKERS = 20


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Session
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
        allowed_methods=["GET", "HEAD"],
    )

    adapter = HTTPAdapter(
        max_retries=retries
    )

    session.mount(
        "http://",
        adapter,
    )

    session.mount(
        "https://",
        adapter,
    )

    return session


# --------------------------------------------------
# Thread Local Session
# --------------------------------------------------

_thread_local = threading.local()


def get_session():

    if not hasattr(
        _thread_local,
        "session",
    ):
        _thread_local.session = (
            create_session()
        )

    return _thread_local.session


# --------------------------------------------------
# Fetch JSON
# --------------------------------------------------

def fetch_json(url):

    session = create_session()

    logger.info(
        "Downloading JSON..."
    )

    response = session.get(
        url,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


# --------------------------------------------------
# Validation
# --------------------------------------------------

def validate_data(data):

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            "Root JSON must be list"
        )

    for idx, channel in enumerate(data):

        if not isinstance(
            channel,
            dict,
        ):
            raise ValueError(
                f"Channel #{idx} invalid"
            )

        formats = channel.get(
            "formats"
        )

        if not isinstance(
            formats,
            list,
        ):
            raise ValueError(
                f"Channel #{idx} formats invalid"
            )

    return True


# --------------------------------------------------
# Clearkey
# --------------------------------------------------

def normalize_clearkey(api_value):

    if not api_value:
        return ""

    api_value = str(
        api_value
    ).strip()

    if ":" not in api_value:
        return api_value

    kid, key = api_value.split(
        ":",
        1,
    )

    return json.dumps(
        {
            "keys": [
                {
                    "kty": "oct",
                    "kid": kid.strip(),
                    "k": key.strip(),
                }
            ]
        },
        separators=(",", ":"),
    )


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def split_headers(url):

    if "|" not in url:
        return url, {}

    stream_url, header_string = (
        url.split("|", 1)
    )

    header_string = (
        header_string
        .replace(
            "&amp;amp;amp;",
            "&amp;amp;",
        )
    )

    headers = {}

    for item in header_string.split(
        "&amp;amp;"
    ):

        if "=" not in item:
            continue

        key, value = item.split(
            "=",
            1,
        )

        headers[
            key.lower().strip()
        ] = value.strip()

    return (
        stream_url.strip(),
        headers,
    )


def detect_stream_type(url):

    parsed = urlparse(url)

    path = parsed.path.lower()
    query = parsed.query.lower()

    if (
        ".mpd" in path
        or ".mpd" in query
    ):
        return "mpd"

    if (
        ".m3u8" in path
        or ".m3u8" in query
    ):
        return "hls"

    return "unknown"


# --------------------------------------------------
# Stream Health Check
# --------------------------------------------------

def check_stream(
    stream_url,
    headers=None,
):

    session = get_session()

    headers = headers or {}

    try:

        response = session.head(
            stream_url,
            headers=headers,
            allow_redirects=True,
            timeout=CHECK_TIMEOUT,
        )

        if (
            200
            <= response.status_code
            < 300
        ):
            return True

        if response.status_code in (
            403,
            404,
        ):
            return False

    except requests.RequestException:
        pass

    try:

        response = session.get(
            stream_url,
            headers=headers,
            stream=True,
            timeout=CHECK_TIMEOUT,
        )

        response.close()

        return (
            200
            <= response.status_code
            < 300
        )

    except requests.RequestException:

        return False


# --------------------------------------------------
# Worker
# --------------------------------------------------

def validate_format(
    channel,
    fmt,
):

    link = fmt.get(
        "link",
        "",
    )

    if not link:
        return None

    stream_url, headers = (
        split_headers(link)
    )

    ok = check_stream(
        stream_url,
        headers=headers,
    )

    if ok:

        logger.info(
            "OK   | %s",
            stream_url,
        )

        return (
            channel,
            fmt,
        )

    logger.warning(
        "DEAD | %s",
        stream_url,
    )

    return None


# --------------------------------------------------
# Parallel Filter
# --------------------------------------------------

def filter_valid_streams(data):

    total = 0
    valid = 0

    channels_map = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = []

        for channel in data:

            for fmt in channel.get(
                "formats",
                [],
            ):

                total += 1

                futures.append(
                    executor.submit(
                        validate_format,
                        channel,
                        fmt,
                    )
                )

        for future in as_completed(
            futures
        ):

            try:

                result = (
                    future.result()
                )

            except Exception as exc:

                logger.error(
                    "Worker Error: %s",
                    exc,
                )

                continue

            if not result:
                continue

            channel, fmt = result

            title = channel.get(
                "title",
                "Unknown",
            )

            if (
                title
                not in channels_map
            ):

                channel_copy = dict(
                    channel
                )

                channel_copy[
                    "formats"
                ] = []

                channels_map[
                    title
                ] = channel_copy

            channels_map[
                title
            ][
                "formats"
            ].append(fmt)

            valid += 1

    logger.info(
        "Valid Streams: %s/%s",
        valid,
        total,
    )

    return list(
        channels_map.values()
    )


# --------------------------------------------------
# M3U
# --------------------------------------------------

def create_m3u(
    data,
    filename,
):

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
                channel.get(
                    "title"
                )
                or "Unknown"
            )

            logo = channel.get(
                "image",
                "",
            )

            group = channel.get(
                "cat",
                "Sports",
            )

            for fmt in channel.get(
                "formats",
                [],
            ):

                title = (
                    fmt.get(
                        "title"
                    )
                    or channel_name
                )

                link = fmt.get(
                    "link",
                    "",
                )

                api = fmt.get(
                    "api",
                    "",
                )

                stream_url, headers = (
                    split_headers(
                        link
                    )
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
# Report
# --------------------------------------------------

def create_log(
    data,
    filename,
):

    from datetime import datetime

    path = Path(filename)

    total_streams = sum(
        len(
            ch.get(
                "formats",
                [],
            )
        )
        for ch in data
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as log:

        log.write(
            f"Generated : {datetime.now()}\n"
        )

        log.write(
            f"Channels  : {len(data)}\n"
        )

        log.write(
            f"Streams   : {total_streams}\n\n"
        )

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

        data = fetch_json(
            URL
        )

        validate_data(
            data
        )

        logger.info(
            "Checking streams..."
        )

        data = (
            filter_valid_streams(
                data
            )
        )

        create_m3u(
            data,
            OUTPUT_M3U,
        )

        create_log(
            data,
            OUTPUT_LOG,
        )

        total_streams = sum(
            len(
                ch.get(
                    "formats",
                    [],
                )
            )
            for ch in data
        )

        logger.info(
            "Done | Channels=%s | Streams=%s",
            len(data),
            total_streams,
        )

    except Exception as exc:

        logger.exception(
            "Fatal Error: %s",
            exc,
        )


if __name__ == "__main__":
    main()
