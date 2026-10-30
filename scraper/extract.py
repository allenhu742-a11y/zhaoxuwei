"""Price extraction: brand-specific parsers, generic fallbacks, name cleaning.

Extractors return dicts: {name, variant, price, list_price, sku, url, source, pos}
Prices are in the country's local currency (EUR / RON / PLN / TRY).
"""
import html as htmllib
import json
import re

# ---------------------------------------------------------------- currency
CUR_SYM = {
    "EUR": r"€|EUR",
    "PLN": r"zł|zl|PLN",
    "RON": r"lei|Lei|LEI|RON",
    "TRY": r"₺|TL|TRY",
}
CUR_RANGE = {"EUR": (1, 12000), "PLN": (4, 50000), "RON": (5, 60000), "TRY": (30, 600000)}
NUM = r"\d{1,3}(?:[.   ']\d{3})+(?:,\d{1,2}|,-)?|\d+(?:,\d{1,2}|,-)?"
_PRICE_RE = {}


def price_re(cur):
    if cur not in _PRICE_RE:
        sym = CUR_SYM[cur]
        _PRICE_RE[cur] = re.compile(rf"(?:(?:{sym})\s?({NUM}))|(?:({NUM})\s?(?:{sym})(?![a-zA-Z]))")
    return _PRICE_RE[cur]


def _to_float(raw):
    raw = raw.replace(" ", "").replace(" ", "").replace(" ", "").replace("'", "").replace(",-", "")
    if re.fullmatch(r"\d+\.\d{1,2}", raw):          # 1099.00 (API style)
        return float(raw)
    return float(raw.replace(".", "").replace(",", "."))


def parse_price(s, cur="EUR"):
    """'1.099,00 €' -> 1099.0 ; '1 299,99 zł' -> 1299.99 ; '₺49.999' -> 49999.0"""
    lo, hi = CUR_RANGE[cur]
    if s is None or isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        v = float(s)
        return v if lo <= v <= hi else None
    s = str(s)
    m = price_re(cur).search(s)
    raw = (m.group(1) or m.group(2)) if m else None
    if not raw and re.fullmatch(r"\s*\d+(?:[.,]\d{1,2})?\s*", s):
        raw = s.strip()
    if not raw:
        return None
    try:
        v = _to_float(raw)
    except ValueError:
        return None
    return v if lo <= v <= hi else None


def all_prices(text, cur="EUR"):
    out = []
    for m in price_re(cur).finditer(text or ""):
        v = parse_price(m.group(0), cur)
        if v:
            out.append(v)
    return out


# ---------------------------------------------------------------- localized word lists
MONTHLY_RE = re.compile(
    r"monat|mtl\.|/\s?mo\b|monthly|\brate|finanz|sparen|spare|rabatt|gutschein|coupon|cashback|bonus|eintausch|trade|"
    r"/\s?mois|par mois|mensuel|économ|remise|reprise|"           # fr
    r"mies|miesięcz|rat\b|raty|oszczęd|zniżk|"                    # pl
    r"/\s?lun|pe lun|lunar|economis|reducere|"                     # ro
    r"\bay\b|/\s?ay|aylık|taksit|indirim|tasarruf",                # tr
    re.I)
STORAGE_RE = re.compile(r"(\d{1,4})\s?(GB|TB|Go|To)\b", re.I)

COLORS = (
    "schwarz black weiß weiss white silber silver grau gray grey blau blue grün green rot red gelb yellow "
    "rosa pink lila purple violett violet gold orange beige creme cream titan titanium natur natural "
    "graphit graphite mint lavendel lavender koralle coral navy marine sand bronze kupfer champagner "
    "obsidian porcelain porzellan hazel rose jade ice icy blush cobalt kobalt onyx phantom midnight mitternacht "
    "polarstern starlight nebelblau salbei sage ultramarin wüstensand desert tiefblau cosmic kosmisch "
    "aqua teal amber khaki olive forest velvet emerald smaragd ivory elfenbein moonlight shadow ocean sky himmelblau "
    "noir blanc bleu vert rouge jaune gris argent "                       # fr
    "czarny biały niebieski zielony szary srebrny złoty różowy fioletowy "   # pl
    "negru alb albastru verde gri argintiu auriu roz mov "                  # ro
    "siyah beyaz mavi yeşil gri gümüş altın pembe mor"                      # tr
).split()
COLOR_RE = re.compile(r"(?<!\w)(" + "|".join(map(re.escape, COLORS)) + r")(?!\w)", re.I)

