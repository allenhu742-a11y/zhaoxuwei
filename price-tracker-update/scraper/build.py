"""Merge all daily snapshots into history, flag price changes, render the dashboard data.

Usage:  python -m scraper.build
Reads:  data/snapshots/<date>/<CC>.json   (legacy data/snapshots/<date>.json = DE)
Writes: data/history.csv, data/changes.csv, docs/data/<CC>.json, docs/data/index.json, docs/index.html
"""
import csv
import glob
import json
import os
import shutil
from collections import defaultdict

from . import extract as X
from .config import BRAND_COLORS, CATEGORY_LABELS, COUNTRIES, FX_FALLBACK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_snapshots():
    by_cc = defaultdict(list)
    for p in sorted(glob.glob(f"{ROOT}/data/snapshots/*.json")):          # legacy single-country files
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
        s.setdefault("country", "DE"); s.setdefault("currency", "EUR"); s.setdefault("fx_eur", 1.0)
        by_cc["DE"].append(s)
    for p in sorted(glob.glob(f"{ROOT}/data/snapshots/*/*.json")):
        with open(p, encoding="utf-8") as f:
            s = json.load(f)
        cc = s.get("country") or os.path.basename(p)[:2]
        by_cc[cc] = [x for x in by_cc[cc] if x["date"] != s["date"]] + [s]
    for cc in by_cc:
        by_cc[cc].sort(key=lambda s: s["date"])
    return by_cc


def reclean(s):
    """Apply the current cleaning rules to a stored snapshot (keeps old history consistent)."""
    fx = s.get("fx_eur") or FX_FALLBACK.get(s.get("currency", "EUR"), 1.0)
    by_brand = defaultdict(list)
    for it in s["items"]:
        by_brand[it["brand"]].append({**it, "name": it.get("model")})
    rows = []
    for b, items in by_brand.items():
        rows += X.clean_rows(b, items, fx)
    return rows


def build_country(cc, snaps):
    dates = [s["date"] for s in snaps]
    skus, prices, ranks, changes, fx = {}, {}, defaultdict(dict), [], {}
    last = {}
    for s in snaps:
        d = s["date"]
        fx[d] = s.get("fx_eur") or 1.0
        ok_brands = {b for b, st in s.get("status", {}).items() if st.get("count", 0) > 0}
        seen = set()
        for it in reclean(s):
            k = it["key"]
            if k in seen:
                continue
            seen.add(k)
            meta = skus.setdefault(k, {kk: it.get(kk) for kk in ("brand", "category", "model", "variant", "mkey")})
            meta["url"] = it.get("url")
            prices.setdefault(k, {})[d] = [it["price"], it.get("list_price")]
            if k in last and last[k][1] is not None and abs(last[k][1] - it["price"]) >= 0.01:
                old = last[k][1]
                changes.append({"date": d, "key": k, "old": old, "new": it["price"], "delta": round(it["price"] - old, 2),
                                "pct": round((it["price"] - old) / old * 100, 1), "type": "up" if it["price"] > old else "down"})
            elif k not in last and d != dates[0] and it["brand"] in {b for b in snaps[0].get("status", {})}:
                changes.append({"date": d, "key": k, "old": None, "new": it["price"], "delta": None, "pct": None, "type": "new"})
            last[k] = (d, it["price"])
        for k, (ld, lp) in list(last.items()):
            if k not in seen and skus[k]["brand"] in ok_brands and lp is not None:
                changes.append({"date": d, "key": k, "old": lp, "new": None, "delta": None, "pct": None, "type": "gone"})
                last[k] = (d, None)
        for mk, r in (s.get("ranks") or {}).items():
            ranks[mk][d] = r
    c = COUNTRIES.get(cc, {"cur": "EUR", "name": cc})
    return {
        "country": cc, "name": c["name"], "currency": snaps[-1].get("currency", c["cur"]), "dates": dates, "fx": fx,
        "skus": skus, "prices": prices, "ranks": ranks, "changes": changes,
        "status": snaps[-1].get("status", {}), "generated_at": snaps[-1].get("generated_at"),
    }


def main():
    by_cc = load_snapshots()
    os.makedirs(f"{ROOT}/docs/data", exist_ok=True)
    index = {"countries": [], "brandColors": BRAND_COLORS, "categories": CATEGORY_LABELS}
    hist_rows, chg_rows = [], []
    for cc in COUNTRIES:
        snaps = by_cc.get(cc)
        if not snaps:
            continue
        data = build_country(cc, snaps)
        with open(f"{ROOT}/docs/data/{cc}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        index["countries"].append({"code": cc, "name": data["name"], "currency": data["currency"],
                                   "latest": data["dates"][-1], "skus": sum(1 for k in data["prices"] if data["dates"][-1] in data["prices"][k])})
        for k, byd in data["prices"].items():
            m = data["skus"][k]
            for d, (p, lp) in sorted(byd.items()):
                fx = data["fx"].get(d, 1.0)
                hist_rows.append([d, cc, m["brand"], m["category"], m["model"], m["variant"], data["currency"], p, lp or "",
                                  round(p / fx, 2), data["ranks"].get(m["mkey"], {}).get(d, ""), k])
        for ch in data["changes"]:
            m = data["skus"][ch["key"]]
            chg_rows.append([ch["date"], cc, ch["type"], m["brand"], m["category"], m["model"], m["variant"], data["currency"],
                             ch["old"] or "", ch["new"] or "", ch["delta"] or "", ch["pct"] or "", ch["key"]])
        print(f"{cc}: {len(data['dates'])} snapshots, {len(data['skus'])} SKUs, {len(data['changes'])} change events")
    with open(f"{ROOT}/data/history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "country", "brand", "category", "model", "variant", "currency", "price_local", "list_price_local",
                    "price_eur", "listing_rank", "key"])
        w.writerows(sorted(hist_rows))
    with open(f"{ROOT}/data/changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "country", "type", "brand", "category", "model", "variant", "currency", "old", "new", "delta", "pct", "key"])
        w.writerows(sorted(chg_rows))
    with open(f"{ROOT}/docs/data/index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    shutil.copy(f"{ROOT}/scraper/dashboard.html", f"{ROOT}/docs/index.html")


if __name__ == "__main__":
    main()
