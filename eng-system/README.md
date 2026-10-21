# eng-system

The foundation of an end-to-end mechanical engineering system: one part record per part revision, six gates
from data intake to production change, and generated documents for each gate.

```
data inputs -> G0 intake -> G1 concept CAD -> G2 design release -> G3 process release -> G4 FAI / PPAP -> G5 change
```

| Piece | What it is |
|---|---|
| [`docs/brief.md`](docs/brief.md) | The refined ask: role, context, standards, gates, rules |
| [`docs/process.md`](docs/process.md) | Gates, exit criteria, document map, who does what |
| [`CLAUDE.md`](CLAUDE.md) | Lead-engineer charter; copy to `D:\CAD-Agent\CLAUDE.md` |
| [`src/engsys/schema/part-record.schema.json`](src/engsys/schema/part-record.schema.json) | The part record: requirements, characteristics, BOM, reviews, stack-ups, DFMEA, routing, PFMEA, control plan, inspection plan, FAI, ECNs |
| `engsys` CLI (`src/engsys/`) | Validates the record, checks gate criteria and KC traceability, runs stack-ups, writes the workbooks |
| [`claude/agents/`](claude/agents/) | `design-reviewer`, `tolerance-analyst`, `dfm-reviewer` subagents |
| [`claude/skills/`](claude/skills/) | `design-review`, `fmea-chain`, `fai-as9102`, `ecn` skills |
| [`claude/hooks/itar_guard.py`](claude/hooks/itar_guard.py) | Blocks cloud CAD and uploads for Demil B / ITAR parts |
| [`examples/EX-0001/`](examples/EX-0001/) | A public worked example (pillow block bearing housing) that passes every gate |

## Install and run

Python 3.11+.

```
pip install -e ".[dev]"
engsys validate examples/EX-0001/part-record.json
engsys stackup  examples/EX-0001/part-record.json
engsys check    examples/EX-0001/part-record.json --gate G4 --report out/
engsys build    examples/EX-0001/part-record.json --out out/
pytest
```

`engsys build` writes one workbook per controlled document, named `<id>_<Document> (Rev - X).xlsx`:
Characteristics (balloon list), Requirements, BOM, Design-Review, Stack-ups, DFMEA, Routing, PFMEA,
Control-Plan, Inspection-Plan, FAI (AS9102 Forms 1-3) and ECN-Log, plus `<id>_Gate-Report (Rev - X).md`
with the gate result and a KC/CC traceability matrix. MOCK records get MOCK in every file name and a banner
on every sheet; ITAR records carry the export-control warning.

## What the gate check enforces

- Every characteristic has a source tag; KCs and CCs can't stay ASSUMED past G2.
- Every requirement is covered; every KC/CC traces requirement -> DFMEA -> operation -> PFMEA -> control plan
  -> inspection plan -> FAI result.
- Action priority from the AIAG-VDA table; every High needs an action.
- Stack-ups meet their target by the stated method (worst case or RSS).
- PFMEA severity is not below the DFMEA line it links.
- No open blocker or major review findings; a signed review at G2, G3 and G4.
- FAI results inside limits or carrying an NCR; ECN rev matches the record rev.

## Setting up D:\CAD-Agent

1. `pip install -e <path to cad-workflows>/eng-system`
2. Copy `CLAUDE.md` to `D:\CAD-Agent\CLAUDE.md`, `claude/agents/*` to `D:\CAD-Agent\.claude\agents\`,
   `claude/skills/*` to `D:\CAD-Agent\.claude\skills\`, `claude/hooks/itar_guard.py` to
   `D:\CAD-Agent\.claude\hooks\`, and merge `claude/settings.example.json` into `D:\CAD-Agent\.claude\settings.json`.
3. Put the part being worked on in `D:\CAD-Agent\.active-part` (one line, the `specs/` folder name).
   With no active part, the guard blocks cloud CAD and uploads.
4. Put licensed standards (ASME Y14.5, AIAG-VDA FMEA, AS9102, AS9145, AS9103) in `D:\CAD-Agent\standards\`.
   Never commit them.

## Limits

- The AIAG-VDA action priority table and the AS9102 form fields were written from the published standards,
  not copied from licensed copies. Check them against your copies before a customer submission.
- Drawings, work instructions, MSA / gauge R&R and capability studies are not generated yet; their results
  are recorded in the part record.
- Stack-ups are 1D. 2D/3D variation needs a CAD-driven Monte Carlo or a commercial tool (CETOL, 3DCS).
- Never commit export-controlled part records or outputs to this repo. Only public examples live here.
