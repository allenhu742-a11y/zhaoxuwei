"""Scrape today's prices from the official stores of one country.

Usage:  python -m scraper.run --country DE [--brands Apple,Samsung] [--date YYYY-MM-DD]
Writes: data/snapshots/<date>/<CC>.json  and  debug/<CC>/<brand>.json
"""
import argparse
import asyncio
import datetime as dt
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from urllib.parse import urldefrag, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from playwright.async_api import async_playwright

from . import extract as X
from .config import BRANDS, COUNTRIES, FX_FALLBACK, SAMSUNG_API, SAMSUNG_TYPES, tpl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
COOKIE_BUTTONS = [
    "#onetrust-accept-btn-handler", "#truste-consent-button", "button#accept-all",
    "button:has-text('Alle akzeptieren')", "button:has-text('Alle Cookies akzeptieren')", "button:has-text('Akzeptieren')",
    "button:has-text('Zustimmen')", "button:has-text('Accept all')", "button:has-text('Accept All')",
    "button:has-text('Tout accepter')", "button:has-text('Accepter')", "button:has-text('Akceptuj')",
    "button:has-text('Zaakceptuj')", "button:has-text('Accept')", "button:has-text('Acceptă')",
    "button:has-text('Accepta')", "button:has-text('Kabul et')", "button:has-text('Tümünü kabul')",
]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def ecb_rates():
    """Local currency per 1 EUR from the ECB daily reference feed."""
    try:
        r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=20)
        root = ET.fromstring(r.content)
        rates = {"EUR": 1.0}
        for e in root.iter():
            if e.get("currency") and e.get("rate"):
                rates[e.get("currency")] = float(e.get("rate"))
        date = next((e.get("time") for e in root.iter() if e.get("time")), None)
        return {k: rates[k] for k in FX_FALLBACK if k in rates}, date
    except Exception as e:  # noqa: BLE001
        log("ECB rates unavailable, using fallback:", e)
        return dict(FX_FALLBACK), None


# ------------------------------------------------------------------ Samsung API (plain HTTP)
def samsung_api(cc, cur):
    items, dbg = [], []
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": f"https://www.samsung.com/{cc.lower()}/"})
    for cat, typ in SAMSUNG_TYPES.items():
        for sort in ("recommended", "newest"):      # 'recommended' = the listing page's default order
            got_cat, start, total = [], 1, 0
            while start < 600:
                url = SAMSUNG_API.format(type=typ, start=start, cc=cc.lower(), sort=sort)
                try:
                    r = s.get(url, timeout=30)
                    data = r.json()
                except Exception as e:  # noqa: BLE001
                    dbg.append({"url": url, "error": str(e)[:200]})
                    break
                got = X.samsung([data], f"https://www.samsung.com/{cc.lower()}/", cur)
                dbg.append({"url": url, "status": r.status_code, "items": len(got)})
                got_cat += got
                for d in X.walk(data):
                    if str(d.get("totalRecord", "")).isdigit():
                        total = int(d["totalRecord"]); break
                start += 100
                if start > total:
                    break
            if got_cat:
                for i, it in enumerate(got_cat):
                    it["pos"] = i
                items += got_cat
                break
    return items, dbg


# ------------------------------------------------------------------ browser page visit
def same_country(url, final_url, cc):
    """Stores redirect unsupported countries elsewhere; don't record those prices."""
    want = f"/{cc.lower()}"
    p = urlparse(final_url or url)
    return p.path.lower().startswith(want + "/") or p.path.lower() == want


async def visit(ctx, url, brand, link_rx, cc, cur, seed_pos=None):
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
    items, links = [], []
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        rec["status"] = resp.status if resp else None
        rec["final_url"] = page.url
        if not same_country(url, page.url, cc):
            rec["skipped"] = "redirected to another country/site"
            return items, links, rec
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
        for _ in range(12):
            await page.mouse.wheel(0, 2200)
            await page.wait_for_timeout(450)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        html = await page.content()
        title = await page.title()
        info = await page.evaluate(X.DOM_JS, X.CUR_SYM[cur])
        objs = [o for _, o in captured]

        if brand == "Apple":
            items += X.apple(html, page.url, title, cur)
        if brand == "Samsung":
            items += X.samsung(objs, page.url, cur)
        items += X.jsonld(html, page.url, cur)
        items += [i for i in X.dom(info, page.url, cur)
                  if not (seed_pos is not None and i["source"] == "dom-price")]   # a listing page's h1 is a category name
        items += X.generic_json(objs, page.url, cur)
        if seed_pos is not None:                     # listing page: item order = on-page order
            for i, it in enumerate(items):
                it["pos"] = seed_pos * 1000 + 500 + i   # product-link order (seed*1000 + j) ranks first

        rx = re.compile(link_rx)
        seen = set()
        for h, _txt in info.get("cards", []):
            h = urldefrag(urljoin(page.url, h))[0].split("?")[0]
            if rx.search(h) and h not in seen:
                seen.add(h); links.append(h)
        src = {}
        for it in items:
            src[it["source"]] = src.get(it["source"], 0) + 1
        rec.update({
            "title": title, "json_urls": [u[:160] for u, _ in captured][:40], "links": links[:80],
            "tiles": info.get("tiles", [])[:15], "price_texts": info.get("prices", [])[:10], "items_by_source": src,
            "text_sample": re.sub(r"\s+", " ", (await page.inner_text("body"))[:1500]),
        })
        if not items:                                # keep JSON samples so parsers can be added later
            host = urlparse(page.url).hostname.split(".")[-2]
            rec["json_samples"] = [{"url": u[:200], "body": json.dumps(o, ensure_ascii=False)[:2500]}
                                   for u, o in captured if host in (urlparse(u).hostname or "")][:4]
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        await page.close()
    return items, links, rec


