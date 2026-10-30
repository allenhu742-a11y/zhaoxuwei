# 欧洲官网价格追踪 / EU Official Store Price Tracker

Every day this records official-store prices (incl. VAT) in **DE, FR, RO, PL and TR**, in local currency plus EUR at the ECB daily rate, of phones, tablets, wearables and audio products from **Apple, Samsung, Google, Xiaomi, Huawei, Honor, Motorola and OnePlus**. Each storage variant is its own row, and colours are merged at the lowest price. It keeps a snapshot per day and flags price changes.

- `data/snapshots/YYYY-MM-DD/<CC>.json`: raw daily snapshot per country (an older `YYYY-MM-DD.json` file is read as DE)
- `data/history.csv`: long-format price history (date × country × SKU, local + EUR, listing rank)
- `data/changes.csv`: every change event (`up` / `down` / `new` / `gone`)
- `docs/index.html` + `docs/data/<CC>.json`: dashboard with a country switch, a local/EUR toggle, a model trend chart (min/avg/max × rank) and the SKU × date grid
- `debug/<CC>/<Brand>.json`: what each page returned, used to fix brands that come back with 0 SKUs

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

## Model trend (CLI)
```bash
python -m scraper.model --model "Galaxy A07"                 # every country that sells it
python -m scraper.model --model "Galaxy A07" --country PL --eur
python -m scraper.model --model "Galaxy A07" --country PL --png a07.png   # price × rank dual-axis chart (pip install matplotlib)
```
For each day this prints the min / avg / max price across the model's storage variants, plus its **listing rank**. Listing rank is the model's position on the brand's own category page (1 = shown first), counted within that brand and category. Samsung's rank uses the store's default "recommended" order. The dashboard shows the same view: pick a model in 型号走势, or click any model name in the grid. You can deep-link with `?country=PL&model=Galaxy%20A07&cur=eur`.

## Countries
The workflow runs one parallel job per country, then a merge job builds the dashboard. If a store redirects a country to another site (for example, a brand with no shop in that country), the run records it as *skipped*, so no prices from the wrong country are saved. To re-run part of a day, use **Run workflow** and enter countries (e.g. `PL,TR`) and/or brands.
