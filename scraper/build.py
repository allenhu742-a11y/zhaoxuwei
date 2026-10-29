"""Merge all daily snapshots into history, flag price changes, render the dashboard.

Usage:  python -m scraper.build
Reads:  data/snapshots/*.json
Writes: data/history.csv, data/changes.csv, docs/index.html
"""
import csv
import glob
import json
import os

from .config import BRAND_COLORS, CATEGORY_LABELS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    snaps = []
    for p in sorted(glob.glob(f"{ROOT}/data/snapshots/*.json")):
        with open(p, encoding="utf-8") as f:
            snaps.append(json.load(f))
    dates = [s["date"] for s in snaps]
    skus, prices, changes = {}, {}, []
    last = {}                                  # key -> (date, price)
    for s in snaps:
        d = s["date"]
        ok_brands = {b for b, st in s.get("status", {}).items() if st.get("count", 0) > 0}
        seen = set()
        for it in s["items"]:
            k = it["key"]
            seen.add(k)
            meta = skus.setdefault(k, {kk: it.get(kk) for kk in ("brand", "category", "model", "variant")})
            meta.update(url=it.get("url"), first=meta.get("first") or d)
            prices.setdefault(k, {})[d] = [it["price"], it.get("list_price")]
            if k in last and last[k][1] is not None and abs(last[k][1] - it["price"]) >= 0.01:
                old = last[k][1]
                changes.append({"date": d, "key": k, "old": old, "new": it["price"],
                                "delta": round(it["price"] - old, 2), "pct": round((it["price"] - old) / old * 100, 1),
                                "type": "up" if it["price"] > old else "down"})
            elif k not in last and d != dates[0]:
                changes.append({"date": d, "key": k, "old": None, "new": it["price"], "delta": None, "pct": None, "type": "new"})
            last[k] = (d, it["price"])
        # SKUs gone from a brand that scraped fine today -> delisted / out of stock
        for k, (ld, lp) in list(last.items()):
            if k not in seen and skus[k]["brand"] in ok_brands and lp is not None:
                changes.append({"date": d, "key": k, "old": lp, "new": None, "delta": None, "pct": None, "type": "gone"})
                last[k] = (d, None)

    for k, m in skus.items():
        m["last"] = last.get(k, (None, None))[1]

    with open(f"{ROOT}/data/history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "brand", "category", "model", "variant", "price_eur", "list_price_eur", "key"])
        for k, byd in prices.items():
            m = skus[k]
            for d, (p, lp) in sorted(byd.items()):
                w.writerow([d, m["brand"], m["category"], m["model"], m["variant"], p, lp or "", k])
    with open(f"{ROOT}/data/changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "type", "brand", "category", "model", "variant", "old_eur", "new_eur", "delta_eur", "pct", "key"])
        for c in changes:
            m = skus[c["key"]]
            w.writerow([c["date"], c["type"], m["brand"], m["category"], m["model"], m["variant"],
                        c["old"] or "", c["new"] or "", c["delta"] or "", c["pct"] or "", c["key"]])

    payload = {
        "dates": dates, "skus": skus, "prices": prices, "changes": changes,
        "status": snaps[-1].get("status", {}) if snaps else {},
        "generated_at": snaps[-1].get("generated_at") if snaps else None,
        "brandColors": BRAND_COLORS, "categories": CATEGORY_LABELS,
    }
    with open(f"{ROOT}/scraper/dashboard.html", encoding="utf-8") as f:
        tpl = f.read()
    os.makedirs(f"{ROOT}/docs", exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    with open(f"{ROOT}/docs/index.html", "w", encoding="utf-8") as f:
        f.write(tpl.replace("/*__DATA__*/null", data))
    print(f"{len(dates)} snapshots, {len(skus)} SKUs, {len(changes)} change events")


if __name__ == "__main__":
    main()