ACCESSORY = re.compile(
    r"hülle|\bcase\b|cover|folie|schutzglas|displayschutz|ladegerät|ladekabel|charger|kabel|cable|adapter|"
    r"armband|strap|\bloop\b|tastatur|keyboard|pencil|stylus|s pen\b|stift|ständer|halterung|\bstand\b|powerbank|"
    r"smarttag|airtag|magsafe|\bdock\b|tasche|sleeve|wallet|ladestation|netzteil|ohreinsätze|ear ?tips|einsätze|"
    r"fernseher|\btv\b|monitor|staubsauger|vacuum|scooter|router|kamera|camera|lautsprecher|speaker|soundbar|"
    r"coque|étui|housse|chargeur|câble|adaptateur|bracelet|clavier|stylet|embouts|"     # fr
    r"etui|pokrowiec|szkło|ładowarka|kabel|pasek|klawiatura|rysik|"                      # pl
    r"husă|husa|încărcător|incarcator|cablu|adaptor|curea|tastatur|"                     # ro
    r"kılıf|kilif|ekran koruyucu|şarj|sarj|kablo|adaptör|kordon|kayış|klavye|kalem",     # tr
    re.I)
REFURB = re.compile(r"entdecke|discover|découvr|odkryj|descoper|keşfet|refurb|re-?newed|certified|reconditionn|odnowion|recondi|yenilenmi|generalüberholt|wie neu|"
                    r"bundle|paket|pack\b|加价|[぀-ヿ一-鿿]", re.I)
BUY_WORDS = re.compile(r"\s+(kaufen|jetzt kaufen|acheter|kup(?:uj)?|cumpără|cumpara|satın al)\b.*$", re.I)

CATS = [
    ("audio", re.compile(r"buds|airpods|freebuds|freeclip|earbuds|earphones?|kopfhörer|headphones?|beats|\bpods\b|freelace|"
                         r"écouteurs|casque|słuchawki|căști|casti|kulaklık", re.I)),
    ("wear", re.compile(r"watch|\bring\b|galaxy fit|\bfit\s?\d|smart\s?band|mi band|\bband\s?\d|honor band|huawei band|"
                        r"montre|zegarek|smartwatch", re.I)),
    ("tablet", re.compile(r"\bpad\b|\bpad\s?\d|ipad|matepad|galaxy tab|\btab\b|tablet|magicpad|tablette", re.I)),
    ("phone", re.compile(r"iphone|galaxy [samz]\d|galaxy z|galaxy xcover|pixel\s?\d|xiaomi\s?\d|redmi|poco|pura|mate\s?x?\d|"
                         r"nova|magic\s?v?\d|honor\s?\d|\bmoto\b|razr|edge|oneplus\s?\d|nord|smartphone|handy", re.I)),
]


def classify(name):
    if not name or ACCESSORY.search(name) or REFURB.search(name):
        return None
    for cat, rx in CATS:
        if rx.search(name):
            return cat
    return None


def storage_variant(text):
    """'12 GB + 512 GB' -> '12GB+512GB', '256 GB' -> '256GB', none -> ''"""
    vals = []
    for n, unit in STORAGE_RE.findall(text or ""):
        u = unit.upper().replace("GO", "GB").replace("TO", "TB")
        gb = int(n) * (1024 if u == "TB" else 1)
        vals.append((gb, f"{n}{u}"))
    if not vals:
        return ""
    storage = [v for v in vals if v[0] >= 32]
    ram = [v for v in vals if v[0] <= 24]
    if storage and ram:
        return f"{ram[0][1]}+{max(storage)[1]}"
    if storage:
        return max(storage)[1]
    return vals[0][1]


