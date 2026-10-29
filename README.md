# 德国官网价格追踪 / DE Official Store Price Tracker

Every day this records the German official-store prices (incl. VAT) of phones, tablets, wearables and audio products from **Apple, Samsung, Google, Xiaomi, Huawei, Honor, Motorola and OnePlus**. Each storage variant is its own row, and colours are merged at the lowest price. It keeps a snapshot per day and flags price changes.

- `data/snapshots/YYYY-MM-DD.json`: raw daily snapshot
- `data/history.csv`: long-format price history (date × SKU)
- `data/changes.csv`: every change event (`up` / `down` / `new` / `gone`)
- `docs/index.html`: dashboard (SKU × date grid; changed cells are highlighted)
- `debug/<Brand>.json`: what each page returned, used to fix brands that come back with 0 SKUs

## Setup (one time, about 5 minutes)

1. Create a new GitHub repo (public is easiest, because it lets Claude read the debug output) and push this folder to it:
   ```bash
   git init -b main && git add . && git commit -m "init"
   git remote add origin https://github.com/<you>/de-price-tracker.git
   git push -u origin main
   ```
2. **Settings → Actions → General → Workflow permissions**: select *Read and write permissions*.
3. **Settings → Pages**: Source = *Deploy from a branch*, Branch = `main`, folder = `/docs`.
4. **Actions → Daily DE price snapshot → Run workflow** starts the first snapshot now. After that it runs every day at 09:00 UTC (10:00 Berlin in winter, 11:00 in summer).

The dashboard is at `https://<you>.github.io/de-price-tracker/`.

## Run locally
```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m scraper.run --brands Apple,Samsung   # or omit --brands for all
python -m scraper.build
```

## How prices are read
| Brand | Method |
|---|---|
| Apple | `PRODUCT_SELECTION_BOOTSTRAP` JSON embedded in each buy page (per part number) |
| Samsung | Samsung's own product-finder JSON API (`searchapi.samsung.com`), the same one its listing pages use |
| Others | Headless Chrome renders listing and product pages, then reads (1) JSON-LD offers, (2) storage tiles showing a price, (3) the store's own JSON responses |

Monthly instalments, trade-in bonuses and coupon amounts are ignored. Accessories are filtered out.

**Note:** official stores change their page structure often. When a brand shows ⚠ 0 in the dashboard status line, open `debug/<Brand>.json` to see which URLs failed and what the page returned, then adjust `scraper/config.py` (seed URLs or link pattern) or add a parser in `scraper/extract.py`.
