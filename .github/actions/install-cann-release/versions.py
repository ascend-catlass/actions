"""Select CANN releases by SemVer precedence, never lexical/date order."""
from html.parser import HTMLParser
import re
import sys

NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION = re.compile(rf"({NUMBER})\.({NUMBER})\.({NUMBER})(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?")


def version_key(version):
    match = VERSION.fullmatch(version)
    if not match:
        raise ValueError(f"Invalid CANN release version: {version}")
    major, minor, patch, prerelease = match.groups()
    identifiers = []
    for value in prerelease.split(".") if prerelease else []:
        if value.isdigit() and len(value) > 1 and value.startswith("0"):
            raise ValueError(f"Leading zero in prerelease: {version}")
        identifiers.append((0, int(value)) if value.isdigit() else (1, value))
    return int(major), int(minor), int(patch), prerelease is None, tuple(identifiers)


class ReleaseLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.versions = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        for key, value in attrs if tag == "a" else []:
            if key == "href" and value and value.endswith("/"):
                version = value[:-1]
                if VERSION.fullmatch(version):
                    version_key(version)
                    self.versions.add(version)


def latest_version(html):
    versions = ReleaseLinks(html).versions
    if not versions:
        raise ValueError("No CANN release version directories found")
    return max(versions, key=version_key)


if __name__ == "__main__":
    operation, *args = sys.argv[1:]
    if operation == "latest":
        print(latest_version(sys.stdin.read()))
    elif operation == "validate":
        version_key(args[0])
    elif operation == "newer":
        raise SystemExit(0 if version_key(args[0]) > version_key(args[1]) else 1)
    else:
        raise SystemExit(f"Unknown operation: {operation}")