def has_storage(variant):
    return bool(re.search(r"(\d{2,4}GB|\d TB|\dTB)", variant or "")) and not re.fullmatch(r"\d{1,2}GB", variant or "")


# ---------------------------------------------------------------- model-name canonicalisation
BRAND_PREFIX = {"Apple": "", "Samsung": "Samsung", "Google": "Google", "Xiaomi": "Xiaomi", "Huawei": "HUAWEI",
                "Honor": "HONOR", "Motorola": "Motorola", "OnePlus": "OnePlus"}


def _cut_outside_parens(s, ch=","):
    depth = 0
    for i, c in enumerate(s):
        if c in "([":
            depth += 1
        elif c in ")]":
            depth = max(0, depth - 1)
        elif c == ch and depth == 0 and not (i + 1 < len(s) and s[i + 1].isdigit()):
            return s[:i]
    return s


def canonical_model(brand, name):
    n = htmllib.unescape(name or "").replace("‏", "").replace("‎", "")
    n = re.sub(r"<[^>]+>", " ", n)
    n = BUY_WORDS.sub("", n)
    n = re.sub(r"\((?:[^)]*\b(?:only|exklusiv|exclusive|uniquement|doar|tylko|sadece)\b[^)]*)\)", " ", n, flags=re.I)
    n = re.sub(r"\s+(im|dans|w|în|in)\s+(offiziellen\s+)?(HUAWEI|HONOR|Samsung|Xiaomi)?\s*(Shop|Store|Sklep|Magazin|Mağaza)\b.*$", "", n, flags=re.I)
    n = re.sub(r"\b[A-Z]{2,4}(?:\+[A-Z]{2,4})?(?:\s+offer)?_(?:(?:HUAWEI|HONOR)\s+)?", "", n)   # Huawei internal 'SMP_', 'WEA+CB offer_'
    n = re.sub(r"^(Huawei|Honor)\s+(Huawei|Honor)\s+", r"\1 ", n, flags=re.I)
    n = re.sub(r"\bRAM\b|\bROM\b|\bSM-[A-Z0-9]{4,}\b|\bStandard\b", " ", n)
    n = _cut_outside_parens(n, ",")
    n = re.sub(r"\s[|–—]\s.*$", "", n)
    n = STORAGE_RE.sub(" ", n)
    n = COLOR_RE.sub(" ", n)
    n = re.sub(r"\(\s*[,+/]?\s*\)|\s\+\s*(?=\s|$)", " ", n)
    n = re.sub(r"(\d+)\s+\d{1,2}\s*$", r"\1", n.strip())      # 'HONOR 400 8' (RAM leftover)
    n = re.sub(r"\s{2,}", " ", n).strip(" ,-|/+:")
    # unify brand prefix
    pref = BRAND_PREFIX.get(brand, brand)
    n = re.sub(rf"^{re.escape(brand)}\s+", "", n, flags=re.I)
    if pref:
        n = re.sub(rf"^{re.escape(pref)}\s+", "", n, flags=re.I)
        n = f"{pref} {n}"
    return n.strip()


def model_key(brand, model):
    return re.sub(r"[^a-z0-9+]+", "-", f"{brand}|{model}".lower()).strip("-")


def bad_name(name):
    """Descriptions, URL slugs and other non-model strings."""
    if not name:
        return True
    words = name.split()
    if len(words) > 8:
        return True
    if re.search(r"[a-z]+-[a-z]+-[a-z]+", name) and " " not in name.split(" ", 1)[-1]:
        return True
    if re.search(r"-global-|-row-|ecom|pdp", name, re.I):
        return True
    rest = re.sub(r"^(Apple|Samsung|Google|Xiaomi|HUAWEI|HONOR|Motorola|OnePlus)\s*", "", name, flags=re.I).strip().lower()
    if rest in GENERIC_WORDS or not rest:
        return True
    return False


