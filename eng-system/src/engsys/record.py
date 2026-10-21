"""Load a part record, validate it against the schema, and check gate exit criteria.

Gates are cumulative: checking G3 also runs the G0, G1 and G2 checks. Each check returns
Issue objects; a gate passes when no issue has level "error".
"""

import json
from dataclasses import dataclass
from importlib import resources

import jsonschema

from .ap import action_priority
from .stackup import analyze

GATES = ["G0", "G1", "G2", "G3", "G4", "G5"]
TRACKED = {"KC", "CC"}
# Characteristic kinds that are toleranced features, so they need limits and get stack-ups and FAI values.
MEASURED_KINDS = {"dimension", "gdt"}


@dataclass
class Issue:
    gate: str
    level: str  # "error" or "warn"
    code: str
    message: str

    def __str__(self):
        return f"[{self.gate} {self.level.upper()}] {self.code}: {self.message}"


def schema():
    text = resources.files("engsys").joinpath("schema/part-record.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(record):
    """Return schema errors as strings (empty when the record is valid)."""
    v = jsonschema.Draft202012Validator(schema())
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in v.iter_errors(record)]


def tracked(record):
    return [c for c in record["characteristics"] if c["class"] in TRACKED]


def trace(record):
    """Traceability for each KC/CC: which documents carry it. Used by the gate report and the checks."""
    rows = []
    fai_ids = {r["char_id"] for r in record.get("fai", {}).get("results", [])}
    for c in tracked(record):
        cid = c["id"]
        rows.append({
            "char": c,
            "requirements": c.get("requirement_ids", []),
            "dfmea": [l["id"] for l in record.get("dfmea", []) if cid in l.get("char_ids", [])],
            "ops": [p["op"] for p in record.get("process", []) if cid in p.get("makes", [])],
            "pfmea": [l["id"] for l in record.get("pfmea", []) if cid in l.get("char_ids", [])],
            "control_plan": [r["op"] for r in record.get("control_plan", []) if r["char_id"] == cid],
            "inspection": [r["stage"] for r in record.get("inspection_plan", []) if r["char_id"] == cid],
            "fai": cid in fai_ids,
        })
    return rows


def _g0(r):
    out = []
    p = r["part"]
    if not r["requirements"]:
        out.append(Issue("G0", "error", "no-requirements", "record has no requirements"))
    for kind, items in (("requirement", r["requirements"]), ("characteristic", r["characteristics"])):
        ids = [i["id"] for i in items]
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            out.append(Issue("G0", "error", f"duplicate-{kind}", f"duplicate {kind} ids: {', '.join(dups)}"))
    req_ids = {q["id"] for q in r["requirements"]}
    for c in r["characteristics"]:
        for rid in c.get("requirement_ids", []):
            if rid not in req_ids:
                out.append(Issue("G0", "error", "unknown-requirement", f"{c['id']} links unknown requirement {rid}"))
        if c["source"] == "MOCK" and not p.get("mock"):
            out.append(Issue("G0", "error", "mock-in-real-record",
                             f"{c['id']} has source MOCK but the part is not marked mock"))
    if p["export_control"]["itar"] and not p.get("mock"):
        out.append(Issue("G0", "warn", "itar", "ITAR part: keep this record and all outputs on the local PC, no cloud CAD or uploads"))
    return out


def _g1(r):
    out = []
    for c in r["characteristics"]:
        if c["kind"] == "dimension" and not ("lsl" in c and "usl" in c):
            out.append(Issue("G1", "error", "no-limits", f"{c['id']} {c['feature']}: dimension has no lsl/usl"))
        if c["kind"] == "dimension" and "lsl" in c and "usl" in c and c["lsl"] > c["usl"]:
            out.append(Issue("G1", "error", "bad-limits", f"{c['id']}: lsl is above usl"))
        if c["kind"] == "gdt" and "tol" not in c.get("gdt", {}):
            out.append(Issue("G1", "error", "no-gdt-tol", f"{c['id']} {c['feature']}: GD&T characteristic has no tolerance"))
    return out


def _signed(r, gate):
    return any(d["gate"] == gate and d.get("signed") for d in r.get("design_reviews", []))


