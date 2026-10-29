"""Brands, seed pages and product-link patterns for the German official stores.

Each brand has:
  seeds:  {category_hint: [listing URLs]}  - pages to render first
  link:   regex for product/buy pages to follow from the listing pages
  max_pages: cap on product pages visited per run
Categories: phone, tablet, wear, audio
"""

BRANDS = {
    "Apple": {
        "seeds": {
            "phone": ["https://www.apple.com/de/shop/buy-iphone"],
            "tablet": ["https://www.apple.com/de/shop/buy-ipad"],
            "wear": ["https://www.apple.com/de/shop/buy-watch"],
            "audio": ["https://www.apple.com/de/airpods/", "https://www.apple.com/de/shop/accessories/all/headphones-speakers"],
        },
        "link": r"^https://www\.apple\.com/de/shop/(buy-iphone|buy-ipad|buy-watch|buy-airpods)/[a-z0-9-]+/?$|^https://www\.apple\.com/de/shop/product/[A-Z0-9]+/[^?#]*(airpods|beats)[^?#]*$",
        "max_pages": 40,
    },
    "Samsung": {
        "seeds": {
            "phone": ["https://www.samsung.com/de/smartphones/all-smartphones/"],
            "tablet": ["https://www.samsung.com/de/tablets/all-tablets/"],
            "wear": ["https://www.samsung.com/de/watches/all-watches/", "https://www.samsung.com/de/rings/all-rings/"],
            "audio": ["https://www.samsung.com/de/audio-sound/all-audio-sound/"],
        },
        # Samsung listing pages call a JSON search API that already has every SKU price,
        # so product pages are normally not needed.
        "link": r"^https://www\.samsung\.com/de/(smartphones|tablets|watches|audio-sound|rings)/[a-z0-9-]+/buy/?",
        "max_pages": 25,
        "api": "samsung",
    },
    "Google": {
        "seeds": {
            "phone": ["https://store.google.com/de/category/phones"],
            "tablet": ["https://store.google.com/de/category/tablets"],
            "wear": ["https://store.google.com/de/category/watches"],
            "audio": ["https://store.google.com/de/category/earbuds"],
        },
        "link": r"^https://store\.google\.com/de/(product|config)/[a-z0-9_]+",
        "max_pages": 30,
        "expand": [(r"/de/product/", "/de/config/")],
    },
    "Xiaomi": {
        "seeds": {
            "phone": ["https://www.mi.com/de/", "https://www.mi.com/de/product-list/phone/"],
            "tablet": ["https://www.mi.com/de/product-list/tablet/"],
            "wear": ["https://www.mi.com/de/product-list/wearables/"],
            "audio": ["https://www.mi.com/de/product-list/audio/"],
        },
        "link": r"^https://www\.mi\.com/de/product/[a-z0-9-]+/?(buy/?)?$",
        "max_pages": 50,
        "expand": [(r"/(?:buy/?)?$", "/buy/")],
    },
    "Huawei": {
        "seeds": {
            "phone": ["https://consumer.huawei.com/de/phones/", "https://consumer.huawei.com/de/shop/"],
            "tablet": ["https://consumer.huawei.com/de/tablets/"],
            "wear": ["https://consumer.huawei.com/de/wearables/"],
            "audio": ["https://consumer.huawei.com/de/audio/"],
        },
        "link": r"^https://consumer\.huawei\.com/de/(shop/product/[^?#]+|(phones|tablets|wearables|audio)/[a-z0-9-]+/buy/?)",
        "max_pages": 50,
    },
    "Honor": {
        "seeds": {
            "phone": ["https://www.honor.com/de/phones/"],
            "tablet": ["https://www.honor.com/de/tablets/"],
            "wear": ["https://www.honor.com/de/wearables/"],
            "audio": ["https://www.honor.com/de/audio/"],
        },
        "link": r"^https://www\.honor\.com/de/shop/product/[^?#]+|^https://www\.honor\.com/de/(phones|tablets|wearables|audio)/[a-z0-9-]+/buy/?",
        "max_pages": 50,
    },
    "Motorola": {
        "seeds": {
            "phone": ["https://www.motorola.com/de/de/smartphones", "https://www.motorola.com/de/de/"],
            "tablet": ["https://www.motorola.com/de/de/tablets"],
            "audio": ["https://www.motorola.com/de/de/audio"],
            "wear": ["https://www.motorola.com/de/de/wearables"],
        },
        "link": r"^https://www\.motorola\.com/de/de/p/[^?#]+",
        "max_pages": 40,
    },
    "OnePlus": {
        "seeds": {
            "phone": ["https://www.oneplus.com/de/store/phone"],
            "tablet": ["https://www.oneplus.com/de/store/tablet"],
            "audio": ["https://www.oneplus.com/de/store/audio"],
            "wear": ["https://www.oneplus.com/de/store/wearables"],
        },
        "link": r"^https://www\.oneplus\.com/de/[a-z0-9-]+/buy/?$|^https://www\.oneplus\.com/de/store/buy/[^?#]+",
        "max_pages": 40,
    },
}

# Samsung's public product-finder API (used by its own listing pages).
SAMSUNG_TYPES = {"phone": "01010000", "tablet": "01020000", "wear": "01030000", "audio": "01040000"}
SAMSUNG_API = (
    "https://searchapi.samsung.com/v6/front/b2c/product/finder/newhybris"
    "?type={type}&siteCode=de&start={start}&num=100&sort=newest"
    "&onlyFilterInfoYN=N&keySummaryYN=N&specHighlightYN=N&familyId="
)

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
