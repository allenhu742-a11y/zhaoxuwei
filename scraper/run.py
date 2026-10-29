"""Scrape today's prices from the German official stores.

Usage:  python -m scraper.run [--brands Apple,Samsung] [--date YYYY-MM-DD]
Writes: data/snapshots/<date>.json  and  debug/<brand>.json
"""
import argparse
import asyncio
import datetime as dt
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urldefrag
from zoneinfo import ZoneInfo

import requests
from playwright.async_api import async_playwright

from . import extract as X
from .config import BRANDS, SAMSUNG_API, SAMSUNG_TYPES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
COOKIE_BUTTONS = [
    "#onetrust-accept-btn-handler", "#truste-consent-button", "button#accept-all",
    "button:has-text('Alle akzeptieren')", "button:has-text('Alle Cookies akzeptieren')",
    "button:has-text('Akzeptieren')", "button:has-text('Zustimmen')", "button:has-text('Accept all')",
    "button:has-text('Accept All')", "button:has-text('Einverstanden')", "button:has-text('Ich stimme zu')",
]
SOURCE_RANK = {"apple-bootstrap": 0, "samsung-api": 0, "jsonld": 1, "dom-tile": 2, "json": 3, "dom-price": 4}
MIN_PRICE = {"phone": 60, "tablet": 60, "wear": 15, "audio": 10}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ Samsung API (plain HTTP)
def samsung_api():
    items, dbg = [], []
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.samsung.com/de/"})
    for cat, typ in SAMSUNG_TYPES.items():
        start = 1
        while start < 600:
            url = SAMSUNG_API.format(type=typ, start=start)
            try:
                r = s.get(url, timeout=30)
                data = r.json()
            except Exception as e:  # noqa: BLE001
                dbg.append({"url": url, "error": str(e)[:200]})
                break
            got = X.samsung([data])
            dbg.append({"url": url, "status": r.status_code, "items": len(got)})
            items += got
            total = 0
            for d in X.walk(data):
                if isinstance(d.get("totalRecord"), (int, str)) and str(d["totalRecord"]).isdigit():
                    total = int(d["totalRecord"]); break
            start += 100
            if start > total:
                break
    return items, dbg


# ------------------------------------------------------------------ browser page visit
async def visit(ctx, url, brand, link_rx):
    page = await ctx.new_page()
    captured = []

    async def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct and resp.request.resource_type in ("xhr", "fetch"):
                body = await resp.body()
                if len(body) < 4_000_000:
                    captured.append((resp.url, json.loads(body)))
        except Exception:  # noqa: BLE001
            pass

    page.on("response", on_response)
    rec = {"url": url}
    items, links = [], set()
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        rec["status"] = resp.status if resp else None
        rec["final_url"] = page.url
        await page.wait_for_timeout(2500)
        for sel in COOKIE_BUTTONS:
            try:
                b = page.locator(sel).first
                if await b.is_visible(timeout=300):
                    await b.click(timeout=2000)
                    await page.wait_for_timeout(800)
                    break
            except Exception:  # noqa: BLE001
                pass
        for _ in range(12):                      # lazy-loaded grids
            await page.mouse.wheel(0, 2200)
            await page.wait_for_timeout(450)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        html = await page.content()
        title = await page.title()
        info = await page.evaluate(X.DOM_JS)
        hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        objs = [o for _, o in captured]

        if brand == "Apple":
            items += X.apple(html, page.url, title)
        if brand == "Samsung":
            items += X.samsung(objs, page.url)
        items += X.jsonld(html, page.url)
        items += X.dom(info, page.url)
        items += X.generic_json(objs, page.url)

        rx = re.compile(link_rx)
        for h in hrefs:
            h = urldefrag(urljoin(page.url, h))[0].split("?")[0]
            if rx.search(h):
                links.add(h)
        rec.update({
            "title": title, "json_urls": [u[:160] for u, _ in captured][:40], "links": sorted(links)[:80],
            "tiles": info.get("tiles", [])[:15], "price_texts": info.get("prices", [])[:10],
            "items_by_source": {s: sum(1 for i in items if i["source"] == s) for s in SOURCE_RANK},
            "text_sample": re.sub(r"\s+", " ", (await page.inner_text("body"))[:1500]),
        })
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        await page.close()
    return items, links, rec