def _ap_issues(lines, gate, doc):
    out = []
    for l in lines:
        ap = action_priority(l["S"], l["O"], l["D"])
        if ap == "H" and not l.get("actions"):
            out.append(Issue(gate, "error", "high-ap-no-action",
                             f"{doc} {l['id']} ({l['failure_mode']}) is AP High (S{l['S']} O{l['O']} D{l['D']}) with no action"))
    return out


def _g2(r):
    out = []
    if not _signed(r, "G2"):
        out.append(Issue("G2", "error", "review-not-signed", "no signed G2 design review"))
    for d in r.get("design_reviews", []):
        for f in d["findings"]:
            if f["status"] == "open" and f["severity"] in ("blocker", "major"):
                out.append(Issue("G2", "error", "open-finding", f"{d['id']}/{f['id']} {f['severity']}: {f['text']}"))
    dfmea = r.get("dfmea", [])
    if not dfmea:
        out.append(Issue("G2", "error", "no-dfmea", "no DFMEA lines"))
    linked = {rid for c in r["characteristics"] for rid in c.get("requirement_ids", [])}
    linked |= {rid for l in dfmea for rid in l.get("requirement_ids", [])}
    for q in r["requirements"]:
        if q["id"] not in linked:
            out.append(Issue("G2", "error", "orphan-requirement", f"{q['id']} is not covered by any characteristic or DFMEA line"))
    by_id = {c["id"]: c for c in r["characteristics"]}
    for row in trace(r):
        c = row["char"]
        if not row["dfmea"]:
            out.append(Issue("G2", "error", "kc-not-in-dfmea", f"{c['class']} {c['id']} {c['feature']} is not in the DFMEA"))
        if c["source"] == "ASSUMED":
            out.append(Issue("G2", "error", "kc-assumed", f"{c['class']} {c['id']} {c['feature']} is still ASSUMED"))
        if c["source"] == "MOCK":
            out.append(Issue("G2", "warn", "kc-mock", f"{c['class']} {c['id']} {c['feature']} is MOCK data"))
    for l in dfmea:
        for cid in l.get("char_ids", []):
            if cid not in by_id:
                out.append(Issue("G2", "error", "unknown-char", f"DFMEA {l['id']} links unknown characteristic {cid}"))
            elif l["S"] >= 9 and by_id[cid]["class"] not in TRACKED:
                out.append(Issue("G2", "warn", "high-s-not-kc",
                                 f"DFMEA {l['id']} has S{l['S']} but {cid} is class {by_id[cid]['class']}; consider KC/CC (AS9103)"))
    out += _ap_issues(dfmea, "G2", "DFMEA")
    for s in r.get("stackups", []):
        try:
            res = analyze(s, r["characteristics"], samples=20_000)
        except ValueError as e:
            out.append(Issue("G2", "error", "stackup-invalid", str(e)))
            continue
        if not res["meets"]:
            m = res[res["method"]]
            out.append(Issue("G2", "error", "stackup-fails",
                             f"{s['id']} {s['name']}: {res['method']} {m['min']:.4f} to {m['max']:.4f} misses target "
                             f"{s['target'].get('min')} to {s['target'].get('max')}"))
    if not r.get("bom"):
        out.append(Issue("G2", "warn", "no-bom", "no BOM"))
    return out


