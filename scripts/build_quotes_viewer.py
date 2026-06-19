#!/usr/bin/env python3
"""
build_quotes_viewer.py — wrap the canonical .jsx template into a self-contained
HTML artifact, with per-project data baked in.

Reads:
  - scripts/quotes_viewer_template.jsx (the canonical React component)
  - One of:
      (a) A pre-assembled project data JSON file (--data option)
      (b) Auto-discovered files in the project handoffs folder
          (tagged-quotes-v*.json, trimmed-quotes-v*.json,
          editing-versions/v*.json, pipeline-state.json).
          Tight-window exports (trimmed-quotes-v[N]-tight.json) are window
          variants, not rounds — round discovery/version counting ignores them.

Writes:
  - A genuinely self-contained HTML viewer: React 18 + ReactDOM UMD bundles
    and the JSX-compiled-to-JS component are all inlined. No CDN fetch, no
    runtime Babel — the file renders offline and inside sandboxed webviews.

Architecture:
  - Strips the ES `import` and `export default` from the template
  - Substitutes the DATA BLOCK constants (PROJECT_TITLE, PROJECT_META,
    SOURCE_QUOTES, ROUNDS, INITIAL_ROUND_INDEX, INITIAL_FOCUS)
  - Migrates timeline entries from the v5.0 segment-based shape to the
    character-range trim shape the new viewer uses
  - Compiles the JSX to plain JS at build time (Node + vendored
    @babel/standalone in scripts/vendor/), then inlines the vendored React +
    ReactDOM UMD bundles and the compiled component into a single HTML file
  - Mounts behind a React error boundary + try/catch that paints any failure
    into #root, so a thrown render never degrades to a blank page

Usage:
  python3 build_quotes_viewer.py \\
      --slug tccs-dr-pan-testimonials \\
      --ssd-root /Volumes/TCCS_2026/TCCS_2026 \\
      --output /Volumes/TCCS_2026/TCCS_2026/handoffs/tccs-dr-pan-testimonials/tccs-dr-pan-testimonials_quotes_view.html
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


# ============================================================================
# Data assembly
# ============================================================================

def tokens_of(text: str):
    return re.findall(r"\S+", text or "")


def find_substring_with_offset(haystack: str, needle: str, start_hint: int = 0):
    """Find needle in haystack starting at start_hint. Returns (start, end) or None."""
    if not needle:
        return None
    idx = haystack.find(needle, start_hint)
    if idx < 0:
        return None
    return (idx, idx + len(needle))


def lookup_source_quote(by_num: dict, sid):
    """Resolve a source quote by num, tolerating int/str id coupling (Bug 6).

    `by_num` is keyed on the integer `num`; upstream `source_quote_id` may be a
    string ("23") or int (23). Return the quote or None.
    """
    if sid is None:
        return None
    if sid in by_num:
        return by_num[sid]
    try:
        return by_num.get(int(sid))
    except (ValueError, TypeError):
        return None


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "speaker"


def latest_versioned(paths):
    """Return the highest-v[N] Path from an iterable, or None."""
    best, best_n = None, -1
    for p in paths:
        m = re.search(r"v(\d+)", p.name)
        n = int(m.group(1)) if m else 0
        if n >= best_n:
            best_n, best = n, p
    return best


def parse_act_structure_md(text: str):
    """Parse project name, act labels, and speakers from act-structure-v*.md.

    Format is defined by the Creative Context Agent (SKILL-creative-context.md):
        # Approved Act Structure
        ## Project: [Project Name]
        ### Speakers
        - [Name] — [Role] — [description]
        ### Act Labels (...)
        - [Label]
        - Orphan

    Returns (project_name | None, act_labels [list], speakers [list of dicts]).
    Any field that can't be located comes back empty/None.
    """
    project_name = None
    m = re.search(r"^##\s*Project:\s*(.+?)\s*$", text, re.MULTILINE)
    if m:
        project_name = m.group(1).strip()

    def section_body(heading_re):
        m = re.search(
            r"^###\s*" + heading_re + r".*?$(.*?)(?=^###\s|\Z)",
            text, re.MULTILINE | re.DOTALL,
        )
        return m.group(1) if m else ""

    # Act labels: PREFER the explicit canonical "### Act Labels" bullet list
    # (the list downstream agents are told to tag against). Keep its order and
    # include every bullet line — including a trailing "Orphan" bullet, which a
    # downstream step filters out (the viewer's act_labels at build time drops
    # "Orphan"). Only fall back to deriving labels from the act headings when
    # that explicit section is absent; the heading scan yields bare names like
    # "Act 1".."Act 4", which is exactly why the explicit list is preferred.
    act_labels = []
    labels_body = section_body(r"Act Labels")
    if labels_body.strip():
        for line in labels_body.splitlines():
            lm = re.match(r"\s*[-*]\s+(.+?)\s*$", line)
            if lm:
                label = re.sub(r"^\[|\]$", "", lm.group(1).strip()).strip()
                # Strip any parenthetical gloss (e.g. "Orphan (for quotes that
                # don't fit any act)") down to the bare label, and skip unfilled
                # template placeholders like "[Label 1]".
                label = re.sub(r"\s*\(.*\)\s*$", "", label).strip()
                if label and not re.match(r"^Label \d", label, re.I):
                    act_labels.append(label)
    else:
        # Fallback only: derive from act headings such as
        #   ### Act 1 — "Philosophy"   or   **Act 2 — "Used Right":**   or   ## Act 1
        # Yields bare "Act N" names when no descriptive title is present.
        seen = set()
        for hm in re.finditer(
            r"^(?:#{2,4}\s*|\*{2}\s*)Act\s+(\d+)\b", text, re.MULTILINE
        ):
            label = f"Act {hm.group(1)}"
            if label not in seen:
                seen.add(label)
                act_labels.append(label)

    speakers = []
    for line in section_body(r"Speakers").splitlines():
        lm = re.match(r"\s*[-*]\s+(.+?)\s*$", line)
        if lm:
            # "Name — Role — description"; split on em/en dash only so hyphenated
            # names survive.
            parts = re.split(r"\s+[—–]\s+", lm.group(1).strip())
            name = re.sub(r"^\[|\]$", "", parts[0]).strip()
            role = parts[1].strip() if len(parts) > 1 else ""
            if name and not name.startswith("Speaker Name"):
                speakers.append({"name": name, "slug": slugify(name), "role": role})

    return project_name, act_labels, speakers


def parse_act_roadmaps_md(text: str):
    """Parse per-act one-liner roadmaps + a project premise from act-structure-v*.md.

    Looks at the "### Structure" section, whose entries look like:

        **Act 2 — "Used Right":** How BizTrack lets Shane and the team actually
        live that philosophy ...

    The quoted act NAME ("Used Right") equals the canonical Act Label, so the
    roadmaps key on that name. Returns:
        (roadmaps {label -> one_line_summary}, premise | "")

    Defensive (SPEC §10): a missing/unparseable section yields ({}, "") — never
    raises. The caller aligns roadmaps to act_labels and substitutes "" for any
    label with no match.
    """
    roadmaps = {}
    premise = ""
    if not text:
        return roadmaps, premise

    # Isolate the "### Structure" section body (up to the next ### heading).
    m = re.search(
        r"^###\s*Structure.*?$(.*?)(?=^###\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    structure_body = m.group(1) if m else ""

    # Each entry: a bold heading with a label token before the em-dash and a
    # quoted act name, then a colon, then the one-liner sentence(s):
    #   **Intro — "Who Is ProTec":** Meet ProTec: a young ...      (label "Intro")
    #   **Act 1 — "Philosophy":** How Shane believes ...           (label "Philosophy")
    #   **Act 2 — "Used Right":** ...                              (label "Used Right")
    # The canonical Act Label equals the QUOTED name for the numbered acts, but
    # for the Intro the quoted name is a title ("Who Is ProTec") while the label
    # is the pre-dash token ("Intro"). Key the roadmap under BOTH the quoted name
    # and the pre-dash token so the caller's `act_roadmaps.get(label)` matches
    # whichever form the canonical Act Labels list uses.
    for em in re.finditer(
        r'\*\*\s*([^—–*"""]+?)\s*[—–]\s*[""]([^""]+)[""]\s*:\*\*\s*(.+?)'
        r'(?=\n\s*\n|\n\s*\*\*|\Z)',
        structure_body, re.DOTALL,
    ):
        pre = em.group(1).strip()
        quoted = em.group(2).strip()
        summary = re.sub(r"\s+", " ", em.group(3).strip())
        if not summary:
            continue
        for key in (quoted, pre):
            if key and key not in roadmaps:
                roadmaps[key] = summary

    # Premise: prefer the Intro one-liner if present (concise project framing);
    # the caller can override from the creative brief. Leave to caller; here we
    # only return the structure-derived roadmaps + a best-effort premise.
    premise = roadmaps.get("Intro", "")
    return roadmaps, premise