GENERIC_WORDS = {
    "smartphones", "smartphone", "phones", "handys", "tablets", "tablet", "wearables", "audio", "kopfhörer", "headphones",
    "earbuds", "watches", "smartwatches", "téléphones", "tablettes", "montres", "écouteurs", "telefony", "smartfony",
    "słuchawki", "zegarki", "telefoane", "tablete", "căști", "ceasuri", "telefonlar", "tabletler", "kulaklıklar", "akıllı saatler",
}


# ---------------------------------------------------------------- JSON helpers
def iter_json_blocks(html, key):
    dec = json.JSONDecoder()
    for m in re.finditer(r'"%s"\s*:\s*' % re.escape(key), html):
        try:
            val, _ = dec.raw_decode(html, m.end())
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


def _num(v, cur):
    if isinstance(v, dict):
        for k in ("raw_amount", "value", "amount", "price"):
            if k in v:
                return _num(v[k], cur)
        return None
    return parse_price(v, cur)


def generic_json(objs, url, cur):
    out = []
    for root in objs:
        for d in walk(root):
            name = next((d[k] for k in NAME_KEYS if isinstance(d.get(k), str) and 2 < len(d[k]) < 140), None)
            if not name:
                continue
            price = None
            for k in PRICE_KEYS:
                if k in d:
                    price = _num(d[k], cur)
                    if price:
                        break
            if not price:
                continue
            lst = None
            for k in LIST_KEYS:
                if k in d:
                    v = _num(d[k], cur)
                    if v and v > price:
                        lst = v
                        break
            sku = next((str(d[k]) for k in SKU_KEYS if d.get(k) not in (None, "", [])), "")
            variant_src = " ".join(str(d.get(k, "")) for k in ("storage", "capacity", "memory", "romSize", "ram", "rom", "attrValue", "specName", "optionName"))
            out.append({"name": name, "variant": storage_variant(name + " " + variant_src), "price": price,
                        "list_price": lst, "sku": sku, "url": url, "source": "json"})
    return out


def jsonld(html, url, cur):
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
                if str(o.get("priceCurrency", cur)).upper() != cur:
                    continue
                price = parse_price(o.get("price") or o.get("lowPrice"), cur)
                if price:
                    nm = o.get("name") or name
                    out.append({"name": nm, "variant": storage_variant(nm + " " + str(o.get("sku", ""))), "price": price,
                                "list_price": None, "sku": str(o.get("sku") or d.get("sku") or ""), "url": url, "source": "jsonld"})
    return out


# ---------------------------------------------------------------- Apple
APPLE_DIM = {"wifi": "Wi-Fi", "wificell": "Wi-Fi + Cellular", "glossy": "", "matte": "Nano-texture"}


def apple(html, url, title, cur):
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
    base = re.sub(r"\s*[-|–]\s*Apple.*$", "", title or "", flags=re.I)
    base = BUY_WORDS.sub("", " " + base).strip()
    base = re.sub(r"^(Acheter|Kup|Cumpără|Buy)\s+(l[’'ea]\s*|un\s+|une\s+)?", "", base, flags=re.I).strip() or "Apple"
    base = re.sub(r"\s+(satın alın?|al)$", "", base, flags=re.I)
    names = [n.strip() for n in re.split(r"\s+(?:und|et|i|și|ve|and)\s+|\s*&\s*", base) if n.strip()]
    sizes = sorted({p.get("dimensionScreensize") for p in products if p.get("dimensionScreensize")},
                   key=lambda s: float(re.sub(r"[^0-9_.]", "", s).replace("_", ".") or 0))
    out = []
    for p in products:
        pr = prices.get(p.get("partNumber")) or prices.get(p.get("fullPrice", ""))
        if not pr:
            continue
        price = _num(pr.get("currentPrice", pr), cur) or parse_price(pr.get("amount"), cur)
        if not price:
            continue
        name = names[0] if names else base
        size = p.get("dimensionScreensize")
        if size and len(names) == len(sizes) > 1:
            name = names[sizes.index(size)]
        parts = []
        cap = p.get("dimensionCapacity")
        if cap:
            parts.append(cap.upper())
        for k, v in sorted(p.items()):
            if k.startswith("dimension") and k not in ("dimensionColor", "dimensionCapacity", "dimensionScreensize") and isinstance(v, str):
                v = APPLE_DIM.get(v, v)
                if v:
                    parts.append(v)
        if size and len(names) != len(sizes):
            parts.insert(0, size.replace("_", ",").replace("inch", '"'))
        out.append({"name": name, "variant": " ".join(parts).strip(), "price": price, "list_price": None,
                    "sku": p.get("partNumber", ""), "url": url, "source": "apple-bootstrap"})
    return out