async def scrape_brand(pw, brand, cfg, cc):
    c = COUNTRIES[cc]
    cur = c["cur"]
    log(f"== {cc} {brand}")
    raw, debug = [], {"brand": brand, "country": cc, "pages": []}
    if cfg.get("api") == "samsung":
        got, dbg = samsung_api(cc, cur)
        raw += got
        debug["api"] = dbg
        log(f"   samsung api items: {len(got)}")

    launch = {"args": ["--disable-blink-features=AutomationControlled"]}
    if cfg.get("headful") and os.environ.get("DISPLAY"):
        launch["headless"] = False
    browser = await pw.chromium.launch(**launch)
    ctx = await browser.new_context(locale=c["locale"], timezone_id=c["tz"], user_agent=UA,
                                    viewport={"width": 1440, "height": 1000},
                                    extra_http_headers={"Accept-Language": f"{c['locale']},{c['lang']};q=0.9,en;q=0.6"})
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    link_rx = tpl(cfg["link"], cc)
    links, link_order = [], {}
    seed_i = 0
    for urls in cfg["seeds"].values():
        for u in urls:
            u = tpl(u, cc)
            items, ls, rec = await visit(ctx, u, brand, link_rx, cc, cur, seed_pos=seed_i)
            raw += items; debug["pages"].append(rec)
            for j, l in enumerate(ls):
                if l not in link_order:
                    link_order[l] = seed_i * 1000 + j
                    links.append(l)
            seed_i += 1
            log(f"   seed {u} -> {len(items)} items, {len(ls)} links {rec.get('error', '')}{rec.get('skipped', '')}")

    targets = {l: link_order[l] for l in links}
    for pat, rep in cfg.get("expand", []):
        for l in links:
            targets.setdefault(re.sub(pat, rep, l, count=1), link_order[l])
    if cfg.get("api") == "samsung" and len(raw) > 20:
        targets = {}
    chosen = sorted(targets.items(), key=lambda kv: kv[1])[: cfg.get("max_pages", 40)]
    sem = asyncio.Semaphore(3)

    async def one(u, pos):
        async with sem:
            items, _, rec = await visit(ctx, u, brand, link_rx, cc, cur)
            for it in items:                        # product page: rank by where its link sat on the listing
                it.setdefault("pos", pos)
            return items, rec

    for items, rec in await asyncio.gather(*(one(u, p) for u, p in chosen)):
        raw += items; debug["pages"].append(rec)
    log(f"   product pages: {len(chosen)}, raw items: {len(raw)}")
    await browser.close()
    return raw, debug


def listing_ranks(rows):
    """Model rank within (brand, category) by first position on the store's listing pages."""
    best = {}
    for r in rows:
        if r.get("pos") is None:
            continue
        k = r["mkey"]
        best[k] = min(best.get(k, 1e12), r["pos"])
    ranks = {}
    groups = {}
    for r in rows:
        if r["mkey"] in best:
            groups.setdefault((r["brand"], r["category"]), set()).add(r["mkey"])
    for _, ms in groups.items():
        for i, m in enumerate(sorted(ms, key=lambda m: best[m]), 1):
            ranks[m] = i
    return ranks


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="DE", choices=list(COUNTRIES))
    ap.add_argument("--brands", default="")
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    cc = a.country
    c = COUNTRIES[cc]
    date = a.date or dt.datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    brands = [b.strip() for b in a.brands.split(",") if b.strip()] or [b for b, cfg in BRANDS.items() if cc in cfg["countries"]]
    os.makedirs(f"{ROOT}/data/snapshots/{date}", exist_ok=True)
    os.makedirs(f"{ROOT}/debug/{cc}", exist_ok=True)
    fx, fx_date = ecb_rates()
    rate = fx.get(c["cur"], 1.0)
    snap = {"date": date, "country": cc, "currency": c["cur"], "fx_eur": rate, "fx_date": fx_date,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "items": [], "status": {}, "ranks": {}}
    async with async_playwright() as pw:
        for brand in brands:
            try:
                raw, debug = await scrape_brand(pw, brand, BRANDS[brand], cc)
                rows = X.clean_rows(brand, raw, rate)
                snap["ranks"].update(listing_ranks(rows))
                for r in rows:
                    r.pop("pos", None)
                snap["items"] += rows
                snap["status"][brand] = {"count": len(rows), "raw": len(raw)}
            except Exception as e:  # noqa: BLE001
                debug = {"brand": brand, "country": cc, "fatal": f"{type(e).__name__}: {e}"}
                snap["status"][brand] = {"count": 0, "error": str(e)[:300]}
            with open(f"{ROOT}/debug/{cc}/{brand}.json", "w", encoding="utf-8") as f:
                json.dump(debug, f, ensure_ascii=False, indent=1)
            log(f"   {cc} {brand}: {snap['status'][brand]}")
    path = f"{ROOT}/data/snapshots/{date}/{cc}.json"
    if os.path.exists(path) and a.brands:            # partial re-run: keep other brands from today's file
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        done = set(snap["status"])
        snap["items"] = [i for i in old.get("items", []) if i["brand"] not in done] + snap["items"]
        snap["status"] = {**{b: s for b, s in old.get("status", {}).items() if b not in done}, **snap["status"]}
        snap["ranks"] = {**{k: v for k, v in old.get("ranks", {}).items() if k.split("-")[0] not in {d.lower() for d in done}}, **snap["ranks"]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    log(f"wrote {path} with {len(snap['items'])} SKUs")
    if not snap["items"]:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
