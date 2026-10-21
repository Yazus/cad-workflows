---
name: fmea-chain
description: Write the linked DFMEA, routing, PFMEA and control plan for a part record in AIAG-VDA 2019 form, so every key characteristic traces from requirement to gauge. Use at G2 (DFMEA) and G3 (PFMEA, control plan).
---

# FMEA chain: DFMEA -> PFMEA -> control plan

The value is in the links, not in any single sheet. Work in the part record (`part-record.json`) and generate
the workbooks with `engsys build`. Check with `engsys check --gate G2` (DFMEA) and `--gate G3` (the rest).

## DFMEA (AIAG-VDA 7 steps, compressed)
1. **Scope and structure:** the part and its interfaces (mating parts, fasteners, environment). For a detail
   part the structure is part -> features; for an assembly, assembly -> components -> features.
2. **Functions:** one per requirement (link `requirement_ids`). Phrase as verb + object + measurable
   condition ("hold the bearing against 200 lbf axial").
3. **Failure modes:** the negation of each function: none, partial, intermittent, too much, too little.
4. **Effects and severity S:** effect on the next level and the end user. S 9-10 = safety or regulatory;
   S 7-8 = loss of primary function; S 4-6 = degraded function; S 2-3 = annoyance; S 1 = none.
5. **Causes:** design causes only (wrong tolerance, wrong material, missed load), each linked to the
   characteristics it acts through (`char_ids`). Assume manufacturing makes the part to drawing.
6. **Controls and O, D:** prevention (stack-up, standard, prior design) sets O; detection (analysis, test,
   design review) sets D. D rates how well the design-verification method finds the cause before release.
7. **Action priority:** `engsys` computes AP from the AIAG-VDA table. Every H needs an action, owner and due
   date; M needs an action or a recorded reason for none.

Mark characteristics touched by S >= 9 lines as KC or CC (AS9103); the gate warns otherwise.

## Routing (process)
Draft it with the `dfm-reviewer`, then make sure every characteristic id appears in `makes` of the operation
that creates it. Receiving inspection makes material characteristics; outside finishing makes finish ones.

## PFMEA
One line per process failure that could break a characteristic, per operation:
- `op` and `item` = the operation; `function` = what the operation must achieve on that characteristic.
- `dfmea_ids` = the DFMEA line(s) whose effect this failure leads to. PFMEA S must not be below that line's S.
- Causes are process causes: setup, tool wear, fixture seating, offset error, operator, material.
- Prevention sets O (poka-yoke, tool life limits, setup approval). Detection sets D (in-process gauging at the
  machine scores better than final inspection; 100% automated beats sampling).

## Control plan (AIAG Control Plan 2024 / AS9145)
One row per characteristic per operation where it is controlled. Every KC and CC must have a row with:
evaluation method, gauge, sample size, frequency, control method (SPC chart, setup approval, 100% test) and a
reaction plan (stop, contain since last good part, correct, sort, NCR). The gauge must be able to resolve
1/10 of the tolerance; plan a gauge R&R for KC gauges.

## Hand-off
When the chain is written, run `engsys check <record> --gate G3 --report out/<NSN>/` and fix every
`kc-not-in-*`, `char-not-made`, `pfmea-s-below-dfmea` and `high-ap-no-action` error before reporting done.
