"""Countries, brands, seed pages and product-link patterns for the official stores.

URL templates use:
  {cc}   lowercase country code in the store path (de, fr, ro, pl, tr)
  {lang} language code (de, fr, ro, pl, tr)
Each brand has:
  seeds:     {category_hint: [listing URL templates]}
  link:      regex template for product/buy pages to follow from listing pages
  countries: where the brand runs an online store (others are skipped)
Categories: phone, tablet, wear, audio
"""

COUNTRIES = {
    "DE": {"name": "德国 Germany", "cur": "EUR", "lang": "de", "tz": "Europe/Berlin", "locale": "de-DE"},
    "FR": {"name": "法国 France", "cur": "EUR", "lang": "fr", "tz": "Europe/Paris", "locale": "fr-FR"},
    "RO": {"name": "罗马尼亚 Romania", "cur": "RON", "lang": "ro", "tz": "Europe/Bucharest", "locale": "ro-RO"},
    "PL": {"name": "波兰 Poland", "cur": "PLN", "lang": "pl", "tz": "Europe/Warsaw", "locale": "pl-PL"},
    "TR": {"name": "土耳其 Türkiye", "cur": "TRY", "lang": "tr", "tz": "Europe/Istanbul", "locale": "tr-TR"},
}
ALL = list(COUNTRIES)

BRANDS = {
    "Apple": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://www.apple.com/{cc}/shop/buy-iphone"],
            "tablet": ["https://www.apple.com/{cc}/shop/buy-ipad"],
            "wear": ["https://www.apple.com/{cc}/shop/buy-watch"],
            "audio": ["https://www.apple.com/{cc}/shop/accessories/all/headphones-speakers"],
        },
        "link": r"^https://www\.apple\.com/{cc}/shop/(buy-iphone|buy-ipad|buy-watch|buy-airpods)/[a-z0-9-]+/?$|^https://www\.apple\.com/{cc}/shop/product/[A-Z0-9]+/[^?#]*(airpods|beats)[^?#]*$",
        "max_pages": 40,
    },
    "Samsung": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://www.samsung.com/{cc}/smartphones/all-smartphones/"],
            "tablet": ["https://www.samsung.com/{cc}/tablets/all-tablets/"],
            "wear": ["https://www.samsung.com/{cc}/watches/all-watches/"],
            "audio": ["https://www.samsung.com/{cc}/audio-sound/all-audio-sound/"],
        },
        "link": r"^https://www\.samsung\.com/{cc}/(smartphones|tablets|watches|audio-sound)/[a-z0-9-]+/buy/?",
        "max_pages": 25,
        "api": "samsung",
    },
    "Google": {
        "countries": ["DE", "FR", "PL", "RO", "TR"],
        "seeds": {
            "phone": ["https://store.google.com/{cc}/category/phones"],
            "tablet": ["https://store.google.com/{cc}/category/tablets"],
            "wear": ["https://store.google.com/{cc}/category/watches"],
            "audio": ["https://store.google.com/{cc}/category/earbuds"],
        },
        "link": r"^https://store\.google\.com/{cc}/(product|config)/[a-z0-9_]+",
        "max_pages": 30,
        "expand": [(r"/product/", "/config/")],
    },
    "Xiaomi": {
        "countries": ALL,
        "headful": True,     # mi.com's CDN refused headless Chrome on GitHub runners (HTTP 403)
        "seeds": {
            "phone": ["https://www.mi.com/{cc}/product-list/phone/"],
            "tablet": ["https://www.mi.com/{cc}/product-list/tablet/"],
            "wear": ["https://www.mi.com/{cc}/product-list/wearables/"],
            "audio": ["https://www.mi.com/{cc}/product-list/audio/"],
        },
        "link": r"^https://www\.mi\.com/{cc}/product/[a-z0-9-]+/?(buy/?)?$",
        "max_pages": 50,
        "expand": [(r"/(?:buy/?)?$", "/buy/")],
    },
    "Huawei": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://consumer.huawei.com/{cc}/phones/"],
            "tablet": ["https://consumer.huawei.com/{cc}/tablets/"],
            "wear": ["https://consumer.huawei.com/{cc}/wearables/"],
            "audio": ["https://consumer.huawei.com/{cc}/audio/"],
        },
        "link": r"^https://consumer\.huawei\.com/{cc}/(shop/product/[^?#]+|(phones|tablets|wearables|audio)/[a-z0-9-]+/buy/?)",
        "max_pages": 50,
    },
    "Honor": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://www.honor.com/{cc}/phones/"],
            "tablet": ["https://www.honor.com/{cc}/tablets/"],
            "wear": ["https://www.honor.com/{cc}/wearables/"],
            "audio": ["https://www.honor.com/{cc}/audio/"],
        },
        "link": r"^https://www\.honor\.com/{cc}/shop/product/[^?#]+|^https://www\.honor\.com/{cc}/(phones|tablets|wearables|audio)/[a-z0-9-]+/buy/?",
        "max_pages": 50,
    },
    "Motorola": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://www.motorola.com/{cc}/{lang}/smartphones"],
            "tablet": ["https://www.motorola.com/{cc}/{lang}/tablets"],
            "audio": ["https://www.motorola.com/{cc}/{lang}/audio"],
            "wear": ["https://www.motorola.com/{cc}/{lang}/wearables"],
        },
        "link": r"^https://www\.motorola\.com/{cc}/{lang}/p/[^?#]+",
        "max_pages": 40,
    },
    "OnePlus": {
        "countries": ALL,
        "seeds": {
            "phone": ["https://www.oneplus.com/{cc}/store/phone"],
            "tablet": ["https://www.oneplus.com/{cc}/store/tablet"],
            "audio": ["https://www.oneplus.com/{cc}/store/audio"],
            "wear": ["https://www.oneplus.com/{cc}/store/wearables"],
        },
        "link": r"^https://www\.oneplus\.com/{cc}/[a-z0-9-]+/buy/?$|^https://www\.oneplus\.com/{cc}/store/buy/[^?#]+",
        "max_pages": 40,
    },
}


def tpl(s, country):
    c = COUNTRIES[country]
    return s.replace("{cc}", country.lower()).replace("{lang}", c["lang"])


# Samsung's public product-finder API (used by its own listing pages).
SAMSUNG_TYPES = {"phone": "01010000", "tablet": "01020000", "wear": "01030000", "audio": "01040000"}
SAMSUNG_API = (
    "https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris"
    "?type={type}&siteCode={cc}&start={start}&num=100&sort={sort}"
    "&onlyFilterInfoYN=N&keySummaryYN=N&specHighlightYN=N&familyId="
)

# Fallback EUR rates if the ECB feed is unreachable (local currency per 1 EUR).
FX_FALLBACK = {"EUR": 1.0, "RON": 5.05, "PLN": 4.25, "TRY": 48.0}

CATEGORY_LABELS = {
    "phone": "手机 / Smartphones",
    "tablet": "平板 / Tablets",
    "wear": "穿戴 / Wearables",
    "audio": "音频 / Audio",
}

BRAND_COLORS = {
    "Apple": "#e9d5ff", "Samsung": "#bfdbfe", "Google": "#fde68a", "Xiaomi": "#bbf7d0",
    "Huawei": "#fecaca", "Honor": "#fef3c7", "Motorola": "#fed7aa", "OnePlus": "#fbcfe8",
}
