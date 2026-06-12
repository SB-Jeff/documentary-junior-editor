#!/usr/bin/env python3
"""Drift linter for the documentary-junior-editor skill system (S2/W7).

Catches the documentation-drift class found in skill-review-2026-06-10.md:
stale version footers, wrong agent counts, references to files that don't
exist, and retired symbols/instructions that keep resurfacing.

Run from the skill folder root (or pass the root as the first argument):

    python3 scripts/lint_skill_drift.py [skill_root]

Exit codes: 0 = clean, 1 = findings, 2 = could not run.

Wired into SKILL-review.md Phase 6: run before presenting proposed skill
edits AND after applying them. All findings must be clean or explicitly
acknowledged by Jeff.
"""

import re
import sys
from pathlib import Path

# Files that participate in the versioned skill system.
SKILL_GLOB = "SKILL*.md"
GUIDE = "cowork-session-guide.md"

# SKILL files exempt from the version-footer sync requirement, with the
# marker string that must appear instead (near the top of the file).
FROZEN = {
    "SKILL-edit-pipeline.md": "frozen",  # v5.0 fossil; banner required (Q10)
}

# Lines that mention a retired symbol while explaining it is retired are fine;
# only flag mentions presented as live instructions.
DEPRECATION_CONTEXT = re.compile(
    r"\b(no|not|never|deprecated|legacy|replaced?s?|removed|removal|retired|"
    r"dropped|drops|ignore|historical|formerly|obsolete)\b",
    re.I,
)

# Retired symbols: (regex, human label, allowed filenames, negation_ok).
# negation_ok=True: skip lines that carry deprecation context.
RETIRED = [
    (re.compile(r"find_quote_range"), "nonexistent function `find_quote_range`", set(), False),
    (re.compile(r"git-crypt|git crypt", re.I), "retired git-crypt instructions (replaced by .env in v5.1)", set(), True),
    (re.compile(r"secrets/assembly_ai\.key"), "retired secrets/assembly_ai.key path", set(), True),
    (re.compile(r"mcp__[0-9a-f]{8}-[0-9a-f]{4}"), "per-install MCP tool UUID (use capability names — F1)", set(), False),
    (re.compile(r"cowork-session-guide-restore\.md"), "reference to nonexistent cowork-session-guide-restore.md", set(), False),
    (re.compile(r"runtime_recommendation"), "retired runtime_recommendation field (v5.9 uses membership)",
     {"SKILL-edit-pipeline.md"}, True),  # frozen file may still describe it
]

# Agent-count language: the pipeline is ten agents (v5.5+).
BAD_COUNTS = re.compile(
    r"\b(eight|nine|seven|8|9)\s+agents\b|\b[Nn]inth and final\b|\b[Ee]ighth and final\b"
)

# Repo-relative file references worth verifying. Conservative patterns only,
# to avoid false positives on placeholders like [speaker-slug]-summary.md.
REF_PATTERNS = [
    re.compile(r"\b(SKILL-[A-Za-z0-9-]+\.md)\b"),
    re.compile(r"\b(cowork-session-guide[A-Za-z0-9-]*\.md)\b"),
    re.compile(r"\b(quotes-viewer-roadmap\.md)\b"),
    re.compile(r"\bscripts/([A-Za-z0-9_]+\.(?:py|jsx))\b"),
]


def find_version(root: Path):
    """Current version from the SKILL.md header, e.g. 'Version 5.10 | June 2026'."""
    text = (root / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Version\s+(\d+\.\d+)", text)
    return m.group(1) if m else None


def lint(root: Path):
    findings = []
    version = find_version(root)
    if not version:
        findings.append(("SKILL.md", "could not parse a `Version X.Y` header"))
        version = "?"

    targets = sorted(root.glob(SKILL_GLOB)) + ([root / GUIDE] if (root / GUIDE).exists() else [])
    targets = [t for t in targets if t.is_file()]
    known_names = {p.name for p in root.iterdir()} | {
        f"scripts/{p.name}" for p in (root / "scripts").iterdir() if (root / "scripts").is_dir()
    }

    for path in targets:
        name = path.name
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        # 1. Version footer sync (last 12 lines must mention the current version).
        if name in FROZEN:
            head = "\n".join(lines[:40]).lower()
            if FROZEN[name] not in head:
                findings.append((name, f"frozen file is missing its '{FROZEN[name]}' banner near the top"))
        elif name != "SKILL.md":
            tail = "\n".join(lines[-12:])
            if f"v{version}" not in tail and f"Version {version}" not in tail and version not in tail:
                findings.append((name, f"footer does not mention current version {version}"))

        # 2. Agent-count language.
        for i, line in enumerate(lines, 1):
            if BAD_COUNTS.search(line):
                findings.append((f"{name}:{i}", f"stale agent-count wording: {line.strip()[:90]}"))

        # 3. Retired symbols.
        for rx, label, allowed, negation_ok in RETIRED:
            if name in allowed:
                continue
            for i, line in enumerate(lines, 1):
                if rx.search(line):
                    if negation_ok and DEPRECATION_CONTEXT.search(line):
                        continue
                    findings.append((f"{name}:{i}", f"{label}: {line.strip()[:90]}"))

        # 4. Referenced files must exist.
        for rx in REF_PATTERNS:
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    ref = m.group(0) if m.group(0).startswith("scripts/") else m.group(1)
                    if ref not in known_names and not (root / ref).exists():
                        findings.append((f"{name}:{i}", f"references missing file: {ref}"))

    return version, findings


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    if not (root / "SKILL.md").exists():
        print(f"lint_skill_drift: no SKILL.md under {root}", file=sys.stderr)
        return 2
    version, findings = lint(root)
    if findings:
        print(f"DRIFT LINT: {len(findings)} finding(s) against version {version}\n")
        for loc, msg in findings:
            print(f"  {loc}: {msg}")
        return 1
    print(f"DRIFT LINT: clean (version {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
