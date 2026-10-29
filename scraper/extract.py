"""Price extraction: brand-specific parsers plus generic fallbacks.

Every extractor returns a list of dicts:
  {name, variant, price, list_price, sku, url, source}
`normalize()` later turns these into tracked rows (brand, category, model, variant).
"""
import json
import re

# ---------------------------------------------------------------- number / text helpers
PRICE_RE = re.compile(
    r"(?:€\s?(\d{1,3}(?:[.  ]\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?))"
    r"|(?:(\d{1,3}(?:[.  ]\d{3})*(?:,\d{1,2}|,-)?|\d+(?:,\d{1,2}|,-)?)\s?(?:€|EUR))"
)
STORAGE_RE = re.compile(r"(\d{1,4})\s?(GB|TB)\b", re.I)
MONTHLY_RE = re.compile(r"monat|mtl\.|/\s?mo\b|monthly|rate|finanz|raten|sparen|spare|rabatt|gutschein|coupon|cashback|bonus|eintausch|trade", re.I)

COLORS = (
    "schwarz black weiß weiss white silber silver grau gray grey blau blue grün green rot red gelb yellow "
    "rosa pink lila purple violett violet gold orange beige creme cream titan titanium natur natural "
    "graphit graphite mint lavendel lavender koralle coral navy marine sand bronze kupfer champagner "
    "obsidian porcelain porzellan hazel rose jade ice icy blush cobalt kobalt onyx phantom midnight mitternacht "
    "polarstern starlight nebelblau salbei sage ultramarin wüstensand desert tiefblau cosmic kosmisch "
    "aqua teal amber khaki olive emerald smaragd ivory elfenbein moonlight shadow ocean sky himmelblau"
).split()
COLOR_RE = re.compile(r"\b(" + "|".join(COLORS) + r")\b", re.I)


