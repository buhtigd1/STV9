import requests
import datetime

PLAYLIST_URL = "https://raw.githubusercontent.com/darkbyteprojects/iptv_png/refs/heads/main/provider_3/sports_channels.json"

OUTPUT_M3U = "stv9.m3u"
OUTPUT_LOG = "stv9.log"

TIMEOUT = 15


def download_playlist(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def extract_real_url(url):
    return url.split("|", 1)[0].strip()


def parse_playlist(content):
    lines = content.splitlines()

    header = []
    blocks = []
    current_block = []

    for line in lines:

        if line.startswith("#EXTM3U"):
            header.append(line)
            continue

        if line.startswith("#EXTINF"):

            if current_block:
                blocks.append(current_block)

            current_block = [line]

        else:

            if current_block:
                current_block.append(line)

    if current_block:
        blocks.append(current_block)

    return header, blocks


def get_channel_name(block):

    for line in block:

        if line.startswith("#EXTINF"):

            if "," in line:
                return line.split(",", 1)[1].strip()

            return "Unknown"

    return "Unknown"


def get_stream_url(block):

    for line in reversed(block):

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        return extract_real_url(line)

    return None


def stream_online(url):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        try:

            resp = requests.head(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=TIMEOUT,
            )

            if resp.status_code in (
                200,
                206,
                301,
                302,
            ):
                return True

        except Exception:
            pass

        resp = requests.get(
            url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT,
        )

        return resp.status_code in (
            200,
            206,
        )

    except Exception:
        return False


def save_playlist(header, blocks, filename):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        for line in header:
            f.write(line + "\n")

        for block in blocks:

            for line in block:
                f.write(line + "\n")


def save_log(
    filename,
    total,
    online_list,
    offline_list
):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as log:

        log.write(
            "STREAM VALIDATION REPORT\n"
        )

        log.write(
            "=" * 60 + "\n"
        )

        log.write(
            f"Generated : {datetime.datetime.now()}\n\n"
        )

        log.write(
            f"Total Channel : {total}\n"
        )

        log.write(
            f"Online        : {len(online_list)}\n"
        )

        log.write(
            f"Offline       : {len(offline_list)}\n\n"
        )

        log.write(
            "ONLINE CHANNELS\n"
        )

        log.write(
            "-" * 60 + "\n"
        )

        for name, url in online_list:

            log.write(
                f"[ONLINE] {name}\n"
            )

            log.write(
                f"URL: {url}\n\n"
            )

        log.write("\n")

        log.write(
            "OFFLINE CHANNELS\n"
        )

        log.write(
            "-" * 60 + "\n"
        )

        for name, url in offline_list:

            log.write(
                f"[OFFLINE] {name}\n"
            )

            log.write(
                f"URL: {url}\n\n"
            )


def main():

    print("Downloading playlist...")

    content = download_playlist(
        PLAYLIST_URL
    )

    header, blocks = parse_playlist(
        content
    )

    total = len(blocks)

    alive_blocks = []
    online_list = []
    offline_list = []

    print(
        f"Found {total} channels\n"
    )

    for idx, block in enumerate(
        blocks,
        start=1
    ):

        name = get_channel_name(block)

        url = get_stream_url(block)

        if not url:

            print(
                f"[{idx}/{total}] {name} -> NO URL"
            )

            offline_list.append(
                (name, "NO URL")
            )

            continue

        print(
            f"[{idx}/{total}] Checking {name}"
        )

        if stream_online(url):

            alive_blocks.append(block)

            online_list.append(
                (name, url)
            )

            print("  ONLINE")

        else:

            offline_list.append(
                (name, url)
            )

            print("  OFFLINE")

    save_playlist(
        header,
        alive_blocks,
        OUTPUT_M3U,
    )

    save_log(
        OUTPUT_LOG,
        total,
        online_list,
        offline_list,
    )

    print("\nDone")
    print(
        f"Total   : {total}"
    )
    print(
        f"Online  : {len(online_list)}"
    )
    print(
        f"Offline : {len(offline_list)}"
    )
    print(
        f"Saved   : {OUTPUT_M3U}"
    )
    print(
        f"Log     : {OUTPUT_LOG}"
    )


if __name__ == "__main__":
    main()
