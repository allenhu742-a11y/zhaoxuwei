"""Daily trend for one model: min / avg / max across its storage variants + store listing rank.

Usage:
  python -m scraper.model --model "Galaxy A07"                    # every country that sells it
  python -m scraper.model --model "Galaxy A07" --country PL --eur
  python -m scraper.model --model "iPhone 17" --country DE --png a07.png   # dual-axis chart (needs matplotlib)
"""
import argparse
import re
import sys

from .build import build_country, load_snapshots


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def find_models(data, query):
    q = norm(query)
    models = {}
    for k, m in data["skus"].items():
        nm = norm(m["model"])
        if q in nm:
            models.setdefault(m["mkey"], m["model"])
    if not models:
        return []
    # exact match (ignoring brand prefix) wins, else every model containing the query
    exact = [mk for mk, nm in models.items() if norm(nm).endswith(q) and len(norm(nm)) - len(q) <= 8]
    exact.sort(key=lambda mk: len(models[mk]))
    return [(mk, models[mk]) for mk in (exact[:1] if exact else sorted(models, key=lambda mk: models[mk]))]


def series(data, mkey, eur=False):
    keys = [k for k, m in data["skus"].items() if m["mkey"] == mkey]
    rows = []
    for d in data["dates"]:
        fx = data["fx"].get(d, 1.0) if eur else 1.0
        ps = [data["prices"][k][d][0] / fx for k in keys if d in data["prices"][k]]
        rank = data["ranks"].get(mkey, {}).get(d)
        if ps or rank:
            rows.append({"date": d, "min": min(ps) if ps else None, "avg": sum(ps) / len(ps) if ps else None,
                         "max": max(ps) if ps else None, "n": len(ps), "rank": rank})
    variants = sorted({data["skus"][k]["variant"] for k in keys})
    return rows, variants


def fmt(v):
    return "—" if v is None else f"{v:,.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--country", default="")
    ap.add_argument("--eur", action="store_true", help="convert to EUR with the stored ECB rate")
    ap.add_argument("--png", default="", help="write a price × rank dual-axis chart")
    a = ap.parse_args()
    by_cc = load_snapshots()
    ccs = [a.country.upper()] if a.country else list(by_cc)
    plots = []
    for cc in ccs:
        if cc not in by_cc:
            print(f"[{cc}] no snapshots"); continue
        data = build_country(cc, by_cc[cc])
        for mkey, name in find_models(data, a.model):
            rows, variants = series(data, mkey, a.eur)
            cur = "EUR" if a.eur else data["currency"]
            print(f"\n[{cc}] {name}  ({cur}; variants: {', '.join(variants)})")
            print(f"{'date':<11}{'min':>12}{'avg':>12}{'max':>12}{'#var':>6}{'rank':>6}")
            for r in rows:
                print(f"{r['date']:<11}{fmt(r['min']):>12}{fmt(r['avg']):>12}{fmt(r['max']):>12}{r['n']:>6}{(r['rank'] or '—'):>6}")
            plots.append((cc, name, cur, rows))
    if not plots:
        print(f"No model matching '{a.model}'."); sys.exit(1)
    if a.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        n = len(plots)
        fig, axes = plt.subplots(n, 1, figsize=(11, 3.6 * n), squeeze=False)
        for ax, (cc, name, cur, rows) in zip(axes[:, 0], plots):
            x = [r["date"][5:] for r in rows]
            ax.fill_between(x, [r["min"] for r in rows], [r["max"] for r in rows], alpha=.15, color="#2563eb", label="min–max")
            ax.plot(x, [r["avg"] for r in rows], color="#2563eb", marker="o", label=f"avg ({cur})")
            ax.plot(x, [r["min"] for r in rows], color="#2563eb", lw=.8, ls="--", label="min")
            ax.set_ylabel(cur); ax.set_title(f"{cc} · {name}")
            ax2 = ax.twinx()
            ax2.plot(x, [r["rank"] for r in rows], color="#ea580c", marker="s", label="listing rank")
            ax2.invert_yaxis(); ax2.set_ylabel("rank (1 = top)")
            h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
            ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
            ax.tick_params(axis="x", rotation=45)
        fig.tight_layout(); fig.savefig(a.png, dpi=130)
        print(f"\nchart -> {a.png}")


if __name__ == "__main__":
    main()