def parse_eur(s):
    """'1.099,00 €' -> 1099.0 ; returns None if no plausible price."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        v = float(s)
        return v if 1 <= v <= 10000 else None
    s = str(s)
    m = PRICE_RE.search(s)
    raw = None
    if m:
        raw = m.group(1) or m.group(2)
    elif re.fullmatch(r"\s*\d+(?:[.,]\d{1,2})?\s*", s):
        raw = s.strip()
    if not raw:
        return None
    raw = raw.replace(" ", "").replace(" ", "").replace(",-", "")
    if re.fullmatch(r"\d+\.\d{1,2}", raw):          # 1099.00 (API style)
        v = float(raw)
    else:                                            # 1.099,00 (German style)
        v = float(raw.replace(".", "").replace(",", "."))
    return v if 1 <= v <= 10000 else None


def all_prices(text):
    out = []
    for m in PRICE_RE.finditer(text or ""):
        v = parse_eur(m.group(0))
        if v:
            out.append(v)
    return out


def storage_variant(text):
    """'12 GB + 512 GB' -> '12GB+512GB', '256 GB' -> '256GB', none -> ''"""
    vals = []
    for n, unit in STORAGE_RE.findall(text or ""):
        gb = int(n) * (1024 if unit.upper() == "TB" else 1)
        vals.append((gb, f"{n}{unit.upper()}"))
    if not vals:
        return ""
    # RAM values are small (<=24GB) and storage >=32GB
    storage = [v for v in vals if v[0] >= 32]
    ram = [v for v in vals if v[0] <= 24]
    if storage and ram:
        return f"{ram[0][1]}+{max(storage)[1]}"
    if storage:
        return max(storage)[1]
    return vals[0][1]


def strip_variant_tokens(name):
    n = STORAGE_RE.sub(" ", name or "")
    n = re.sub(r"\(\s*\+?\s*\)|\+\s*(?=\s|$)", " ", n)
    n = COLOR_RE.sub(" ", n)
    n = re.sub(r"\s*[,/|–-]\s*(?=[,/|–-]|$)", " ", n)
    return re.sub(r"\s{2,}", " ", n).strip(" ,-|/")


# ---------------------------------------------------------------- category classifier
ACCESSORY = re.compile(
    r"hülle|\bcase\b|cover|folie|schutzglas|displayschutz|ladegerät|ladekabel|charger|kabel|cable|adapter|"
    r"armband|strap|\bloop\b|tastatur|keyboard|pencil|stylus|s pen\b|stift|ständer|halterung|stand\b|powerbank|"
    r"smarttag|airtag|magsafe|dock|tasche|sleeve|wallet|ladestation|netzteil|schutzhülle|book cover|"
    r"fernseher|\btv\b|monitor|staubsauger|vacuum|scooter|router|kamera|camera|lautsprecher|speaker|soundbar",
    re.I,
)
CATS = [
    ("audio", re.compile(r"buds|airpods|freebuds|freeclip|earbuds|earphones?|kopfhörer|headphones?|beats|\bpods\b|freelace|moto buds|nord buds|oneplus buds", re.I)),
    ("wear", re.compile(r"watch|\bring\b|galaxy fit|\bfit\s?\d|smart\s?band|mi band|\bband\s?\d|honor band|huawei band", re.I)),
    ("tablet", re.compile(r"\bpad\b|\bpad\s?\d|ipad|matepad|galaxy tab|\btab\b|tablet|magicpad|oneplus pad|redmi pad|xiaomi pad|poco pad", re.I)),
    ("phone", re.compile(r"iphone|galaxy [samz]\d|galaxy z|galaxy xcover|pixel\s?\d|xiaomi\s?\d|redmi|poco|pura|mate\s?x?\d|nova|magic\s?v?\d|honor\s?\d|\bmoto\b|razr|edge|oneplus\s?\d|nord|smartphone|handy", re.I)),
]


def classify(name, hint=None):
    if not name or ACCESSORY.search(name):
        return None
    for cat, rx in CATS:
        if rx.search(name):
            return cat
    return None  # never guess: names that match no category keyword are dropped


# ---------------------------------------------------------------- JSON helpers
def iter_json_blocks(html, key):
    """Find every JSON value that follows `"key":` in raw HTML/JS and decode it."""
    dec = json.JSONDecoder()
    for m in re.finditer(r'"%s"\s*:\s*' % re.escape(key), html):
        i = m.end()
        try:
            val, _ = dec.raw_decode(html, i)
            yield val
        except ValueError:
            continue


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


NAME_KEYS = ["displayName", "fmyMarketingName", "productName", "skuName", "goodsName", "spuName", "modelName", "name", "title", "marketingName"]
PRICE_KEYS = ["promotionPrice", "salePrice", "finalPrice", "currentPrice", "sellingPrice", "specialPrice", "discountPrice", "price", "priceValue", "unitPrice", "minPrice", "displayPrice", "amount"]
LIST_KEYS = ["originalPrice", "listPrice", "marketPrice", "rrp", "uvp", "strikePrice", "regularPrice", "price"]
SKU_KEYS = ["modelCode", "sku", "skuCode", "skuId", "partNumber", "productCode", "code", "itemCode", "gtin", "ean"]


def _num(v):
    if isinstance(v, dict):
        for k in ("raw_amount", "value", "amount", "price"):
            if k in v:
                return _num(v[k])
        return None
    return parse_eur(v)


def generic_json(objs, url):
    """Heuristic: any dict with a product-ish name and a price-ish number."""
    out = []
    for root in objs:
        for d in walk(root):
            name = next((d[k] for k in NAME_KEYS if isinstance(d.get(k), str) and 2 < len(d[k]) < 140), None)
            if not name:
                continue
            price = None
            for k in PRICE_KEYS:
                if k in d:
                    price = _num(d[k])
                    if price:
                        break
            if not price:
                continue
            lst = None
            for k in LIST_KEYS:
                if k in d:
                    v = _num(d[k])
                    if v and v > price:
                        lst = v
                        break
            sku = next((str(d[k]) for k in SKU_KEYS if d.get(k) not in (None, "", [])), "")
            variant_src = " ".join(str(d.get(k, "")) for k in ("storage", "capacity", "memory", "romSize", "ram", "rom", "attrValue", "specName", "optionName"))
            out.append({"name": name, "variant": storage_variant(name + " " + variant_src), "price": price,
                        "list_price": lst, "sku": sku, "url": url, "source": "json"})
    return out


# ---------------------------------------------------------------- JSON-LD
def jsonld(html, url):
    out = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        for d in walk(data):
            t = d.get("@type")
            t = " ".join(t) if isinstance(t, list) else str(t or "")
            if "Product" not in t:
                continue
            name = d.get("name") or ""
            offers = d.get("offers") or []
            if isinstance(offers, dict):
                offers = offers.get("offers") or [offers]
            for o in offers if isinstance(offers, list) else []:
                if not isinstance(o, dict):
                    continue
                price = parse_eur(o.get("price") or o.get("lowPrice"))
                if price and str(o.get("priceCurrency", "EUR")).upper() == "EUR":
                    nm = o.get("name") or name
                    out.append({"name": nm, "variant": storage_variant(nm + " " + str(o.get("sku", ""))), "price": price,
                                "list_price": None, "sku": str(o.get("sku") or d.get("sku") or ""), "url": url, "source": "jsonld"})
    return out


# ---------------------------------------------------------------- Apple
def apple(html, url, title):
    """Apple buy pages embed PRODUCT_SELECTION_BOOTSTRAP with products + displayValues.prices."""
    products, prices = [], {}
    for v in iter_json_blocks(html, "products"):
        if isinstance(v, list) and v and isinstance(v[0], dict) and "partNumber" in v[0]:
            products.extend(v)
    for v in iter_json_blocks(html, "prices"):
        if isinstance(v, dict):
            for k, p in v.items():
                if isinstance(p, dict):
                    prices[k] = p
    if not products or not prices:
        return []
    base = re.sub(r"\s*(kaufen|-\s*Apple.*|\|.*)$", "", title or "", flags=re.I).strip()
    base = re.sub(r"\s+kaufen.*$", "", base, flags=re.I).strip() or "Apple"
    names = [n.strip() for n in re.split(r"\s+und\s+|\s*&\s*", base) if n.strip()]
    sizes = sorted({p.get("dimensionScreensize") for p in products if p.get("dimensionScreensize")},
                   key=lambda s: float(re.sub(r"[^0-9_.]", "", s).replace("_", ".") or 0))
    out = []
    for p in products:
        pr = prices.get(p.get("partNumber")) or prices.get(p.get("fullPrice", ""))
        if not pr:
            continue
        cur = pr.get("currentPrice", pr)
        price = _num(cur) or parse_eur(pr.get("amount"))
        if not price:
            continue
        name = names[0] if names else base
        size = p.get("dimensionScreensize")
        if size and len(names) == len(sizes) > 1:
            name = names[sizes.index(size)]
        parts = []
        cap = p.get("dimensionCapacity")
        if cap:
            parts.append(cap.upper().replace("GB", "GB").replace("TB", "TB"))
        for k, v in sorted(p.items()):
            if k.startswith("dimension") and k not in ("dimensionColor", "dimensionCapacity", "dimensionScreensize") and isinstance(v, str):
                parts.append(v)
        if size and len(names) != len(sizes):
            parts.insert(0, size.replace("_", ",").replace("inch", '"'))
        out.append({"name": name, "variant": " ".join(parts).strip(), "price": price, "list_price": None,
                    "sku": p.get("partNumber", ""), "url": url, "source": "apple-bootstrap"})
    return out


# ---------------------------------------------------------------- Samsung
def samsung(objs, url="https://www.samsung.com/de/"):
    """Samsung product-finder API: resultData.productList[].modelList[]"""
    out = []
    for root in objs:
        for d in walk(root):
            ml = d.get("modelList")
            if not isinstance(ml, list):
                continue
            fam = d.get("fmyMarketingName") or ""
            for m in ml:
                if not isinstance(m, dict):
                    continue
                price = parse_eur(m.get("promotionPrice")) or parse_eur(m.get("price"))
                if not price:
                    continue
                lst = parse_eur(m.get("price"))
                name = re.sub(r"<[^>]+>", "", m.get("displayName") or fam)
                opts = " ".join(
                    str(o.get("fmyChipName") or o.get("fmyChipLocalName") or "")
                    for o in (m.get("fmyChipList") or []) if isinstance(o, dict))
                pdp = m.get("pdpUrl") or m.get("originPdpUrl") or ""
                out.append({"name": fam or name, "variant": storage_variant(name + " " + opts + " " + (m.get("modelName") or "")),
                            "price": price, "list_price": lst if lst and lst > price else None,
                            "sku": m.get("modelCode", ""), "source": "samsung-api",
                            "url": ("https://www.samsung.com" + pdp) if pdp.startswith("/") else (pdp or url)})
    return out


# ---------------------------------------------------------------- DOM heuristic (runs in the browser)
DOM_JS = r"""
() => {
  const txt = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const h1 = document.querySelector('h1');
  const og = document.querySelector('meta[property="og:title"]');
  const out = {title: document.title, h1: h1 ? txt(h1) : '', og: og ? og.content : '', tiles: [], prices: []};
  const st = /\b\d{1,4}\s?(GB|TB)\b/i, eur = /(€\s?\d|\d\s?€|\d,-)/;
  const seen = new Set();
  for (const el of document.querySelectorAll('button,label,li,a,[role=radio],[role=option],div,span')) {
    if (el.children.length > 12) continue;
    const t = txt(el);
    if (t.length < 4 || t.length > 160 || !st.test(t) || !eur.test(t)) continue;
    // keep the smallest element: skip if a child already matches
    let childHit = false;
    for (const c of el.children) { const ct = txt(c); if (st.test(ct) && eur.test(ct)) { childHit = true; break; } }
    if (childHit || seen.has(t)) continue;
    seen.add(t); out.tiles.push(t);
    if (out.tiles.length > 80) break;
  }
  for (const el of document.querySelectorAll('[class*="price" i],[data-price],[itemprop=price]')) {
    const t = txt(el); if (t && t.length < 60 && eur.test(t)) out.prices.push(t);
    if (out.prices.length > 40) break;
  }
  return out;
}
"""


def dom(info, url):
    """Turn the DOM_JS result into items: one per storage tile, else one 'base' price."""
    name = (info.get("h1") or info.get("og") or info.get("title") or "").strip()
    name = re.sub(r"\s*[|–-]\s*(Offizieller|Official|Kaufen|Buy|Google Store|Xiaomi|HUAWEI|HONOR|OnePlus|Motorola).*$", "", name, flags=re.I)
    name = re.sub(r"^(Kaufen|Buy)\s+", "", name, flags=re.I).strip()
    out = []
    for t in info.get("tiles", []):
        if MONTHLY_RE.search(t):
            continue
        ps = all_prices(t)
        var = storage_variant(t)
        if not ps or not var:
            continue
        out.append({"name": name, "variant": var, "price": min(ps), "list_price": max(ps) if max(ps) > min(ps) else None,
                    "sku": "", "url": url, "source": "dom-tile"})
    if not out:
        ps = [p for t in info.get("prices", []) if not MONTHLY_RE.search(t) for p in all_prices(t)]
        if ps and name:
            out.append({"name": name, "variant": storage_variant(name), "price": min(ps), "list_price": None,
                        "sku": "", "url": url, "source": "dom-price"})
    return out
