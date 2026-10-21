---
name: design-review
description: Checklist for a mechanical design review and ASME Y14.5-2018 drawing check of a machined part or simple assembly. Used by the design-reviewer agent at G2.
---

# Design review checklist

Record every "no" as a finding (blocker / major / minor / note) with the characteristic ids it touches.

## Function and fit
- Each requirement has characteristics that deliver it, and each toleranced function has a stack-up or a cited
  fit table.
- Mating parts and fasteners are identified; floating or fixed fastener formula applied to hole size and
  position.
- Press fits checked at both limits against the bearing or bushing maker's data for the housing material.
- Retention (staking, adhesive, retaining ring) defined with a verifiable requirement (push-out load).
- Strength: lugs, bearing stress, bolt shear and tension, edge distance at least 1.5D, or a reason.
- Material and temper, grain direction if it matters, finish and its effect on fits (masking, build-up).

## Datums and GD&T (Y14.5-2018)
- Datum features match how the part is mounted and works (primary = the seating face, secondary and
  tertiary = the locating features).
- Every feature is fully located and oriented: no implied 90 degrees or basic dims without a feature control
  frame, no double dimensioning.
- Modifiers are deliberate: MMC on clearance holes for bonus tolerance and functional gauging; RFS on a press
  fit bore that sets alignment.
- Form controls (flatness, cylindricity) are tighter than the size and orientation controls they refine.
- Basic dimensions are boxed; general tolerances in the title block cover every untoleranced dimension.

## Drawing content
- Title block: part number, name, rev, material, finish, scale, units, projection, general tolerances,
  standard (ASME Y14.5-2018), CAGE.
- Notes: material spec, finish spec, marking (MIL-STD-130 where required), break sharp edges, surface texture.
- Revision block matches the record rev; distribution statement and export-control warning on controlled parts.
- MOCK parts say MOCK-UP ONLY on every sheet.
- Drawing values equal model `_params.json` and record characteristics.

## Traceability
- Every characteristic on the drawing is in the record with a balloon, class and source tag.
- No KC or CC is ASSUMED. Conflicting sources are listed, not resolved silently.