async def scrape_brand(pw, brand, cfg):
    log(f"== {brand}")
    raw, debug = [], {"brand": brand, "pages": []}
    if cfg.get("api") == "samsung":
        got, dbg = samsung_api()
        raw += got
        debug["api"] = dbg
        log(f"   samsung api items: {len(got)}")

    browser = await pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = await browser.new_context(locale="de-DE", timezone_id="Europe/Berlin", user_agent=UA,
                                    viewport={"width": 1440, "height": 1000},
                                    extra_http_headers={"Accept-Language": "de-DE,de;q=0.9,en;q=0.6"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    links = set()
    for urls in cfg["seeds"].values():
        for u in urls:
            items, ls, rec = await visit(ctx, u, brand, cfg["link"])
            raw += items; links |= ls; debug["pages"].append(rec)
            log(f"   seed {u} -> {len(items)} items, {len(ls)} links {rec.get('error','')}")

    # expand product links (e.g. product page -> config/buy page)
    targets = set(links)
    for pat, rep in cfg.get("expand", []):
        for l in list(links):
            targets.add(re.sub(pat, rep, l, count=1))
    # Samsung: product pages only if the API gave nothing
    if cfg.get("api") == "samsung" and len(raw) > 20:
        targets = set()
    targets = sorted(targets)[: cfg.get("max_pages", 40)]
    sem = asyncio.Semaphore(3)

    async def one(u):
        async with sem:
            return await visit(ctx, u, brand, cfg["link"])

    for items, _, rec in await asyncio.gather(*(one(u) for u in targets)):
        raw += items; debug["pages"].append(rec)
    log(f"   product pages: {len(targets)}, raw items: {len(raw)}")
    await browser.close()
    return raw, debug


# ------------------------------------------------------------------ normalise
def normalize(brand, raw):
    best = {}
    for it in raw:
        name = (it.get("name") or "").strip()
        cat = X.classify(name)
        if not cat or not it.get("price") or it["price"] < MIN_PRICE[cat]:
            continue
        model = X.strip_variant_tokens(name)
        if brand.lower() not in model.lower() and brand not in ("Apple", "Google"):
            model = f"{brand} {model}"
        variant = (it.get("variant") or "").strip() or "—"
        key = re.sub(r"[^a-z0-9+]+", "-", f"{brand}|{model}|{variant}".lower()).strip("-")
        rank = SOURCE_RANK.get(it["source"], 9)
        cur = best.get(key)
        row = {"key": key, "brand": brand, "category": cat, "model": model, "variant": variant,
               "price": round(it["price"], 2), "list_price": it.get("list_price"), "url": it.get("url"),
               "sku": it.get("sku") or "", "source": it["source"], "_rank": rank}
        if cur is None or rank < cur["_rank"] or (rank == cur["_rank"] and row["price"] < cur["price"]):
            if cur and rank == cur["_rank"] and cur.get("list_price") and not row["list_price"]:
                row["list_price"] = cur["list_price"]
            best[key] = row
    rows = sorted(best.values(), key=lambda r: (r["category"], r["model"], r["price"]))
    for r in rows:
        r.pop("_rank", None)
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brands", default=",".join(BRANDS))
    ap.add_argument("--date", default=dt.datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    os.makedirs(f"{ROOT}/data/snapshots", exist_ok=True)
    os.makedirs(f"{ROOT}/debug", exist_ok=True)
    snap = {"date": a.date, "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "items": [], "status": {}}
    async with async_playwright() as pw:
        for brand in [b.strip() for b in a.brands.split(",") if b.strip()]:
            try:
                raw, debug = await scrape_brand(pw, brand, BRANDS[brand])
                rows = normalize(brand, raw)
                snap["items"] += rows
                snap["status"][brand] = {"count": len(rows), "raw": len(raw)}
            except Exception as e:  # noqa: BLE001
                debug = {"brand": brand, "fatal": f"{type(e).__name__}: {e}"}
                snap["status"][brand] = {"count": 0, "error": str(e)[:300]}
            with open(f"{ROOT}/debug/{brand}.json", "w", encoding="utf-8") as f:
                json.dump(debug, f, ensure_ascii=False, indent=1)
            log(f"   {brand}: {snap['status'][brand]}")
    path = f"{ROOT}/data/snapshots/{a.date}.json"
    if os.path.exists(path):                     # partial re-run: keep other brands from today's file
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        done = set(snap["status"])
        snap["items"] = [i for i in old.get("items", []) if i["brand"] not in done] + snap["items"]
        snap["status"] = {**{b: s for b, s in old.get("status", {}).items() if b not in done}, **snap["status"]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    log(f"wrote {path} with {len(snap['items'])} SKUs")
    if not snap["items"]:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
