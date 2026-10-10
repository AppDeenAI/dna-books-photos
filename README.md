# DNA Lifestyle — Books catalogue for Shopify

**Browse the photos:** https://appdeenai.github.io/dna-books-photos/

Source sheet: `Books _16.9.26_1.xlsx` — 2,179 products (2,063 books, 116 stationery items).

| File | What it is |
|---|---|
| `Books_Shopify_Import.csv` | Ready-to-import Shopify product CSV (current Shopify template): titles, English descriptions, vendor, category, tags, SKU, barcode, price, photos |
| `Books_Shopify_Review.xlsx` | Review workbook: match result per product, photo source, notes, and a **Needs attention** tab (209 items) |
| `photos/` | Every product photo, downloaded from its source — `photos/books/<letter>/<handle>-<n>.jpg`, `photos/stationery/<handle>-<n>.jpg` |
| `photos_manifest.csv` | Photo list: barcode, SKU, title, photo number, source URL, file path |
| `photos_report.csv` | Download result for every photo (status, file, size) |
| `index.html`, `gallery_data.json`, `thumbs/` | The GitHub Pages gallery — rebuild with `python scripts/build_site.py` |

## Photos
- **Books:** front cover. 1,755 are Amazon's 1500px image for the exact ISBN (verified against Goodreads or by eye); the rest come from Goodreads / Open Library.
- **DNH stationery:** 2–5 photos each from Dawenha's Jordan store (matched by barcode).
- **43 products have no photo** — they import as Draft; listed in the review workbook.

## Import into Shopify
1. Shopify admin → Products → Import → upload `Books_Shopify_Import.csv`. Leave "Overwrite products with matching handles" unticked.
2. Inventory is tracked and starts at 0 — load stock before products show as available.
3. Descriptions are in English; use Translate & Adapt for Arabic.

The photos in `photos/` are downloaded by the **Download product photos** GitHub Action (`.github/workflows/download-photos.yml`) — re-run it from the Actions tab to fetch anything that failed.
