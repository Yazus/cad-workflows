"""1D tolerance stack-ups: worst case, RSS and Monte Carlo.

A stack-up sums signed contributors. Each contributor has limits (lsl, usl); its mean is the
mid-limit and its half tolerance is (usl - lsl) / 2. A contributor can name a characteristic id
instead of carrying its own limits, and the limits are then read from the part record.
Monte Carlo treats a normal contributor's half tolerance as 3 sigma, and a uniform one as spread
evenly between its limits.
"""

import math

import numpy as np


def resolve(stack, characteristics):
    """Return the contributors of `stack` with limits filled in from the characteristics list."""
    by_id = {c["id"]: c for c in characteristics}
    out = []
    for c in stack["contributors"]:
        c = dict(c)
        if ("lsl" not in c or "usl" not in c) and c.get("char_id"):
            ch = by_id.get(c["char_id"])
            if ch is None:
                raise ValueError(f"{stack['id']}: contributor {c['name']} names unknown characteristic {c['char_id']}")
            if "lsl" not in ch or "usl" not in ch:
                raise ValueError(f"{stack['id']}: characteristic {c['char_id']} has no limits")
            c["lsl"], c["usl"] = ch["lsl"], ch["usl"]
            c.setdefault("nominal", ch.get("nominal"))
        if "lsl" not in c or "usl" not in c:
            raise ValueError(f"{stack['id']}: contributor {c['name']} has no limits")
        if c["usl"] < c["lsl"]:
            raise ValueError(f"{stack['id']}: contributor {c['name']} has usl below lsl")
        out.append(c)
    return out


def analyze(stack, characteristics=(), samples=200_000, seed=0):
    """Analyze one stack-up. Returns a dict with worst case, RSS and Monte Carlo results."""
    contribs = resolve(stack, list(characteristics))
    means = np.array([(c["lsl"] + c["usl"]) / 2 for c in contribs])
    halves = np.array([(c["usl"] - c["lsl"]) / 2 for c in contribs])
    signs = np.array([c["sign"] for c in contribs])

    mean = float(np.sum(signs * means))
    wc = float(np.sum(halves))
    rss = float(math.sqrt(np.sum(halves**2)))

    rng = np.random.default_rng(seed)
    total = np.zeros(samples)
    for c, m, h, s in zip(contribs, means, halves, signs):
        if c.get("dist", "normal") == "uniform":
            x = rng.uniform(m - h, m + h, samples)
        else:
            x = rng.normal(m, h / 3 if h > 0 else 0.0, samples)
        total += s * x

    target = stack.get("target", {})
    lo, hi = target.get("min", -math.inf), target.get("max", math.inf)
    mc_in = float(np.mean((total >= lo) & (total <= hi)))

    def meets(half):
        return mean - half >= lo and mean + half <= hi

    method = stack.get("method", "worst_case")
    return {
        "id": stack["id"],
        "name": stack["name"],
        "method": method,
        "target": {"min": target.get("min"), "max": target.get("max")},
        "contributors": contribs,
        "mean": mean,
        "worst_case": {"min": mean - wc, "max": mean + wc, "meets": meets(wc)},
        "rss": {"min": mean - rss, "max": mean + rss, "meets": meets(rss)},
        "monte_carlo": {
            "samples": samples,
            "mean": float(np.mean(total)),
            "sigma": float(np.std(total)),
            "min": float(np.min(total)),
            "max": float(np.max(total)),
            "in_target": mc_in,
        },
        "meets": meets(wc) if method == "worst_case" else meets(rss),
    }
