---
name: ecn
description: Raise and close an engineering change notice for a released part record, with impact on every linked document and the FAI decision. Use for any change after G2, and for NCR or 8D outcomes that change the design or process.
---

# Engineering change (ECN)

A released revision is never edited in place. A change is an ECN entry in the record's `changes` array, then
a new revision of the record and every affected document.

## Steps
1. **Describe** the change and the reason (NCR number, customer request, cost, obsolescence, 8D root cause).
2. **Classify:** Class I if it affects form, fit, function, interchangeability, safety, weight or a KC; it needs
   customer (and for DLA, engineering support activity) approval before use. Otherwise Class II.
3. **Impact:** list `char_ids` changed, then follow the thread from each: requirements, stack-ups, DFMEA lines,
   operations, PFMEA lines, control plan rows, inspection plan rows, FAI Form 3 lines. List every affected
   document in `affected_docs` (drawing, model, part record, DFMEA, PFMEA, control plan, inspection plan, work
   instructions, CMM programs, gauges).
4. **FAI decision:** `fai_required` = partial for changes that affect the changed characteristics only,
   full for a new source or a broad process change, none for documentation-only Class II changes.
5. **Approve:** `status: approved`, `approved_by`. Then set `part.rev` to the ECN's `to_rev`, update the
   affected records, and rebuild with `engsys build`. New files get the new `(Rev - X)`; old ones stay.
6. **Check:** `engsys check <record> --gate G5` fails if the record rev doesn't match the latest approved ECN
   or an ECN lists no affected documents.

Feed every lesson back: a new failure cause goes into the DFMEA or PFMEA with fresh O and D ratings.