# ---------------------------------------------------------------- Samsung
def samsung(objs, url, cur):
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
                price = parse_price(m.get("promotionPrice"), cur) or parse_price(m.get("price"), cur)
                if not price:
                    continue
                lst = parse_price(m.get("price"), cur)
                name = re.sub(r"<[^>]+>", "", m.get("displayName") or fam)
                opts = " ".join(str(o.get("fmyChipName") or o.get("fmyChipLocalName") or "")
                                for o in (m.get("fmyChipList") or []) if isinstance(o, dict))
                pdp = m.get("pdpUrl") or m.get("originPdpUrl") or ""
                out.append({"name": fam or name, "variant": storage_variant(name + " " + opts + " " + (m.get("modelName") or "")),
                            "price": price, "list_price": lst if lst and lst > price else None,
                            "sku": m.get("modelCode", ""), "source": "samsung-api",
                            "url": ("https://www.samsung.com" + pdp) if pdp.startswith("/") else (pdp or url)})
    return out


# ---------------------------------------------------------------- DOM heuristic (runs in the browser)
DOM_JS = r"""
(symSrc) => {
  const txt = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const h1 = document.querySelector('h1');
  const og = document.querySelector('meta[property="og:title"]');
  const out = {title: document.title, h1: h1 ? txt(h1) : '', og: og ? og.content : '', tiles: [], prices: [], cards: []};
  const st = /\b\d{1,4}\s?(GB|TB|Go|To)\b/i;
  const eur = new RegExp('((' + symSrc + ')\\s?\\d|\\d\\s?(' + symSrc + ')|\\d,-)');
  const seen = new Set();
  for (const el of document.querySelectorAll('button,label,li,a,[role=radio],[role=option],div,span')) {
    if (el.children.length > 12) continue;
    const t = txt(el);
    if (t.length < 4 || t.length > 160 || !st.test(t) || !eur.test(t)) continue;
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
  // product cards in on-screen order (for listing position)
  const cardSeen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const t = txt(a).slice(0, 120);
    if (!t || t.length < 3) continue;
    const key = a.href.split('?')[0];
    if (cardSeen.has(key)) continue;
    cardSeen.add(key); out.cards.push([key, t]);
    if (out.cards.length > 400) break;
  }
  return out;
}
"""


