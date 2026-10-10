"""Download every product photo listed in photos_manifest.csv into the repo.

Runs inside GitHub Actions (see .github/workflows/download-photos.yml).
Already-downloaded files are skipped, so the workflow can be re-run safely.
Writes photos_report.csv with the result for every photo.
"""
import csv
import io
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

MANIFEST = 'photos_manifest.csv'
REPORT = 'photos_report.csv'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
}
EXT = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'GIF': '.gif'}


def existing(stem):
    for ext in EXT.values():
        if os.path.exists(stem + ext):
            return stem + ext
    return None


def fetch(row):
    stem = row['file_stem']
    done = existing(stem)
    if done:
        with Image.open(done) as im:
            return {**row, 'status': 'ok', 'file': done, 'width': im.width, 'height': im.height, 'error': ''}
    last = ''
    for attempt in range(4):
        try:
            r = requests.get(row['source_url'], headers=HEADERS, timeout=40)
            if r.status_code != 200:
                last = f'HTTP {r.status_code}'
                time.sleep(2 * (attempt + 1))
                continue
            im = Image.open(io.BytesIO(r.content))
            im.load()
            if im.width < 100 or im.height < 100:
                return {**row, 'status': 'too_small', 'file': '', 'width': im.width, 'height': im.height, 'error': ''}
            path = stem + EXT.get(im.format, '.jpg')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as fh:
                fh.write(r.content)
            return {**row, 'status': 'ok', 'file': path, 'width': im.width, 'height': im.height, 'error': ''}
        except Exception as e:  # network error or not an image
            last = str(e)[:200]
            time.sleep(2 * (attempt + 1))
    return {**row, 'status': 'failed', 'file': '', 'width': '', 'height': '', 'error': last}


def main():
    rows = list(csv.DictReader(open(MANIFEST, encoding='utf-8')))
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(fetch, rows))
    fields = list(rows[0].keys()) + ['status', 'file', 'width', 'height', 'error']
    with open(REPORT, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(results)
    ok = sum(1 for r in results if r['status'] == 'ok')
    print(f'{ok}/{len(results)} photos downloaded')
    for r in results:
        if r['status'] != 'ok':
            print('  ', r['status'], r['barcode'], r['source_url'], r['error'])


if __name__ == '__main__':
    main()
