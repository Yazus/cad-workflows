"""PreToolUse hook: block cloud CAD, uploads and outbound file transfers for export-controlled parts.

The active part is named in `.active-part` at the project root (one line: an NSN or part id that is a
folder under specs/). Its `part-record.json` or `part-spec.json` decides whether it is controlled:
`export_control.itar` true, `itar` true, or a Demil code other than A.

Rules, in order:
- The tool is not on the guarded list: allow.
- The tool input mentions MOCK: allow (MOCK data is photo-scaled or invented, never measured).
- No active part, or its spec can't be read: block (fail closed).
- The active part is controlled: block.
- Otherwise: allow.

Exit code 2 blocks the call and shows stderr to Claude. Configure the guarded tools in
`.claude/hooks/itar-guard.json` (see itar-guard.example.json).
"""

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "tool_patterns": [r"^mcp__onshape__", r"^mcp__kernelCAD__", r"^mcp__.*[Dd]rive__.*(create|update|upload|copy|share)"],
    "bash_patterns": [r"curl\s.*(-F|--form|-T|--upload-file|--data-binary\s+@)", r"\bscp\b", r"\brsync\b.*:", r"\bsftp\b",
                      r"\bgh\s+(gist|release)\s+(create|upload)", r"\bgit\s+push\b"],
}


def _load_config(root):
    p = root / ".claude" / "hooks" / "itar-guard.json"
    if p.exists():
        return {**DEFAULT_CONFIG, **json.loads(p.read_text(encoding="utf-8"))}
    return DEFAULT_CONFIG


def _controlled(spec):
    ec = spec.get("part", {}).get("export_control") or spec.get("export_control") or {}
    if ec.get("itar") or spec.get("itar"):
        return True
    demil = str(ec.get("demil") or spec.get("demil") or "").strip()
    return bool(demil) and not demil.upper().startswith("A")


def _active_spec(root):
    marker = root / ".active-part"
    if not marker.exists():
        return None, "no .active-part file names the part being worked on"
    part = marker.read_text(encoding="utf-8").strip()
    for name in ("part-record.json", "part-spec.json"):
        p = root / "specs" / part / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), part
    return None, f"no part-record.json or part-spec.json under specs/{part}"


def decide(event, root):
    """Return (allow, reason)."""
    cfg = _load_config(root)
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    if tool == "Bash":
        guarded = any(re.search(p, tool_input.get("command", "")) for p in cfg["bash_patterns"])
    else:
        guarded = any(re.search(p, tool) for p in cfg["tool_patterns"])
    if not guarded:
        return True, ""
    if "MOCK" in json.dumps(tool_input):
        return True, ""
    spec, part = _active_spec(root)
    if spec is None:
        return False, f"ITAR guard: blocked {tool}: {part}. Set .active-part, or work on a MOCK file."
    if _controlled(spec):
        return False, (f"ITAR guard: blocked {tool}: active part {part} is export-controlled. "
                       "Keep its data on this PC. Only files with MOCK in the name may leave it.")
    return True, ""


def main():
    event = json.load(sys.stdin)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    try:
        allow, reason = decide(event, root)
    except Exception as e:  # fail closed on a broken spec or config
        allow, reason = False, f"ITAR guard: blocked because the guard could not decide ({e})"
    if not allow:
        print(reason, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