def dom(info, url, cur):
    name = (info.get("h1") or info.get("og") or info.get("title") or "").strip()
    name = re.sub(r"\s*[|–-]\s*(Offizieller|Official|Officiel|Oficjal|Oficial|Resmi|Kaufen|Buy|Google Store|Xiaomi|HUAWEI|HONOR|OnePlus|Motorola).*$", "", name, flags=re.I)
    name = re.sub(r"^(Kaufen|Buy|Acheter|Kup|Cumpără)\s+", "", name, flags=re.I).strip()
    out = []
    for t in info.get("tiles", []):
        if MONTHLY_RE.search(t):
            continue
        ps = all_prices(t, cur)
        var = storage_variant(t)
        if not ps or not has_storage(var):
            continue
        # a tile that names a product (recommendation carousel) belongs to that product, not to the page
        rest = price_re(cur).sub(" ", t)
        rest = STORAGE_RE.sub(" ", rest)
        rest = re.sub(r"[+|/•·()]|\b(ab|ab\.|dès|à partir de|od|de la|from|itibaren)\b", " ", rest, flags=re.I)
        rest = re.sub(r"\s{2,}", " ", rest).strip()
        tile_name = name
        if len(rest.split()) > 6:
            continue
        if len(rest.split()) >= 2 and classify(rest):
            tile_name = rest[:80]
        elif len(rest.split()) > 4:
            continue
        out.append({"name": tile_name, "variant": var, "price": min(ps), "list_price": max(ps) if max(ps) > min(ps) else None,
                    "sku": "", "url": url, "source": "dom-tile"})
    if not out:
        ps = [p for t in info.get("prices", []) if not MONTHLY_RE.search(t) for p in all_prices(t, cur)]
        if ps and name:
            out.append({"name": name, "variant": storage_variant(name), "price": min(ps), "list_price": None,
                        "sku": "", "url": url, "source": "dom-price"})
    return out


# ---------------------------------------------------------------- final row cleaning (used by run + build)
SOURCE_RANK = {"apple-bootstrap": 0, "samsung-api": 0, "jsonld": 1, "dom-tile": 2, "json": 3, "dom-price": 4}
MIN_EUR = {"phone": 60, "tablet": 60, "wear": 25, "audio": 20}


def normalize_variant(v):
    v = " ".join(APPLE_DIM.get(t, t) for t in str(v).split())
    return re.sub(r"\s{2,}", " ", v).strip()


def clean_rows(brand, raw, fx=1.0):
    """raw items -> one row per (model, variant); also re-cleans rows from older snapshots."""
    best = {}
    for it in raw:
        name = (it.get("name") or it.get("model") or "").strip()
        cat = classify(name)
        if not cat or bad_name(name):
            continue
        price = it.get("price")
        if not price or price / fx < MIN_EUR[cat]:
            continue
        model = canonical_model(brand, name)
        if not model or bad_name(model):
            continue
        variant = normalize_variant(it.get("variant") or "")
        if variant in ("", "—") or (it.get("source") == "dom-tile" and not has_storage(variant)):
            variant = "—"
        key = model_key(brand, model) + "|" + re.sub(r"[^a-z0-9+]+", "-", variant.lower()).strip("-")
        rank = SOURCE_RANK.get(it.get("source"), 9)
        cur = best.get(key)
        row = {"key": key, "mkey": model_key(brand, model), "brand": brand, "category": cat, "model": model,
               "variant": variant, "price": round(price, 2), "list_price": it.get("list_price"),
               "url": it.get("url"), "sku": it.get("sku") or "", "source": it.get("source"), "_rank": rank,
               "pos": it.get("pos")}
        if cur is None or rank < cur["_rank"] or (rank == cur["_rank"] and row["price"] < cur["price"]):
            if cur:
                row["pos"] = min([p for p in (cur.get("pos"), row["pos"]) if p is not None], default=None)
            best[key] = row
        elif row["pos"] is not None and (cur.get("pos") is None or row["pos"] < cur["pos"]):
            cur["pos"] = row["pos"]
    rows = list(best.values())
    # a model that has storage-variant rows drops its variant-less "base price" row
    with_var = {r["mkey"] for r in rows if r["variant"] != "—"}
    rows = [r for r in rows if not (r["variant"] == "—" and r["mkey"] in with_var)]
    # dom-price is the weakest signal: keep only when nothing else exists for that model
    strong = {r["mkey"] for r in rows if r["source"] != "dom-price"}
    rows = [r for r in rows if not (r["source"] == "dom-price" and r["mkey"] in strong)]
    for r in rows:
        r.pop("_rank", None)
    return sorted(rows, key=lambda r: (r["category"], r["model"], r["price"]))
