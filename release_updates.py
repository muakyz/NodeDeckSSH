"""Check a publisher-controlled HTTPS release manifest."""
import json
import re
from urllib.parse import urlsplit
from urllib.request import urlopen

VERSION = "0.10.4"
DEFAULT_FEED_URL = "https://updates.waytfeys.uk/latest.json"


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,5}(\.[0-9]{1,5}){2}", value):
        raise ValueError("Invalid release version.")
    return tuple(map(int, value.split(".")))


def https_url(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None


def check_release(url):
    if not https_url(url):
        raise ValueError("Enter an HTTPS release manifest URL.")
    with urlopen(url, timeout=8) as response:
        if not https_url(response.geturl()):
            raise ValueError("The release feed must use HTTPS.")
        content = response.read(65537)
    if len(content) > 65536:
        raise ValueError("The release manifest is too large.")
    manifest = json.loads(content)
    version, download = manifest["version"], manifest["download_url"]
    if not https_url(download):
        raise ValueError("The installer link must use HTTPS.")
    return (version, download) if version_tuple(version) > version_tuple(VERSION) else None
