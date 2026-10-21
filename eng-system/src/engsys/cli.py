"""engsys command line: validate, check gates, run stack-ups, build documents, start a new record."""

import argparse
import json
import sys
from pathlib import Path

from . import record as rec
from .stackup import analyze
from .workbooks import build, gate_report


def _template(part_id, name, units):
    return {
        "schema": "engsys/part-record/v1",
        "part": {"id": part_id, "name": name, "rev": "A", "units": units, "drafting_standard": "ASME Y14.5-2018",
                 "mock": False, "export_control": {"itar": True, "demil": "", "distribution": ""}},
        "requirements": [{"id": "R1", "text": "Describe what the part must do", "type": "function", "source": "ASSUMED"}],
        "characteristics": [],
        "bom": [], "design_reviews": [], "stackups": [], "dfmea": [], "process": [], "pfmea": [],
        "control_plan": [], "inspection_plan": [], "fai": {}, "changes": [],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engsys", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="check the record against the schema")
    p.add_argument("record")

    p = sub.add_parser("check", help="check gate exit criteria (cumulative)")
    p.add_argument("record")
    p.add_argument("--gate", default="G2", choices=rec.GATES)
    p.add_argument("--report", metavar="DIR", help="also write the gate report to DIR")

    p = sub.add_parser("stackup", help="run the record's stack-ups")
    p.add_argument("record")
    p.add_argument("--id", help="only this stack-up")
    p.add_argument("--json", action="store_true", help="print full results as JSON")

    p = sub.add_parser("build", help="write every document the record has data for")
    p.add_argument("record")
    p.add_argument("--out", required=True)

    p = sub.add_parser("init", help="write a new record template")
    p.add_argument("path")
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--units", default="in", choices=["in", "mm"])

    a = ap.parse_args(argv)

    if a.cmd == "init":
        path = Path(a.path)
        if path.exists():
            print(f"{path} exists; not overwriting", file=sys.stderr)
            return 2
        path.write_text(json.dumps(_template(a.id, a.name, a.units), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}. Set export_control before anything else.")
        return 0

    r = rec.load(a.record)

    if a.cmd == "validate":
        errs = rec.validate(r)
        for e in errs:
            print(e)
        print("valid" if not errs else f"{len(errs)} schema errors")
        return 0 if not errs else 1

    if a.cmd == "check":
        issues = rec.check(r, a.gate)
        for i in issues:
            print(i)
        ok = rec.passed(issues)
        print(f"{a.gate}: {'PASS' if ok else 'FAIL'} ({sum(i.level == 'error' for i in issues)} errors, "
              f"{sum(i.level == 'warn' for i in issues)} warnings)")
        if a.report:
            Path(a.report).mkdir(parents=True, exist_ok=True)
            print(f"wrote {gate_report(r, a.report, a.gate)}")
        return 0 if ok else 1

    if a.cmd == "stackup":
        results = [analyze(s, r["characteristics"]) for s in r.get("stackups", []) if not a.id or s["id"] == a.id]
        if a.json:
            print(json.dumps(results, indent=2))
            return 0
        for x in results:
            t = x["target"]
            print(f"{x['id']} {x['name']}  target {t['min']} to {t['max']}")
            print(f"  worst case {x['worst_case']['min']:.5f} to {x['worst_case']['max']:.5f}  {'ok' if x['worst_case']['meets'] else 'MISS'}")
            print(f"  RSS        {x['rss']['min']:.5f} to {x['rss']['max']:.5f}  {'ok' if x['rss']['meets'] else 'MISS'}")
            mc = x["monte_carlo"]
            print(f"  Monte Carlo mean {mc['mean']:.5f} sigma {mc['sigma']:.5f}, {mc['in_target']:.4%} in target")
            print(f"  judged by {x['method']}: {'PASS' if x['meets'] else 'FAIL'}")
        return 0 if all(x["meets"] for x in results) else 1

    if a.cmd == "build":
        errs = rec.validate(r)
        if errs:
            for e in errs:
                print(e, file=sys.stderr)
            return 1
        for f in build(r, a.out):
            print(f"wrote {f}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
