"""AIAG-VDA FMEA action priority (AP).

The table follows the AIAG-VDA FMEA Handbook (2019) action priority table for DFMEA and PFMEA, which
uses the same S/O/D bands for both. It was written from the published table, not copied from a licensed
copy in this repo: check it against your handbook before a customer submission.
"""

# Detection bands, left to right: D 7-10, D 5-6, D 2-4, D 1.
# Occurrence bands, top to bottom: O 8-10, O 6-7, O 4-5, O 2-3, O 1.
_TABLE = {
    "S9-10": ["HHHH", "HHHH", "HHHM", "HMLL", "LLLL"],
    "S7-8": ["HHHH", "HHHM", "HMMM", "MMLL", "LLLL"],
    "S4-6": ["HHMM", "MMML", "MLLL", "LLLL", "LLLL"],
    "S2-3": ["MMLL", "LLLL", "LLLL", "LLLL", "LLLL"],
    "S1": ["LLLL", "LLLL", "LLLL", "LLLL", "LLLL"],
}


def _s_band(s):
    if s >= 9:
        return "S9-10"
    if s >= 7:
        return "S7-8"
    if s >= 4:
        return "S4-6"
    if s >= 2:
        return "S2-3"
    return "S1"


def _o_row(o):
    if o >= 8:
        return 0
    if o >= 6:
        return 1
    if o >= 4:
        return 2
    if o >= 2:
        return 3
    return 4


def _d_col(d):
    if d >= 7:
        return 0
    if d >= 5:
        return 1
    if d >= 2:
        return 2
    return 3


def action_priority(s, o, d):
    """Return 'H', 'M' or 'L' for severity, occurrence and detection ratings 1-10."""
    for name, v in (("S", s), ("O", o), ("D", d)):
        if not 1 <= v <= 10:
            raise ValueError(f"{name}={v} is outside 1-10")
    return _TABLE[_s_band(s)][_o_row(o)][_d_col(d)]
