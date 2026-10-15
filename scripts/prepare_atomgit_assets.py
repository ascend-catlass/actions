"""Validate the CATLASS eight-wheel bundle and select assets for the shared uploader."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen

from scripts.atomgit_api import AtomGitAPI


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def prepare(api, repository, tag, bundle):
    files = sorted((bundle / 'wheels').glob('*.whl')) + [bundle / 'SHA256SUMS']
    if len(files) != 9 or any(not p.is_file() for p in files):
        raise ValueError('Release bundle must contain eight wheels and SHA256SUMS')
    sums = dict(line.split(None, 1)[::-1] for line in (bundle / 'SHA256SUMS').read_text().splitlines())
    sums = {name.strip().removeprefix('*'): value for name, value in sums.items()}
    for path in files[:-1]:
        if sums.get('wheels/' + path.name, sums.get(path.name)) != digest(path):
            raise ValueError(f'Wheel checksum mismatch: {path.name}')
    from urllib.parse import quote
    try:
        release = api.request('GET', f'/repos/{repository}/releases/tags/{quote(tag, safe="")}')
    except RuntimeError as error:
        if '(HTTP 404)' not in str(error):
            raise
        release = {}
    existing = {asset.get('name'): asset for asset in release.get('assets', [])}
    pending = []
    for path in files:
        if path.name not in existing:
            pending.append(str(path.resolve()))
            continue
        url = existing[path.name].get('browser_download_url', '')
        if not url.startswith('https://'):
            raise ValueError('Existing release asset must have an HTTPS download URL')
        with urlopen(url, timeout=900) as stream:
            remote = hashlib.file_digest(stream, 'sha256').hexdigest()
        if remote != digest(path):
            raise ValueError(f'Release contains a conflicting asset: {path.name}')
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pending = prepare(AtomGitAPI(os.environ['ATOMGIT_TOKEN']), args.repository, args.tag, args.bundle)
    args.output.write_text(json.dumps(pending), encoding='utf-8')


if __name__ == '__main__':
    main()
