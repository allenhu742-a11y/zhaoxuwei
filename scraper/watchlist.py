"""Target model lists ("watchlists") per category, e.g. data/watchlist_audio.csv (brand,model).

Used for three things:
  * discovery  - find product URLs for models the listing pages missed (sitemap / robots.txt)
  * naming     - map a scraped name onto the canonical watchlist name ('AirPods 4 mit aktiver ...' -> 'AirPods 4 ANC')
  * coverage   - report which target models were / were not found per country
"""
import csv
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND_ALIASES = {"huawei": "Huawei", "google pixel": "Google", "google": "Google", "honor": "Honor", "oppo": "OPPO",
                 "vivo": "vivo", "apple": "Apple", "samsung": "Samsung", "xiaomi": "Xiaomi", "shokz": "Shokz",
                 "sony": "Sony", "jbl": "JBL", "soundcore": "Soundcore", "motorola": "Motorola", "oneplus": "OnePlus"}

# feature phrases that stores spell out in their own language -> the short token used in the watchlist
ALIASES = [
    (r"(mit\s+)?aktive[rn]?\s+geräuschunterdrückung|active noise cancell?ation|réduction active du bruit|"
     r"cancellazione attiva del rumore|aktywn\w+ redukcj\w+ szum\w+|anulare activă a zgomotului|aktif gürültü engelleme|"
     r"\bavec\s+anc\b|\bmit\s+anc\b|\bwith\s+anc\b|\bcon\s+anc\b|\bz\s+anc\b", " ANC "),
    (r"usb[\s\-‑]?c", "USB-C"),
    (r"\(?\b(\d)\s*(?:\.|nd|rd|th|st|e|ème|ª|a)?\s*(?:generation|génération|generazione|generacji|generație|generatie|nesil|gen)\b\.?\)?", r" \1 "),
]


def norm(s):
    s = s or ""
    for rx, rep in ALIASES:
        s = re.sub(rx, rep, s, flags=re.I)
    s = s.lower().replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_CACHE = {}


def load(category=None):
    if category in _CACHE:
        return _CACHE[category]
    _CACHE[category] = out = []
    for p in sorted(glob.glob(f"{ROOT}/data/watchlist_*.csv")):
        cat = os.path.basename(p)[len("watchlist_"):-4]
        if category and cat != category:
            continue
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                b = BRAND_ALIASES.get(r["brand"].strip().lower(), r["brand"].strip())
                out.append({"brand": b, "model": r["model"].strip(), "category": cat})
    return out


def _core(brand, model):
    """model text without the brand word, normalised: 'JBL Charge 6' -> 'charge 6'."""
    n = norm(model)
    for w in (brand.lower(), "google"):
        if n.startswith(w + " "):
            n = n[len(w) + 1:]
    return n


def match(brand, name, items=None):
    """Longest watchlist model of this brand whose words appear as a phrase in the scraped name."""
    items = items if items is not None else load()
    n = " " + norm(name) + " "
    best = None
    for w in items:
        if w["brand"].lower() != brand.lower():
            continue
        core = _core(w["brand"], w["model"])
        if core and f" {core} " in n:
            # the scraped name must not continue with another model word ('liberty 5' inside 'liberty 5 pro')
            tail = n.split(f" {core} ", 1)[1].split()
            if tail and tail[0] in {"pro", "max", "plus", "lite", "mini", "ultra", "active", "play", "air", "2", "3", "4", "5", "6"}:
                continue
            if best is None or len(core) > len(_core(best["brand"], best["model"])):
                best = w
    return best


def slugs(brand, model):
    core = _core(brand, model)
    full = norm(model)
    out = {full.replace(" ", "-"), core.replace(" ", "-"), core.replace(" ", ""), core.replace(" ", "_")}
    return {s for s in out if len(s) >= 3}


def url_for_model(urls, brand, model, limit=2):
    """Pick product URLs whose path contains the model slug as a whole segment part."""
    hits = []
    for s in slugs(brand, model):
        rx = re.compile(r"(?:^|[/_\-.])" + re.escape(s) + r"(?:$|[/_\-.?#])", re.I)
        for u in urls:
            path = re.sub(r"^https?://[^/]+", "", u).lower()
            if rx.search(path):
                # avoid 'charge-6' matching 'charge-6-case' style accessory pages
                rest = path.split(s, 1)[1] if s in path else ""
                if re.match(r"[-_](case|cover|strap|tips|cushion|charger|cable|stand|bag|etui|hulle|coque|custodia)", rest):
                    continue
                hits.append(u)
    hits = sorted(set(hits), key=len)
    return hits[:limit]