def _g3(r):
    out = []
    if not _signed(r, "G3"):
        out.append(Issue("G3", "error", "review-not-signed", "no signed G3 process review"))
    process = r.get("process", [])
    if not process:
        out.append(Issue("G3", "error", "no-routing", "no routing"))
    made = {cid for p in process for cid in p.get("makes", [])}
    ops = {p["op"] for p in process}
    for c in r["characteristics"]:
        if c["id"] not in made:
            out.append(Issue("G3", "error", "char-not-made", f"{c['id']} {c['feature']} is not made at any operation"))
    dfmea_s = {}
    for l in r.get("dfmea", []):
        for cid in l.get("char_ids", []):
            dfmea_s[cid] = max(dfmea_s.get(cid, 0), l["S"])
    dfmea_by_id = {l["id"]: l for l in r.get("dfmea", [])}
    for row in trace(r):
        c = row["char"]
        for key, doc in (("pfmea", "PFMEA"), ("control_plan", "control plan"), ("inspection", "inspection plan")):
            if not row[key]:
                out.append(Issue("G3", "error", f"kc-not-in-{key.replace('_', '-')}", f"{c['class']} {c['id']} {c['feature']} is not in the {doc}"))
    for l in r.get("pfmea", []):
        if "op" in l and l["op"] not in ops:
            out.append(Issue("G3", "error", "unknown-op", f"PFMEA {l['id']} names op {l['op']}, which is not in the routing"))
        # A PFMEA line that names the DFMEA lines it carries must not rate severity below them.
        # Without that link, fall back to the highest DFMEA severity for its characteristics, as a warning.
        if l.get("dfmea_ids"):
            for did in l["dfmea_ids"]:
                d = dfmea_by_id.get(did)
                if d is None:
                    out.append(Issue("G3", "error", "unknown-dfmea", f"PFMEA {l['id']} names unknown DFMEA line {did}"))
                elif l["S"] < d["S"]:
                    out.append(Issue("G3", "error", "pfmea-s-below-dfmea",
                                     f"PFMEA {l['id']} rates S{l['S']}, below DFMEA {did} S{d['S']}"))
        else:
            for cid in l.get("char_ids", []):
                if l["S"] < dfmea_s.get(cid, 0):
                    out.append(Issue("G3", "warn", "pfmea-s-below-dfmea",
                                     f"PFMEA {l['id']} rates S{l['S']} for {cid}, below the highest DFMEA S{dfmea_s[cid]}; "
                                     f"link dfmea_ids to compare against the right DFMEA line"))
    out += _ap_issues(r.get("pfmea", []), "G3", "PFMEA")
    for row in r.get("control_plan", []):
        if row["op"] not in ops:
            out.append(Issue("G3", "error", "unknown-op", f"control plan row for {row['char_id']} names op {row['op']}, not in the routing"))
        if not row.get("gauge"):
            out.append(Issue("G3", "error", "no-gauge", f"control plan row for {row['char_id']} has no gauge"))
    return out


def _g4(r):
    out = []
    if not _signed(r, "G4"):
        out.append(Issue("G4", "error", "review-not-signed", "no signed G4 FAI review"))
    fai = r.get("fai", {})
    results = {x["char_id"]: x for x in fai.get("results", [])}
    for c in r["characteristics"]:
        res = results.get(c["id"])
        if res is None:
            out.append(Issue("G4", "error", "no-fai-result", f"{c['id']} {c['feature']} has no FAI result"))
            continue
        v = res["result"]
        if isinstance(v, (int, float)) and "lsl" in c and "usl" in c and not c["lsl"] <= v <= c["usl"]:
            if not res.get("ncr"):
                out.append(Issue("G4", "error", "fai-reject-no-ncr", f"{c['id']} result {v} is outside {c['lsl']}-{c['usl']} with no NCR"))
    if any(c["kind"] == "material" for c in r["characteristics"]) and not fai.get("materials"):
        out.append(Issue("G4", "warn", "no-form2-materials", "material characteristics exist but FAI Form 2 lists no material certs"))
    return out


def _g5(r):
    out = []
    approved = [c for c in r.get("changes", []) if c.get("status") == "approved"]
    for c in r.get("changes", []):
        if not c.get("affected_docs"):
            out.append(Issue("G5", "error", "ecn-no-impact", f"{c['ecn']} lists no affected documents"))
        if not c.get("char_ids"):
            out.append(Issue("G5", "warn", "ecn-no-chars", f"{c['ecn']} lists no affected characteristics"))
    if approved and approved[-1]["to_rev"] != r["part"]["rev"]:
        out.append(Issue("G5", "error", "rev-mismatch",
                         f"latest approved ECN {approved[-1]['ecn']} goes to rev {approved[-1]['to_rev']} but the record is rev {r['part']['rev']}"))
    return out


_CHECKS = {"G0": _g0, "G1": _g1, "G2": _g2, "G3": _g3, "G4": _g4, "G5": _g5}


def check(record, gate):
    """Run every check up to and including `gate`. Schema errors come back as G0 errors."""
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate}; use one of {', '.join(GATES)}")
    errs = validate(record)
    if errs:
        return [Issue("G0", "error", "schema", e) for e in errs]
    out = []
    for g in GATES[: GATES.index(gate) + 1]:
        out += _CHECKS[g](record)
    return out


def passed(issues):
    return not any(i.level == "error" for i in issues)