def parse_premise_md(text: str):
    """Best-effort project premise from creative-brief-summary-v*.md (1-2 sentences).

    Prefers the "## Central narrative" section's first sentence(s). Defensive
    (SPEC §10): returns "" if the file/section is missing or unparseable — never
    raises.
    """
    if not text:
        return ""
    m = re.search(
        r"^##\s*Central narrative.*?$(.*?)(?=^##\s|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    body = (m.group(1) if m else "").strip()
    if not body:
        return ""
    body = re.sub(r"\s+", " ", body)
    # Keep it short: first 1-2 sentences. Split on sentence-ending punctuation
    # followed by a space + capital/quote (avoids splitting "$40M.").
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", body)
    premise = " ".join(sentences[:2]).strip()
    return premise


def derive_speakers_from_quotes(quotes):
    """Distinct {name, slug, role} from the source quote pool (Bug 3).

    Keys on speakerSlug so the slugs are guaranteed to match the values the
    viewer's Speaker filter and color map look up. Preserves first-seen order.
    """
    seen, order = {}, []
    for q in quotes:
        # Skip unattributed quotes (e.g. orphans parsed from markdown with no
        # speaker) — they'd otherwise mint a junk "speaker" chip.
        if not (q.get("speakerSlug") or q.get("speaker")):
            continue
        slug = q.get("speakerSlug") or slugify(q.get("speaker", ""))
        if not slug or slug in seen:
            continue
        seen[slug] = {
            "name": q.get("speaker") or slug,
            "slug": slug,
            "role": q.get("role", ""),
        }
        order.append(slug)
    return [seen[s] for s in order]


def parse_orphans_md(text: str, start_num: int):
    """Best-effort extraction of orphan quotes from a free-form *-orphans-v*.md.

    The orphan markdown has no strict schema (SKILL-transcript.md Output 2 is
    prose), so this is heuristic: it lifts verbatim quotes from markdown
    blockquote lines (`> ...`) and from lines that are wholly wrapped in double
    quotes. Each becomes a minimal orphan quote object. The durable fix is
    upstream (Synthesis emitting is_orphan entries inside tagged-quotes-v*.json,
    which this build already consumes) — see the scope flag in the build output.
    """
    orphans = []
    num = start_num
    for raw in text.splitlines():
        line = raw.strip()
        quote_text = None
        bq = re.match(r">\s*(.+)$", line)
        if bq:
            quote_text = bq.group(1).strip().strip('"“”')
        else:
            qm = re.match(r'^[-*]?\s*["“](.+?)["”]\s*$', line)
            if qm:
                quote_text = qm.group(1).strip()
        if quote_text and len(quote_text) > 1:
            orphans.append({
                "num": num,
                "originalNum": num,
                "speaker": "",
                "speakerSlug": "",
                "role": "",
                "quote": quote_text,
                "startTC": "",
                "endTC": "",
                "part": "Orphan",
                "rationale": "",
                "is_orphan": True,
                "segments": [{"idx": 0, "text": quote_text, "startTC": "", "endTC": ""}],
            })
            num += 1
    return orphans


def migrate_entry_trims(entry: dict, source_quotes_by_num: dict) -> dict:
    """Convert v5.0 segment-based entry → new viewer's character-range entry.

    Old entry shape:
        {
            "entry_id": "e_002",
            "source_quote_id": 2,
            "speaker": "...",
            "part": "...",
            "runtime_recommendation": "...",
            "segments": [
                {"source_segment_idx": 0, "head_trim_words": 1},
                {"source_segment_idx": 2}
            ],
            "notes": "..."
        }

    New entry shape:
        {
            "entry_id": "2",                    # bare source num, no e_NNN
            "_subLabel": null,
            "source_quote_id": 2,
            "type": "spoken",
            "speaker": "...",
            "part": "...",
            "runtime_recommendation": "...",
            "_editCuts": [[start, end], ...],   # char ranges to cut
            "notes": "..."
        }
    """
    src = lookup_source_quote(source_quotes_by_num, entry.get("source_quote_id"))
    if not src:
        return None

    # Already-runtime-shaped entry (saved BY THE VIEWER, e.g. a named cut in
    # editing-versions): it carries char-range `_editCuts` and has NO old
    # `segments` list. The segment→char migration below assumes the old shape and
    # would re-derive cuts from a missing `segments` field — yielding [[0, len]]
    # (the whole quote cut) and a blank card. Detect and pass it through intact,
    # only normalising the entry_id + canonical int source num + sub-label.
    if "segments" not in entry and "_editCuts" in entry:
        old_id = str(entry.get("entry_id", src["num"]))
        new_id = str(src["num"]) if old_id.startswith("e_") else old_id
        return {
            "entry_id": new_id,
            "_subLabel": entry.get("_subLabel"),
            "source_quote_id": src["num"],
            "type": entry.get("type", "spoken"),
            "speaker": entry.get("speaker"),
            "part": entry.get("part"),
            "runtime_recommendation": entry.get("runtime_recommendation", "probable-keep"),
            "membership": entry.get("membership"),
            "_editCuts": entry.get("_editCuts", []),
            "notes": entry.get("notes", ""),
        }

    # Build full original text (join all segments with single space, matching
    # what the new viewer's fullQuoteText does).
    full_text = " ".join(seg["text"] for seg in src["segments"])

    # Track character offset of each segment in full_text
    seg_offsets = {}
    pos = 0
    for i, seg in enumerate(src["segments"]):
        seg_offsets[seg["idx"]] = (pos, pos + len(seg["text"]))
        pos += len(seg["text"])
        if i < len(src["segments"]) - 1:
            pos += 1  # space separator

    # Build kept char ranges from entry's segments list + word trims
    kept_ranges = []
    for seg_ref in entry.get("segments", []):
        idx = seg_ref["source_segment_idx"]
        if idx not in seg_offsets:
            continue
        seg_start, seg_end = seg_offsets[idx]
        seg_text = full_text[seg_start:seg_end]
        head_trim = seg_ref.get("head_trim_words", 0)
        tail_trim = seg_ref.get("tail_trim_words", 0)

        # Compute the kept text inside this segment by skipping head_trim words
        # at the start and tail_trim words at the end
        tokens = tokens_of(seg_text)
        if not tokens:
            continue
        if head_trim + tail_trim >= len(tokens):
            continue  # nothing kept

        # Find the kept portion's char range within seg_text
        # Use regex to find each word's position in seg_text
        word_spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", seg_text)]
        if not word_spans:
            continue
        kept_word_start = word_spans[head_trim][0] if head_trim < len(word_spans) else len(seg_text)
        kept_word_end = word_spans[len(word_spans) - tail_trim - 1][1] if tail_trim < len(word_spans) else 0

        if kept_word_end <= kept_word_start:
            continue
        kept_ranges.append((seg_start + kept_word_start, seg_start + kept_word_end))

    # Merge adjacent kept ranges that are separated only by whitespace —
    # otherwise the segment-join spaces become spurious 1-char cuts.
    kept_ranges.sort()
    if kept_ranges:
        merged = [list(kept_ranges[0])]
        for kr in kept_ranges[1:]:
            last = merged[-1]
            if kr[0] <= last[1]:
                last[1] = max(last[1], kr[1])
            elif full_text[last[1]:kr[0]].strip() == "":
                # only whitespace between → merge
                last[1] = kr[1]
            else:
                merged.append(list(kr))
        kept_ranges = [tuple(r) for r in merged]

    # Cuts = complement of kept_ranges within full_text
    cuts = []
    if not kept_ranges:
        cuts.append([0, len(full_text)])
    else:
        pos = 0
        for kr_start, kr_end in kept_ranges:
            if pos < kr_start:
                cuts.append([pos, kr_start])
            pos = kr_end
        if pos < len(full_text):
            cuts.append([pos, len(full_text)])

    # Drop any pure-whitespace cuts (defensive — shouldn't happen after merge)
    cuts = [[s, e] for s, e in cuts if full_text[s:e].strip() != ""]

    # Migrate entry_id: e_NNN → bare source num (no e_ prefix, no padding)
    # Reasoning: under v5.0 punch list, entry IDs derive from source num.
    old_id = str(entry.get("entry_id", ""))
    if old_id.startswith("e_"):
        new_id = str(entry["source_quote_id"])
    else:
        new_id = old_id

    return {
        "entry_id": new_id,
        "_subLabel": None,
        # Emit the canonical source num (int) so the viewer's strict-equality
        # findSourceQuote(q.num === id) resolves it even when upstream wrote a
        # string id like "23" (Bug 6).
        "source_quote_id": src["num"],
        "type": entry.get("type", "spoken"),
        "speaker": entry.get("speaker"),
        "part": entry.get("part"),
        "runtime_recommendation": entry.get("runtime_recommendation", "probable-keep"),
        "membership": entry.get("membership"),
        "_editCuts": cuts,
        "notes": entry.get("notes", ""),
    }


def migrate_membership(entries):
    """Assign each timeline entry a membership stratum: "tight" or "loose".

    New data carries `membership` directly. Legacy data carries the retired
    conviction tiers — must-keep / tight-candidate map to tight, everything else
    to loose; non-spoken structural entries (title cards, interstitials, context
    beats) are always tight. The retired `runtime_recommendation` field is dropped
    from the emitted entry.
    """
    out = []
    for e in entries:
        e = dict(e)
        mship = e.get("membership")
        if mship not in ("tight", "loose"):
            is_spoken = e.get("type") == "spoken" or e.get("source_quote_id") is not None
            rec = e.get("runtime_recommendation", "probable-keep")
            if not is_spoken:
                mship = "tight"
            elif rec in ("must-keep", "tight-candidate"):
                mship = "tight"
            else:
                mship = "loose"
        e["membership"] = mship
        e.pop("runtime_recommendation", None)
        out.append(e)
    return out


def resolve_handoffs_dir(slug: str, ssd_root: Path) -> Path:
    """Resolve the handoffs directory for a project, tolerating two layouts.

    Standard (multi-project) layout::
        <ssd_root>/handoffs/<slug>/tagged-quotes-v*.json

    Flat (single-project) layout — what SKILL-edit documents and what the
    Epicor ProTec project ships::
        <ssd_root>/handoffs/tagged-quotes-v*.json   (no per-slug subdir)

    Prefers the slugged subdir when it exists. Otherwise, if the bare
    ``handoffs`` dir exists AND directly contains tagged-quotes-v*.json, use it
    (the flat single-project layout). Raises SystemExit only when neither
    layout resolves, so no symlink is required for flat projects.
    """
    slugged = ssd_root / "handoffs" / slug
    if slugged.is_dir():
        return slugged
    flat = ssd_root / "handoffs"
    if flat.is_dir() and any(flat.glob("tagged-quotes-v*.json")):
        return flat
    raise SystemExit(
        f"Handoffs folder not found: {slugged} "
        f"(and no flat {flat}/tagged-quotes-v*.json fallback)"
    )


def load_project_data_from_handoffs(slug: str, ssd_root: Path,
                                     title_override: str = None,
                                     act_labels_override=None,
                                     client_override: str = None,
                                     project_override: str = None) -> dict:
    """Auto-discover project data files in the handoffs folder.

    Project metadata (title, act labels, speakers) is derived from files that
    always exist on a clean run rather than from optional pipeline-state fields
    (Bug 3): act labels + project name from act-structure-v*.md, speakers from
    the tagged-quotes pool. pipeline-state.json is consulted only as a fallback.

    Returns the assembled project data dict in the shape the new template expects.
    """
    handoffs = resolve_handoffs_dir(slug, ssd_root)

    # pipeline-state.json is a fallback source only — not required, and not
    # depended on for title/act_labels/speakers (those frequently aren't written
    # into it; see Bug 3).
    ps = {}
    ps_path = handoffs / "pipeline-state.json"
    if ps_path.exists():
        try:
            ps = json.loads(ps_path.read_text())
        except Exception as e:
            print(f"Warning: could not parse {ps_path.name}: {e}", file=sys.stderr)
    else:
        print(f"Warning: {ps_path.name} not found; deriving metadata from handoffs.",
              file=sys.stderr)
    cc = ps.get("agents", {}).get("creative-context", {})

    target_seconds = 120
    # Best-effort: look for target_runtime_seconds in any trimmed-quotes file
    # (or, pre-emit, in editing-versions working rounds). Deliberately matches
    # -tight window variants too — they carry the same target_runtime_seconds
    # and this scan is value-lookup only, not version counting.
    for f in sorted(handoffs.glob("trimmed-quotes-v*.json")) + sorted((handoffs / "editing-versions").glob("v*.json") if (handoffs / "editing-versions").is_dir() else []):
        try:
            j = json.loads(f.read_text())
            if "target_runtime_seconds" in j:
                target_seconds = j["target_runtime_seconds"]
                break
        except Exception:
            pass

    # Source quotes: tagged-quotes-v[latest].json + any embedded orphans.
    source_quotes = []
    orphans = []
    tagged_latest = latest_versioned(handoffs.glob("tagged-quotes-v*.json"))
    if tagged_latest:
        tq = json.loads(tagged_latest.read_text())
        quotes = tq if isinstance(tq, list) else tq.get("quotes", []) if isinstance(tq, dict) else []
        source_quotes = [q for q in quotes if not q.get("is_orphan")]
        orphans = [q for q in quotes if q.get("is_orphan")]

    # Orphans (Bug 4): the Synthesis/Transcript agents emit orphans as standalone
    # markdown (*-orphans-v*.md / orphan-quotes-v*.md), not inside tagged-quotes.
    # If none were embedded, parse the markdown. Last resort: a prior viewer HTML.
    if not orphans:
        next_num = (max((q.get("num", 0) for q in source_quotes), default=0)) + 1
        # Latest version of each distinct orphan-md stem.
        orphan_md = {}
        for p in list(handoffs.glob("*orphans-v*.md")) + list(handoffs.glob("orphan-quotes-v*.md")):
            stem = re.sub(r"-v\d+", "", p.stem)
            cur = orphan_md.get(stem)
            if cur is None or latest_versioned([cur, p]) == p:
                orphan_md[stem] = p
        for p in orphan_md.values():
            try:
                parsed = parse_orphans_md(p.read_text(errors="ignore"), next_num)
            except Exception as e:
                print(f"Warning: could not parse {p.name}: {e}", file=sys.stderr)
                continue
            orphans.extend(parsed)
            next_num += len(parsed)
        if orphans:
            print(f"Loaded {len(orphans)} orphan(s) from markdown (best-effort parse).",
                  file=sys.stderr)

    if not orphans:
        viewer_html = handoffs / f"{slug}_quotes_view.html"
        if viewer_html.exists():
            html = viewer_html.read_text(errors="ignore")
            m = re.search(r"window\.__VIEWER_DATA__\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
            if m:
                try:
                    d = json.loads(m.group(1))
                    if not source_quotes:
                        source_quotes = d.get("source_quotes", [])
                    orphans = d.get("orphan_quotes", []) or []
                except Exception:
                    pass

    # Mark orphans
    for o in orphans:
        o["is_orphan"] = True
    combined_quotes = list(source_quotes) + list(orphans)

    # Edit-Agent notes sidecar (M5): the Edit Agent records WHY it left a quote
    # out (agent_note, keyed by quote num → shown on not-used Library cards, the
    # silent-omissions fix) and the narrative-coherence seam-flags it found when
    # it read the cut (shown inline in Review mode). Optional; absent = empty.
    seam_flags = []
    notes_latest = latest_versioned(handoffs.glob("edit-agent-notes-v*.json"))
    if notes_latest:
        try:
            notes = json.loads(notes_latest.read_text())
        except (ValueError, OSError) as e:
            print(f"Warning: could not read {notes_latest.name}: {e}", file=sys.stderr)
            notes = {}
        by_num = notes.get("by_num", {}) if isinstance(notes, dict) else {}
        if by_num:
            for q in combined_quotes:
                # JSON object keys are strings; quote nums are ints.
                note = by_num.get(str(q.get("num"))) or by_num.get(q.get("num"))
                if note:
                    q["agent_note"] = note
        raw_flags = notes.get("seam_flags", []) if isinstance(notes, dict) else []
        if isinstance(raw_flags, list):
            seam_flags = [f for f in raw_flags if isinstance(f, dict) and f.get("before_entry_id")]

    # --- Metadata: derive from always-present files, args win (Bug 3) ---
    as_path = latest_versioned(handoffs.glob("act-structure-v*.md"))
    as_name, as_labels, as_speakers = None, [], []
    if as_path:
        as_name, as_labels, as_speakers = parse_act_structure_md(as_path.read_text(errors="ignore"))

    # project name: --title > act-structure Project > pipeline-state > slug
    project_name = (
        title_override
        or as_name
        or (ps.get("project_name") if ps.get("project_name") not in (None, "", slug) else None)
        or slug
    )
    # Header identity split (eyebrow "Client · Project" + edit name as headline).
    # No reliable upstream client field today, so: --client > a forward-compatible
    # "## Client:" line in act-structure > blank. project: --project > the derived
    # title. The template falls back to PROJECT_TITLE when both are blank.
    as_text = as_path.read_text(errors="ignore") if as_path else ""
    cm = re.search(r"^##\s*Client:\s*(.+?)\s*$", as_text, re.MULTILINE)
    client_name = (client_override or (cm.group(1).strip() if cm else "") or "").strip()
    project_label = (project_override or project_name or "").strip()
    # act labels: --act-labels > act-structure > pipeline-state.
    # NO silent ["Act 1","Act 2","Act 3"] default — a missing/empty result is a
    # hard failure in validate_project_metadata (kickoff brief P2). The old
    # default produced a blank page because real-act-tagged entries matched no
    # section.
    act_labels_full = (
        list(act_labels_override) if act_labels_override
        else as_labels or cc.get("act_labels") or []
    )
    # speakers: derived from the quote pool (slugs guaranteed to match) >
    # pipeline-state > act-structure (slugified names).
    speakers = (
        derive_speakers_from_quotes(combined_quotes)
        or cc.get("speakers")
        or as_speakers
    )

    # --- Creative context: per-act roadmaps + project premise (SPEC §3.3) ---
    # Read the act-structure "### Structure" one-liners and the creative-brief
    # premise. Defensive (SPEC §10): any missing/unparseable file or section
    # degrades to "" — never crashes.
    act_roadmaps, structure_premise = {}, ""
    if as_path:
        try:
            act_roadmaps, structure_premise = parse_act_roadmaps_md(
                as_path.read_text(errors="ignore"))
        except Exception as e:
            print(f"Roadmap parse skipped ({as_path.name}): {e}", file=sys.stderr)

    brief_premise = ""
    cb_path = latest_versioned(handoffs.glob("creative-brief-summary-v*.md"))
    if cb_path:
        try:
            brief_premise = parse_premise_md(cb_path.read_text(errors="ignore"))
        except Exception as e:
            print(f"Premise parse skipped ({cb_path.name}): {e}", file=sys.stderr)

    # premise: creative-brief central-narrative > structure Intro one-liner > "".
    premise = brief_premise or structure_premise or ""

    # acts: aligned to act_labels (Orphan excluded later in build_data_block),
    # each {label, roadmap}. Match by quoted act name == label; "" if no match.
    acts = [
        {"label": lbl, "roadmap": act_roadmaps.get(lbl, "")}
        for lbl in act_labels_full
        if lbl != "Orphan"
    ]

    # Rounds + named cuts: prefer editing-versions/, fallback to trimmed-quotes.
    # Numbered rounds are v<N>.json; NAMED deliverables (e.g. social-short.json)
    # are any other *.json. Globbing only "v*.json" both crashes on names that
    # match the glob without a v<digit> (e.g. vlog.json) AND hides named saves so
    # they never reload — so we glob *.json and classify each file.
    rounds = []

    def _round_vnum(name):
        m = re.fullmatch(r"(?:trimmed-quotes-)?v(\d+)\.json", name)
        return int(m.group(1)) if m else None

    editing_versions_dir = handoffs / "editing-versions"
    if editing_versions_dir.is_dir():
        all_ev = list(editing_versions_dir.glob("*.json"))
        numbered = sorted((p for p in all_ev if _round_vnum(p.name) is not None),
                          key=lambda p: _round_vnum(p.name))
        named = sorted((p for p in all_ev if _round_vnum(p.name) is None),
                       key=lambda p: p.name)
        round_files = numbered + named
    else:
        # Anchor on trimmed-quotes-v(\d+).json exactly: Tight-window exports
        # (trimmed-quotes-v[N]-tight.json) are window variants of an existing
        # round, NOT rounds of their own — they must never appear in the round
        # dropdown or shift version numbering (B3).
        round_files = sorted(
            (p for p in handoffs.glob("trimmed-quotes-v*.json")
             if re.fullmatch(r"trimmed-quotes-v(\d+)\.json", p.name)),
            key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))

    for f in round_files:
        try:
            j = json.loads(f.read_text())
        except Exception as e:
            print(f"Skipping {f.name}: {e}", file=sys.stderr)
            continue
        entries = j.get("entries", [])
        vnum = _round_vnum(f.name)
        if vnum is not None:
            round_num = j.get("round", vnum)
            round_label = f"Round {round_num}"
        else:
            # Named deliverable (e.g. "Social 30s") — label by its saved cut_name.
            round_num = j.get("round", 0)
            round_label = j.get("cut_name") or f.stem
        rounds.append({
            "round_number": round_num,
            "round_label": round_label,
            "version": f.stem,
            "_raw_entries": entries,
        })

    return {
        "project_name": project_name,
        "client": client_name,
        "project": project_label,
        "slug": slug,
        "ssd_root": str(ssd_root),
        "act_labels": act_labels_full,
        "speakers": speakers,
        "acts": acts,
        "premise": premise,
        "target_seconds": target_seconds,
        "source_quotes": combined_quotes,
        "rounds": rounds,
        "seam_flags": seam_flags,
    }


class BuildContractError(SystemExit):
    """Raised to fail the build LOUD on an input-contract violation (P2).

    Subclasses SystemExit so an unguarded build aborts with a non-zero exit and
    a descriptive message instead of shipping a blank viewer.
    """


def validate_project_metadata(project_meta: dict, source: str) -> None:
    """Hard-check the metadata contract before build (kickoff brief P2).

    Every historical blank-page failure was an input-contract violation that
    used to fall back silently. Fail loud here instead:

    - ``act_labels`` must be a non-empty list of non-empty strings. (The old
      ``["Act 1","Act 2","Act 3"]`` default made real-act-tagged entries match
      no section and rendered the body empty.)
    - ``speakers`` must be a non-empty list of ``{name, slug}`` objects. Plain
      strings throw at runtime in the template (it indexes ``s.slug``) and blank
      the whole page.

    `source` describes where the metadata came from, for the error message.
    """
    problems = []

    labels = project_meta.get("act_labels")
    if not isinstance(labels, list) or not labels:
        problems.append(
            "act_labels is missing or empty — expected a non-empty list of act "
            "names (e.g. derived from act-structure-v*.md, or passed via "
            "--act-labels). Refusing to fall back to generic 'Act 1/2/3', which "
            "renders a blank body when entries are tagged with the real names.")
    elif not all(isinstance(a, str) and a.strip() for a in labels):
        problems.append(
            f"act_labels must be non-empty strings; got {labels!r}.")

    speakers = project_meta.get("speakers")
    if not isinstance(speakers, list) or not speakers:
        problems.append(
            "speakers is missing or empty — expected a non-empty list of "
            "{name, slug, ...} objects (derived from the tagged-quotes pool, "
            "pipeline-state, or act-structure).")
    else:
        bad = [
            s for s in speakers
            if not (isinstance(s, dict)
                    and isinstance(s.get("name"), str) and s.get("name").strip()
                    and isinstance(s.get("slug"), str) and s.get("slug").strip())
        ]
        if bad:
            sample = bad[0]
            kind = "string" if isinstance(sample, str) else type(sample).__name__
            problems.append(
                f"speakers must be {{name, slug}} objects; {len(bad)} entr"
                f"{'y' if len(bad) == 1 else 'ies'} are not "
                f"(first offender is a {kind}: {sample!r}). Plain strings throw "
                f"at runtime (the template indexes s.slug) and blank the page.")

    if problems:
        msg = (f"\nBuild aborted — input-contract violation in {source}:\n"
               + "\n".join(f"  • {p}" for p in problems)
               + "\n\nFix the upstream data (or the fixture) and rebuild. "
                 "See the data contract in the kickoff brief / quote-viewer "
                 "roadmap.\n")
        raise BuildContractError(msg)


def assemble_data_block(data: dict) -> dict:
    """Convert auto-discovered data into the shape the template's data block expects.

    Migrates timeline entries from segment-based v5.0 shape to character-range
    shape, and assigns each entry a tight/loose membership stratum.
    """
    by_num = {q["num"]: q for q in data["source_quotes"]}
    migrated_rounds = []
    for r in data["rounds"]:
        migrated_entries = []
        for e in r["_raw_entries"]:
            if e.get("source_quote_id") is None:
                # Non-spoken entry (title card / interstitial / context beat)
                migrated_entries.append({
                    "entry_id": str(e.get("entry_id", "")),
                    "_subLabel": None,
                    "source_quote_id": None,
                    "type": e.get("type", "spoken"),
                    "part": e.get("part", ""),
                    "runtime_recommendation": e.get("runtime_recommendation", "probable-keep"),
                    "membership": e.get("membership"),
                    "_editCuts": [],
                    "notes": e.get("notes", ""),
                    "text": e.get("text", ""),
                })
                continue
            mig = migrate_entry_trims(e, by_num)
            if mig:
                migrated_entries.append(mig)
        migrated_entries = migrate_membership(migrated_entries)
        migrated_rounds.append({
            "round_number": r["round_number"],
            "round_label": r["round_label"],
            "version": r["version"],
            "timeline": migrated_entries,
        })

    project_meta = {
        "slug": data["slug"],
        "ssd_root": data["ssd_root"],
        # Header identity (option 2): eyebrow "Client · Project", edit name as the
        # headline. Both optional; the template falls back to PROJECT_TITLE.
        "client": data.get("client", ""),
        "project": data.get("project", "") or data["project_name"],
        "target_seconds": data["target_seconds"],
        # Keep only real act labels (Orphan filtered out — orphans live as flag
        # on quotes, not as an act). Preserve order.
        "act_labels": [a for a in data["act_labels"] if a != "Orphan"],
        "speakers": data["speakers"],
        # Creative context (SPEC §3.3): per-act narrative roadmaps + premise,
        # for the act-scoped "Creative context" dropdown. acts is aligned to
        # act_labels; each {label, roadmap}. Defensive defaults ([] / "").
        "acts": data.get("acts", []),
        "premise": data.get("premise", ""),
    }

    return {
        "PROJECT_TITLE": data["project_name"],
        "PROJECT_META": project_meta,
        "SOURCE_QUOTES": data["source_quotes"],
        "ROUNDS": migrated_rounds,
        "INITIAL_ROUND_INDEX": max(0, len(migrated_rounds) - 1),
        "INITIAL_FOCUS": None,
        "SEAM_FLAGS": data.get("seam_flags", []),
    }


# ============================================================================
# Template substitution + HTML wrap
# ============================================================================

def js_literal(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def substitute_data_block(template_src: str, data_block: dict) -> str:
    """Replace canonical data-block placeholders with project data."""
    # Use lambda replacements to avoid Python regex's backslash-escape interpretation
    # on JSON output containing \uXXXX sequences.
    out = template_src

    out = re.sub(
        r'^const PROJECT_TITLE = "[^"]*";',
        lambda _: f'const PROJECT_TITLE = {json.dumps(data_block["PROJECT_TITLE"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # PROJECT_META: replace the full constant block
    out = re.sub(
        r'^const PROJECT_META = \{.*?\n\};',
        lambda _: f'const PROJECT_META = {js_literal(data_block["PROJECT_META"])};',
        out,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )

    # SOURCE_QUOTES: replace empty list with real data
    out = re.sub(
        r'^const SOURCE_QUOTES = \[\];',
        lambda _: f'const SOURCE_QUOTES = {js_literal(data_block["SOURCE_QUOTES"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # ROUNDS: replace empty list
    out = re.sub(
        r'^const ROUNDS = \[\s*//[^\n]*\n\];',
        lambda _: f'const ROUNDS = {js_literal(data_block["ROUNDS"])};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # INITIAL_ROUND_INDEX
    out = re.sub(
        r'^const INITIAL_ROUND_INDEX = \d+;',
        lambda _: f'const INITIAL_ROUND_INDEX = {data_block["INITIAL_ROUND_INDEX"]};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # INITIAL_FOCUS
    focus = data_block.get("INITIAL_FOCUS")
    focus_literal = "null" if focus is None else json.dumps(focus)
    out = re.sub(
        r'^const INITIAL_FOCUS = null;',
        lambda _: f'const INITIAL_FOCUS = {focus_literal};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    # SEAM_FLAGS (M5): the Edit Agent's Review-mode coherence flags. Empty list
    # when the agent hasn't run / no notes sidecar present.
    out = re.sub(
        r'^const SEAM_FLAGS = \[\];',
        lambda _: f'const SEAM_FLAGS = {js_literal(data_block.get("SEAM_FLAGS", []))};',
        out,
        count=1,
        flags=re.MULTILINE,
    )

    return out


def strip_module_syntax(template_src: str) -> str:
    """Strip ES import and convert export default → bare function for in-browser Babel."""
    # Strip the import line
    out = re.sub(
        r'^import \{[^}]+\} from "react";\s*\n',
        "",
        template_src,
        count=1,
        flags=re.MULTILINE,
    )
    # Convert export default function → function
    out = re.sub(
        r'^export default function QuotesView\(\)',
        "function QuotesView()",
        out,
        count=1,
        flags=re.MULTILINE,
    )
    return out


VIEWER_CSS = """
:root {
  --bg: #fafaf9;
  --surface: #ffffff;
  --surface-2: #f5f5f4;
  --border: #e7e5e4;
  --border-strong: #d6d3d1;
  --text: #1c1917;
  --text-muted: #57534e;
  --text-subtle: #78716c;
  --accent: #0369a1;
  --accent-soft: #e0f2fe;
  --accent-strong: #075985;
  --must: #059669;
  --must-soft: #d1fae5;
  --tight: #0d9488;
  --tight-soft: #ccfbf1;
  --probable: #2563eb;
  --probable-soft: #dbeafe;
  --warn: #d97706;
  --warn-soft: #fef3c7;
  --danger: #dc2626;
  --danger-soft: #fee2e2;
  --highlight: #fde68a;
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.05);
  color-scheme: light;
  font: 14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); }
body { padding-bottom: 80px; }
button { font: inherit; cursor: pointer; }
kbd { background: #fff; border: 1px solid #ddd; border-radius: 3px; padding: 0 4px; font-size: 11px; }

.viewer { min-height: 100vh; }

/* === Header (two-tone: gray top, white bottom) ===
   Backgrounds are full-bleed; inner wrappers centered to align with .main. */
.hdr { position: sticky; top: 0; z-index: 50; background: var(--surface); }
.hdr-row1 {
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.hdr-row1-inner {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 20px;
  max-width: 1100px;
  margin: 0 auto;
}
.hdr-row2 {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.hdr-row2-inner {
  display: flex; flex-direction: column; gap: 8px;
  padding: 10px 20px;
  max-width: 1100px;
  margin: 0 auto;
}
/* Each filter line is a horizontal row; the Cut block (margin-left:auto)
   right-aligns on the Act line. Speaker sits on its own line beneath. */
.hdr-filter-line {
  display: flex; align-items: center; gap: 14px;
  flex-wrap: wrap;
}
.hdr-identity { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.hdr-eyebrow { font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--text-subtle); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hdr-title { font-size: 15px; font-weight: 600; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.round-select {
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 4px 26px 4px 10px; font: inherit; font-size: 12px; color: var(--text);
  height: 28px; cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2378716c' fill='none' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 8px center;
}

/* Mode toggle (tab pattern with bold accent underline + faint dividers) */
.mode-toggle { display: inline-flex; gap: 0; }
.mode-toggle button {
  background: transparent; border: 0;
  border-bottom: 3px solid transparent;
  border-radius: 0;
  padding: 8px 18px; font-size: 13px; color: var(--text-muted); font-weight: 500;
  position: relative; transition: color .15s, border-color .15s;
}
.mode-toggle button:hover { color: var(--text); }
.mode-toggle button + button::before {
  content: ""; position: absolute; left: -1px; top: 25%; bottom: 25%;
  width: 1px; background: var(--border);
}
.mode-toggle button.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 700;
}

/* Unsynced pill */
.unsynced-pill {
  background: var(--warn-soft); border: 1px solid var(--warn);
  border-radius: 999px; padding: 3px 10px;
  font-size: 11px; color: var(--warn); font-weight: 600;
  margin-left: auto; cursor: pointer;
}
.unsynced-pill:hover { background: var(--warn); color: white; }

/* Filter groups (outlined containers, no fill) */
.filter-group {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: transparent;
}
.filter-group .group-label {
  color: var(--text-subtle); margin-right: 4px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
}
.chip {
  background: transparent; border: 1px solid transparent;
  color: var(--text-muted); padding: 3px 10px;
  border-radius: 999px; font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.chip:hover { background: var(--surface-2); color: var(--text); }
.chip.active { background: var(--text); color: white; border-color: var(--text); }

/* Window block */
.win-block {
  display: inline-flex; align-items: center; gap: 10px;
  padding: 3px 4px 3px 10px;
  margin-left: auto;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: transparent;
}
.win-toggle { display: inline-flex; gap: 2px; }
.win-toggle button {
  background: transparent; border: 0;
  padding: 4px 12px; border-radius: 4px;
  font-size: 12px; color: var(--text-muted); font-weight: 500;
}
.win-toggle button:hover:not(.active) { background: var(--surface-2); }
.win-toggle button.active.tight { background: var(--must-soft); color: var(--must); }
.win-toggle button.active.loose { background: var(--probable-soft); color: var(--probable); }
.win-metric { font-size: 12px; color: var(--text); font-variant-numeric: tabular-nums; padding-left: 10px; border-left: 1px solid var(--border); }
.win-metric .val { font-weight: 600; }
.win-metric.tight .val { color: var(--must); }
.win-metric.loose .val { color: var(--probable); }
.cut-export {
  background: var(--accent); color: white; border: 1px solid var(--accent);
  border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: 500;
  margin-left: 4px;
}
.cut-export:hover { background: var(--accent-strong); border-color: var(--accent-strong); }

/* Export → FCPXML Agent handoff modal */
.export-overlay { position: fixed; inset: 0; background: rgba(28,25,23,.45); z-index: 60; display: flex; align-items: center; justify-content: center; padding: 24px; }
.export-modal { background: var(--surface); border-radius: 12px; box-shadow: 0 16px 48px rgba(0,0,0,.25); max-width: 620px; width: 100%; padding: 22px 24px; }
.export-modal h3 { margin: 0 0 4px; font-size: 16px; }
.export-sub { color: var(--text-muted); font-size: 13px; margin: 0 0 16px; }
.export-step { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 12px; }
.export-num { flex: none; width: 22px; height: 22px; border-radius: 50%; background: var(--accent-soft); color: var(--accent-strong); font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.export-step-body { font-size: 13px; line-height: 1.5; }
.export-step-body code { background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-size: 12px; }
.export-ok { font-size: 11px; font-weight: 600; color: var(--must); }
.export-warn { font-size: 12px; font-weight: 600; color: var(--danger); }
.export-promptbox { position: relative; margin: 6px 0 0; }
.export-prompt { width: 100%; min-height: 150px; font: 12px/1.5 ui-monospace, Menlo, monospace; color: var(--text); background: var(--surface-2); border: 1px solid var(--border-strong); border-radius: 8px; padding: 12px; resize: vertical; }
.export-copy { position: absolute; top: 8px; right: 8px; background: var(--accent); color: #fff; border: 0; border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 600; cursor: pointer; }
.export-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.export-win { font-weight: 700; }
.export-win.tight { color: var(--must); }
.export-win.loose { color: var(--probable); }

/* === Main pane === */
.main { padding: 20px; max-width: 1100px; margin: 0 auto; }
.act-section { margin-bottom: 32px; }
.act-header {
  display: flex; align-items: baseline; gap: 12px; padding: 8px 0; margin-bottom: 12px;
  border-bottom: 2px solid var(--border-strong);
}
.act-title { font-size: 18px; font-weight: 600; margin: 0; }
.act-sub { color: var(--text-muted); font-size: 13px; }
/* One "Add title card" button per act (option C) — replaces the old per-gap
   "+ interstitial" rows. Right-aligned in the act header. */
.act-header-actions { margin-left: auto; align-self: center; }
.act-add-btn {
  background: transparent; border: 1px solid var(--border-strong); border-radius: 6px;
  padding: 4px 11px; font: inherit; font-size: 12px; color: var(--text-muted);
  cursor: pointer; white-space: nowrap;
}
.act-add-btn:hover { color: var(--text); background: var(--surface-2); border-color: var(--text-muted); }
.act-add-btn.active { color: var(--text); background: var(--surface-2); border-color: var(--text-muted); }
.ins-add-pos {
  width: 100%; margin-bottom: 8px; padding: 5px 8px; font: inherit; font-size: 12px;
  border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text);
}

/* === Library toolbar (hide-in-cut toggle + search) === */
.lib-toolbar {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.lib-hide-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--text-muted); cursor: pointer; user-select: none;
}
.lib-hide-toggle input { cursor: pointer; }
.lib-hide-count {
  font-size: 10px; font-weight: 600; color: var(--must); background: var(--must-soft);
  border-radius: 999px; padding: 1px 8px; margin-left: 2px;
}
.lib-search {
  flex: 1; min-width: 200px; max-width: 420px; font: inherit; font-size: 13px;
  border: 1px solid var(--border-strong); border-radius: 8px; padding: 7px 12px;
  background: var(--surface); color: var(--text);
}
.lib-search:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.lib-search-meta { font-size: 11px; color: var(--text-subtle); }

/* === Library cards === */
.lib-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; margin-bottom: 10px; box-shadow: var(--shadow);
}
.lib-card.orphan { background: var(--surface-2); border-style: dashed; }
.lib-card.in-tl { border-left: 4px solid var(--must); }
.card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.qid {
  font-weight: 600; font-variant-numeric: tabular-nums; color: var(--text);
  background: var(--surface-2); padding: 2px 8px; border-radius: 4px; font-size: 13px;
}
.qid.split { background: var(--probable-soft); color: var(--probable); }
.speaker-tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 500; }
.act-tag-static {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: var(--surface-2); color: var(--text-muted);
}
.tc { color: var(--text-subtle); font-size: 11px; font-variant-numeric: tabular-nums; font-family: ui-monospace,Menlo,monospace; }
.in-tl-pill {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--must-soft); color: var(--must); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.orphan-pill {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--surface-2); color: var(--text-muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.lib-card .quote-text { color: var(--text); line-height: 1.55; margin: 8px 0 10px; }
.lib-card .rationale {
  color: var(--text-muted); font-size: 12.5px; margin-top: 8px;
  padding-top: 8px; border-top: 1px dashed var(--border);
}
.rationale-label { color: var(--text-subtle); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; margin-right: 4px; }

.lib-actions, .tl-actions {
  display: flex; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
}
.btn {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px;
  padding: 5px 11px; font-size: 12px; color: var(--text); transition: all 0.15s;
}
.btn:hover { background: var(--surface); border-color: var(--border-strong); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); border-color: var(--accent); color: white; }
.btn-primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
.btn-primary:disabled { background: var(--must-soft); color: var(--must); border-color: var(--must-soft); opacity: 1; cursor: default; }
.btn-comment {
  background: var(--probable-soft); border-color: var(--probable-soft); color: var(--probable);
}
.btn-comment:hover { background: var(--probable); border-color: var(--probable); color: white; }
.btn-danger { color: var(--danger); }
.btn-danger:hover { background: var(--danger-soft); border-color: var(--danger); color: var(--danger); }

/* === Timeline cards (v4.0.1-style) === */
.tl-card {
  display: flex; gap: 0; padding: 0; margin-bottom: 10px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  overflow: visible;
  box-shadow: var(--shadow);
  cursor: grab;
  touch-action: none;
}
.tl-card:active { cursor: grabbing; }
.tl-card.dragging { opacity: 0.45; cursor: grabbing; }
.tl-card.drag-over { box-shadow: 0 -3px 0 0 var(--accent), var(--shadow); }
/* Interactive zones inside a card keep their own cursor (buttons set pointer
   via the button rule; text editors get a text caret so they read as editable). */
.trim-text, .ins-text, .ins-add-text, .tl-card input, .tl-card textarea { cursor: text; }
.tl-card button, .tl-quote-hint, .split-marker { cursor: pointer; }
.tl-card.is-tight { border-left: 4px solid var(--must); }
.tl-card.is-loose { border-left: 4px solid var(--probable); }
.tl-card.focus-flash { animation: focusHL 1.6s ease-out; }
@keyframes focusHL {
  0% { background: var(--highlight); }
  100% { background: var(--surface); }
}
.tl-drag {
  display: flex; align-items: stretch; padding: 0 6px;
  cursor: grab; color: var(--text-subtle);
  background: var(--surface-2); border-right: 1px solid var(--border);
  user-select: none;
  border-top-left-radius: 7px; border-bottom-left-radius: 7px;
}
.tl-drag:active { cursor: grabbing; }
.tl-drag svg { margin: auto; }
.tl-body { flex: 1; padding: 14px 16px; min-width: 0; }
.tl-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.tl-move-btns { display: inline-flex; gap: 2px; }
.tl-move-btn {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px;
  padding: 2px 6px; font-size: 11px; color: var(--text-muted);
  font-family: ui-monospace, Menlo, monospace; cursor: pointer; line-height: 1;
}
.tl-move-btn:hover:not(:disabled) { background: var(--surface); color: var(--text); border-color: var(--border-strong); }
.tl-move-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.tl-scissors {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px;
  padding: 3px 6px; font-size: 12px; cursor: pointer; color: var(--text-muted);
  display: inline-flex; align-items: center; gap: 4px;
}
.tl-scissors:hover { background: var(--probable-soft); border-color: var(--probable); color: var(--probable); }

.act-tag-wrap { position: relative; display: inline-block; }
.act-tag-btn {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer;
  background: var(--surface-2); color: var(--text-muted);
  border: 1px solid transparent;
}
.act-tag-btn:hover { border-color: var(--border-strong); }
.act-tag-btn .caret { opacity: 0.5; font-size: 9px; margin-left: 2px; }
.reassign-pop {
  position: absolute; z-index: 30; margin-top: 4px; left: 0;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 6px;
  box-shadow: var(--shadow); padding: 4px; min-width: 160px;
}
.reassign-pop button {
  display: block; width: 100%; text-align: left;
  background: transparent; border: 0; padding: 6px 10px; border-radius: 4px;
  font-size: 12px; color: var(--text);
}
.reassign-pop button:hover { background: var(--surface-2); }

.mship-badge {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  padding: 3px 9px; border-radius: 4px; border: none;
}
.mship-badge.tight { background: var(--must-soft); color: var(--must); }
.mship-badge.loose { background: var(--probable-soft); color: var(--probable); }
/* Membership verb buttons: Cut → Loose (blue) · Add Back → Tight (green) · Drop → Library (red) */
.btn-cut { color: var(--probable); border-color: var(--probable-soft); background: var(--probable-soft); }
.btn-cut:hover { background: var(--probable); color: white; border-color: var(--probable); }
.btn-add { color: var(--must); border-color: var(--must-soft); background: var(--must-soft); }
.btn-add:hover { background: var(--must); color: white; border-color: var(--must); }
.btn-drop { color: var(--danger); }
.btn-drop:hover { background: var(--danger-soft); border-color: var(--danger); }
.verb-dest { font-size: 11px; font-weight: 600; opacity: 0.75; margin-left: 1px; }

/* Unified Edit page — clean read cards (default) flip to edit-in-place */
.read-card { padding: 10px 14px 14px 16px; border-bottom: 1px solid var(--border); border-left: 3px solid transparent; position: relative; }
.read-card.tight-mark { border-left-color: var(--must); }
.read-card.loose-mark { border-left-color: var(--probable); background: rgba(37,99,235,0.035); }
.rc-head { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; flex-wrap: wrap; }
.rc-quote { font-size: 15px; line-height: 1.6; margin: 2px 0 0; color: var(--text); }
.rc-quote.rc-interstitial { font-style: italic; color: var(--text-muted); }
.mship-chip { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; padding: 2px 8px; border-radius: 999px; }
.mship-chip.tight { color: var(--must); background: var(--must-soft); }
.mship-chip.loose { color: var(--probable); background: var(--probable-soft); }
.rc-tools { margin-left: auto; display: inline-flex; gap: 4px; align-items: center; }
.rc-tool { background: transparent; border: 1px solid var(--border); color: var(--text-subtle); font-size: 12px; padding: 3px 9px; border-radius: 6px; cursor: pointer; opacity: .6; transition: opacity .12s, background .12s, color .12s, border-color .12s; }
.read-card:hover .rc-tool, .read-card:focus-within .rc-tool { opacity: 1; }
.rc-tool:hover { background: var(--surface-2); color: var(--text); border-color: var(--border-strong); }
.rc-tool.edit:hover { background: var(--surface-2); color: var(--accent); border-color: var(--accent); }
.rc-collapse { margin-left: auto; background: transparent; border: 1px solid var(--border); color: var(--text-subtle); font-size: 12px; padding: 3px 9px; border-radius: 6px; cursor: pointer; }
.rc-collapse:hover { background: var(--surface-2); color: var(--text); border-color: var(--border-strong); }
.reveal-block { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border: 1px solid var(--border-strong); border-radius: 8px; margin-left: auto; }
.reveal-block .group-label { margin-right: 2px; }
.reveal-block button { background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; font-size: 12px; color: var(--text); cursor: pointer; }
.reveal-block button:hover { background: var(--surface); border-color: var(--border-strong); }

.tl-quote { color: var(--text); line-height: 1.55; font-size: 14px; margin: 6px 0 0; }
.tl-quote-cut { color: var(--danger); text-decoration: line-through; opacity: 0.65; }
.tl-quote-hint {
  font-size: 11px; color: var(--text-subtle); margin-top: 4px;
  display: inline-block; cursor: pointer; user-select: none;
}
.tl-quote-hint:hover { color: var(--text); }
.tl-notes {
  color: var(--text-muted); font-size: 12px; margin-top: 10px;
  padding-top: 8px; border-top: 1px dashed var(--border); font-style: italic;
}
.tl-notes-label { color: var(--text-subtle); font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px; font-style: normal; }

/* === Interstitial / title-card / context-beat cards === */
.tl-interstitial { border-left: 4px solid var(--warn); background: var(--warn-soft); }
.tl-interstitial .tl-drag { background: rgba(217,119,6,0.10); border-right-color: rgba(217,119,6,0.25); }
.ins-type-badge {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 8px; border-radius: 4px; background: var(--warn); color: white;
}
.ins-edit-row { display: flex; gap: 8px; align-items: flex-start; margin: 8px 0 0; }
.ins-text {
  flex: 1; min-height: 42px; resize: vertical; font: inherit; font-size: 14px; line-height: 1.5;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 6px;
  padding: 8px 10px; color: var(--text);
}
.ins-text:focus { outline: none; border-color: var(--warn); box-shadow: 0 0 0 2px var(--warn-soft); }
.ins-secs { display: inline-flex; align-items: center; gap: 2px; font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.ins-secs input {
  width: 48px; font: inherit; font-size: 13px; text-align: right;
  border: 1px solid var(--border-strong); border-radius: 4px; padding: 4px 6px; margin: 0 2px;
  background: var(--surface); color: var(--text);
}
.ins-research { font-size: 11px; color: var(--warn); font-weight: 600; margin-top: 8px; }

/* "+ interstitial" insertion slot between timeline cards */
.ins-slot { display: flex; justify-content: center; margin: -2px 0 8px; min-height: 16px; }
.ins-add-btn {
  background: transparent; border: 1px dashed var(--border-strong); border-radius: 999px;
  color: var(--text-subtle); font-size: 11px; padding: 2px 12px; opacity: 0.55; transition: all 0.15s;
}
.ins-add-btn:hover { opacity: 1; border-color: var(--warn); color: var(--warn); background: var(--warn-soft); }
.ins-add {
  width: 100%; max-width: 620px; margin: 4px auto 10px;
  background: var(--surface); border: 1px solid var(--warn); border-radius: 8px;
  padding: 12px; box-shadow: var(--shadow);
}
.ins-add-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.ins-add-type {
  flex: 1; font: inherit; font-size: 12px; padding: 5px 8px;
  border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text);
}
.ins-add-text {
  width: 100%; min-height: 56px; resize: vertical; font: inherit; font-size: 14px; line-height: 1.5;
  border: 1px solid var(--border-strong); border-radius: 6px; padding: 8px 10px; color: var(--text);
  box-sizing: border-box;
}
.ins-add-text:focus { outline: none; border-color: var(--warn); box-shadow: 0 0 0 2px var(--warn-soft); }
.ins-add-actions { display: flex; gap: 6px; margin-top: 8px; }

/* Interstitials in Review view — inline like a quote, attributed as their type
   (e.g. "— TITLE CARD") with the text italicized to set it apart from the
   verbatim spoken quotes. */
.review-interstitial-text { font-style: italic; color: var(--text-muted); }

/* Trim + split panels */
.trim-panel, .split-panel {
  margin-top: 10px; padding: 12px; background: var(--surface-2);
  border-radius: 6px; border: 1px solid var(--border);
}
.trim-hint, .split-hint { font-size: 11px; color: var(--text-subtle); margin: 0 0 8px; }
.trim-text {
  font-size: 14px; line-height: 1.55; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  user-select: text; -webkit-user-select: text; cursor: text;
}
.trim-cut { color: var(--danger); text-decoration: line-through; opacity: 0.6; }
.trim-actions, .split-actions { display: flex; gap: 6px; margin-top: 10px; }
.split-text {
  font-size: 14px; line-height: 1.85; padding: 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
}
.split-marker {
  display: inline-block; cursor: pointer; padding: 0 3px; margin: 0 1px;
  color: var(--border-strong); border-radius: 3px; user-select: none;
}
.split-marker:hover { background: var(--probable-soft); color: var(--probable); }
.split-marker.active { background: var(--probable); color: white; font-weight: 700; }
/* Words already trimmed away — shown struck so the split lands on what plays. */
.split-word-cut { text-decoration: line-through; color: var(--text-subtle); opacity: 0.55; }
.split-counter { font-size: 11px; color: var(--text-subtle); margin: 8px 0; }

/* === Review === */
.review-tabs {
  display: flex; gap: 18px; justify-content: center; flex-wrap: wrap;
  border-bottom: 1px solid var(--border); margin-bottom: 16px;
}
.review-tab {
  background: transparent; border: 0; border-bottom: 2px solid transparent;
  padding: 8px 4px; margin-bottom: -1px; font-size: 13px; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s;
}
.review-tab.active { color: var(--text); border-color: var(--text); font-weight: 500; }
.review-tab .count { color: var(--text-subtle); font-size: 11px; margin-left: 4px; }
.review-act { margin-bottom: 28px; max-width: 700px; margin-left: auto; margin-right: auto; }
.review-act h2 { font-size: 20px; margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--text); display: inline-block; }
.review-act h2 .meta { color: var(--text-muted); font-size: 12px; margin-left: 10px; font-weight: 400; }
.review-block { margin-bottom: 14px; }
.review-block .speaker {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-subtle); margin-bottom: 4px;
}
.review-text { font-size: 16px; line-height: 1.65; color: var(--text); }

/* === Empty === */
.empty {
  text-align: center; padding: 60px 20px; color: var(--text-muted);
  border: 2px dashed var(--border); border-radius: 8px; background: var(--surface);
}
.empty h3 { margin: 0 0 8px; font-size: 16px; color: var(--text); }

/* Orphan-section empty states (kickoff brief P5) — never render nothing. */
.orphans-empty {
  padding: 14px 16px; border-radius: 8px; font-size: 13px;
  color: var(--text-muted); background: var(--surface);
  border: 1px dashed var(--border);
}
.orphans-empty.warn {
  color: var(--warn); background: var(--warn-soft);
  border: 1px solid var(--warn);
}
.orphans-empty code {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: rgba(0,0,0,.06); padding: 1px 4px; border-radius: 3px;
}

/* === Send-to-agent panel === */
.send-panel {
  position: fixed; bottom: 16px; right: 16px;
  width: 380px; max-height: 70vh;
  background: var(--surface); border: 1px solid var(--border-strong);
  border-radius: 10px; box-shadow: 0 8px 30px rgba(0,0,0,.18);
  display: flex; flex-direction: column;
  overflow: hidden; z-index: 90;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.send-panel.collapsed { width: auto; }
/* When there are pending tweaks AND the panel is collapsed, emphasize the
   panel so it functions as the single "you have unsent work" indicator
   (replacing the redundant header pill). */
.send-panel.has-pending.collapsed {
  border-color: var(--warn);
  box-shadow: 0 4px 18px rgba(217, 119, 6, 0.28), 0 1px 2px rgba(0,0,0,.05);
}
.send-panel.collapsed .sp-body { display: none; }
.send-panel.collapsed .sp-foot { display: none; }
.sp-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; cursor: pointer; user-select: none;
  font-size: 13px; border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.send-panel.collapsed .sp-head { border-bottom: 0; }
.sp-title { font-weight: 600; }
.sp-count {
  background: var(--warn); color: white;
  border-radius: 999px; padding: 1px 8px;
  font-size: 11px; font-weight: 700; min-width: 22px; text-align: center;
}
.sp-count.zero { background: var(--surface-2); color: var(--text-muted); }
.sp-toggle { margin-left: auto; color: var(--text-muted); font-size: 13px; }
.sp-body { padding: 12px 14px; overflow: auto; flex: 1; min-height: 0; }
.sp-section { margin-bottom: 14px; }
.sp-section-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.sp-section-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-subtle); font-weight: 600; }
.sp-optional { color: var(--text-subtle); font-size: 10px; }
.sp-batchnote { font-size: 11px; color: var(--text-subtle); margin-left: auto; }
.sp-ops { list-style: none; padding: 0; margin: 0; font-size: 12px; }
.sp-ops li { padding: 6px 0; border-bottom: 1px solid var(--border); line-height: 1.45; color: var(--text); }
.sp-ops li:last-child { border-bottom: 0; }
.sp-ops li::before { content: "→ "; color: var(--text-subtle); }
.sp-ops li.empty { color: var(--text-subtle); font-style: italic; }
.sp-ops li.empty::before { content: ""; }
.sp-textarea {
  width: 100%; resize: vertical; min-height: 70px; max-height: 200px;
  font: inherit; font-size: 13px; line-height: 1.5;
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px; color: var(--text); margin: 0; box-sizing: border-box;
}
.sp-textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.sp-hint { font-size: 10px; color: var(--text-subtle); margin-top: 6px; }
.sp-foot {
  padding: 10px 14px; border-top: 1px solid var(--border);
  display: flex; gap: 8px; align-items: center;
}
.sp-send {
  background: var(--accent); color: white; border: 1px solid var(--accent);
  border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 500;
}
.sp-send:hover:not(:disabled) { background: var(--accent-strong); border-color: var(--accent-strong); }
.sp-send:disabled { background: var(--surface-2); color: var(--text-subtle); border-color: var(--border); cursor: not-allowed; }
.sp-status { font-size: 11px; color: var(--text-subtle); }
.sp-status.ok { color: var(--must); font-weight: 500; }
.sp-status.warn { color: var(--warn); font-weight: 500; }
.sp-version { margin-left: auto; font-family: ui-monospace, Menlo, monospace; font-size: 10px; color: var(--text-subtle); }
"""


def compile_jsx(inner_src: str, here: Path) -> str:
    """Compile JSX → plain JS at build time via Node + vendored Babel.

    Keeps the runtime artifact free of any Babel/CDN dependency.
    """
    compiler = here / "compile_jsx.js"
    if not compiler.exists():
        raise SystemExit(f"JSX compiler helper not found: {compiler}")
    try:
        proc = subprocess.run(
            ["node", str(compiler)],
            input=inner_src,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise SystemExit(
            "Node.js is required to build the viewer (compiles JSX at build "
            "time). Install Node and re-run."
        )
    if proc.returncode != 0:
        raise SystemExit(f"JSX compile failed:\n{proc.stderr}")
    return proc.stdout


def read_vendor(here: Path, name: str) -> str:
    path = here / "vendor" / name
    if not path.exists():
        raise SystemExit(
            f"Vendored runtime library missing: {path}\n"
            "Re-vendor with, e.g.:\n"
            f"  curl -sL https://unpkg.com/react@18.3.1/umd/{name} -o {path}"
        )
    return path.read_text(encoding="utf-8")


# Mount harness: an error boundary plus a try/catch around the initial render.
# Either layer paints the failure into #root with inline styles, so no thrown
# error can leave the page blank (the bug class this replaces).
MOUNT_SRC = """
const { useState, useCallback, useRef, useEffect } = React;

%(component)s

class __ViewerErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) {
    if (window.console) console.error("Quote viewer render error:", err, info);
  }
  render() {
    if (this.state.err) {
      const e = this.state.err;
      return React.createElement("div", { className: "viewer-error" },
        React.createElement("h2", null, "Quote viewer failed to render"),
        React.createElement("pre", null, String((e && e.stack) || e))
      );
    }
    return this.props.children;
  }
}

(function mountViewer() {
  const el = document.getElementById("root");
  try {
    const root = ReactDOM.createRoot(el);
    root.render(
      React.createElement(__ViewerErrorBoundary, null,
        React.createElement(QuotesView))
    );
  } catch (err) {
    if (window.console) console.error("Quote viewer mount error:", err);
    el.innerHTML = "";
    const box = document.createElement("div");
    box.className = "viewer-error";
    const h = document.createElement("h2");
    h.textContent = "Quote viewer failed to mount";
    const pre = document.createElement("pre");
    pre.textContent = String((err && err.stack) || err);
    box.appendChild(h); box.appendChild(pre);
    el.appendChild(box);
  }
})();
"""

ERROR_CSS = """
.viewer-error { max-width: 900px; margin: 40px auto; padding: 20px 24px;
  background: #fee2e2; border: 1px solid #dc2626; border-radius: 8px;
  color: #7f1d1d; font: 13px/1.5 ui-monospace, Menlo, monospace; }
.viewer-error h2 { margin: 0 0 10px; font-size: 15px; font-family: -apple-system, sans-serif; }
.viewer-error pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
"""


def wrap_html(component_src: str, project_title: str, here: Path) -> str:
    react_js = read_vendor(here, "react.production.min.js")
    react_dom_js = read_vendor(here, "react-dom.production.min.js")
    inner_jsx = MOUNT_SRC % {"component": component_src}
    compiled = compile_jsx(inner_jsx, here)
    # Escape any "</script>" that could appear inside compiled string literals
    # so it cannot prematurely close the inline <script> element.
    compiled = compiled.replace("</script>", "<\\/script>")
    title = (project_title or "Quote Viewer").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title} — Quote Viewer</title>
<style>
{VIEWER_CSS}
{ERROR_CSS}
</style>
</head>
<body>
<div id="root"></div>
<script>
{react_js}
</script>
<script>
{react_dom_js}
</script>
<script>
{compiled}
</script>
</body>
</html>
"""


# ============================================================================
# Main
# ============================================================================

def main():
    p = argparse.ArgumentParser(description="Build documentary-junior-editor quote viewer HTML.")
    p.add_argument("--slug", help="Project slug (folder name under handoffs/)")
    p.add_argument("--ssd-root", help="Project SSD root path", default=None)
    p.add_argument("--data", help="Pre-assembled project data JSON (alternative to --slug)")
    p.add_argument("--template", default=None, help="Template .jsx path")
    p.add_argument("--output", help="Output HTML path")
    p.add_argument("--title", default=None,
                   help="Override the project title (else derived from act-structure-v*.md)")
    p.add_argument("--client", default=None,
                   help="Client name for the header eyebrow (else from a '## Client:' "
                        "line in act-structure-v*.md, else blank)")
    p.add_argument("--project", default=None,
                   help="Project name for the header eyebrow (else the derived title)")
    p.add_argument("--act-labels", default=None,
                   help="Override act labels, comma-separated (else from act-structure-v*.md)")
    args = p.parse_args()

    here = Path(__file__).resolve().parent
    tpl_path = Path(args.template) if args.template else here / "quotes_viewer_template.jsx"
    if not tpl_path.exists():
        print(f"Template not found: {tpl_path}", file=sys.stderr)
        return 1

    template_src = tpl_path.read_text()

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"Data file not found: {data_path}", file=sys.stderr)
            return 1
        data_block = json.loads(data_path.read_text())
        slug = data_block.get("PROJECT_META", {}).get("slug") or "project"
        validate_project_metadata(data_block.get("PROJECT_META", {}),
                                  f"data file {data_path}")
    else:
        if not args.slug or not args.ssd_root:
            print("Provide either --data, or both --slug and --ssd-root", file=sys.stderr)
            return 1
        act_labels_override = (
            [s.strip() for s in args.act_labels.split(",") if s.strip()]
            if args.act_labels else None
        )
        raw = load_project_data_from_handoffs(
            args.slug, Path(args.ssd_root),
            title_override=args.title, act_labels_override=act_labels_override,
            client_override=args.client, project_override=args.project,
        )
        data_block = assemble_data_block(raw)
        slug = raw["slug"]
        validate_project_metadata(data_block.get("PROJECT_META", {}),
                                  f"handoffs/{slug}")

    out_path = Path(args.output) if args.output else None
    if out_path is None:
        ssd_root = data_block["PROJECT_META"].get("ssd_root") or args.ssd_root
        if not ssd_root:
            print("Cannot infer output path; provide --output", file=sys.stderr)
            return 1
        # Default the output into whichever handoffs layout the project uses, so
        # a flat single-project layout (handoffs/ holding tagged-quotes-v*.json
        # directly, no per-slug subdir) lands the html in that flat dir rather
        # than a nonexistent handoffs/<slug>/.
        out_path = resolve_handoffs_dir(slug, Path(ssd_root)) / f"{slug}_quotes_view.html"

    # Substitute data, strip module syntax, wrap
    substituted = substitute_data_block(template_src, data_block)
    component_src = strip_module_syntax(substituted)
    html = wrap_html(component_src, data_block["PROJECT_TITLE"], here)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
