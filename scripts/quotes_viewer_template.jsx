import { useState, useCallback, useRef, useEffect } from "react";

// ============================================================================
// Documentary Junior Editor — Quote Viewer Template (v5.0)
// ============================================================================
//
// React component rendered by build_quotes_viewer.py into a standalone HTML
// artifact (React 18 + Babel-standalone + inline stylesheet). The build
// script substitutes the data block at the top of this file with project data.
//
// THIS FILE has TWO sections:
//   1. DATA BLOCK — replaced per-project at build time. Do not modify the
//      shape of the constants; only update the values via the build script.
//   2. REACT COMPONENT — universal, identical across projects. Bug fixes and
//      feature changes happen here.
//
// Architecture (v5.0 + M2 view redesign):
//   - Three top-level views, in workflow order: Quote Library / Timeline / Cuts
//   - Quote Library shows every source quote + orphans (segments backend-only),
//     a per-quote status badge (In timeline / In cuts / Not used), and any
//     agent_note inline
//   - Timeline view = the working cut (entries with membership "tight"); uses
//     v4.0.1-style quote-block cards with character-range trim, scissors split,
//     drag, ↑/↓, and per-entry Cut/Add Back membership verbs
//   - Cuts view = entries cut from the Timeline (membership "loose"), as read
//     cards with Restore → Timeline / Discard actions; replaces the old
//     Tight/Loose window toggle
//   - Internal membership values stay "tight"/"loose" (data/logic + export
//     filename suffix); only the UI labels are Timeline/Cuts
//   - Round dropdown loads from baked-in rounds; "Save as new round" writes
//     directly to disk via window.cowork.callMcpTool (graceful no-op outside
//     Cowork)
//   - Send-to-agent panel: per-batch pending tweaks + a per-batch intent note;
//     Send copies the batch to chat and appends it to the cumulative tweak log
//   - "Talk to agent" sends iteratively — each Send is one batch, then the panel
//     clears for the next while the cumulative log keeps every batch
//   - Export is offered from the Timeline view: the default button writes the
//     working (tight) cut to trimmed-quotes-v[N]-tight.json; a secondary "Full
//     timeline" button writes the full cut (tight ∪ loose) to
//     trimmed-quotes-v[N].json (so the two never overwrite each other), each
//     with a ready-to-paste agent launch prompt naming that exact file
//
// ============================================================================
// DATA BLOCK — Replaced per-project by build_quotes_viewer.py at build time.
// ============================================================================

const PROJECT_TITLE = "Subject Name — Project Name";

// Project metadata (act labels, target runtime, speakers).
const PROJECT_META = {
  slug: "project-slug",
  ssd_root: "/Volumes/PROJECT_SSD",  // for callMcpTool save/export paths
  // Header identity (option 2): eyebrow "Client · Project" over the edit name.
  // Both optional; the header falls back to PROJECT_TITLE when blank.
  client: "",
  project: "",
  target_seconds: 120,
  // Order matters — drives section ordering. "Orphan" should not appear here.
  act_labels: ["Act 1", "Act 2", "Act 3"],
  // Speaker list — used by the Speaker filter chips. slug values must match
  // source_quote.speakerSlug for filtering to work.
  speakers: [
    // { name: "Speaker Name", slug: "speaker-slug", role: "patient", primary: true },
  ],
  // Creative context (SPEC §3.3) — populated by the build script from the
  // Creative Context handoffs. Drives the sub-header "Creative context" panel.
  // acts is aligned to act_labels (Orphan excluded); roadmap/premise default to "".
  acts: [
    // { label: "Act 1", roadmap: "One-line narrative roadmap for this act." },
  ],
  premise: "",
};

// Source quote pool. Every catalogued quote, including orphans. The viewer
// surfaces orphans in a dedicated section at the bottom of the Quote Library
// view (not as a filter option). Each quote retains segments[] in the JSON for
// downstream agents, but segments are not exposed in the viewer UI.
//
// Shape:
//   {
//     num: 1, originalNum: 1, speaker: "Name", speakerSlug: "slug",
//     role: "patient", quote: "Full verbatim text.",
//     startTC: "HH:MM:SS", endTC: "HH:MM:SS",
//     part: "Act 1" | "Act 2" | "Act 3" | "Orphan",
//     rationale: "Editorial note.",
//     is_orphan: false,
//     segments: [{ idx: 0, text: "...", startTC: "...", endTC: "..." }]
//   }
const SOURCE_QUOTES = [];

// Edits (v5.15) — each has its own always-saved working timeline. The Main
// edit is the default landing view; alternatives ("Save as") are listed in the
// header's edit chip. Each edit's step history (read-only snapshots the agent
// writes as the work moves act to act) is loaded live from the app server;
// the build bakes only the light manifest + the current entries as an
// offline fallback.
//
// Edit shape:
//   {
//     slug: "main", name: "Main edit", is_main: true,
//     forked_from: { edit: "main", step: 6 } | null,
//     steps: [{ seq, who: "jeff"|"claude"|"pipeline", label, created_at, entry_count, path }],
//     timeline: [
//       {
//         entry_id: "1" | "1a" | "1b" | "T1",        // sub-letters denote splits
//         source_quote_id: 1 | null,                 // null for interstitial/title-card
//         type: "spoken" | "title_card" | "interstitial" | "context_beat",
//         speaker: "Name",
//         part: "Act 1",
//         membership: "tight" | "loose",
//         _editCuts: [[startChar, endChar], ...],    // character-range trims
//         _subLabel: "a" | "b" | null,
//         notes: "Editorial note.",
//         why: "Placement rationale.",               // why selected + why HERE in the order;
//                                                    // rendered on Timeline cards as "Why here:"
//         text: "..."                                // for non-spoken entry types
//       }
//     ]
//   }
const EDITS = [
  // { slug: "main", name: "Main edit", is_main: true, forked_from: null, steps: [], timeline: [] },
];

// The edit to open on load (the Main edit). Build script sets this.
const INITIAL_EDIT_INDEX = 0;

// Step-history helpers (v5.15).
const whoName = (w) => (w === "claude" ? "Claude" : w === "jeff" ? "Jeff" : "Pipeline");
function fmtWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  const sameDay = d.toDateString() === new Date().toDateString();
  const day = sameDay ? "Today" : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${day} ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
}

// Optional focus target — viewer auto-scrolls and flashes the focused element
// on first render. Build script populates from the agent's current focus.
//   { type: "entry" | "source", id: "1" }
const INITIAL_FOCUS = null;

// Agent seam-flags (M5 / SPEC §6.6) — narrative-coherence breaks the Edit Agent
// found when it read the assembled cut. Surfaced inline in Review mode, right
// before the entry where the read breaks. Populated by the build from the Edit
// Agent's notes sidecar (edit-agent-notes-v*.json); empty when the agent hasn't
// run. Shape:
//   { before_entry_id: "e_007", kind: "orphan-pronoun",
//     message: "Opens on 'they' with no antecedent.",
//     suggestion: "Lead with Dana naming the team first." }
const SEAM_FLAGS = [];

// Build timestamp (ISO) — set by the build script. Informational: the on-disk
// edits/<edit>/current.json is always preferred over the baked entries.
const BUILD_GENERATED_AT = "";

// Dedicated tags that live in act_labels but are NOT narrative acts. They are
// held out of the three-act nav and rendered after a divider as set-apart
// filter chips (the approved structure calls Safety Lines "a dedicated tag, not
// an act"). "Orphan" is filtered separately everywhere it appears.
const NAV_TAG_LABELS = ["Safety Lines"];

// ============================================================================
// REACT COMPONENT — Universal UI. Same across all projects.
// To fix bugs or add features, update this section without touching the data
// block above.
// ============================================================================

// --- Color tokens (Tailwind-free; rendered via inline styles + class names) ---
const COLORS = {
  surface: "#ffffff",
  surface2: "#f5f5f4",
  border: "#e7e5e4",
  text: "#1c1917",
  textMuted: "#57534e",
  textSubtle: "#78716c",
};

// Membership model — every timeline entry belongs to exactly one stratum:
// "tight" (the active working cut) or "loose" (cut from Tight but not dropped).
// Library = source quotes with no active entry. Containment Library ⊇ Loose ⊇ Tight.
// membershipOf reads the explicit field; for legacy data it derives membership
// from the retired conviction tiers (must-keep / tight-candidate → tight, the
// rest → loose) and treats non-spoken structural entries as tight.
function membershipOf(entry) {
  if (entry.membership === "tight" || entry.membership === "loose") return entry.membership;
  const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
  if (!isSpoken) return "tight";
  const rec = entry.runtime_recommendation;
  return rec === "must-keep" || rec === "tight-candidate" ? "tight" : "loose";
}

// User-facing label for an internal membership value. Internal data/logic keeps
// "tight"/"loose" everywhere; the UI shows "Timeline"/"Cuts".
function membershipLabel(m) {
  return m === "tight" ? "Timeline" : "Cuts";
}

// Speaker color palette — assigned in order of appearance.
const SPEAKER_PALETTE = [
  { bg: "#fef3c7", fg: "#7c2d12" },
  { bg: "#dbeafe", fg: "#1e3a8a" },
  { bg: "#d1fae5", fg: "#065f46" },
  { bg: "#ede9fe", fg: "#5b21b6" },
  { bg: "#fce7f3", fg: "#9d174d" },
];

function buildSpeakerColors(speakers) {
  const colors = {};
  speakers.forEach((s, i) => {
    colors[s.slug] = SPEAKER_PALETTE[i % SPEAKER_PALETTE.length];
  });
  return colors;
}

// ============================================================================
// Helpers — text, time, character ranges, etc.
// ============================================================================

function tcToSeconds(tc) {
  if (!tc) return 0;
  const parts = String(tc).split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

function tcFmt(startTC, endTC) {
  if (!startTC) return "";
  const a = String(startTC).replace(/^00:/, "");
  const b = endTC ? String(endTC).replace(/^00:/, "") : "";
  return b && b !== a ? `${a}–${b}` : a;
}

function fmtSec(s) {
  if (!s || isNaN(s)) return "0s";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const r = (s - m * 60).toFixed(0).padStart(2, "0");
  return `${m}:${r}`;
}

function tokensOf(text) {
  return (text || "").match(/\S+/g) || [];
}

// ============================================================================
// Character-range cut helpers (v4.0.1 trim editor logic, ported)
// ============================================================================

function normalizeRanges(ranges) {
  if (ranges.length === 0) return [];
  const sorted = [...ranges].sort((a, b) => a[0] - b[0]);
  const merged = [sorted[0]];
  for (let i = 1; i < sorted.length; i++) {
    const last = merged[merged.length - 1];
    if (sorted[i][0] <= last[1]) {
      last[1] = Math.max(last[1], sorted[i][1]);
    } else {
      merged.push(sorted[i]);
    }
  }
  return merged;
}

function toggleRange(existing, selStart, selEnd) {
  let result = [];
  for (const [cs, ce] of existing) {
    if (ce <= selStart || cs >= selEnd) {
      result.push([cs, ce]);
    } else {
      if (cs < selStart) result.push([cs, selStart]);
      if (ce > selEnd) result.push([selEnd, ce]);
    }
  }
  let pos = selStart;
  for (const [cs, ce] of existing) {
    const overlapStart = Math.max(cs, selStart);
    const overlapEnd = Math.min(ce, selEnd);
    if (overlapStart >= overlapEnd) continue;
    if (pos < overlapStart) result.push([pos, overlapStart]);
    pos = overlapEnd;
  }
  if (pos < selEnd) result.push([pos, selEnd]);
  return normalizeRanges(result);
}

function snapToWordBounds(text, start, end) {
  while (start > 0 && text[start - 1] !== " ") start--;
  while (end < text.length && text[end] !== " ") end++;
  while (end < text.length && text[end] === " ") end++;
  if (start > 0 && end === text.length) {
    while (start > 0 && text[start - 1] === " ") start--;
  }
  return [start, end];
}

function buildRenderSegments(original, cuts) {
  if (cuts.length === 0) return [{ text: original, cut: false }];
  const segs = [];
  let pos = 0;
  for (const [s, e] of cuts) {
    if (pos < s) segs.push({ text: original.slice(pos, s), cut: false });
    segs.push({ text: original.slice(s, e), cut: true });
    pos = e;
  }
  if (pos < original.length) segs.push({ text: original.slice(pos), cut: false });
  return segs;
}

function buildKeptText(original, cuts) {
  if (cuts.length === 0) return original;
  // Collect the kept slices and join with a single space. Cuts always snap to
  // word boundaries, so two kept slices flanking a cut are whole words that must
  // stay space-separated — concatenating raw would run them together (a dropped
  // middle segment rendered "right?So data" instead of "right? So data").
  const parts = [];
  let pos = 0;
  for (const [s, e] of cuts) {
    parts.push(original.slice(pos, s));
    pos = e;
  }
  parts.push(original.slice(pos));
  return parts.map((p) => p.trim()).filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

// ============================================================================
// Source quote → derived helpers
// ============================================================================

function findSourceQuote(num) {
  return SOURCE_QUOTES.find((q) => q.num === num) || null;
}

// "Full quote" text for a timeline entry — concatenated source segments.
// This is what the character-range trim editor operates on.
function fullQuoteText(entry) {
  if (entry.type === "title_card" || entry.type === "interstitial") return entry.text || "";
  if (entry.type === "context_beat") return `[CONTEXT BEAT — ${entry.intent || "research needed"}]`;
  const src = findSourceQuote(entry.source_quote_id);
  if (!src) return `[unresolved source #${entry.source_quote_id}]`;
  return src.segments.map((s) => s.text).join(" ");
}

function trimmedQuoteText(entry) {
  const original = fullQuoteText(entry);
  const cuts = entry._editCuts || [];
  if (cuts.length === 0) return original;
  return buildKeptText(original, cuts);
}

function isTrimmed(entry) {
  return (entry._editCuts || []).length > 0;
}

// Detect mid-segment (interior) cuts — trims that remove words from the MIDDLE
// of a source segment, leaving non-contiguous kept words within that one
// segment. The FCPXML export path (segments[] + head/tail word-trims, produced
// by scripts/editcuts_to_segments.py) can only keep a single CONTIGUOUS span
// per segment, so it approximates such a cut with the widest span — first-kept
// through last-kept word — RETAINING the interior words the viewer cut. The
// exported clip therefore "plays slightly wider" at those points and must be
// tightened in Final Cut Pro (documented v5.7 limitation; epicor-rf-fager #68,
// #130). This mirrors editcuts_to_segments.editcuts_to_segments so the viewer
// warns on exactly the entries the converter will flag.
//
// `cutsOverride` lets the live trim editor pass its in-progress cuts; when
// omitted the entry's saved `_editCuts` are used. Returns an array of
// { segIdx, retained: [word, ...] }, one per affected segment — empty when the
// trim is exactly representable (or there are no cuts / no source).
function interiorCutSegments(entry, cutsOverride) {
  if (!entry || entry.type === "title_card" || entry.type === "interstitial" || entry.type === "context_beat") return [];
  const src = findSourceQuote(entry.source_quote_id);
  if (!src || !src.segments) return [];
  const cuts = cutsOverride || entry._editCuts || [];
  if (cuts.length === 0) return [];

  // full text = segment texts joined with a SINGLE space (matches
  // fullQuoteText and build_quotes_viewer.migrate_entry_trims exactly, so the
  // char coordinates in _editCuts line up).
  const full = src.segments.map((s) => s.text || "").join(" ");
  const kept = keptRangesOf(cuts, full.length);
  const overlapsKept = (a, b) => kept.some(([ks, ke]) => Math.max(ks, a) < Math.min(ke, b));

  const affected = [];
  let pos = 0;
  src.segments.forEach((seg, si) => {
    const text = seg.text || "";
    const segStart = pos;
    pos += text.length + 1; // + the single-space separator between segments

    const words = [];
    const re = /\S+/g;
    let m;
    while ((m = re.exec(text)) !== null) {
      words.push({ w: m[0], s: segStart + m.index, e: segStart + m.index + m[0].length });
    }
    if (words.length === 0) return;

    const keptFlags = words.map((wd) => overlapsKept(wd.s, wd.e));
    const keptIdx = [];
    keptFlags.forEach((k, i) => { if (k) keptIdx.push(i); });
    if (keptIdx.length === 0) return; // segment fully cut → dropped, not an interior cut

    const first = keptIdx[0];
    const last = keptIdx[keptIdx.length - 1];
    const retained = [];
    for (let i = first + 1; i < last; i++) {
      if (!keptFlags[i]) retained.push(words[i].w); // fully-cut word between two kept words
    }
    if (retained.length > 0) {
      affected.push({ segIdx: seg.idx != null ? seg.idx : si, retained });
    }
  });
  return affected;
}

// Fidelity notice for a mid-segment (interior) cut — see interiorCutSegments.
// `compact` renders a small inline badge (for the collapsed timeline card);
// otherwise a full explanatory notice (trim editor + revealed card).
function InteriorCutNotice({ affected, compact }) {
  if (!affected || affected.length === 0) return null;
  const title = "Interior cut — the FCPXML export plays slightly wider here; tighten the in/out in Final Cut Pro.";
  if (compact) {
    return <span className="interior-cut-badge" title={title}>⚠ interior cut</span>;
  }
  const words = affected.reduce((a, x) => a.concat(x.retained), []);
  const preview = words.slice(0, 6).join(" ");
  return (
    <div className="interior-cut-notice">
      <div className="interior-cut-head">
        <span className="interior-cut-glyph" aria-hidden="true">⚠</span>
        <span className="interior-cut-kind">Interior cut</span>
      </div>
      <div className="interior-cut-msg">
        This trim removes words from the <strong>middle</strong> of a segment.
        The FCPXML export can only keep one continuous span per segment, so it
        approximates — the clip will <strong>play slightly wider</strong> here
        {words.length > 0 && <> (it retains “{preview}{words.length > 6 ? "…" : ""}”)</>}.
        Tighten the in/out in Final Cut Pro.
      </div>
    </div>
  );
}

// Kept ranges = the complement of `cuts` over [0, len] (the spans that play).
function keptRangesOf(cuts, len) {
  const sorted = (cuts || []).map((r) => [r[0], r[1]]).sort((a, b) => a[0] - b[0]);
  const kept = [];
  let pos = 0;
  for (const [s, e] of sorted) {
    if (s > pos) kept.push([pos, Math.min(s, len)]);
    pos = Math.max(pos, e);
  }
  if (pos < len) kept.push([pos, len]);
  return kept;
}

// Clip ranges to [a, b], dropping anything outside.
function clipRanges(ranges, a, b) {
  const out = [];
  for (const [s, e] of ranges) {
    const ns = Math.max(s, a), ne = Math.min(e, b);
    if (ne > ns) out.push([ns, ne]);
  }
  return out;
}

// Estimated runtime in seconds — proportional to kept tokens.
function entrySeconds(entry) {
  if (entry.type === "title_card" || entry.type === "interstitial" || entry.type === "context_beat") {
    return entry.estimated_seconds || 0;
  }
  const src = findSourceQuote(entry.source_quote_id);
  if (!src) return 0;
  const totalSec = src.segments.reduce(
    (a, s) => a + Math.max(0, tcToSeconds(s.endTC) - tcToSeconds(s.startTC)),
    0
  );
  const totalTokens = src.segments.reduce((a, s) => a + tokensOf(s.text).length, 0) || 1;
  const keptTokens = tokensOf(trimmedQuoteText(entry)).length;
  return totalSec * (keptTokens / totalTokens);
}

function entryActOf(entry) {
  return entry.part || findSourceQuote(entry.source_quote_id)?.part || "—";
}

// ============================================================================
// callMcpTool helpers — direct write to disk for Save/Export, with graceful
// no-op fallback when the viewer is opened outside Cowork.
// ============================================================================

function hasCallMcpTool() {
  return typeof window !== "undefined" &&
    window.cowork &&
    typeof window.cowork.callMcpTool === "function";
}

async function callBash(command) {
  if (!hasCallMcpTool()) {
    return { ok: false, reason: "Not running in Cowork — callMcpTool unavailable" };
  }
  try {
    const result = await window.cowork.callMcpTool("mcp__workspace__bash", { command });
    return { ok: true, result };
  } catch (e) {
    return { ok: false, reason: String(e) };
  }
}

// ============================================================================
// persistFile — robust browser-first persistence (kickoff brief P1).
//
// Tries three tiers, most-robust first, and reports which one wrote:
//   1. "cowork"   — window.cowork.callMcpTool bash (inside Cowork)
//   2. "helper"   — the local save-server (scripts/viewer_save_server.py) on
//                   localhost; writes the file to the correct path silently
//   3. "download" — plain browser download (never-lose-data fallback)
//
// `relPath` is project-root-relative (e.g.
// "handoffs/slug/editing-versions/v3.json"); the helper + download tiers use
// it, while the Cowork tier prefixes PROJECT_META.ssd_root for the abs path.
// Pass { allowDownload:false } for best-effort writes (e.g. the tweak log)
// that should NOT spam a download on every call when no writer is available.
// ============================================================================

// When the page is served over http (the app server), talk to the server that
// served it — this keeps sibling pages at /view/<slug> and test sandboxes on
// other ports saving to their own server, never to a hardcoded port. file://
// opens fall back to the configured/default helper.
const SAVE_HELPER_URL =
  (typeof window !== "undefined" && /^https?:$/.test(window.location.protocol)
    ? window.location.origin
    : null) ||
  (typeof PROJECT_META !== "undefined" && PROJECT_META.save_helper_url) ||
  "http://127.0.0.1:8765";

async function saveViaHelper(relPath, content) {
  if (typeof fetch !== "function") return { ok: false, reason: "no fetch" };
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 1500);
    const res = await fetch(SAVE_HELPER_URL + "/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: relPath, content }),
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    if (!res.ok) return { ok: false, reason: "helper HTTP " + res.status };
    const data = await res.json();
    return { ok: !!data.ok, path: data.path, reason: data.error };
  } catch (e) {
    // Helper not running / unreachable → caller falls through to download.
    return { ok: false, reason: String(e) };
  }
}

function downloadFile(content, downloadName) {
  try {
    const blob = new Blob([content], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    a.click();
    URL.revokeObjectURL(url);
    return true;
  } catch (_) {
    return false;
  }
}

async function persistFile(relPath, content, opts) {
  const allowDownload = !opts || opts.allowDownload !== false;
  const downloadName = (opts && opts.downloadName) || relPath.split("/").pop();

  // Tier 1: Cowork.
  if (hasCallMcpTool()) {
    const absPath = `${PROJECT_META.ssd_root}/${relPath}`;
    const dir = absPath.slice(0, absPath.lastIndexOf("/"));
    const cmd = `mkdir -p "${dir}" && cat > "${absPath}" <<'__PERSIST_EOF__'\n${content}\n__PERSIST_EOF__`;
    const { ok, reason } = await callBash(cmd);
    if (ok) return { ok: true, method: "cowork", detail: absPath };
    // fall through to helper/download if the Cowork write failed
    var coworkReason = reason;
  }

  // Tier 2: local helper.
  const helper = await saveViaHelper(relPath, content);
  if (helper.ok) return { ok: true, method: "helper", detail: helper.path };

  // Tier 3: download.
  if (allowDownload && downloadFile(content, downloadName)) {
    return { ok: true, method: "download", detail: downloadName };
  }

  return {
    ok: false,
    method: "fail",
    detail: helper.reason || coworkReason || "no writer available",
  };
}

// ============================================================================
// EditPanel — character-range trim editor (selection + Delete key)
// ============================================================================

function EditPanel({ entry, editCuts, setEditCuts, onSave, onCancel }) {
  const textRef = useRef(null);
  const original = fullQuoteText(entry);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !textRef.current) return;
      if (!textRef.current.contains(sel.anchorNode) || !textRef.current.contains(sel.focusNode)) return;
      e.preventDefault();

      const container = textRef.current;
      let charOffset = 0;
      let selStart = null;
      let selEnd = null;
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const len = node.textContent.length;
        if (node === sel.anchorNode) {
          const off = charOffset + sel.anchorOffset;
          if (selStart === null) selStart = off;
          else selEnd = off;
        }
        if (node === sel.focusNode) {
          const off = charOffset + sel.focusOffset;
          if (selStart === null) selStart = off;
          else selEnd = off;
        }
        charOffset += len;
      }
      if (selStart === null || selEnd === null) return;
      if (selStart > selEnd) { const tmp = selStart; selStart = selEnd; selEnd = tmp; }
      if (selStart === selEnd) return;

      [selStart, selEnd] = snapToWordBounds(original, selStart, selEnd);
      setEditCuts((prev) => toggleRange(prev, selStart, selEnd));
      sel.removeAllRanges();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [original, setEditCuts]);

  const segments = buildRenderSegments(original, editCuts);

  return (
    <div className="trim-panel" onClick={(e) => e.stopPropagation()}>
      <p className="trim-hint">
        Select text, then press <kbd>Delete</kbd> to cut or restore it. Cuts snap to word boundaries.
      </p>
      <div ref={textRef} className="trim-text">
        {segments.map((seg, i) => (
          <span key={i} className={seg.cut ? "trim-cut" : ""}>
            {seg.text}
          </span>
        ))}
      </div>
      <InteriorCutNotice affected={interiorCutSegments(entry, editCuts)} />
      <div className="trim-actions">
        <button className="btn btn-primary" onClick={onSave}>Save trim</button>
        <button className="btn" onClick={onCancel}>Cancel</button>
        {editCuts.length > 0 && (
          <button className="btn btn-danger" onClick={() => setEditCuts([])}>
            Reset cuts
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// SplitPanel — word-boundary marker placement for entry split (v4.0.1 port)
// ============================================================================

function SplitPanel({ entry, markers, setMarkers, onSplit, onCancel }) {
  const original = fullQuoteText(entry);
  // Words already trimmed away show struck-through here, so a split is placed
  // against what actually plays — not text that was cut.
  const cuts = entry._editCuts || [];
  const isCut = (start, end) => cuts.some(([s, e]) => s <= start && end <= e);
  const words = [];
  const re = /(\S+)(\s*)/g;
  let m;
  while ((m = re.exec(original)) !== null) {
    words.push({ word: m[1], boundaryAfter: m.index + m[0].length, cut: isCut(m.index, m.index + m[1].length) });
  }
  const sorted = [...markers].sort((a, b) => a - b);

  const toggleMarker = (pos) => {
    setMarkers((prev) =>
      prev.includes(pos) ? prev.filter((x) => x !== pos) : [...prev, pos].sort((a, b) => a - b)
    );
  };

  return (
    <div className="split-panel" onClick={(e) => e.stopPropagation()}>
      <p className="split-hint">
        Click between words to place split markers. Click a marker again to remove it.
      </p>
      <div className="split-text">
        {words.map((w, i) => {
          const active = sorted.includes(w.boundaryAfter);
          return (
            <span key={i}>
              <span className={w.cut ? "split-word-cut" : undefined}>{w.word}</span>
              {i < words.length - 1 && (
                <>
                  <span
                    onClick={() => toggleMarker(w.boundaryAfter)}
                    className={`split-marker${active ? " active" : ""}`}
                    title={active ? "Remove split here" : "Add split here"}
                  >
                    {active ? "✂" : "|"}
                  </span>
                  {!active && " "}
                </>
              )}
            </span>
          );
        })}
      </div>
      {sorted.length > 0 && (
        <div className="split-counter">
          Will create <strong>{sorted.length + 1}</strong> sub-quotes
          {entry.source_quote_id && (
            <>
              {" "}(#{entry.source_quote_id}a, #{entry.source_quote_id}b
              {sorted.length > 1 && <>, #{entry.source_quote_id}c</>}
              {sorted.length > 2 && <>…</>})
            </>
          )}
        </div>
      )}
      <div className="split-actions">
        <button className="btn btn-primary" onClick={onSplit} disabled={sorted.length === 0}>
          Split into {sorted.length + 1} sub-quotes
        </button>
        <button className="btn" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

// Stopwords stripped from a Library search so a natural-language question
// ("What did they say about usability or customer support?") reduces to its
// meaningful terms (usability, customer, support) instead of matching nothing.
const SEARCH_STOPWORDS = new Set([
  "a", "an", "and", "or", "the", "of", "to", "in", "on", "for", "at", "by",
  "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
  "i", "we", "you", "they", "he", "she", "it", "them", "us", "my", "our",
  "your", "their", "this", "that", "these", "those", "with", "about", "as",
  "so", "if", "then", "than", "what", "when", "where", "why", "how", "who",
  "say", "said", "says", "tell", "talk", "talked", "mention", "mentioned",
  "me", "him", "her", "his", "its", "from", "into", "any", "some", "there",
]);

// ============================================================================
// Main component — QuotesView
// ============================================================================

export default function QuotesView() {
  // === Round + view state ===
  const [roundIndex, setRoundIndex] = useState(INITIAL_EDIT_INDEX);  // index into `cuts` (the edits)
  // Three top-level views, in workflow order: Quote Library → Timeline → Cuts.
  //   library  — every source quote, grouped by act + orphans, with a status badge.
  //   timeline — the working cut: entries where membershipOf(e) === "tight".
  //   cuts     — entries where membershipOf(e) === "loose" (cut from the Timeline).
  // This replaces the former two-view (timeline/library) switch AND the old
  // Tight/Loose window toggle — the Timeline vs Cuts views now do that job.
  // Internal membership values stay "tight"/"loose"; only the labels changed.
  const [view, setView] = useState("timeline");
  // Timeline sub-mode (M3 T2 §A): "edit" = the working cards (trim/split/cut/
  // drag) — the existing surface, unchanged; "review" = a clean serif read of
  // the cut as it plays (kept post-trim text only, grouped by act, no controls,
  // trimmed text hidden). Default Edit. Only meaningful in the Timeline view;
  // Library/Cuts ignore it.
  const [timelineMode, setTimelineMode] = useState("edit");
  const [revealedIds, setRevealedIds] = useState(() => new Set());
  // entry_id of a just-added title card, so its text field autofocuses on open.
  const [justAddedId, setJustAddedId] = useState(null);
  const [speakerFilter, setSpeakerFilter] = useState("all");
  const [actFilter, setActFilter] = useState("all");
  // Quote Library: "Hide quotes already in the current cut" — persisted per project.
  const [hideInCut, setHideInCut] = useState(() => {
    try { return localStorage.getItem("odv-hideInCut-" + PROJECT_META.slug) === "1"; }
    catch (_) { return false; }
  });
  function toggleHideInCut() {
    setHideInCut((v) => {
      const next = !v;
      try { localStorage.setItem("odv-hideInCut-" + PROJECT_META.slug, next ? "1" : "0"); } catch (_) {}
      return next;
    });
  }
  // Quote Library text search — transient (not persisted); matches verbatim
  // quote text + rationale, case-insensitive, composed after speaker/act filters.
  const [librarySearch, setLibrarySearch] = useState("");
  // Quote Library act re-tagging. Overrides a source quote's act in the viewer's
  // working state; logged as a `reassign_source_act` tweak so the Edit Agent
  // persists it canonically to the source pool. The viewer never overwrites the
  // upstream tagged-quotes file directly. Timeline entries keep their own `part`.
  const [sourceActOverrides, setSourceActOverrides] = useState({});
  const [reassigningQuoteNum, setReassigningQuoteNum] = useState(null);
  const quoteActOf = (q) => sourceActOverrides[q.num] || q.part;
  function reassignSourceAct(q, newAct) {
    const prevAct = quoteActOf(q);
    setSourceActOverrides((prev) => ({ ...prev, [q.num]: newAct }));
    applyLocalEdit("reassign_source_act",
      () => {},  // no timeline mutation — source-pool re-tag only
      `Re-tagged source #${q.num} (${q.speaker}) act: ${prevAct} → ${newAct}`,
      { change_type: "reassign_source_act", entry_id: String(q.num), before: { part: prevAct }, after: { part: newAct } }
    );
    setReassigningQuoteNum(null);
  }

  // === Edits (live) ===
  // `cuts` is the list of EDITS (v5.15): the ones baked at build time, kept
  // live by refreshEdits() polling the app server's /edits — new edits created
  // in another tab or by the agent, fresh step manifests, and agent writes to
  // the open edit's current.json. Indexed by `roundIndex` (internal name kept
  // from the rounds era; it is simply the open edit's index).
  const [cuts, setCuts] = useState(EDITS);
  const cutsRef = useRef(cuts);
  useEffect(() => { cutsRef.current = cuts; }, [cuts]);

  // === Per-edit working timeline (deep-clone of the baked fallback; replaced
  // by the on-disk current.json the moment the app server answers) ===
  const [workingByRound, setWorkingByRound] = useState(() => {
    const init = {};
    EDITS.forEach((r, i) => {
      init[i] = JSON.parse(JSON.stringify(r.timeline || []));
    });
    return init;
  });
  const [pendingOpsByRound, setPendingOpsByRound] = useState(() => {
    const init = {};
    EDITS.forEach((_, i) => { init[i] = []; });
    return init;
  });

  const getTimeline = () => workingByRound[roundIndex] || [];
  const getPendingOps = () => pendingOpsByRound[roundIndex] || [];

  // ====== Edits + steps, live from the app server (v5.15) ======
  // /edits?slug= returns every edit with its step manifest and the current
  // state's stamp. Polled every 4s: new edits appear in the chip, History
  // stays fresh, and a current.json the AGENT wrote (its proposal beat) is
  // adopted into the open edit — no rebuild, no reload, no banner to dismiss
  // before you can work. The baked page is only the offline fallback.
  const editPathOf = (cut) => `handoffs/${PROJECT_META.slug}/edits/${(cut && cut.slug) || "main"}`;
  const lastLocalWriteAt = useRef(0);        // ms of our last successful current.json write
  const lastAdoptedAgentWrite = useRef("");  // generated_at of the last agent write adopted
  const [agentUpdate, setAgentUpdate] = useState(null);  // { label, at } — toast after adopting
  const viewingStepRef = useRef(null);
  const roundIndexRef = useRef(roundIndex);
  useEffect(() => { roundIndexRef.current = roundIndex; }, [roundIndex]);

  function shapeEdit(d) {
    return {
      slug: d.slug, name: d.name || d.slug, is_main: !!d.is_main,
      forked_from: d.forked_from || null, created_at: d.created_at || null,
      steps: Array.isArray(d.steps) ? d.steps : [],
      current_generated_at: (d.current && d.current.generated_at) || null,
      current_written_by: (d.current && d.current.written_by) || null,
    };
  }
  function mergeEdits(prev, disk) {
    const bySlug = new Map(prev.map((c, i) => [c.slug, i]));
    const next = prev.slice();
    disk.forEach((d) => {
      const shaped = shapeEdit(d);
      if (bySlug.has(d.slug)) next[bySlug.get(d.slug)] = { ...next[bySlug.get(d.slug)], ...shaped };
      else next.push({ ...shaped, timeline: [] });
    });
    return next;
  }

  async function readJson(rel) {
    const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent(rel)}`);
    if (!res.ok) return null;
    const j = await res.json();
    return (j && j.ok) ? j.data : null;
  }

  // Load an edit's on-disk current.json into its working slot. Returns the
  // state adopted, or null. `st` may be passed when already fetched.
  async function adoptCurrent(idx, st) {
    const cut = cutsRef.current[idx];
    if (!cut) return null;
    if (!st) st = await readJson(`${editPathOf(cut)}/current.json`);
    if (!st || !Array.isArray(st.entries)) return null;
    setWorkingByRound((prev) => ({ ...prev, [idx]: JSON.parse(JSON.stringify(st.entries)) }));
    if (st.source_act_overrides && typeof st.source_act_overrides === "object") {
      setSourceActOverrides(st.source_act_overrides);
    }
    if (Array.isArray(st.pending_ops)) {
      setPendingOpsByRound((prev) => ({ ...prev, [idx]: st.pending_ops }));
    }
    return st;
  }

  async function refreshEdits() {
    if (typeof fetch !== "function") return;
    let data;
    try {
      const res = await fetch(`${SAVE_HELPER_URL}/edits?slug=${encodeURIComponent(PROJECT_META.slug)}`);
      if (!res.ok) return;
      data = await res.json();
    } catch (_) { return; /* server down — the baked list stands */ }
    if (!data || !data.ok || !Array.isArray(data.edits)) return;
    setCuts((prev) => mergeEdits(prev, data.edits));
    // An AGENT write to the open edit's current.json → adopt it (never while
    // viewing history, never when we wrote after the agent did).
    const idx = roundIndexRef.current;
    const open = cutsRef.current[idx];
    const d = open && data.edits.find((e) => e.slug === open.slug);
    const cur = d && d.current;
    if (!cur || cur.written_by !== "agent" || !cur.generated_at) return;
    if (viewingStepRef.current) return;
    if (cur.generated_at === lastAdoptedAgentWrite.current) return;
    if ((Date.parse(cur.generated_at) || 0) <= lastLocalWriteAt.current) return;
    lastAdoptedAgentWrite.current = cur.generated_at;
    let st = null;
    try { st = await readJson(cur.path || `${editPathOf(open)}/current.json`); } catch (_) { return; }
    if (!st || st.written_by !== "agent") return;
    if (await adoptCurrent(idx, st)) {
      const stepRec = st.agent_step && (d.steps || []).find((x) => x.stem === st.agent_step);
      const label = (stepRec && stepRec.label)
        || (st.agent_step ? String(st.agent_step).replace(/^\d+-[a-z]+-/, "").replace(/-/g, " ") : "a new proposal");
      setAgentUpdate({ label, at: Date.now() });
    }
  }

  // On mount: the on-disk current.json of the open edit is the truth (it may
  // have moved on in another tab or under the agent since this page was
  // baked); the baked timeline is only the fallback. Then keep polling.
  const initialLoadDone = useRef(false);
  useEffect(() => {
    (async () => {
      try {
        const st = await adoptCurrent(INITIAL_EDIT_INDEX);
        if (st && st.written_by === "agent" && st.generated_at) {
          lastAdoptedAgentWrite.current = st.generated_at;  // no toast for what was already there
        }
      } catch (_) { /* file:// open or server down — the baked build stands */ }
      initialLoadDone.current = true;
      refreshEdits();
    })();
    const id = setInterval(refreshEdits, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, []);

  // The agent-update toast fades on its own.
  useEffect(() => {
    if (!agentUpdate) return;
    const t = setTimeout(() => setAgentUpdate(null), 12000);
    return () => clearTimeout(t);
  }, [agentUpdate]);
  // Per-round Talk-to-agent batch counter. Each op is tagged with the batch it
  // was made in; Send advances the counter so the panel clears for the next
  // batch while the cumulative log keeps every batch.
  const [batchByRound, setBatchByRound] = useState(() => {
    const init = {}; EDITS.forEach((_, i) => { init[i] = 1; }); return init;
  });

  // applyLocalEdit records a structured op alongside the human-readable
  // description. `meta` carries the fields the Editing Coach Agent reads from
  // the persisted tweak log: entry_id, change_type, before/after state, and an
  // optional free-text note. change_type defaults to opTag when not supplied.
  const applyLocalEdit = useCallback((opTag, mutator, description, meta) => {
    setWorkingByRound((prev) => {
      const tl = JSON.parse(JSON.stringify(prev[roundIndex] || []));
      mutator(tl);
      return { ...prev, [roundIndex]: tl };
    });
    // Staleness (M5): stamp this cut's last-edit time. The cue compares it
    // against the agent's last read (agent-cursor.json) — no manual Send.
    setLastEditAtByRound((m) => ({ ...m, [roundIndex]: Date.now() }));
    setPendingOpsByRound((prev) => {
      const list = prev[roundIndex] || [];
      const op = {
        seq: list.length + 1,
        batch: batchByRound[roundIndex] || 1,
        op: opTag,
        description,
        change_type: (meta && meta.change_type) || opTag,
        entry_id: (meta && meta.entry_id) ?? null,
        before: (meta && meta.before) ?? null,
        after: (meta && meta.after) ?? null,
        note: (meta && meta.note) ?? null,
        ts: Date.now(),
        timestamp: new Date().toISOString(),
      };
      return { ...prev, [roundIndex]: [...list, op] };
    });
  }, [roundIndex, batchByRound]);

  // Within-act position of an entry — used to record reorder before/after.
  function actLocalIndex(tl, entryId) {
    const e = tl.find((x) => x.entry_id === entryId);
    if (!e) return -1;
    const act = entryActOf(e);
    return tl.filter((x) => entryActOf(x) === act).findIndex((x) => x.entry_id === entryId);
  }

  // === Edit / split / reassign UI state ===
  const [editingEntryId, setEditingEntryId] = useState(null);
  const [editCuts, setEditCuts] = useState([]);
  const [splittingEntryId, setSplittingEntryId] = useState(null);
  const [splitMarkers, setSplitMarkers] = useState([]);
  const [reassigningEntryId, setReassigningEntryId] = useState(null);

  // === Live-partner agent panel state (M5 redesign) ===
  // The old clipboard "Send batch" model is gone. The agent reads the viewer's
  // live state from disk (edits/<edit>/current.json) on its turn; Jeff just edits and
  // talks in chat. This panel is a STATUS surface, not a send surface.
  const [sendPanelOpen, setSendPanelOpen] = useState(false);
  // The note Jeff is composing for the agent right now ("tell me now" — it rides
  // in edits/<edit>/current.json and is consumed when the agent next reads). NOT a queue.
  const [batchNote, setBatchNote] = useState("");
  // Quotes Jeff tagged with "Point at this" — { entry_id, label }. Staged as
  // chips in the composer; they ride the next Send and clear immediately.
  const [pointedAt, setPointedAt] = useState([]);
  // === Ongoing chat (project-chat.json) ===
  // The durable two-way thread. Send appends {id, who, text, ts, pointed_at}
  // to handoffs/<slug>/project-chat.json (merge-by-id, matching the hosted
  // viewer's contract); the agent appends who:"agent" replies. Polled like
  // agent-cursor.json so replies appear without a reload.
  const [chatLog, setChatLog] = useState([]);
  const [chatSending, setChatSending] = useState(false);
  // Mirror of the LAST SENT message — edits/<edit>/current.json's pending_message keeps
  // advertising Jeff's latest note (the skill contract) even though the
  // composer clears on Send. The full thread is the chat log.
  const [lastSent, setLastSent] = useState(null);
  const chatEndRef = useRef(null);

  // Staleness, honest edition (M5). Instead of a flag cleared by a manual Send,
  // we compare the time of Jeff's last edit (per cut) against the time the Edit
  // Agent last acknowledged reading the viewer (agent-cursor.json, polled from
  // disk). Three states: not-connected (agent never looked) / caught-up / behind.
  const [lastEditAtByRound, setLastEditAtByRound] = useState({});
  const [agentCursor, setAgentCursor] = useState(null);  // { read_at, message? } | null
  const lastEditMs = lastEditAtByRound[roundIndex] || 0;
  const cursorReadMs = (agentCursor && agentCursor.read_at) ? Date.parse(agentCursor.read_at) || 0 : 0;
  const agentConnected = !!agentCursor;
  // "behind" = Jeff has edited since the agent last read. Drives the amber cue.
  const agentBehind = lastEditMs > 0 && lastEditMs > cursorReadMs;
  // Back-compat alias used across the build sites + buildLiveState.
  const dirtySinceSend = agentBehind;
  // Export → FCPXML Agent handoff modal. null when closed; otherwise carries the
  // written-file info + the ready-to-paste agent prompt.
  const [exportInfo, setExportInfo] = useState(null);
  const [exportCopied, setExportCopied] = useState(false);
  // The export the viewer has queued for the Edit Agent (it launches the FCPXML
  // Agent itself — no copy-paste, no new session). Surfaced in edits/<edit>/current.json
  // and written to export-request.json; the agent owns its lifecycle.
  const [pendingExport, setPendingExport] = useState(null);

  // === Top-bar menus (v5.15): edit chip (open) · History · Save as · Export ===
  // Each header button toggles a small inline panel; only one is open at a
  // time. The edit chip lists the project's edits and opens one. History lists
  // the open edit's steps (View / rename; Restore lives in the viewing
  // banner). Save as forks the current state into a new named edit. Export
  // consolidates the two FCPXML export flows (Timeline → -tight file, Full
  // timeline → non-suffixed).
  const [topMenu, setTopMenu] = useState(null);   // "save" | "open" | "history" | "export" | null
  const [newEditName, setNewEditName] = useState("");  // typed name for "Save as"
  const [saveStatus, setSaveStatus] = useState({ text: "", cls: "" });

  // === Live autosave / persistence status (M4 — persistent app shell) ===
  // The viewer is no longer a throwaway chat artifact: it runs as a persistent
  // local app and shares its working state with the Edit Agent through a single
  // file on disk, handoffs/<slug>/edits/<edit>/current.json, autosaved
  // (debounced) on every edit. SKILL-edit reads that file at the top of each of its turns to
  // see the current cut — no copy-paste, no PDF-print. `persistState` drives the
  // top-bar indicator: "saved" (written to disk via the app server / Cowork),
  // "saving", "offline" (no writer reachable — the app server isn't running), or
  // "error". It is the honest signal that disk-sharing with the agent is live.
  const [persistState, setPersistState] = useState({ state: "idle", at: null, detail: "" });
  const autosaveTimer = useRef(null);
  const autosaveSeq = useRef(0);

  // Sub-header "Creative context" inline panel (M3 §5). Act-scoped: a single
  // act shows only PROJECT_META.acts[that].roadmap; All shows premise + every
  // act's roadmap. Sourced from the Creative Context agent.
  const [creativeOpen, setCreativeOpen] = useState(false);

  // Creative context as a persistent SIDE PANEL (Jeff, 2026-08-21): the
  // roadmaps are edit-against targets, and a popup forces memorize-close-edit.
  // Pinned state survives reloads via localStorage; on narrow windows the
  // panel hides (CSS) and the popup remains the fallback.
  const [ccPinned, setCcPinned] = useState(() => {
    try { return localStorage.getItem("cc-pinned") === "1"; } catch (_) { return false; }
  });
  function toggleCcPinned() {
    setCcPinned((v) => {
      const nv = !v;
      try { localStorage.setItem("cc-pinned", nv ? "1" : "0"); } catch (_) { /* private mode */ }
      return nv;
    });
  }

  // Speaker-context ("who's who") panel — mirrors creativeOpen. Speaker-scoped:
  // All shows every voice's summary; one speaker selected shows just theirs.
  const [speakerCtxOpen, setSpeakerCtxOpen] = useState(false);

  // === Display names (client / project / edit) — handoffs/project-names.json ===
  // The header's hierarchy (Client · Project / Edit) is renamable in place; the
  // names live in ONE file shared by every edit on the SSD, edited only through
  // this UI. Baked values from the build are the fallback; the live file wins so
  // a rename made on any sibling page shows up here on next load.
  const [names, setNames] = useState({
    client: PROJECT_META.client || "",
    project: PROJECT_META.project || "",
    edit: PROJECT_META.edit_display || PROJECT_META.slug,
  });
  const [siblingLabels, setSiblingLabels] = useState({});
  const [namesEditing, setNamesEditing] = useState(false);
  const [namesDraft, setNamesDraft] = useState({ client: "", project: "" });
  const [editRenaming, setEditRenaming] = useState(false);
  const [editNameDraft, setEditNameDraft] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent("handoffs/project-names.json")}`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data || !data.ok || !data.data) return;
        const f = data.data;
        setNames((prev) => ({
          client: f.client || prev.client,
          project: f.project || prev.project,
          edit: (f.edits && f.edits[PROJECT_META.slug]) || prev.edit,
        }));
        if (f.edits) setSiblingLabels(f.edits);
      } catch (_) { /* no server / no file yet — baked names stand */ }
    })();
  }, []);

  // Merge-write the names file: read the latest copy first so a rename on this
  // page never clobbers a sibling's display name written from another tab.
  async function writeNamesFile(patch) {
    let current = {};
    try {
      const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent("handoffs/project-names.json")}`);
      if (res.ok) { const d = await res.json(); if (d && d.ok && d.data) current = d.data; }
    } catch (_) {}
    const merged = {
      client: patch.client !== undefined ? patch.client : (current.client || names.client),
      project: patch.project !== undefined ? patch.project : (current.project || names.project),
      edits: { ...(current.edits || {}) },
    };
    if (patch.edit !== undefined) merged.edits[PROJECT_META.slug] = patch.edit;
    const { ok } = await persistFile("handoffs/project-names.json",
      JSON.stringify(merged, null, 2), { allowDownload: false });
    if (ok && merged.edits) setSiblingLabels(merged.edits);
    return ok;
  }

  async function commitNames() {
    const client = namesDraft.client.trim();
    const project = namesDraft.project.trim();
    setNames((p) => ({ ...p, client, project }));
    setNamesEditing(false);
    await writeNamesFile({ client, project });
  }

  async function commitEditRename() {
    const name = editNameDraft.trim();
    if (!name) { setEditRenaming(false); return; }
    setNames((p) => ({ ...p, edit: name }));
    setEditRenaming(false);
    setTopMenu(null);
    await writeNamesFile({ edit: name });
  }

  // === Drag-to-reorder state (pointer-events based) ===
  // Native HTML5 drag-and-drop is unreliable inside Cowork's sandboxed artifact
  // iframe. Pointer events + setPointerCapture work in every context and are
  // synthetically testable. The WHOLE card is a drag source (not just the
  // left-edge grip) — grabbing the quote is what Jeff reaches for — except over
  // buttons and the trim/text editors, which keep their normal behavior. A small
  // move threshold distinguishes a drag from a click, and text selection is
  // suppressed during a drag. Reorder is constrained to within an act (cross-act
  // moves use the act-reassign dropdown); ↑/↓ buttons remain as a fallback.
  const [dragId, setDragId] = useState(null);
  const [dragOverId, setDragOverId] = useState(null);
  const dragIdRef = useRef(null);
  const dragOverRef = useRef(null);
  const dragStartRef = useRef(null);  // { x, y, active } between pointerdown and threshold

  function clearPointerDrag() {
    dragIdRef.current = null;
    dragOverRef.current = null;
    dragStartRef.current = null;
    try { document.body.style.userSelect = ""; } catch (_) {}
    setDragId(null);
    setDragOverId(null);
  }

  // True when a pointerdown landed on something that should keep its own
  // behavior (buttons, the trim editor's selectable text, inputs, popups) —
  // those must not start a card drag.
  function isInteractiveDragTarget(el) {
    return !!(el && el.closest && el.closest(
      "button, input, textarea, select, a, [contenteditable], " +
      ".reassign-pop, .trim-panel, .split-panel, .tl-quote-hint, .ins-secs"
    ));
  }

  // Pointer-drag handler props shared by spoken and interstitial cards.
  function cardDragHandlers(entry) {
    return {
      onPointerDown: (e) => {
        if (e.button !== 0) return;                 // left button only
        if (isInteractiveDragTarget(e.target)) return;
        dragIdRef.current = entry.entry_id;
        dragOverRef.current = entry.entry_id;
        dragStartRef.current = { x: e.clientX, y: e.clientY, active: false };
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}
      },
      onPointerMove: (e) => {
        if (!dragIdRef.current) return;
        const st = dragStartRef.current;
        if (st && !st.active) {
          if (Math.abs(e.clientX - st.x) + Math.abs(e.clientY - st.y) < 5) return;
          st.active = true;                          // crossed the drag threshold
          try { document.body.style.userSelect = "none"; } catch (_) {}
          try { const s = window.getSelection(); s && s.removeAllRanges(); } catch (_) {}
          setDragId(entry.entry_id);
        }
        const el = document.elementFromPoint(e.clientX, e.clientY);
        // Collapsed cards (.read-card) are drop targets too, not just expanded
        // .tl-card — so drag-reorder works in the default Edit view.
        const card = el && el.closest ? el.closest(".tl-card, .read-card") : null;
        if (!card || !card.id) return;
        const tl = getTimeline();
        const de = tl.find((x) => x.entry_id === dragIdRef.current);
        const oe = tl.find((x) => x.entry_id === card.id);
        if (!de || !oe || entryActOf(de) !== entryActOf(oe)) return;
        if (card.id !== dragOverRef.current) {
          dragOverRef.current = card.id;
          setDragOverId(card.id);
        }
      },
      onPointerUp: (e) => {
        try { e.currentTarget.releasePointerCapture(e.pointerId); } catch (_) {}
        const wasActive = dragStartRef.current && dragStartRef.current.active;
        if (wasActive) finishPointerDrag(); else clearPointerDrag();
      },
      onPointerCancel: clearPointerDrag,
    };
  }

  function finishPointerDrag() {
    const draggedId = dragIdRef.current;
    const overId = dragOverRef.current;
    if (draggedId && overId && draggedId !== overId) {
      const tlNow = getTimeline();
      const act = entryActOf(tlNow.find((x) => x.entry_id === draggedId) || {});
      const fromActIdx = actLocalIndex(tlNow, draggedId);
      const toActIdx = actLocalIndex(tlNow, overId);
      applyLocalEdit("reorder",
        (tl) => {
          const fromIdx = tl.findIndex((x) => x.entry_id === draggedId);
          const toIdx = tl.findIndex((x) => x.entry_id === overId);
          if (fromIdx < 0 || toIdx < 0) return;
          if (entryActOf(tl[fromIdx]) !== entryActOf(tl[toIdx])) return;
          const [m] = tl.splice(fromIdx, 1);
          const newToIdx = tl.findIndex((x) => x.entry_id === overId);
          tl.splice(newToIdx, 0, m);
        },
        `Reordered: moved ${draggedId} to ${overId}'s position`,
        {
          change_type: "reorder",
          entry_id: draggedId,
          before: { act, act_index: fromActIdx },
          after: { act, act_index: toActIdx, over: overId },
        }
      );
    }
    clearPointerDrag();
  }

  // === Speaker color memo ===
  const speakerColors = buildSpeakerColors(PROJECT_META.speakers || []);

  // ====== Save as — fork an alternative edit (v5.15) ======
  // The current working state becomes a NEW edit with its own history; the
  // edit you branched from is untouched. Writes edit.json + step 001 +
  // current.json through the app server, then switches to the new edit.
  function slugifyName(name) {
    return (name || "")
      .trim()
      .toLowerCase()
      .replace(/['"]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
  const nowIso = () => new Date().toISOString();

  async function saveAsNewEdit() {
    const name = newEditName.trim();
    const slug = slugifyName(name);
    if (!slug) { setSaveStatus({ text: "Type a name for the new edit first.", cls: "warn" }); return; }
    if (slug === "main" || cuts.some((c) => c.slug === slug)) {
      setSaveStatus({ text: `An edit named “${name}” already exists — pick another name.`, cls: "warn" });
      return;
    }
    const from = cuts[roundIndex];
    const fromStep = from && from.steps && from.steps.length ? from.steps[from.steps.length - 1].seq : null;
    const entries = getTimeline();
    const base = `handoffs/${PROJECT_META.slug}/edits/${slug}`;
    setSaveStatus({ text: "Creating…", cls: "" });
    const meta = {
      schema_version: 1, kind: "edit", project_slug: PROJECT_META.slug, slug, name, is_main: false,
      created_at: nowIso(), forked_from: from ? { edit: from.slug, step: fromStep } : null,
    };
    const stepLabel = from ? `forked from ${from.name}${fromStep ? ` step ${fromStep}` : ""}` : "created";
    const step = {
      schema_version: 1, kind: "edit-step", project_slug: PROJECT_META.slug, edit: slug, seq: 1, who: "jeff",
      label: stepLabel, note: null, created_at: nowIso(), target_runtime_seconds: PROJECT_META.target_seconds,
      entry_count: entries.length, entries,
    };
    const stepPath = `${base}/steps/001-jeff-${slugifyName(stepLabel).slice(0, 60)}.json`;
    const current = { ...buildLiveState(), edit: slug, edit_name: name, entries, generated_at: nowIso(), written_by: "viewer" };
    const w1 = await persistFile(`${base}/edit.json`, JSON.stringify(meta, null, 2), { allowDownload: false });
    const w2 = w1.ok && await persistFile(stepPath, JSON.stringify(step, null, 2), { allowDownload: false });
    const w3 = w2 && w2.ok && await persistFile(`${base}/current.json`, JSON.stringify(current, null, 2), { allowDownload: false });
    if (!(w3 && w3.ok)) {
      setSaveStatus({ text: `Couldn't create the edit: ${(w1 && !w1.ok && w1.detail) || "is the app server running?"}`, cls: "err" });
      return;
    }
    const newCut = {
      slug, name, is_main: false, forked_from: meta.forked_from, created_at: meta.created_at,
      steps: [{ seq: 1, who: "jeff", label: stepLabel, created_at: step.created_at, entry_count: entries.length, path: stepPath }],
      timeline: [],
    };
    const nextIndex = cuts.length;
    setCuts((prev) => [...prev, newCut]);
    setWorkingByRound((prev) => ({ ...prev, [nextIndex]: JSON.parse(JSON.stringify(entries)) }));
    setPendingOpsByRound((prev) => ({ ...prev, [nextIndex]: [] }));
    setNewEditName("");
    setSaveStatus({ text: "", cls: "" });
    setRoundIndex(nextIndex);
    setTopMenu(null);
  }

  // ====== History — view / restore / rename a step (v5.15) ======
  // Viewing is read-only: the step's entries replace the Timeline while the
  // live working state is stashed; autosave and agent adoption pause. Back
  // restores the stash. Restore copies the step forward as a NEW step on the
  // open edit (history is never rewritten) and makes it the working state.
  const [viewingStep, setViewingStep] = useState(null);  // { seq, who, label, created_at, path }
  const stashRef = useRef(null);
  useEffect(() => { viewingStepRef.current = viewingStep; }, [viewingStep]);

  async function viewStep(step) {
    if (viewingStep && viewingStep.path === step.path) { setTopMenu(null); return; }
    let j = null;
    try { j = await readJson(step.path); } catch (_) { /* handled below */ }
    if (!j || !Array.isArray(j.entries)) {
      setSaveStatus({ text: `Couldn't load step ${step.seq} — is the app server running?`, cls: "err" });
      return;
    }
    if (!viewingStep) stashRef.current = { idx: roundIndex, entries: JSON.parse(JSON.stringify(getTimeline())) };
    setWorkingByRound((prev) => ({ ...prev, [roundIndex]: JSON.parse(JSON.stringify(j.entries)) }));
    setViewingStep({ ...step, label: j.label || step.label });
    setTopMenu(null);
  }
  function backToNow() {
    const stash = stashRef.current;
    if (stash) setWorkingByRound((prev) => ({ ...prev, [stash.idx]: stash.entries }));
    stashRef.current = null;
    setViewingStep(null);
  }
  async function restoreStep() {
    if (!viewingStep) return;
    const cut = cuts[roundIndex];
    const entries = getTimeline();  // = the viewed step's entries
    const seq = (cut.steps || []).reduce((m, s) => Math.max(m, s.seq || 0), 0) + 1;
    const label = `restored step ${viewingStep.seq} (${viewingStep.label})`;
    const step = {
      schema_version: 1, kind: "edit-step", project_slug: PROJECT_META.slug, edit: cut.slug, seq, who: "jeff",
      label, note: null, created_at: nowIso(), target_runtime_seconds: PROJECT_META.target_seconds,
      entry_count: entries.length, entries,
    };
    const stepPath = `${editPathOf(cut)}/steps/${String(seq).padStart(3, "0")}-jeff-${slugifyName(label).slice(0, 60)}.json`;
    const w = await persistFile(stepPath, JSON.stringify(step, null, 2), { allowDownload: false });
    if (!w.ok) { setSaveStatus({ text: `Couldn't write the restore step: ${w.detail}`, cls: "err" }); return; }
    setCuts((prev) => prev.map((c, i) => i === roundIndex
      ? { ...c, steps: [...(c.steps || []), { seq, who: "jeff", label, created_at: step.created_at, entry_count: entries.length, path: stepPath }] }
      : c));
    stashRef.current = null;
    setViewingStep(null);  // autosave resumes → current.json = the restored entries
    setLastEditAtByRound((m) => ({ ...m, [roundIndex]: Date.now() }));
  }
  async function renameStep(step) {
    const label = window.prompt("Rename this step", step.label);
    if (label == null || !label.trim() || label.trim() === step.label) return;
    let j = null;
    try { j = await readJson(step.path); } catch (_) { /* handled below */ }
    if (!j) { setSaveStatus({ text: "Couldn't load the step to rename it.", cls: "err" }); return; }
    j.label = label.trim();
    const w = await persistFile(step.path, JSON.stringify(j, null, 2), { allowDownload: false });
    if (w.ok) {
      setCuts((prev) => prev.map((c, i) => i === roundIndex
        ? { ...c, steps: (c.steps || []).map((s) => (s.path === step.path ? { ...s, label: j.label } : s)) }
        : c));
    }
  }

  // Switch to another edit (edit chip). Exits history viewing first. The
  // edit's on-disk current.json is loaded on every open — it may have moved on
  // in another tab or under the agent; the baked timeline is the fallback.
  async function openCut(nextIndex) {
    if (nextIndex === roundIndex) { setTopMenu(null); return; }
    if (viewingStep) backToNow();
    const cut = cuts[nextIndex];
    if (!cut) return;
    setSaveStatus({ text: `Opening “${cut.name}”…`, cls: "" });
    let adopted = null;
    try { adopted = await adoptCurrent(nextIndex); } catch (_) { /* fallback below */ }
    if (!adopted && !workingByRound[nextIndex]) {
      setWorkingByRound((prev) => ({ ...prev, [nextIndex]: JSON.parse(JSON.stringify(cut.timeline || [])) }));
    }
    setPendingOpsByRound((prev) => ({ ...prev, [nextIndex]: prev[nextIndex] || [] }));
    setSaveStatus({ text: "", cls: "" });
    setRoundIndex(nextIndex);
    setTopMenu(null);
  }

  // ====== Live autosave → edits/<edit>/current.json (v5.15) ======

  // The single agent-readable snapshot of the open edit's working state. Flat
  // and self-describing so SKILL-edit can read the whole cut, what is in/out,
  // what Jeff just changed, and where his attention is — from ONE file, on
  // each of its turns. Membership lives on each entry (tight = Timeline,
  // loose = Cuts); not-used Library quotes are SOURCE_QUOTES with no entry, so
  // the agent reconstructs the Library from its baked-in pool plus
  // `source_act_overrides` (Jeff's Library recategorizations).
  function buildLiveState() {
    const cut = cuts[roundIndex];
    const tl = getTimeline();
    const ops = getPendingOps();
    return {
      schema_version: 1,
      kind: "edit-current",
      project_slug: PROJECT_META.slug,
      project_title: PROJECT_TITLE,
      edit: cut ? cut.slug : "main",
      edit_name: cut ? cut.name : "Main edit",
      generated_at: new Date().toISOString(),
      written_by: "viewer",
      target_runtime_seconds: PROJECT_META.target_seconds,
      focus: { view, mode: timelineMode, act: actFilter, speaker: speakerFilter },
      // Honest staleness for the agent: has Jeff edited since you last read?
      agent_behind: agentBehind,
      agent_last_read: agentCursor ? agentCursor.read_at : null,
      dirty_since_send: dirtySinceSend,
      counts: {
        timeline: tl.filter((e) => membershipOf(e) === "tight").length,
        cuts: tl.filter((e) => membershipOf(e) === "loose").length,
        pending_ops: ops.length,
      },
      // Jeff's LATEST SENT message (the composer clears on Send; the full
      // thread lives in the chat log below). Kept as pending_message so the
      // agent's read contract is unchanged: this mirrors only the newest note.
      pending_message: lastSent,
      // The durable two-way conversation — read every who:"jeff" message newer
      // than your last reply, not just the pending_message mirror.
      chat_log: `handoffs/${PROJECT_META.slug}/project-chat.json`,
      // A Final Cut export Jeff queued — the agent launches the FCPXML Agent for
      // it (authority is export-request.json; this mirrors it for visibility).
      pending_export: pendingExport,
      // Library recategorizations Jeff made since this build (entry-less retags).
      source_act_overrides: sourceActOverrides,
      // Uncommitted tweaks since his last Send — the live correction signal.
      pending_ops: ops.map((o) => ({
        seq: o.seq, batch: o.batch, entry_id: o.entry_id,
        change_type: o.change_type, description: o.description,
      })),
      // The full working timeline (all tiers), canonical order.
      entries: tl,
    };
  }

  // Debounced write of the live state on every meaningful change. Best-effort
  // and download-suppressed (never spams the browser): if no writer is reachable
  // the indicator simply shows "offline". The autosaveSeq guard drops a stale
  // in-flight write if a newer change already superseded it. Paused while a
  // past step is being viewed (read-only) and until the initial on-disk state
  // has been consulted, so a stale bake can never overwrite live work.
  useEffect(() => {
    if (viewingStep) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(async () => {
      if (!initialLoadDone.current) return;
      const seq = ++autosaveSeq.current;
      setPersistState((p) => ({ ...p, state: "saving" }));
      const relPath = `${editPathOf(cuts[roundIndex])}/current.json`;
      const json = JSON.stringify(buildLiveState(), null, 2);
      const res = await persistFile(relPath, json, { allowDownload: false });
      if (seq !== autosaveSeq.current) return;  // a newer write is already queued
      if (res.ok && (res.method === "cowork" || res.method === "helper")) {
        lastLocalWriteAt.current = Date.now();
        setPersistState({ state: "saved", at: Date.now(), detail: res.detail || relPath });
      } else {
        setPersistState({ state: "offline", at: Date.now(), detail: res.detail || "app server not running" });
      }
      // The tweak log (the Editing Coach's training record) rides the autosave
      // so every correction + Jeff's live note still reach disk. Best-effort.
      writeTweakLog();
    }, 700);
    return () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workingByRound, pendingOpsByRound, roundIndex, view, timelineMode, actFilter, speakerFilter, lastSent, dirtySinceSend, sourceActOverrides, pendingExport, viewingStep]);

  // Offline self-heal (v5.13): the indicator latches "offline" when a save
  // fires while the app server is down (it restarts between agent sessions),
  // and nothing re-tries until the next edit. While offline, ping every 15s
  // and re-run the autosave the moment the server is back.
  useEffect(() => {
    if (persistState.state !== "offline") return;
    const t = setInterval(async () => {
      if (viewingStepRef.current) return;
      try {
        const res = await fetch(SAVE_HELPER_URL + "/ping");
        if (!res.ok) return;
        const relPath = `${editPathOf(cutsRef.current[roundIndexRef.current])}/current.json`;
        const json = JSON.stringify(buildLiveState(), null, 2);
        const r = await persistFile(relPath, json, { allowDownload: false });
        if (r.ok) {
          lastLocalWriteAt.current = Date.now();
          setPersistState({ state: "saved", at: Date.now(), detail: r.detail || relPath });
        }
      } catch (_) { /* still down — keep waiting */ }
    }, 15000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persistState.state]);

  // ====== Export ======

  // Hand the selected window's cut to the FCPXML Agent. Writes
  // trimmed-quotes-v[N].json for the Loose (full-timeline) window and
  // trimmed-quotes-v[N]-tight.json for the Tight window — distinct files so the
  // two exports of the same round never overwrite each other (B3). Version
  // detection downstream anchors on trimmed-quotes-v(\d+).json, so -tight files
  // never count as rounds. Also hands a ready-to-paste FCPXML Agent launch
  // prompt — the viewer does NOT build the XML itself (failure-prone without
  // the agent around it). In Cowork the file is written to disk; in a plain
  // browser it degrades to a download. The prompt copy always works.
  // Export is offered from the Timeline view. By default it exports the working
  // cut (tight entries only) to trimmed-quotes-v[N]-tight.json. Passing
  // `full = true` exports the full timeline (tight ∪ loose) to the non-suffixed
  // trimmed-quotes-v[N].json. The window toggle is gone, so the choice is driven
  // by which export button the user clicks rather than windowMode. Internal
  // `win` values stay "tight"/"loose" so the filename suffix and the downstream
  // window detection are unchanged.
  async function exportToFCPXML(full) {
    const tl = getTimeline();
    const win = full ? "loose" : "tight";
    const label = win === "tight" ? "Timeline" : "Full timeline";
    const filtered = win === "tight" ? tl.filter((e) => membershipOf(e) === "tight") : tl;
    const totalSec = filtered.reduce((a, e) => a + entrySeconds(e), 0);
    const cut = cuts[roundIndex] || { slug: "main", name: "Main edit", steps: [] };
    const stepCount = (cut.steps || []).length || 1;
    // Per-edit export files: trimmed-quotes-<edit>[-tight].json. Never matches
    // the legacy trimmed-quotes-v(\d+) round pattern, so nothing downstream
    // mistakes an export for a round.
    const filename = `trimmed-quotes-${cut.slug}${win === "tight" ? "-tight" : ""}.json`;
    const relPath = `handoffs/${PROJECT_META.slug}/${filename}`;
    // Stamp mid-segment (interior) cuts onto the export so the FCPXML
    // handoff/verify can list the affected entries automatically instead of the
    // Edit Agent listing them by hand. Non-mutating: affected entries get a
    // shallow copy carrying `_fidelity`; the underlying _editCuts are untouched,
    // so scripts/editcuts_to_segments.py still converts (and re-derives the same
    // notes) exactly as before. See interiorCutSegments / session B2.
    const exportEntries = filtered.map((e) => {
      const affected = interiorCutSegments(e);
      if (affected.length === 0) return e;
      return {
        ...e,
        _fidelity: {
          interior_cut: true,
          segments: affected.map((a) => ({ segment_idx: a.segIdx, retained_words: a.retained })),
        },
      };
    });
    const fidelityWarnings = exportEntries
      .filter((e) => e._fidelity && e._fidelity.interior_cut)
      .map((e) => ({
        entry_id: e.entry_id,
        source_quote_id: e.source_quote_id,
        segments: e._fidelity.segments,
      }));
    const payload = {
      schema_version: 5,
      round: stepCount,
      edit: cut.slug,
      edit_name: cut.name,
      project_slug: PROJECT_META.slug,
      window: win,
      target_runtime_seconds: PROJECT_META.target_seconds,
      entries: exportEntries,
      fidelity_warnings: fidelityWarnings,
    };
    const json = JSON.stringify(payload, null, 2);
    const outFcpxml = `XML/imports/${PROJECT_META.slug}_${cut.slug}_${win}_cut.fcpxml`;
    const res = await persistFile(relPath, json, { downloadName: filename });
    const wrote = res.method === "download" ? "download"
      : res.ok ? "disk" : "fail";
    let queued = false;
    if (res.ok && res.method !== "download") {
      await writeTweakLog();  // best-effort: persist the override log alongside the cut
      // Queue the export for the Edit Agent. It reads export-request.json on its
      // turn and launches the FCPXML Agent itself (Task tool + SKILL-fcpxml) —
      // no copy-paste, no new session. The agent owns the status lifecycle
      // (requested → built), so it never rebuilds an already-built request.
      const request = {
        schema_version: 1,
        kind: "export-request",
        requested_at: new Date().toISOString(),
        status: "requested",
        window: win,
        label,
        round: stepCount,
        edit: cut.slug,
        cut_name: cut.name,
        cut_file: relPath,
        out_fcpxml: outFcpxml,
        entry_count: filtered.length,
        // Interior/mid-segment cuts the FCPXML can only approximate (session
        // B2). The Edit Agent surfaces these on handoff/verify; the exported
        // cut_file carries the per-entry detail in `fidelity_warnings`.
        fidelity_warning_count: fidelityWarnings.length,
      };
      const rres = await persistFile(`handoffs/${PROJECT_META.slug}/export-request.json`,
        JSON.stringify(request, null, 2), { allowDownload: false });
      queued = !!(rres && rres.ok);
      if (queued) setPendingExport(request);
    }
    setExportInfo({ win, label, count: filtered.length, time: fmtSec(totalSec), file: relPath, filename, outFcpxml, wrote, queued, fidelity: fidelityWarnings.length });
  }

  // ====== Move + reorder helpers ======

  function canMoveEntry(entry) {
    const tl = getTimeline();
    const i = tl.findIndex((x) => x.entry_id === entry.entry_id);
    if (i < 0) return { up: false, down: false };
    const my = entryActOf(entry);
    let up = false;
    let down = false;
    for (let k = i - 1; k >= 0; k--) { if (entryActOf(tl[k]) === my) { up = true; break; } }
    for (let k = i + 1; k < tl.length; k++) { if (entryActOf(tl[k]) === my) { down = true; break; } }
    return { up, down };
  }

  function moveEntry(entryId, dir) {
    const tl = getTimeline();
    const found = tl.find((x) => x.entry_id === entryId);
    if (!found) return;
    const actName = entryActOf(found);
    const fromActIdx = actLocalIndex(tl, entryId);
    applyLocalEdit("move_" + (dir < 0 ? "up" : "down"),
      (tlMut) => {
        const i = tlMut.findIndex((x) => x.entry_id === entryId);
        if (i < 0) return;
        const my = entryActOf(tlMut[i]);
        let target = -1;
        if (dir === -1) {
          for (let k = i - 1; k >= 0; k--) { if (entryActOf(tlMut[k]) === my) { target = k; break; } }
        } else {
          for (let k = i + 1; k < tlMut.length; k++) { if (entryActOf(tlMut[k]) === my) { target = k; break; } }
        }
        if (target < 0) return;
        const [m] = tlMut.splice(i, 1);
        tlMut.splice(target, 0, m);
      },
      `Moved ${entryId} ${dir < 0 ? "up" : "down"} within ${actName}`,
      {
        change_type: "reorder",
        entry_id: entryId,
        before: { act: actName, act_index: fromActIdx },
        after: { act: actName, act_index: fromActIdx + dir },
      }
    );
  }

  // ====== Sub-quote ID assignment for splits ======

  function executeSplit(entry) {
    const original = fullQuoteText(entry);
    const sorted = [...splitMarkers].sort((a, b) => a - b);
    if (sorted.length === 0) return;
    const boundaries = [0, ...sorted, original.length];
    const letters = "abcdefghijklmnopqrstuvwxyz";
    // Preserve any trims already applied: the kept set of the source entry is the
    // complement of its _editCuts. Each sub-quote keeps only the portion of THAT
    // kept set inside its split span — so a split never resurrects trimmed text.
    const keptRanges = keptRangesOf(entry._editCuts || [], original.length);
    const subEntries = [];
    for (let i = 0; i < boundaries.length - 1; i++) {
      const keepStart = boundaries[i];
      const keepEnd = boundaries[i + 1];
      // What still plays in this span = (already-kept) ∩ [keepStart, keepEnd].
      const subKept = clipRanges(keptRanges, keepStart, keepEnd);
      if (subKept.length === 0) continue;  // wholly-trimmed span → no sub-quote
      const sub = letters[subEntries.length];
      const newId = `${entry.source_quote_id}${sub}`;
      // Cuts = complement of the surviving kept ranges (covers both the split
      // boundaries AND the original trims). Verbatim text is untouched.
      const subCuts = keptRangesOf(subKept, original.length);
      subEntries.push({
        ...entry,
        entry_id: newId,
        _subLabel: sub,
        _editCuts: subCuts,
        notes: (entry.notes ? entry.notes + " " : "") + `(split ${sub})`,
      });
    }
    applyLocalEdit("split_entry",
      (tl) => {
        const idx = tl.findIndex((x) => x.entry_id === entry.entry_id);
        if (idx < 0) return;
        tl.splice(idx, 1, ...subEntries);
      },
      `Split ${entry.entry_id} into ${subEntries.length} sub-quotes (#${entry.source_quote_id}a..)`,
      {
        change_type: "split",
        entry_id: entry.entry_id,
        before: { entry_id: entry.entry_id, source_quote_id: entry.source_quote_id },
        after: { sub_ids: subEntries.map((s) => s.entry_id) },
      }
    );
    setSplittingEntryId(null);
    setSplitMarkers([]);
  }

  // ====== Rejoin (M3 T2 §D) — inverse of executeSplit ======

  // Split siblings share a source_quote_id and each carry a _subLabel ("a"/"b"/…)
  // plus an _editCuts span that partitions the same original source text. Rejoin
  // merges the siblings back into ONE entry: the kept (post-trim) verbatim text
  // of each part, concatenated in source order, restored under a single entry
  // with entry_id = the source number and _subLabel cleared. The parts are
  // removed. It is the exact inverse of executeSplit.
  // True when an entry is a split part that still has a sibling part in the cut
  // (so Rejoin is meaningful — at least two parts to merge).
  function hasRejoinSibling(entry) {
    if (entry.source_quote_id == null || !entry._subLabel) return false;
    return getTimeline().filter(
      (e) => e.source_quote_id === entry.source_quote_id && e._subLabel
    ).length >= 2;
  }

  function rejoinSiblings(entry) {
    const srcId = entry.source_quote_id;
    if (srcId == null || !entry._subLabel) return;
    const tlNow = getTimeline();
    // Siblings = every split part of the same source quote currently in the cut.
    const siblings = tlNow.filter(
      (e) => e.source_quote_id === srcId && e._subLabel
    );
    if (siblings.length < 2) return;
    // Order by _subLabel ("a" < "b" < …) so kept text concatenates in source order.
    const ordered = [...siblings].sort((a, b) =>
      String(a._subLabel).localeCompare(String(b._subLabel))
    );
    const original = fullQuoteText(ordered[0]);
    const len = original.length;
    // Per-part kept ranges = complement of its _editCuts over [0,len]. Union the
    // kept ranges across parts, then the merged _editCuts = complement of that
    // union — this reproduces the parts' kept text, concatenated in order.
    const keptRanges = [];
    for (const part of ordered) {
      const cuts = [...(part._editCuts || [])].sort((a, b) => a[0] - b[0]);
      let pos = 0;
      for (const [s, e] of cuts) {
        if (s > pos) keptRanges.push([pos, s]);
        pos = Math.max(pos, e);
      }
      if (pos < len) keptRanges.push([pos, len]);
    }
    keptRanges.sort((a, b) => a[0] - b[0]);
    const mergedKept = [];
    for (const [s, e] of keptRanges) {
      const last = mergedKept[mergedKept.length - 1];
      if (last && s <= last[1]) last[1] = Math.max(last[1], e);
      else mergedKept.push([s, e]);
    }
    // Complement of the merged kept ranges → merged _editCuts.
    const mergedCuts = [];
    let cur = 0;
    for (const [s, e] of mergedKept) {
      if (s > cur) mergedCuts.push([cur, s]);
      cur = e;
    }
    if (cur < len) mergedCuts.push([cur, len]);

    // entry_id collision guard (mirrors executeSplit's newId contract): the
    // restored single entry takes the source number. Verify nothing else already
    // owns it (siblings are about to be removed, so they don't count).
    const restoredId = String(srcId);
    const collision = tlNow.some(
      (e) => e.entry_id === restoredId && !(e.source_quote_id === srcId && e._subLabel)
    );
    if (collision) {
      setSendStatus({ text: `Can't rejoin — #${srcId} is already taken`, cls: "warn" });
      setTimeout(() => setSendStatus({ text: "", cls: "" }), 3500);
      return;
    }

    const merged = {
      ...ordered[0],
      entry_id: restoredId,
      _subLabel: null,
      _editCuts: mergedCuts,
      notes: (ordered[0].notes || "").replace(/\s*\(split [a-z] of \d+\)/gi, "").trim(),
    };
    const partIds = ordered.map((p) => p.entry_id);
    applyLocalEdit("rejoin",
      (tl) => {
        // Insert the merged entry where the first part sat, then drop all parts.
        const firstIdx = tl.findIndex((x) => x.entry_id === partIds[0]);
        const keep = tl.filter((x) => !partIds.includes(x.entry_id));
        const insertAt = firstIdx < 0 ? keep.length
          : keep.filter((x, i) => tl.indexOf(x) < firstIdx).length;
        keep.splice(insertAt, 0, merged);
        tl.length = 0;
        tl.push(...keep);
      },
      `Rejoined ${partIds.join(", ")} into #${srcId}`,
      {
        change_type: "rejoin",
        entry_id: restoredId,
        before: { sub_ids: partIds, source_quote_id: srcId },
        after: { entry_id: restoredId, source_quote_id: srcId },
      }
    );
  }

  // ====== Point at this ======

  // Tag an exact entry into the live message to the agent without exposing a
  // visible quote number: speaker + first ~6 kept words + the under-the-hood
  // entry_id (the precise handle). Staged as a chip in the agent panel; it
  // rides in edits/<edit>/current.json's pending_message so the agent knows exactly
  // which quote Jeff means on its next read. Opens the panel.
  function pointAtEntry(entry) {
    const src = findSourceQuote(entry.source_quote_id);
    const speaker = src?.speaker || entry.speaker || "Interstitial";
    const words = trimmedQuoteText(entry).split(/\s+/).filter(Boolean).slice(0, 6).join(" ");
    const label = `${speaker}: "${words}…"`;
    setPointedAt((prev) => (prev.some((p) => p.entry_id === entry.entry_id)
      ? prev
      : [...prev, { entry_id: entry.entry_id, label }]));
    setSendPanelOpen(true);
  }

  function removePointedAt(entryId) {
    setPointedAt((prev) => prev.filter((p) => p.entry_id !== entryId));
  }

  // Point at a SOURCE quote from the Quote Library (one that may not be in the
  // timeline at all). Same mechanism as pointAtEntry, but the handle is the
  // source quote num, prefixed "q-" so the agent can tell a Library reference
  // from a timeline entry_id. Lets Jeff point at not-used / Cuts quotes during
  // the categorize + off-timeline review steps.
  function pointAtSource(q) {
    const id = `q-${q.num}`;
    const speaker = q.speaker || "Quote";
    const words = (q.quote || "").split(/\s+/).filter(Boolean).slice(0, 6).join(" ");
    const label = `${speaker}: "${words}…"`;
    setPointedAt((prev) => (prev.some((p) => p.entry_id === id)
      ? prev
      : [...prev, { entry_id: id, label }]));
    setSendPanelOpen(true);
  }

  // ====== Agent read-acknowledgement (M5 live loop) ======
  // The Edit Agent drops handoffs/<slug>/agent-cursor.json each turn after it
  // reads edits/<edit>/current.json (see SKILL-edit). We poll it so the staleness cue
  // clears itself the moment the agent catches up — the honest version of
  // "sending a message clears it," with no manual Send.
  useEffect(() => {
    if (typeof fetch !== "function") return;
    let cancelled = false;
    const rel = `handoffs/${PROJECT_META.slug}/agent-cursor.json`;
    async function poll() {
      try {
        const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent(rel)}`);
        if (!res.ok) return;  // 404 → agent hasn't connected; leave cursor null
        const data = await res.json();
        if (!cancelled && data && data.ok && data.data) setAgentCursor(data.data);
      } catch (_) { /* server down — leave state as-is */ }
    }
    poll();
    const id = setInterval(poll, 4000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ====== Ongoing chat: poll + send (project-chat.json) ======
  // Poll the thread like agent-cursor.json so the agent's replies appear
  // without a reload. (The old behind→caught-up auto-clear of the composer is
  // gone — Send clears it explicitly, like any chat.)
  useEffect(() => {
    if (typeof fetch !== "function") return;
    let cancelled = false;
    const rel = `handoffs/${PROJECT_META.slug}/project-chat.json`;
    async function poll() {
      try {
        const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent(rel)}`);
        if (!res.ok) return;  // 404 → no thread yet
        const data = await res.json();
        if (!cancelled && data && data.ok && data.data && Array.isArray(data.data.messages)) {
          setChatLog(data.data.messages);
        }
      } catch (_) { /* server down — thread stays as-is */ }
    }
    poll();
    const id = setInterval(poll, 4000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Auto-scroll the thread to the newest message.
  useEffect(() => {
    if (chatEndRef.current) chatEndRef.current.scrollIntoView({ block: "nearest" });
  }, [chatLog.length]);

  // Send = append to the thread (merge-by-id against the on-disk file so a
  // concurrent agent append can't be clobbered), then clear the composer.
  async function sendChatMessage() {
    const text = batchNote.trim();
    if ((!text && pointedAt.length === 0) || chatSending) return;
    setChatSending(true);
    const rel = `handoffs/${PROJECT_META.slug}/project-chat.json`;
    let msgs = [];
    try {
      const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent(rel)}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.ok && data.data && Array.isArray(data.data.messages)) msgs = data.data.messages;
      }
    } catch (_) { /* no thread yet — start one */ }
    const seen = new Set(msgs.map((m) => m.id));
    chatLog.forEach((m) => { if (m && m.id && !seen.has(m.id)) { msgs.push(m); seen.add(m.id); } });
    const message = {
      id: `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      who: "jeff",
      text: text || null,
      ts: new Date().toISOString(),
      pointed_at: pointedAt.map((p) => ({ entry_id: p.entry_id, ref: p.label })),
    };
    msgs.push(message);
    msgs.sort((a, b) => String(a.ts || "").localeCompare(String(b.ts || "")));
    const res = await persistFile(rel, JSON.stringify({ schema_version: 1, messages: msgs }, null, 2),
      { allowDownload: false });
    if (res.ok) {
      setChatLog(msgs);
      setLastSent({ note: message.text, pointed_at: message.pointed_at });
      setBatchNote("");
      setPointedAt([]);
    }
    setChatSending(false);
  }

  // ====== Add a title card ======

  // "Add title card" creates a blank title card at the head of the act and opens
  // it in the SAME inline editor used for an existing title card — no separate
  // form. Jeff types the text, sets the duration, reorders with the handle, and
  // hits Done. `justAddedId` autofocuses the new card's text field.
  function addTitleCard(act) {
    const newId = `ic-${Date.now().toString(36)}`;
    const newEntry = {
      entry_id: newId,
      _subLabel: null,
      source_quote_id: null,
      type: "title_card",
      part: act,
      membership: "tight",
      _editCuts: [],
      notes: "",
      estimated_seconds: 3,
      text: "",
    };
    applyLocalEdit("add_title_card",
      (tl) => {
        const idx = tl.findIndex((e) => entryActOf(e) === act);
        if (idx < 0) tl.push(newEntry); else tl.splice(idx, 0, newEntry);
      },
      `Added title card in ${act}`,
      { change_type: "add", entry_id: newId, before: null, after: { entry_id: newId, type: "title_card", part: act } }
    );
    setRevealedIds((prev) => new Set(prev).add(newId));
    setJustAddedId(newId);
  }

  // ====== Membership verbs (Cut / Add Back) ======

  // Move an entry between strata and log a set_membership tweak. Cut = tight→loose
  // (stays in play, just out of the Tight cut); Add Back = loose→tight.
  function setMembership(entry, m) {
    const before = membershipOf(entry);
    if (before === m) return;
    applyLocalEdit("set_membership",
      (tl) => { const e2 = tl.find((x) => x.entry_id === entry.entry_id); if (e2) e2.membership = m; },
      `${entry.entry_id}: ${before} → ${m}`,
      { change_type: "set_membership", entry_id: entry.entry_id, before: { membership: before }, after: { membership: m } }
    );
  }

  // The single membership-changing button in a card's action row. Timeline
  // (tight) entries get Cut → Cuts; Cuts (loose) entries get Add Back → Timeline.
  // Internal membership values stay "tight"/"loose".
  function membershipVerb(entry) {
    return membershipOf(entry) === "tight"
      ? (
        <button
          className="btn btn-cut"
          onClick={() => setMembership(entry, "loose")}
          title="Cut to Cuts — stays recoverable, not dropped"
        >Cut <span className="verb-dest">→ Cuts</span></button>
      )
      : (
        <button
          className="btn btn-add"
          onClick={() => setMembership(entry, "tight")}
          title="Add back to the Timeline"
        >Add Back <span className="verb-dest">→ Timeline</span></button>
      );
  }

  // Drop an entry back to the Library (removes the timeline entry; the source
  // quote stays). Shared by the working card and the collapsed clean card so
  // Drop behaves identically wherever it's offered.
  function dropEntry(entry) {
    if (!confirm(`Drop entry ${entry.entry_id} (#${entry.source_quote_id}) back to the Library? The source quote stays in the Library and can be re-added.`)) return;
    applyLocalEdit("drop_entry",
      (tl) => {
        const i = tl.findIndex((x) => x.entry_id === entry.entry_id);
        if (i >= 0) tl.splice(i, 1);
      },
      `Dropped ${entry.entry_id} (#${entry.source_quote_id})`,
      {
        change_type: "drop",
        entry_id: entry.entry_id,
        before: {
          entry_id: entry.entry_id,
          source_quote_id: entry.source_quote_id,
          part: entryActOf(entry),
          membership: membershipOf(entry),
        },
        after: null,
      }
    );
  }

  // ====== Live-partner agent panel ======

  // Edits Jeff has made since the agent last read the viewer — the "what you'll
  // catch up on" list. When the agent has never connected, show everything
  // pending this round.
  function opsSinceAgentRead() {
    const ops = getPendingOps();
    if (!agentConnected) return ops;
    return ops.filter((o) => (o.ts || 0) > cursorReadMs);
  }

  // Persist the round's tweak log to disk for the Editing Coach Agent — the
  // durable record of every correction (before/after) plus Jeff's live note.
  // The old clipboard Send used to trigger this; now it rides the autosave, so
  // the Coach's training signal keeps flowing without a manual Send. Cumulative
  // (pendingOps is never auto-cleared), best-effort, never forces a download.
  async function writeTweakLog() {
    const ops = getPendingOps();
    if (ops.length === 0 && !batchNote.trim()) return { ok: false, reason: "nothing to log" };
    const cut = cuts[roundIndex];
    if (!cut) return { ok: false, reason: "no edit" };
    const payload = {
      schema_version: 4,
      project_slug: PROJECT_META.slug,
      edit: cut.slug,
      edit_name: cut.name,
      round: (cut.steps || []).length || 1,
      generated_at: new Date().toISOString(),
      baseline: `edit ${cut.slug} (${(cut.steps || []).length} steps)`,
      // Jeff's current live note + what he's pointing at (the "why" for the Coach).
      working_note: batchNote.trim() || null,
      pointed_at: pointedAt.map((p) => ({ entry_id: p.entry_id, ref: p.label })),
      agent_last_read: agentCursor ? agentCursor.read_at : null,
      tweaks: ops.map((o) => ({
        seq: o.seq,
        entry_id: o.entry_id,
        change_type: o.change_type,
        before: o.before,
        after: o.after,
        timestamp: o.timestamp,
        note: o.note,
        description: o.description,
      })),
    };
    const relPath = `${editPathOf(cut)}/tweak-log.json`;
    const json = JSON.stringify(payload, null, 2);
    return await persistFile(relPath, json, { allowDownload: false });
  }

  // ====== Filter passes ======

  function passesSourceFilters(q) {
    if (speakerFilter !== "all" && q.speakerSlug !== speakerFilter) return false;
    if (actFilter !== "all" && quoteActOf(q) !== actFilter) return false;
    return true;
  }
  // Single source of truth for "is this entry in the Timeline (working cut)" —
  // i.e. tight-membership only. The old Tight/Loose window toggle is gone; the
  // Timeline view always shows the tight cut, and the Cuts view renders loose
  // entries through its own path (renderCuts). Reused by the timeline filter,
  // runtime totals, and the Library hide-in-cut filter.
  function inActiveWindow(e) {
    return membershipOf(e) === "tight";
  }
  // source_quote_ids present in the current cut (active round, respecting the
  // active window). Used by the Library "Hide quotes in current cut" filter.
  function sourceIdsInCut() {
    const ids = new Set();
    for (const e of getTimeline()) {
      if (e.source_quote_id == null) continue;
      if (!inActiveWindow(e)) continue;
      ids.add(e.source_quote_id);
    }
    return ids;
  }
  // Speaker/act filters only — no membership filter. Used by the Cuts view,
  // where every entry is loose by construction.
  function passesTimelineFiltersIgnoringWindow(e) {
    if (speakerFilter !== "all") {
      const src = findSourceQuote(e.source_quote_id);
      if (!src || src.speakerSlug !== speakerFilter) return false;
    }
    if (actFilter !== "all" && entryActOf(e) !== actFilter) return false;
    return true;
  }
  function passesTimelineFilters(e) {
    if (!passesTimelineFiltersIgnoringWindow(e)) return false;
    if (!inActiveWindow(e)) return false;
    return true;
  }

  // ====== Runtime totals ======
  const allEntries = getTimeline();
  const tightEntries = allEntries.filter((e) => membershipOf(e) === "tight");
  const looseEntries = allEntries.filter((e) => membershipOf(e) === "loose");
  const fullSec = allEntries.reduce((a, e) => a + entrySeconds(e), 0);
  const tightSec = tightEntries.reduce((a, e) => a + entrySeconds(e), 0);
  const looseSec = looseEntries.reduce((a, e) => a + entrySeconds(e), 0);
  // Timeline header metric = the working (tight) cut.
  const activeEntries = tightEntries.length;
  const activeSec = tightSec;

  // ====== Per-card reveal (unified Edit page) ======
  // Default is a clean read; each card flips to edit-in-place independently.
  // Multiple may be open at once; Reveal all / Collapse all flip every card in
  // the active window.
  function toggleReveal(id) {
    setRevealedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  function revealAll(v) {
    if (!v) { setRevealedIds(new Set()); return; }
    setRevealedIds(new Set(getTimeline().filter((e) => inActiveWindow(e)).map((e) => e.entry_id)));
  }

  // ============================================================================
  // Header
  // ============================================================================

  // Active-act label for the sub-header: the current act filter, or "Full
  // timeline" when ACT=All. The Creative-context panel is act-scoped against it.
  const activeActLabel = actFilter === "all" ? "Full timeline" : actFilter;
  const activeSpeakerLabel = speakerFilter === "all"
    ? "All speakers"
    : ((PROJECT_META.speakers || []).find((s) => s.slug === speakerFilter)?.name || "Speaker");
  const currentCut = cuts[roundIndex] || null;
  const toggleTopMenu = (m) => {
    setSaveStatus({ text: "", cls: "" });
    if (m === "open" || m === "history") refreshEdits();  // reflect disk right now
    setTopMenu((cur) => (cur === m ? null : m));
  };

  // Body of the act-scoped Creative-context panel. Reads PROJECT_META.acts
  // ([{ label, roadmap }]) and PROJECT_META.premise — both emitted by the build
  // script from the Creative Context handoffs (degrade to "" when absent).
  // M4 persistence indicator. Honest about whether the agent can see edits:
  // "saved" (green) = edits/<edit>/current.json written to disk; "saving" (amber pulse);
  // "offline" (grey) = no app server reachable, so the agent is blind to edits
  // until you start scripts/viewer_save_server.py; "error" (red) = a write tried
  // and failed.
  const renderPersistIndicator = () => {
    const s = persistState.state;
    const map = {
      idle:    { cls: "idle",    glyph: "○", text: "Live state" },
      saving:  { cls: "saving",  glyph: "◌", text: "Saving…" },
      saved:   { cls: "saved",   glyph: "●", text: "Synced" },
      offline: { cls: "offline", glyph: "○", text: "Offline" },
      error:   { cls: "error",   glyph: "▲", text: "Save failed" },
    };
    const v = map[s] || map.idle;
    const tip = s === "offline"
      ? "The viewer can't reach the app server, so the Edit Agent can't see your edits. Run: python3 scripts/viewer_save_server.py --serve <built index.html> --root <project root>"
      : s === "saved"
        ? `Working state autosaved to ${persistState.detail || "edits/<edit>/current.json"} — the Edit Agent reads it each turn.`
        : "Your working state is shared with the Edit Agent via edits/<edit>/current.json on disk.";
    return (
      <div className={`persist-ind ${v.cls}`} title={tip}>
        <span className="persist-glyph" aria-hidden="true">{v.glyph}</span>
        <span className="persist-text">{v.text}</span>
      </div>
    );
  };

  const renderCreativeContext = () => {
    const acts = PROJECT_META.acts || [];
    if (actFilter !== "all") {
      const act = acts.find((a) => a.label === actFilter);
      const roadmap = act && act.roadmap;
      if (!roadmap) {
        return <p className="cc-empty">No creative context available yet for {actFilter}.</p>;
      }
      return (
        <div className="cc-block">
          <div className="cc-block-label">{actFilter}</div>
          <p className="cc-roadmap">{roadmap}</p>
        </div>
      );
    }
    // All: premise + every act's roadmap.
    const premise = PROJECT_META.premise || "";
    const withRoadmap = acts.filter((a) => a.roadmap);
    if (!premise && withRoadmap.length === 0) {
      return <p className="cc-empty">No creative context available yet.</p>;
    }
    return (
      <div>
        {premise && (
          <div className="cc-block">
            <div className="cc-block-label">Premise</div>
            <p className="cc-roadmap">{premise}</p>
          </div>
        )}
        {withRoadmap.map((a) => (
          <div className="cc-block" key={a.label}>
            <div className="cc-block-label">{a.label}</div>
            <p className="cc-roadmap">{a.roadmap}</p>
          </div>
        ))}
      </div>
    );
  };

  // "Who's who" — speaker summaries, scoped by the Speaker filter exactly like
  // renderCreativeContext is scoped by the Act filter. All speakers selected →
  // every voice; one speaker selected → just theirs.
  const renderSpeakerContext = () => {
    const speakers = (PROJECT_META.speakers || []).filter((s) => s.summary);
    if (speakers.length === 0) {
      return <p className="cc-empty">No speaker summaries available yet.</p>;
    }
    const shown = speakerFilter === "all"
      ? speakers
      : speakers.filter((s) => s.slug === speakerFilter);
    if (shown.length === 0) {
      const sel = (PROJECT_META.speakers || []).find((s) => s.slug === speakerFilter);
      return <p className="cc-empty">No summary yet for {sel ? sel.name : "this speaker"}.</p>;
    }
    return (
      <div>
        {shown.map((s) => (
          <div className="cc-block" key={s.slug}>
            <div className="cc-block-label">{s.name}</div>
            <p className="cc-roadmap">{s.summary}</p>
          </div>
        ))}
      </div>
    );
  };

  const renderHeader = () => (
   <>
    <div className="hdr">
      {/* Context strip — hierarchy levels 1–2 (Client · Project). Quiet, and
          renamable in place via the ✎ (stored in handoffs/project-names.json).
          The autosave-health indicator keeps its honest corner here. */}
      <div className="hdr-strip">
        {namesEditing ? (
          <span className="strip-form">
            <input className="strip-input" value={namesDraft.client} placeholder="Client" autoFocus
              onChange={(e) => setNamesDraft((d) => ({ ...d, client: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter") commitNames(); if (e.key === "Escape") setNamesEditing(false); }} />
            <span className="strip-sep">·</span>
            <input className="strip-input" value={namesDraft.project} placeholder="Project"
              onChange={(e) => setNamesDraft((d) => ({ ...d, project: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter") commitNames(); if (e.key === "Escape") setNamesEditing(false); }} />
            <button className="strip-btn" onClick={commitNames}>Save</button>
            <button className="strip-btn quiet" onClick={() => setNamesEditing(false)}>Cancel</button>
          </span>
        ) : (
          <span className="hdr-eyebrow">
            <span className="hdr-eyebrow-text">
              {[names.client, names.project].filter(Boolean).join(" · ") || PROJECT_TITLE}
            </span>
            <button className="strip-pencil" title="Rename client / project"
              onClick={() => { setNamesDraft({ client: names.client, project: names.project }); setNamesEditing(true); }}
            >✎</button>
          </span>
        )}
        <span className="strip-right">{renderPersistIndicator()}</span>
      </div>
      <div className="hdr-row1">
       <div className="hdr-row1-inner">
        {/* Hierarchy level 3 — the EDIT. The headline IS the switcher: click to
            list every edit on this SSD (served at /view/<slug>) or rename this
            one. Safe to switch any time — each page autosaves its own state. */}
        <div className="edit-ident" data-topbar="1">
          <button className="edit-name" onClick={() => toggleTopMenu("edits")}>
            {names.edit} <span className="chev">▾</span>
          </button>
          {topMenu === "edits" && (
            <div className="tb-panel" data-topbar="1">
              <div className="tb-panel-title">Edits on this SSD</div>
              <ul className="tb-cutlist">
                {(PROJECT_META.sibling_projects || [{ slug: PROJECT_META.slug, label: names.edit }]).map((p) => (
                  <li key={p.slug} className={p.slug === PROJECT_META.slug ? "current" : ""}>
                    <span className="tb-cutname">
                      {p.slug === PROJECT_META.slug ? names.edit : (siblingLabels[p.slug] || p.label)}
                      {p.slug === PROJECT_META.slug && <span className="tb-current-tag">current</span>}
                    </span>
                    <button
                      className="btn tb-open-btn"
                      disabled={p.slug === PROJECT_META.slug}
                      onClick={() => { window.location.href = `/view/${p.slug}`; }}
                    >Open</button>
                  </li>
                ))}
              </ul>
              <div className="tb-panel-divider"><span></span></div>
              {editRenaming ? (
                <div className="tb-saveas">
                  <input className="tb-input" type="text" value={editNameDraft} autoFocus
                    onChange={(e) => setEditNameDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") commitEditRename(); if (e.key === "Escape") setEditRenaming(false); }} />
                  <button className="btn tb-panel-btn" onClick={commitEditRename}>Rename</button>
                </div>
              ) : (
                <button
                  className="btn tb-panel-btn tb-panel-btn-secondary"
                  onClick={() => { setEditNameDraft(names.edit); setEditRenaming(true); }}
                >✎ Rename “{names.edit}”…</button>
              )}
            </div>
          )}
        </div>
        {/* Hierarchy level 4 — the EDIT chip (the one capsule in the header):
            names the edit you are in; clicking it lists every edit of this
            project (v5.15: Main edit + the Save-as alternatives). */}
        <div className="ver-wrap" data-topbar="1">
          <button
            className={`ver-chip${topMenu === "open" ? " active" : ""}`}
            onClick={() => toggleTopMenu("open")}
            title="The edit you are working in — click to switch"
          >
            {currentCut ? currentCut.name : "Main edit"} <span className="chev">▾</span>
          </button>
          {topMenu === "open" && (
            <div className="tb-panel" data-topbar="1">
              <div className="tb-panel-title">Edits of {names.edit}</div>
              <ul className="tb-cutlist">
                {cuts.map((c, i) => {
                  const n = (c.steps || []).length;
                  const src = c.forked_from && (cuts.find((x) => x.slug === c.forked_from.edit) || {});
                  return (
                    <li key={c.slug} className={i === roundIndex ? "current" : ""}>
                      <span className="tb-cutname">
                        <span className="tb-cutname-main">
                          {c.name}
                          {i === roundIndex && <span className="tb-current-tag">open</span>}
                        </span>
                        <span className="tb-cutsub">
                          {c.forked_from ? `from ${src.name || c.forked_from.edit}${c.forked_from.step ? ` step ${c.forked_from.step}` : ""} · ` : ""}
                          {n} step{n === 1 ? "" : "s"}
                        </span>
                      </span>
                      <button
                        className="btn tb-open-btn"
                        disabled={i === roundIndex}
                        onClick={() => openCut(i)}
                      >Open</button>
                    </li>
                  );
                })}
              </ul>
              <div className="tb-footnote">Opening an edit never changes another. Each saves on its own.</div>
              {saveStatus.text && <div className={`tb-status ${saveStatus.cls}`}>{saveStatus.text}</div>}
            </div>
          )}
        </div>
        <div className="hdr-grow" aria-hidden="true"></div>

        {/* RIGHT CLUSTER: views · cut metric · History · Save as · Export.
            No dirty dot: the strip's autosave indicator is the one save state. */}
        <div className="hdr-right">
          <div className="mode-toggle">
            {[
              { mode: "library", label: "Quote Library" },
              { mode: "timeline", label: "Timeline" },
              { mode: "cuts", label: "Cuts" },
            ].map((m) => (
              <button
                key={m.mode}
                className={view === m.mode ? "active" : ""}
                onClick={() => setView(m.mode)}
              >
                {m.label}
              </button>
            ))}
          </div>
          <span className="hdr-meta">
            {activeEntries} entries · {fmtSec(activeSec)}
          </span>
          <div className="topbar-actions" data-topbar="1">
            <button
              className={`tb-btn tb-history${topMenu === "history" ? " active" : ""}`}
              onClick={() => toggleTopMenu("history")}
              title="The steps of this edit, written by the agent as you move act to act"
            >History ▾</button>
            {topMenu === "history" && (
              <div className="tb-panel tb-panel-history" data-topbar="1">
                <div className="tb-panel-title">History of {currentCut ? currentCut.name : "this edit"}</div>
                <ul className="tb-steps">
                  <li className={`tb-step now${viewingStep ? "" : " current"}`}>
                    <span className="tb-who n">●</span>
                    <span className="tb-step-main">
                      <span className="tb-step-label">Now · working</span>
                      <span className="tb-step-meta">
                        {persistState.state === "saved" ? "Saved" : persistState.state === "offline" ? "Offline — not saving" : persistState.state === "saving" ? "Saving…" : "Live"}
                        {" · "}{viewingStep && stashRef.current ? stashRef.current.entries.length : getTimeline().length} entries
                        {" · "}{getPendingOps().length} tweak{getPendingOps().length === 1 ? "" : "s"} logged
                      </span>
                    </span>
                    <span className="tb-step-actions">
                      {viewingStep && <button className="btn tb-open-btn" onClick={backToNow}>Back to now</button>}
                    </span>
                  </li>
                  {[...((currentCut && currentCut.steps) || [])].reverse().map((st) => (
                    <li key={st.path || st.seq} className={`tb-step${viewingStep && viewingStep.path === st.path ? " current" : ""}`}>
                      <span className={`tb-who ${st.who === "claude" ? "c" : st.who === "jeff" ? "j" : "p"}`}>
                        {st.who === "claude" ? "C" : st.who === "jeff" ? "J" : "P"}
                      </span>
                      <span className="tb-step-main">
                        <span className="tb-step-label">
                          {whoName(st.who)}: {st.label}
                          <button className="tb-step-rename" title="Rename this step" onClick={() => renameStep(st)}>✎</button>
                        </span>
                        <span className="tb-step-meta">{fmtWhen(st.created_at)} · {st.entry_count} entries</span>
                      </span>
                      <span className="tb-step-actions">
                        <button
                          className="btn tb-open-btn"
                          disabled={!!(viewingStep && viewingStep.path === st.path)}
                          onClick={() => viewStep(st)}
                        >View</button>
                      </span>
                    </li>
                  ))}
                  {(!currentCut || !(currentCut.steps || []).length) && (
                    <li className="tb-empty">No steps yet — the agent writes one each time you hand off an act.</li>
                  )}
                </ul>
                <div className="tb-footnote">View is read-only; Restore (in the banner while viewing) copies a step forward as a new step. History is never rewritten.</div>
                {saveStatus.text && <div className={`tb-status ${saveStatus.cls}`}>{saveStatus.text}</div>}
              </div>
            )}
          </div>
          <div className="topbar-actions" data-topbar="1">
            <button
              className={`tb-btn tb-saveas${topMenu === "save" ? " active" : ""}`}
              disabled={!!viewingStep}
              onClick={() => toggleTopMenu("save")}
              title="Fork the current state into a new edit you iterate on separately"
            >Save as ▾</button>
            {topMenu === "save" && (
              <div className="tb-panel" data-topbar="1">
                <div className="tb-panel-title">Save current state as a new edit</div>
                <div className="tb-saveas">
                  <input
                    className="tb-input"
                    type="text"
                    placeholder="Name, e.g. Tighter cut"
                    value={newEditName}
                    autoFocus
                    onChange={(e) => setNewEditName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") saveAsNewEdit(); }}
                  />
                  <button
                    className="btn tb-panel-btn"
                    disabled={!newEditName.trim()}
                    onClick={saveAsNewEdit}
                  >Create</button>
                </div>
                <div className="tb-footnote">Starts from “{currentCut ? currentCut.name : "Main edit"}” as it is now. That edit stays untouched; you will be switched to the new one.</div>
                {saveStatus.text && <div className={`tb-status ${saveStatus.cls}`}>{saveStatus.text}</div>}
              </div>
            )}
          </div>
          <div className="topbar-actions tb-export-wrap" data-topbar="1">
            <button
              className={`tb-btn tb-export${topMenu === "export" ? " active" : ""}`}
              onClick={() => toggleTopMenu("export")}
            >Export to Final Cut</button>
            {topMenu === "export" && (
              <div className="tb-panel" data-topbar="1">
                <div className="tb-panel-title">Export to Final Cut</div>
                <div className="tb-panel-sub">Hands the cut to the FCPXML Agent.</div>
                <button
                  className="btn tb-panel-btn"
                  onClick={() => { setTopMenu(null); exportToFCPXML(false); }}
                >Timeline cut ({activeEntries} · {fmtSec(activeSec)})</button>
                {looseEntries.length > 0 && (
                  <button
                    className="btn tb-panel-btn tb-panel-btn-secondary"
                    onClick={() => { setTopMenu(null); exportToFCPXML(true); }}
                    title="Export the full timeline including cut quotes (Timeline + Cuts)"
                  >Full timeline ({allEntries.length} · {fmtSec(fullSec)})</button>
                )}
              </div>
            )}
          </div>
        </div>
       </div>
      </div>
    </div>
      {/* Filters sit OUTSIDE the elevated header, on the page background — the
          shadowed .hdr is "the app", this zone is "the workspace". */}
      <div className="hdr-filters">
          {/* Line 1: Act filter + Speaker dropdown, one line of "what's included" */}
          <div className="hdr-filter-line">
            <div className="filter-group">
              <span className="group-label">Act</span>
              <button
                className={`chip${actFilter === "all" ? " active" : ""}`}
                onClick={() => setActFilter("all")}
              >All</button>
              {/* Three narrative acts (from the approved structure). "Safety
                  Lines" is a dedicated tag, not an act, so it is held out here
                  and rendered after a divider as a set-apart filter chip; the
                  same for any future non-act tags. "Orphan" never appears. */}
              {PROJECT_META.act_labels
                .filter((a) => a !== "Orphan" && !NAV_TAG_LABELS.includes(a))
                .map((label) => (
                <button
                  key={label}
                  className={`chip${actFilter === label ? " active" : ""}`}
                  onClick={() => setActFilter(label)}
                  title={label}
                >
                  {label}
                </button>
              ))}
              {PROJECT_META.act_labels.some((a) => NAV_TAG_LABELS.includes(a)) && (
                <span className="nav-tag-divider" aria-hidden="true"></span>
              )}
              {PROJECT_META.act_labels
                .filter((a) => NAV_TAG_LABELS.includes(a))
                .map((label) => (
                <button
                  key={label}
                  className={`chip chip-tag${actFilter === label ? " active" : ""}`}
                  onClick={() => setActFilter(label)}
                  title={`${label} — scripted reads (not a narrative act)`}
                >
                  {label}
                </button>
              ))}
              {/* Creative context (act-scoped) — a compact "?" affordance tucked
                  INSIDE the Act bubble (after a hairline) so it reads as part of
                  the same unit. Panel anchors to this wrapper; data-topbar keeps
                  the outside-click close working. */}
              <span className="cc-divider" aria-hidden="true"></span>
              <div className="cc-inline" data-topbar="1">
                <button
                  className={`cc-help-btn${creativeOpen ? " active" : ""}`}
                  onClick={() => setCreativeOpen((v) => !v)}
                  aria-label={`Creative context — ${activeActLabel}`}
                  title={`Creative context — ${activeActLabel}`}
                >?</button>
                {creativeOpen && (
                  <div className="cc-panel">
                    <button
                      className="cc-pin-btn"
                      onClick={() => { toggleCcPinned(); setCreativeOpen(false); }}
                      title="Keep the creative context visible beside the editor"
                    >{ccPinned ? "Unpin side panel" : "⇥ Pin as side panel"}</button>
                    {renderCreativeContext()}
                    <div className="cc-source">from Creative Context agent</div>
                  </div>
                )}
              </div>
            </div>
            {/* Speaker — a compact dropdown on the same line as Act (single-
                choice, same behavior the pills had). Who's-who ? kept beside. */}
            <div className="filter-group speaker-group">
              <span className="group-label">Speaker</span>
              <select
                className="speaker-select"
                value={speakerFilter}
                onChange={(e) => setSpeakerFilter(e.target.value)}
              >
                <option value="all">All</option>
                {(PROJECT_META.speakers || []).map((s) => (
                  <option key={s.slug} value={s.slug}>{s.name}</option>
                ))}
              </select>
              {(PROJECT_META.speakers || []).some((s) => s.summary) && (
                <>
                  <span className="cc-divider" aria-hidden="true"></span>
                  <div className="cc-inline" data-topbar="1">
                    <button
                      className={`cc-help-btn${speakerCtxOpen ? " active" : ""}`}
                      onClick={() => setSpeakerCtxOpen((v) => !v)}
                      aria-label={`Who's who — ${activeSpeakerLabel}`}
                      title={`Who's who — ${activeSpeakerLabel}`}
                    >?</button>
                    {speakerCtxOpen && (
                      <div className="cc-panel cc-panel-right">
                        {renderSpeakerContext()}
                        <div className="cc-source">from Creative Context agent</div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          {/* Line 2 (Timeline only): Review|Edit, left-aligned under the Act
              bar. The Quotes tray extends OUT OF the Edit side — options the
              Edit mode grants, not free-floating buttons. */}
          {view === "timeline" && (
            <div className="hdr-filter-line">
              <div className="mode-tray">
                <div className="tl-mode-toggle" role="tablist" aria-label="Timeline mode">
                  {[
                    { m: "review", label: "Review" },
                    { m: "edit", label: "Edit" },
                  ].map(({ m, label }) => (
                    <button
                      key={m}
                      role="tab"
                      aria-selected={timelineMode === m}
                      className={timelineMode === m ? "active" : ""}
                      onClick={() => setTimelineMode(m)}
                      title={m === "review"
                        ? "Read the cut as it plays — kept text only, no controls"
                        : "Working cards — trim, split, cut, reorder"}
                    >{label}</button>
                  ))}
                </div>
                {timelineMode === "edit" && (
                  <div className="tray-ext">
                    <span className="tray-lbl">Quotes</span>
                    <button className="tray-btn" onClick={() => revealAll(true)}>Open</button>
                    <span className="tray-dot" aria-hidden="true">·</span>
                    <button className="tray-btn" onClick={() => revealAll(false)}>Collapse</button>
                  </div>
                )}
              </div>
            </div>
          )}
      </div>
   </>
  );

  // ============================================================================
  // Quote Library view
  // ============================================================================

  const renderLibrary = () => {
    const realActs = PROJECT_META.act_labels.filter((a) => a !== "Orphan");
    const inCutIds = hideInCut ? sourceIdsInCut() : null;
    // Term-based search over quote text + rationale + agent note. A single word
    // ("usability") and a natural-language question ("What did they say about
    // usability or customer support?") both work: the query is tokenized,
    // stopwords are dropped, and a quote matches if ANY remaining term appears.
    // Falls back to a raw substring match when the query is only stopwords.
    const rawNeedle = librarySearch.trim().toLowerCase();
    const allTerms = rawNeedle.match(/[a-z0-9]+/g) || [];
    const terms = allTerms.filter((t) => t.length >= 2 && !SEARCH_STOPWORDS.has(t));
    const matchesSearch = (q) => {
      if (!rawNeedle) return true;
      const hay = `${q.quote || ""} ${q.rationale || ""} ${q.agent_note || ""}`.toLowerCase();
      if (terms.length === 0) return hay.includes(rawNeedle);  // all-stopword query
      return terms.some((t) => hay.includes(t));
    };
    const needle = rawNeedle;  // drives the "N matches" meta + empty-state copy
    const passLib = (q) => passesSourceFilters(q) && (!inCutIds || !inCutIds.has(q.num)) && matchesSearch(q);
    const inScope = SOURCE_QUOTES.filter((q) => !q.is_orphan && passLib(q));
    const orphans = SOURCE_QUOTES.filter((q) => q.is_orphan && passLib(q));
    // Whether the pool carries ANY orphans at all, ignoring filters — distinguishes
    // "filtered out right now" from "none ever merged into the pool" (P5).
    const poolHasOrphans = SOURCE_QUOTES.some((q) => q.is_orphan);
    const hiddenCount = inCutIds ? inCutIds.size : 0;
    const matchCount = inScope.length + orphans.length;
    const acts = realActs.map((act) => ({
      name: act,
      list: inScope.filter((q) => quoteActOf(q) === act),
    })).filter((a) => a.list.length > 0);

    const renderQuoteCard = (q) => {
      const srcEntries = getTimeline().filter((e) => e.source_quote_id === q.num);
      const tightCount = srcEntries.filter((e) => membershipOf(e) === "tight").length;
      const looseCount = srcEntries.filter((e) => membershipOf(e) === "loose").length;
      // Status badge: a tight entry means it's in the Timeline; otherwise a loose
      // entry means it's in Cuts; no entry means Not used.
      const status = tightCount > 0 ? "timeline" : looseCount > 0 ? "cuts" : "none";
      const statusLabel = status === "timeline" ? "In timeline" : status === "cuts" ? "In cuts" : "Not used";
      // "Add to timeline" is disabled only when the quote is already in the
      // Timeline (a tight entry exists). A quote sitting only in Cuts can be
      // re-added here (it lands as a new tight entry).
      const inTimeline = tightCount > 0;
      // Gate the Library "Add" button on ANY existing entry (tight OR loose):
      // a quote sitting in Cuts is re-added via the Cuts view's "Restore", not
      // here — re-adding here would push a duplicate entry_id (= source num).
      const hasEntry = tightCount > 0 || looseCount > 0;
      const useCount = tightCount;
      const speakerC = speakerColors[q.speakerSlug] || { bg: COLORS.surface2, fg: COLORS.textMuted };
      return (
        <div key={q.num} id={`q-${q.num}`} className={`lib-card${q.is_orphan ? " orphan" : ""}${inTimeline ? " in-tl" : ""}`}>
          <div className="card-head">
            <span className="qid">#{q.num}</span>
            <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>
              {q.speaker}
            </span>
            {q.is_orphan ? (
              <span className="act-tag-static">{quoteActOf(q)}</span>
            ) : (
              <span className="act-tag-wrap">
                <button
                  className="act-tag-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setReassigningQuoteNum(reassigningQuoteNum === q.num ? null : q.num);
                  }}
                  title="Re-tag this quote's act"
                >
                  {quoteActOf(q)} <span className="caret">▾</span>
                </button>
                {reassigningQuoteNum === q.num && (
                  <div className="reassign-pop" onClick={(e) => e.stopPropagation()}>
                    {PROJECT_META.act_labels
                      .filter((a) => a !== quoteActOf(q) && a !== "Orphan")
                      .map((a) => (
                        <button key={a} onClick={() => reassignSourceAct(q, a)}>{a}</button>
                      ))}
                  </div>
                )}
              </span>
            )}
            <span className="tc">{tcFmt(q.startTC, q.endTC)}</span>
            <span className={`status-badge ${status}`}>{statusLabel}{status === "timeline" && tightCount > 1 ? ` ×${tightCount}` : ""}</span>
            {q.is_orphan && <span className="orphan-pill">orphan</span>}
          </div>
          <p className="quote-text">{q.quote}</p>
          {q.agent_note && (
            <div className="agent-note">
              <span className="agent-note-glyph" aria-hidden="true">🤖</span> {q.agent_note}
            </div>
          )}
          {status === "cuts" && (() => {
            // Why-not-selected, visible in the Library (Jeff, 2026-07-26): a quote
            // sitting in Cuts surfaces its cut reason here, not only on the Cuts card.
            const noted = srcEntries.find((e) => membershipOf(e) === "loose" && e.notes);
            return noted ? (
              <div className="agent-note cut-reason">
                <span className="agent-note-glyph" aria-hidden="true">✂️</span> Not selected — {noted.notes}
              </div>
            ) : null;
          })()}
          {q.rationale && (
            <div className="rationale">
              <span className="rationale-label">Why:</span> {q.rationale}
            </div>
          )}
          <div className="lib-actions">
            <button
              className="btn btn-primary"
              disabled={hasEntry}
              onClick={() => {
                if (hasEntry) return;
                const newId = String(q.num);
                const addedPart = q.part === "Orphan" ? (PROJECT_META.act_labels[0] || "Act 1") : q.part;
                applyLocalEdit("add_entry",
                  (tl) => {
                    tl.push({
                      entry_id: newId,
                      _subLabel: null,
                      source_quote_id: q.num,
                      type: "spoken",
                      speaker: q.speaker,
                      part: addedPart,
                      membership: "tight",
                      _editCuts: [],
                      notes: q.is_orphan ? "Pulled in from orphans by Jeff." : "Added by Jeff in viewer.",
                    });
                  },
                  `Added #${q.num} (${q.speaker} — ${q.part}) to timeline`,
                  {
                    change_type: "add",
                    entry_id: newId,
                    before: null,
                    after: { entry_id: newId, source_quote_id: q.num, part: addedPart, from_orphan: !!q.is_orphan },
                  }
                );
                // Stay in the Library after adding — Jeff curates a batch of
                // quotes into the Timeline without losing his place. The button
                // flips to "✓ In timeline" for feedback; "View in timeline"
                // (below) is the explicit way to jump over.
              }}
            >
              {status === "timeline" ? "✓ In timeline" : status === "cuts" ? "In Cuts" : `Add #${q.num} to timeline`}
            </button>
            {inTimeline && (
              <button
                className="btn"
                onClick={() => {
                  setView("timeline");
                  requestAnimationFrame(() => {
                    const el = document.getElementById(String(q.num));
                    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
                  });
                }}
              >View in timeline</button>
            )}
            {/* Agent-reference action, set apart on the right — lets Jeff point
                the agent at this exact Library quote (categorize/off-timeline
                review) without typing a quote number. */}
            <button
              className="btn btn-point lib-action-right"
              title="Reference this exact quote into your message to the agent"
              onClick={() => pointAtSource(q)}
            >⌖ Point at this</button>
          </div>
        </div>
      );
    };

    return (
      <div className="library-view">
        <div className="lib-toolbar">
          <input
            type="search"
            className="lib-search"
            placeholder="Search quotes & rationale — a keyword or a question…"
            value={librarySearch}
            onChange={(e) => setLibrarySearch(e.target.value)}
          />
          {needle && <span className="lib-search-meta">{matchCount} match{matchCount === 1 ? "" : "es"}</span>}
          <label className="lib-hide-toggle" title="Hide source quotes already pulled into the current cut">
            <input type="checkbox" checked={hideInCut} onChange={toggleHideInCut} />
            Hide quotes in current cut
            {hideInCut && hiddenCount > 0 && <span className="lib-hide-count">{hiddenCount} hidden</span>}
          </label>
        </div>
        {acts.map((a) => (
          <section key={a.name} className="act-section">
            <div className="act-header">
              <h2 className="act-title">{a.name}</h2>
              <span className="act-sub">{a.list.length} quote{a.list.length === 1 ? "" : "s"}</span>
            </div>
            {a.list.map(renderQuoteCard)}
          </section>
        ))}
        {/* Orphans section is ALWAYS rendered (P5) — an empty orphan pool is a
            silent upstream merge gap, so make it visible rather than absent. */}
        <section className="act-section orphans-section">
          <div className="act-header">
            <h2 className="act-title">Orphans</h2>
            <span className="act-sub">
              {orphans.length > 0
                ? `${orphans.length} quote${orphans.length === 1 ? "" : "s"} · agent recommends excluding`
                : poolHasOrphans ? "none match the current filters" : "none in this pool"}
            </span>
          </div>
          {orphans.length > 0
            ? orphans.map(renderQuoteCard)
            : poolHasOrphans
              ? (
                <p className="orphans-empty">
                  No orphans match the current filters. Loosen the Speaker / Act
                  filters, clear the search, or turn off “Hide quotes in current cut”.
                </p>
              )
              : (
                <p className="orphans-empty warn">
                  No orphans found in this pool. If you expected some, they were
                  likely not merged upstream — Synthesis should emit them as{" "}
                  <code>is_orphan: true</code> entries inside{" "}
                  <code>tagged-quotes-v*.json</code>. Surfaced here instead of
                  rendering nothing, so the gap is visible at review time.
                </p>
              )}
        </section>
        {acts.length === 0 && inScope.length === 0 && (
          <div className="empty">
            <h3>No catalogued quotes match the current filters.</h3>
            <p>Loosen Speaker / Act filters or clear the search above.</p>
          </div>
        )}
      </div>
    );
  };

  // ============================================================================
  // Timeline view
  // ============================================================================

  function renderTrimmedSpans(original, cuts) {
    const segments = buildRenderSegments(original, cuts);
    return segments.map((seg, i) => (
      <span key={i} className={seg.cut ? "tl-quote-cut" : ""}>{seg.text}</span>
    ));
  }

  // Left-edge grip — a visual affordance only. The whole card is the drag
  // source (see cardDragHandlers); pointerdown on this grip bubbles to the card.
  const renderDragHandle = () => (
    <div className="tl-drag" title="Drag anywhere on the card to reorder" aria-hidden="true">
      <svg width="10" height="20" viewBox="0 0 10 20" fill="currentColor">
        <circle cx="2" cy="3" r="1.4"/><circle cx="8" cy="3" r="1.4"/>
        <circle cx="2" cy="10" r="1.4"/><circle cx="8" cy="10" r="1.4"/>
        <circle cx="2" cy="17" r="1.4"/><circle cx="8" cy="17" r="1.4"/>
      </svg>
    </div>
  );

  // Non-spoken entries (title card / interstitial / context beat) render a
  // dedicated card: editable text + duration, no trim/split, no source quote.
  const renderInterstitialCard = (entry) => {
    const mb = canMoveEntry(entry);
    const mship = membershipOf(entry);
    const typeLabel = { title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "Interstitial";
    const isContext = entry.type === "context_beat";
    const fieldVal = isContext ? (entry.intent || "") : (entry.text || "");
    return (
      <div
        key={entry.entry_id}
        id={entry.entry_id}
        className={`tl-card tl-interstitial ins-${entry.type} is-${mship}${dragId === entry.entry_id ? " dragging" : ""}${dragOverId === entry.entry_id && dragId !== entry.entry_id ? " drag-over" : ""}`}
        {...cardDragHandlers(entry)}
      >
        {renderDragHandle()}
        <div className="tl-body">
          <div className="tl-card-head">
            <span className="ins-type-badge">{typeLabel}</span>
            <div className="tl-move-btns">
              <button className="tl-move-btn" disabled={!mb.up}
                onClick={() => moveEntry(entry.entry_id, -1)} title="Move up within act">↑</button>
              <button className="tl-move-btn" disabled={!mb.down}
                onClick={() => moveEntry(entry.entry_id, 1)} title="Move down within act">↓</button>
            </div>
            <span className="act-tag-wrap">
              <button
                className="act-tag-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setReassigningEntryId(reassigningEntryId === entry.entry_id ? null : entry.entry_id);
                }}
              >
                {entryActOf(entry)} <span className="caret">▾</span>
              </button>
              {reassigningEntryId === entry.entry_id && (
                <div className="reassign-pop" onClick={(e) => e.stopPropagation()}>
                  {PROJECT_META.act_labels
                    .filter((a) => a !== entryActOf(entry) && a !== "Orphan")
                    .map((a) => (
                      <button key={a} onClick={() => {
                        const prevAct = entryActOf(entry);
                        applyLocalEdit("reassign_act",
                          (tl) => { const e2 = tl.find((x) => x.entry_id === entry.entry_id); if (e2) e2.part = a; },
                          `${entry.entry_id}: act → ${a}`,
                          { change_type: "reassign_act", entry_id: entry.entry_id, before: { part: prevAct }, after: { part: a } }
                        );
                        setReassigningEntryId(null);
                      }}>{a}</button>
                    ))}
                </div>
              )}
            </span>            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
            <button className="rc-collapse" onClick={() => toggleReveal(entry.entry_id)} title="Collapse to clean read">✕ Done</button>
          </div>
          <div className="ins-edit-row">
            <textarea
              key={`${entry.entry_id}-text-${fieldVal}`}
              className="ins-text"
              defaultValue={fieldVal}
              autoFocus={entry.entry_id === justAddedId}
              placeholder={isContext
                ? "Intent — what context is needed (research filled in later)"
                : "On-screen / bridge text…"}
              onBlur={(e) => {
                const val = e.target.value;
                const field = isContext ? "intent" : "text";
                if (val === fieldVal) return;
                applyLocalEdit("edit_interstitial",
                  (tl) => { const e2 = tl.find((x) => x.entry_id === entry.entry_id); if (e2) e2[field] = val; },
                  `Edited ${typeLabel} text on ${entry.entry_id}`,
                  { change_type: "edit_interstitial", entry_id: entry.entry_id, before: { [field]: fieldVal }, after: { [field]: val } }
                );
              }}
            />
            <label className="ins-secs">~<input
              type="number" min="1" max="60"
              key={`${entry.entry_id}-secs-${entry.estimated_seconds || 3}`}
              defaultValue={entry.estimated_seconds || 3}
              onBlur={(e) => {
                const v = Math.max(1, Number(e.target.value) || 1);
                const old = entry.estimated_seconds || 3;
                if (v === old) return;
                applyLocalEdit("edit_interstitial",
                  (tl) => { const e2 = tl.find((x) => x.entry_id === entry.entry_id); if (e2) e2.estimated_seconds = v; },
                  `Set ${typeLabel} duration to ${v}s on ${entry.entry_id}`,
                  { change_type: "edit_interstitial", entry_id: entry.entry_id, before: { estimated_seconds: old }, after: { estimated_seconds: v } }
                );
              }}
            />s</label>
          </div>
          {isContext && (
            <div className="ins-research">⚑ research needed — Jeff fills the actual content before the FCPXML round</div>
          )}
          {entry.notes && (
            <div className="tl-notes"><span className="tl-notes-label">Notes:</span> {entry.notes}</div>
          )}
          <div className="tl-actions">
            {membershipVerb(entry)}
            {/* Title cards / interstitials are authored (not transcript quotes),
                so they have no Library to return to — removal is a real Delete. */}
            <button
              className="btn btn-drop"
              onClick={() => {
                if (!confirm(`Delete this ${typeLabel.toLowerCase()}?`)) return;
                applyLocalEdit("delete_entry",
                  (tl) => { const i = tl.findIndex((x) => x.entry_id === entry.entry_id); if (i >= 0) tl.splice(i, 1); },
                  `Deleted ${typeLabel} ${entry.entry_id}`,
                  { change_type: "delete", entry_id: entry.entry_id, before: { entry_id: entry.entry_id, type: entry.type, part: entryActOf(entry) }, after: null }
                );
              }}
            >Delete</button>
          </div>
        </div>
      </div>
    );
  };

  // Act-header "Add title card" control. One button per act; clicking it creates
  // a blank title card at the head of the act and opens it in the same inline
  // editor as an existing title card (no separate form).
  const renderActAddControl = (act) => (
    <button
      className="act-add-btn"
      onClick={() => addTitleCard(act)}
      title="Add a title card to this act"
    >+ Add title card</button>
  );

  const renderTimelineCard = (entry) => {
    const src = findSourceQuote(entry.source_quote_id);
    const idLabel = entry._subLabel
      ? `#${entry.source_quote_id}${entry._subLabel}`
      : `#${entry.source_quote_id}`;
    const idClass = entry._subLabel ? "qid split" : "qid";
    const mb = canMoveEntry(entry);
    const isEditing = editingEntryId === entry.entry_id;
    const isSplitting = splittingEntryId === entry.entry_id;
    const original = fullQuoteText(entry);
    const trimmed = isTrimmed(entry);
    const speakerC = (src && speakerColors[src.speakerSlug]) || { bg: COLORS.surface2, fg: COLORS.textMuted };
    const mship = membershipOf(entry);

    // Drag is only initiated from the .tl-drag handle on the left edge of the
    // card — otherwise text selection inside the card (especially in the trim
    // editor) gets hijacked into a card-drag. The whole card still accepts
    // drops; only dragstart/dragend live on the handle.
    return (
      <div
        key={entry.entry_id}
        id={entry.entry_id}
        className={`tl-card is-${mship}${dragId === entry.entry_id ? " dragging" : ""}${dragOverId === entry.entry_id && dragId !== entry.entry_id ? " drag-over" : ""}`}
        {...cardDragHandlers(entry)}
      >
        {renderDragHandle()}
        <div className="tl-body">
          <div className="tl-card-head">
            <span className={idClass}>{idLabel}</span>
            <div className="tl-move-btns">
              <button className="tl-move-btn" disabled={!mb.up}
                onClick={() => moveEntry(entry.entry_id, -1)} title="Move up within act">↑</button>
              <button className="tl-move-btn" disabled={!mb.down}
                onClick={() => moveEntry(entry.entry_id, 1)} title="Move down within act">↓</button>
            </div>
            <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>
              {src?.speaker || entry.speaker || "?"}
            </span>
            <span className="act-tag-wrap">
              <button
                className="act-tag-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setReassigningEntryId(reassigningEntryId === entry.entry_id ? null : entry.entry_id);
                }}
              >
                {entryActOf(entry)} <span className="caret">▾</span>
              </button>
              {reassigningEntryId === entry.entry_id && (
                <div className="reassign-pop" onClick={(e) => e.stopPropagation()}>
                  {PROJECT_META.act_labels
                    .filter((a) => a !== entryActOf(entry) && a !== "Orphan")
                    .map((a) => (
                      <button key={a} onClick={() => {
                        const prevAct = entryActOf(entry);
                        applyLocalEdit("reassign_act",
                          (tl) => {
                            const e2 = tl.find((x) => x.entry_id === entry.entry_id);
                            if (e2) e2.part = a;
                          },
                          `${entry.entry_id}: act → ${a}`,
                          {
                            change_type: "reassign_act",
                            entry_id: entry.entry_id,
                            before: { part: prevAct },
                            after: { part: a },
                          }
                        );
                        setReassigningEntryId(null);
                      }}>{a}</button>
                    ))}
                </div>
              )}
            </span>
            {entry._subLabel && (
              <span className="split-tag" title={`Split sub-quote of source #${entry.source_quote_id}`}>
                Split of #{entry.source_quote_id}
              </span>
            )}            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
            <button
              className="tl-scissors"
              onClick={() => {
                if (splittingEntryId === entry.entry_id) {
                  setSplittingEntryId(null);
                  setSplitMarkers([]);
                } else {
                  setSplittingEntryId(entry.entry_id);
                  setSplitMarkers([]);
                  setEditingEntryId(null);
                }
              }}
              title="Split into sub-quotes"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" d="M6 4l3 6M18 4l-3 6M9 10c0 3 6 3 6 0M9 10l-4 10M15 10l4 10"/>
              </svg>
              split
            </button>
            {/* Rejoin sits right next to Split — they're the inverse structural
                pair. Only shown on a split part that still has a sibling. */}
            {entry._subLabel && hasRejoinSibling(entry) && (
              <button
                className="tl-scissors tl-rejoin"
                title={`Merge the split parts back into one #${entry.source_quote_id}`}
                onClick={() => rejoinSiblings(entry)}
              >⤳ Rejoin</button>
            )}
            <button className="rc-collapse" onClick={() => toggleReveal(entry.entry_id)} title="Collapse to clean read">✕ Done</button>
          </div>
          {!isEditing && (
            <p className="tl-quote">
              "{trimmedQuoteText(entry)}"
            </p>
          )}
          {!isEditing && <InteriorCutNotice affected={interiorCutSegments(entry)} />}
          {!isEditing && !isSplitting && (
            <span
              className="tl-quote-hint"
              onClick={() => {
                setEditingEntryId(entry.entry_id);
                setEditCuts((entry._editCuts || []).map((r) => [...r]));
                setSplittingEntryId(null);
              }}
            >
              ▶ {trimmed ? "show original & edit" : "trim quote"}
            </span>
          )}
          {isEditing && (
            <EditPanel
              entry={entry}
              editCuts={editCuts}
              setEditCuts={setEditCuts}
              onSave={() => {
                const cutsCopy = [...editCuts];
                const prevCuts = (entry._editCuts || []).map((r) => [...r]);
                applyLocalEdit("trim",
                  (tl) => {
                    const e2 = tl.find((x) => x.entry_id === entry.entry_id);
                    if (e2) e2._editCuts = cutsCopy;
                  },
                  cutsCopy.length === 0
                    ? `Reset trim on ${entry.entry_id}`
                    : `Trimmed ${entry.entry_id} (${cutsCopy.length} cut region${cutsCopy.length === 1 ? "" : "s"})`,
                  {
                    change_type: "trim",
                    entry_id: entry.entry_id,
                    before: { edit_cuts: prevCuts },
                    after: { edit_cuts: cutsCopy },
                  }
                );
                setEditingEntryId(null);
                setEditCuts([]);
                // Save trim also collapses the card — no separate "Done" click
                // needed (Jeff, 2026-07-27).
                setRevealedIds((prev) => {
                  const next = new Set(prev);
                  next.delete(entry.entry_id);
                  return next;
                });
              }}
              onCancel={() => { setEditingEntryId(null); setEditCuts([]); }}
            />
          )}
          {isSplitting && (
            <SplitPanel
              entry={entry}
              markers={splitMarkers}
              setMarkers={setSplitMarkers}
              onSplit={() => executeSplit(entry)}
              onCancel={() => { setSplittingEntryId(null); setSplitMarkers([]); }}
            />
          )}
          {entry.notes && (
            <div className="tl-notes">
              <span className="tl-notes-label">Notes:</span> {entry.notes}
            </div>
          )}
          <div className="tl-actions">
            {/* Left group: the disposition actions (Cut / Drop). Split + Rejoin
                live together in the card header (structural pair). */}
            {membershipVerb(entry)}
            <button
              className="btn btn-drop"
              onClick={() => dropEntry(entry)}
            >Drop <span className="verb-dest">→ Library</span></button>
            {/* Agent-reference action, set apart on the right (different intent
                from the disposition buttons — it talks to the agent). */}
            <button
              className="btn btn-point tl-action-right"
              title="Reference this exact quote into your message to the agent"
              onClick={() => pointAtEntry(entry)}
            >⌖ Point at this</button>
          </div>
        </div>
      </div>
    );
  };

  // Clean read card (the Timeline view's default state). Shows ONLY ✎ Edit;
  // Cut / Add Back / Drop live inside the revealed edit card. In the Timeline
  // view every entry is tight, so no membership chip is shown; the chip/edge is
  // only meaningful where memberships mix, which no longer happens in a single
  // view after the window toggle was removed.
  const renderCleanCard = (entry) => {
    const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
    const mship = membershipOf(entry);
    const showChip = false;
    const markCls = showChip ? (mship === "loose" ? " loose-mark" : " tight-mark") : "";
    const chip = showChip ? <span className={`mship-chip ${mship}`}>{membershipLabel(mship)}</span> : null;
    const mb = canMoveEntry(entry);
    // Reorder: drag the grip (primary, fast) OR nudge with ↑/↓ (precise single
    // step). Both work right on the collapsed card — no need to expand.
    const dragHandle = (
      <div className="rc-drag" title="Drag to reorder within the act" aria-hidden="true">
        <svg width="10" height="20" viewBox="0 0 10 20" fill="currentColor">
          <circle cx="2" cy="3" r="1.4"/><circle cx="8" cy="3" r="1.4"/>
          <circle cx="2" cy="10" r="1.4"/><circle cx="8" cy="10" r="1.4"/>
          <circle cx="2" cy="17" r="1.4"/><circle cx="8" cy="17" r="1.4"/>
        </svg>
      </div>
    );
    const moveBtns = (
      <div className="tl-move-btns">
        <button className="tl-move-btn" disabled={!mb.up}
          onClick={() => moveEntry(entry.entry_id, -1)} title="Move up within act">↑</button>
        <button className="tl-move-btn" disabled={!mb.down}
          onClick={() => moveEntry(entry.entry_id, 1)} title="Move down within act">↓</button>
      </div>
    );
    const dragCls = `${dragId === entry.entry_id ? " dragging" : ""}${dragOverId === entry.entry_id && dragId !== entry.entry_id ? " drag-over" : ""}`;
    // All three quick actions sit compact in the upper-right (Cut · Drop · Trim)
    // so the card stays short — no separate action row. Cut keeps the entry
    // recoverable in Cuts; Drop removes the timeline entry (source stays in the
    // Library); ✎ Trim opens the trim editor in one click.
    const tools = (
      <span className="rc-tools">
        {mship === "tight" ? (
          <button className="rc-tool cut" onClick={() => setMembership(entry, "loose")}
            title="Cut to Cuts — stays recoverable">Cut</button>
        ) : (
          <button className="rc-tool" onClick={() => setMembership(entry, "tight")}
            title="Add back to the Timeline">Add Back</button>
        )}
        <button className="rc-tool drop" onClick={() => dropEntry(entry)}
          title="Drop back to the Library — the source quote stays">Drop</button>
        <button className="rc-tool edit"
          onClick={() => {
            toggleReveal(entry.entry_id);
            setEditingEntryId(entry.entry_id);
            setEditCuts((entry._editCuts || []).map((r) => [...r]));
            setSplittingEntryId(null);
          }}
          title="Open the trim editor">✎ Trim</button>
      </span>
    );
    if (!isSpoken) {
      const typeLabel = { title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "Interstitial";
      const insText = entry.type === "context_beat" ? `[${entry.intent || "context needed"}]` : (entry.text || "");
      return (
        <div className={`read-card rc-draggable${markCls}${dragCls}`} id={entry.entry_id} key={entry.entry_id}
          {...cardDragHandlers(entry)}>
          {dragHandle}
          <div className="rc-head">
            {moveBtns}
            <span className="ins-type-badge">{typeLabel}</span>
            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
            {chip}
            {tools}
          </div>
          <p className="rc-quote rc-interstitial">{insText}</p>
          {entry.why && (
            <div className="rc-why">
              <span className="rc-why-label">Why here:</span> {entry.why}
            </div>
          )}
        </div>
      );
    }
    const src = findSourceQuote(entry.source_quote_id);
    const speakerC = (src && speakerColors[src.speakerSlug]) || { bg: COLORS.surface2, fg: COLORS.textMuted };
    const speakerLabel = src?.speaker || entry.speaker || "?";
    return (
      <div className={`read-card rc-draggable${markCls}${dragCls}`} id={entry.entry_id} key={entry.entry_id}
        {...cardDragHandlers(entry)}>
        {dragHandle}
        <div className="rc-head">
          {moveBtns}
          <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>{speakerLabel}</span>
          <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
          {chip}
          <InteriorCutNotice affected={interiorCutSegments(entry)} compact />
          {tools}
        </div>
        <p className="rc-quote">"{trimmedQuoteText(entry)}"</p>
        {entry.why && (
          <div className="rc-why">
            <span className="rc-why-label">Why here:</span> {entry.why}
          </div>
        )}
      </div>
    );
  };

  // Review-mode read card (M3 T2 §A). A clean serif read of one entry as it
  // plays: ONLY the kept post-trim text via trimmedQuoteText(entry). No editing
  // controls; trimmed text is HIDDEN (not struck). Spoken quotes show the
  // speaker; interstitials/title cards show their copy in the same serif voice.
  const renderReviewCard = (entry) => {
    const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
    if (!isSpoken) {
      const insText = entry.type === "context_beat"
        ? `[${entry.intent || "context needed"}]`
        : (entry.text || "");
      return (
        <div className="review-card review-interstitial" id={entry.entry_id} key={entry.entry_id}>
          <p className="review-quote review-ins">{insText}</p>
        </div>
      );
    }
    const src = findSourceQuote(entry.source_quote_id);
    const speakerLabel = src?.speaker || entry.speaker || "?";
    return (
      <div className="review-card" id={entry.entry_id} key={entry.entry_id}>
        <div className="review-speaker">{speakerLabel}</div>
        <p className="review-quote">"{trimmedQuoteText(entry)}"</p>
      </div>
    );
  };

  // Seam-flags (M5 / SPEC §6.6): the Edit Agent's narrative-coherence flags,
  // keyed by the entry they sit BEFORE. Rendered inline in Review mode only, so
  // they appear exactly where the read breaks — not as an always-on panel.
  const seamFlagsByEntry = (() => {
    const m = {};
    (typeof SEAM_FLAGS !== "undefined" ? SEAM_FLAGS : []).forEach((f) => {
      if (!f || !f.before_entry_id) return;
      (m[f.before_entry_id] = m[f.before_entry_id] || []).push(f);
    });
    return m;
  })();

  const renderSeamFlags = (entryId) => {
    const flags = seamFlagsByEntry[entryId];
    if (!flags || flags.length === 0) return null;
    return flags.map((f, i) => (
      <div className="seam-flag" key={`${entryId}-seam-${i}`}>
        <div className="seam-flag-head">
          <span className="seam-flag-glyph" aria-hidden="true">⚑</span>
          <span className="seam-flag-kind">{(f.kind || "seam").replace(/[-_]/g, " ")}</span>
        </div>
        <div className="seam-flag-msg">{f.message}</div>
        {f.suggestion && <div className="seam-flag-fix"><span className="seam-flag-fix-label">Try:</span> {f.suggestion}</div>}
      </div>
    ));
  };

  // Review mode (M3 T2 §A): the cut read end to end, grouped by titled act, with
  // no editing controls. Shares the act grouping/filter logic with Edit mode.
  // Agent seam-flags surface inline (M5), right before the entry they flag.
  const renderTimelineReview = (grouped, realActs) => (
    <div className="timeline-view review-mode">
      {realActs.map((act) => {
        if (actFilter !== "all" && act !== actFilter) return null;
        const entries = (grouped[act] || []).filter(passesTimelineFilters);
        if (entries.length === 0) return null;
        const sec = entries.reduce((a, e) => a + entrySeconds(e), 0);
        return (
          <section key={act} className="act-section review-act">
            <div className="act-header review-act-header">
              <h2 className="act-title review-act-title">{act}</h2>
              <span className="act-sub">
                {entries.length} entr{entries.length === 1 ? "y" : "ies"} · ~{fmtSec(sec)}
              </span>
            </div>
            {entries.map((entry) => (
              <React.Fragment key={`rev-${entry.entry_id}`}>
                {renderSeamFlags(entry.entry_id)}
                {renderReviewCard(entry)}
              </React.Fragment>
            ))}
          </section>
        );
      })}
    </div>
  );

  const renderTimeline = () => {
    const tl = getTimeline();
    if (tl.length === 0) {
      return (
        <div className="empty">
          <h3>Timeline empty.</h3>
          <p>Add quotes from Quote Library, or wait for the Edit Agent's first pass.</p>
        </div>
      );
    }
    const realActs = PROJECT_META.act_labels.filter((a) => a !== "Orphan");
    const grouped = {};
    for (const e of tl) {
      const act = entryActOf(e);
      grouped[act] = grouped[act] || [];
      grouped[act].push(e);
    }
    // Review mode = clean read; Edit mode = the working cards (below).
    if (timelineMode === "review") return renderTimelineReview(grouped, realActs);
    return (
      <div className="timeline-view">
        {realActs.map((act) => {
          if (actFilter !== "all" && act !== actFilter) return null;
          const entries = (grouped[act] || []).filter(passesTimelineFilters);
          if (entries.length === 0) return null;
          const sec = entries.reduce((a, e) => a + entrySeconds(e), 0);
          return (
            <section key={act} className="act-section">
              <div className="act-header">
                <h2 className="act-title">{act}</h2>
                <span className="act-sub">
                  {entries.length} entr{entries.length === 1 ? "y" : "ies"} · ~{fmtSec(sec)}
                </span>
                <span className="act-header-actions">{renderActAddControl(act)}</span>
              </div>
              {entries.map((entry) => {
                const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
                return revealedIds.has(entry.entry_id)
                  ? (isSpoken ? renderTimelineCard(entry) : renderInterstitialCard(entry))
                  : renderCleanCard(entry);
              })}
            </section>
          );
        })}
      </div>
    );
  };

  // ============================================================================
  // Cuts view — entries cut from the Timeline (membership "loose"), grouped by
  // act, rendered as read cards. Restore → Timeline (back to tight); Discard →
  // removes the entry (the source quote then shows as Not used in the Library).
  // Discard is NOT destructive: the source quote stays in the Library and can be
  // re-added. Per spec, no confirm dialogs.
  // ============================================================================

  // Restore a cut entry to the working Timeline (loose → tight).
  function restoreEntry(entry) {
    setMembership(entry, "tight");
  }
  // Discard a cut entry — drop it from the timeline entirely. The source quote
  // remains in the Library (Not used), recoverable via "Add to timeline".
  function discardEntry(entry) {
    applyLocalEdit("drop_entry",
      (tl) => {
        const i = tl.findIndex((x) => x.entry_id === entry.entry_id);
        if (i >= 0) tl.splice(i, 1);
      },
      `Discarded ${entry.entry_id} (#${entry.source_quote_id}) from Cuts`,
      {
        change_type: "drop",
        entry_id: entry.entry_id,
        before: {
          entry_id: entry.entry_id,
          source_quote_id: entry.source_quote_id,
          part: entryActOf(entry),
          membership: membershipOf(entry),
        },
        after: null,
      }
    );
  }

  const renderCutCard = (entry) => {
    const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
    const src = findSourceQuote(entry.source_quote_id);
    const speakerC = (src && speakerColors[src.speakerSlug]) || { bg: COLORS.surface2, fg: COLORS.textMuted };
    const speakerLabel = src?.speaker || entry.speaker || "?";
    const typeLabel = { title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "Interstitial";
    const insText = entry.type === "context_beat" ? `[${entry.intent || "context needed"}]` : (entry.text || "");
    return (
      <div className="read-card cut-card" id={entry.entry_id} key={entry.entry_id}>
        <div className="rc-head">
          {isSpoken ? (
            <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>{speakerLabel}</span>
          ) : (
            <span className="ins-type-badge">{typeLabel}</span>
          )}
          <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
        </div>
        <p className={`rc-quote${isSpoken ? "" : " rc-interstitial"}`}>
          {isSpoken ? `"${trimmedQuoteText(entry)}"` : insText}
        </p>
        {entry.notes && (
          <div className="agent-note">
            <span className="agent-note-glyph" aria-hidden="true">🤖</span> {entry.notes}
          </div>
        )}
        <div className="cut-actions">
          <button className="btn btn-add" onClick={() => restoreEntry(entry)}>Restore <span className="verb-dest">→ Timeline</span></button>
          <button className="btn btn-discard" onClick={() => discardEntry(entry)} title="Remove from Cuts — the source quote stays in the Library">Discard</button>
        </div>
      </div>
    );
  };

  const renderCuts = () => {
    const tl = getTimeline();
    const cutEntries = tl.filter((e) => membershipOf(e) === "loose");
    if (cutEntries.length === 0) {
      return (
        <div className="cuts-view">
          <div className="empty">
            <p>Cuts is empty — quotes you cut from the Timeline land here, recoverable.</p>
          </div>
        </div>
      );
    }
    const realActs = PROJECT_META.act_labels.filter((a) => a !== "Orphan");
    const grouped = {};
    for (const e of cutEntries) {
      const act = entryActOf(e);
      grouped[act] = grouped[act] || [];
      grouped[act].push(e);
    }
    return (
      <div className="cuts-view">
        {realActs.map((act) => {
          if (actFilter !== "all" && act !== actFilter) return null;
          const entries = (grouped[act] || []).filter(passesTimelineFiltersIgnoringWindow);
          if (entries.length === 0) return null;
          const sec = entries.reduce((a, e) => a + entrySeconds(e), 0);
          return (
            <section key={act} className="act-section">
              <div className="act-header">
                <h2 className="act-title">{act}</h2>
                <span className="act-sub">
                  {entries.length} cut{entries.length === 1 ? "" : "s"} · ~{fmtSec(sec)}
                </span>
              </div>
              {entries.map(renderCutCard)}
            </section>
          );
        })}
      </div>
    );
  };

  // ============================================================================
  // Send-to-agent panel
  // ============================================================================

  const renderExportModal = () => {
    if (!exportInfo) return null;
    const { win, label, count, time, file, filename, outFcpxml, wrote, queued, fidelity } = exportInfo;
    return (
      <div className="export-overlay" onClick={() => setExportInfo(null)}>
        <div className="export-modal" onClick={(e) => e.stopPropagation()}>
          <h3>Export the <span className={`export-win ${win}`}>{label}</span> cut to Final Cut</h3>
          {wrote === "disk" && queued ? (
            <>
              <p className="export-sub">
                <span className="export-ok">✓ Queued</span> the {label} cut ({count} entries · {time}). The cut is on disk at <code>{file}</code>.
              </p>
              <p className="export-next">
                Just tell the editing agent <strong>"build the export"</strong> — it already has the request, so it'll launch the FCPXML Agent itself and save <code>{outFcpxml}</code>. No copy-paste, no new session.
              </p>
            </>
          ) : wrote === "download" ? (
            <p className="export-sub">
              <span className="export-ok">✓ Downloaded</span> <code>{filename}</code> ({count} entries · {time}). The app server isn't running, so move it to <code>{file}</code> and start the server, then tell the agent to build the export.
            </p>
          ) : (
            <p className="export-sub export-warn">⚠ Couldn't write the cut file — start the app server (so the agent can read it) and try again.</p>
          )}
          {fidelity > 0 && (
            <p className="export-sub export-fidelity">
              <span className="interior-cut-badge">⚠ {fidelity} interior cut{fidelity === 1 ? "" : "s"}</span>{" "}
              {fidelity === 1 ? "One entry has a" : `${fidelity} entries have a`} mid-segment cut the FCPXML can only approximate — it plays slightly wider there. They're listed in the cut file's <code>fidelity_warnings</code>; tighten the in/out in Final Cut Pro.
            </p>
          )}
          <div className="export-actions">
            <button className="btn" onClick={() => setExportInfo(null)}>Close</button>
          </div>
        </div>
      </div>
    );
  };

  // Live-partner sync state (M5). Three honest states driven by comparing Jeff's
  // last edit time against the agent's last read (polled agent-cursor.json):
  //   not-connected — the agent hasn't read the viewer yet this session
  //   caught-up     — it has read since your last edit
  //   behind        — you've edited since it last looked
  const syncState = !agentConnected ? "idle" : (agentBehind ? "behind" : "fresh");
  const syncMap = {
    idle:   { dot: "#6b7280", glyph: "○", title: "Agent not connected yet",
              line: "Waiting for the agent to read your viewer. Message it in chat to start." },
    fresh:  { dot: "#15803d", glyph: "✓", title: "Agent is up to date",
              line: "Reading your live edits — I'm up to date." },
    behind: { dot: "#d97706", glyph: "↻", title: "You've edited since the agent last looked",
              line: "You've changed things since I last looked — just message me and I'll catch up." },
  };

  const renderAgentPanel = () => {
    const sv = syncMap[syncState];
    const since = opsSinceAgentRead();
    return (
      <div className={`send-panel agent-panel sync-${syncState}${sendPanelOpen ? "" : " collapsed"}`}>
        <div className="sp-head" onClick={() => setSendPanelOpen(!sendPanelOpen)}>
          <span className="sp-dot" style={{ background: sv.dot }} title={sv.title}></span>
          <span className="sp-title">Editing agent</span>
          {!sendPanelOpen && since.length > 0 && (
            <span className="sp-count" title={`${since.length} edit(s) since the agent last looked`}>{since.length}</span>
          )}
          <span className="sp-toggle">{sendPanelOpen ? "▼" : "▲"}</span>
        </div>
        {sendPanelOpen && (
          <>
            <div className={`sp-stale sync-${syncState}`}>
              <span className="sp-stale-glyph">{sv.glyph}</span>
              <span className="sp-stale-text">{sv.line}</span>
            </div>
            <div className="sp-body">
              {since.length > 0 && (
                <div className="sp-section">
                  <div className="sp-section-head">
                    <span className="sp-section-title">{agentConnected ? "Since its last reply" : "Pending edits"}</span>
                  </div>
                  <ul className="sp-ops">
                    {since.slice(-8).map((o, i) => <li key={i}>{o.description}</li>)}
                  </ul>
                </div>
              )}
              <div className="sp-section sp-chat">
                <div className="sp-section-head">
                  <span className="sp-section-title">Chat</span>
                </div>
                {chatLog.length > 0 ? (
                  <div className="sp-thread">
                    {chatLog.slice(-60).map((m) => (
                      <div key={m.id} className={`sp-msg ${m.who === "agent" ? "theirs" : "mine"}`}>
                        {(m.pointed_at || []).map((p) => (
                          <span className="sp-msg-point" key={p.entry_id}>
                            <span aria-hidden="true">⌖</span> {p.ref}
                          </span>
                        ))}
                        {m.text && <span className="sp-msg-text">{m.text}</span>}
                        <span className="sp-msg-ts">
                          {m.who === "agent" ? "Agent · " : ""}
                          {(() => { const t = Date.parse(m.ts); return isNaN(t) ? "" : new Date(t).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); })()}
                        </span>
                      </div>
                    ))}
                    <div ref={chatEndRef} />
                  </div>
                ) : (
                  <div className="sp-thread sp-thread-empty">No messages yet — say something below.</div>
                )}
                {pointedAt.length > 0 && (
                  <div className="sp-points">
                    {pointedAt.map((p) => (
                      <span className="sp-point-chip" key={p.entry_id}>
                        <span className="sp-point-glyph" aria-hidden="true">⌖</span> {p.label}
                        <button className="sp-point-x" aria-label="Remove" onClick={() => removePointedAt(p.entry_id)}>✕</button>
                      </span>
                    ))}
                  </div>
                )}
                <textarea
                  id="send-textarea"
                  className="sp-textarea"
                  placeholder="Message the agent — Enter to send, Shift+Enter for a new line."
                  value={batchNote}
                  onChange={(e) => setBatchNote(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
                  }}
                />
                <div className="sp-sendrow">
                  <button
                    className="sp-send"
                    disabled={chatSending || (!batchNote.trim() && pointedAt.length === 0)}
                    onClick={sendChatMessage}
                  >{chatSending ? "Sending…" : "Send"}</button>
                </div>
              </div>
            </div>
            <div className="sp-foot">
              <span className="sp-batchnote">Timeline edits autosave on their own — Send is just for messages.</span>
            </div>
          </>
        )}
      </div>
    );
  };

  // ============================================================================
  // Apply initial focus on first render
  // ============================================================================

  useEffect(() => {
    if (!INITIAL_FOCUS) return;
    const targetId = INITIAL_FOCUS.type === "entry" ? INITIAL_FOCUS.id : `q-${INITIAL_FOCUS.id}`;
    requestAnimationFrame(() => {
      const el = document.getElementById(targetId);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("focus-flash");
      setTimeout(() => el.classList.remove("focus-flash"), 1700);
    });
  }, []);

  // Close reassign popups on outside click
  useEffect(() => {
    if (!reassigningEntryId) return;
    const onDoc = () => setReassigningEntryId(null);
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [reassigningEntryId]);
  useEffect(() => {
    if (reassigningQuoteNum === null) return;
    const onDoc = () => setReassigningQuoteNum(null);
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [reassigningQuoteNum]);

  // Close the top-bar Save/Open/Export menus and the Creative-context panel on
  // an outside click. Elements that belong to either carry data-topbar="1".
  useEffect(() => {
    if (topMenu === null && !creativeOpen && !speakerCtxOpen) return;
    const onDoc = (e) => {
      if (e.target.closest && e.target.closest('[data-topbar="1"]')) return;
      setTopMenu(null);
      setCreativeOpen(false);
      setSpeakerCtxOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [topMenu, creativeOpen, speakerCtxOpen]);

  // Styles for the Milestone-2 view-redesign classes. The shared stylesheet
  // lives in build_quotes_viewer.py (not editable from this template), so the
  // new classes introduced here ship their own scoped CSS. Reuses the existing
  // CSS custom properties (--must, --probable, --border, etc.) for theme parity.
  const m2Styles = `
    .mode-toggle .cuts-count { display:inline-block; margin-left:6px; min-width:16px; padding:0 5px;
      border-radius:9px; font-size:11px; font-weight:600; line-height:16px; text-align:center;
      background: var(--probable-soft); color: var(--probable); }
    .status-badge { font-size:11px; font-weight:600; padding:1px 8px; border-radius:10px;
      text-transform:none; letter-spacing:.01em; }
    .status-badge.timeline { background: var(--must-soft); color: var(--must); }
    .status-badge.cuts { background: var(--probable-soft); color: var(--probable); }
    .status-badge.none { background: var(--surface-2); color: var(--text-muted); }
    .agent-note { margin:6px 0 0; font-size:13px; color: var(--text-muted); font-style:italic;
      display:flex; gap:6px; align-items:flex-start; }
    .agent-note-glyph { font-style:normal; opacity:.8; }
    .cut-card .cut-actions { display:flex; gap:8px; margin-top:10px; }
    .btn-discard { background: transparent; color: var(--text-muted); border:1px solid var(--border); }
    .btn-discard:hover { color: var(--text); border-color: var(--text-muted); }
    .cuts-view .empty { text-align:center; color: var(--text-muted); padding:48px 16px; }

    /* === M4 persistence indicator === */
    /* Quiet autosave status, grouped beside Save/Open (no filled pill when all
       is well — color carries the state; it only draws attention on trouble). */
    .persist-ind { display:inline-flex; align-items:center; gap:5px; margin-left:2px;
      padding:5px 4px; font-size:11px; font-weight:500;
      letter-spacing:.01em; white-space:nowrap; cursor:default; }
    .persist-glyph { font-size:9px; line-height:1; }
    .persist-ind.saved   { color:#15803d; }
    .persist-ind.saving  { color:#b45309; }
    .persist-ind.offline { color:#b45309; }
    .persist-ind.error   { color:#b91c1c; }
    .persist-ind.idle    { color:#6b7280; }
    .persist-ind.saving .persist-glyph { animation:persist-spin 1s linear infinite; display:inline-block; }
    @keyframes persist-spin { to { transform:rotate(360deg); } }

    /* Right cluster: views + Export, pushed to the right edge. A hairline divides
       the view tabs from Export (their own inter-tab dividers are kept). */
    .hdr-right { margin-left:auto; display:inline-flex; align-items:flex-end; gap:12px; }
    .hdr-right-sep { width:1px; align-self:stretch; background:var(--border-strong); margin:4px 0; }
    .tb-export-wrap { align-self:center; }

    /* === M3 top-bar (Save / Open / Export to Final Cut) === */
    .topbar-actions { position:relative; display:inline-flex; gap:6px; align-items:center; }
    .tb-btn { background: var(--surface); border:1px solid var(--border-strong); border-radius:6px;
      padding:5px 12px; font:inherit; font-size:12px; font-weight:500; color: var(--text);
      cursor:pointer; line-height:1.2; }
    .tb-btn:hover { background: var(--surface-2); }
    .tb-btn.active { background: var(--text); color:#fff; border-color: var(--text); }
    .tb-btn.tb-export { font-weight:600; }
    .tb-btn.tb-export.active { background: var(--must); border-color: var(--must); }
    .tb-panel { position:absolute; top:calc(100% + 6px); right:0; z-index:70; min-width:280px;
      background: var(--surface); border:1px solid var(--border-strong); border-radius:10px;
      box-shadow:0 12px 32px rgba(0,0,0,.16); padding:14px; text-align:left; }
    .tb-panel-title { font-size:13px; font-weight:600; color: var(--text); margin-bottom:8px; }
    .tb-panel-sub { font-size:12px; color: var(--text-muted); margin-bottom:10px; }
    .tb-panel-sub strong { color: var(--text); }
    .tb-panel-btn { display:block; width:100%; text-align:center; margin:0; font-size:12px; }
    .tb-panel-btn + .tb-panel-btn { margin-top:8px; }
    .tb-panel-btn-secondary { background: transparent; color: var(--probable);
      border:1px solid var(--probable); }
    .tb-panel-divider { display:flex; align-items:center; gap:8px; margin:12px 0;
      color: var(--text-subtle); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
    .tb-panel-divider::before, .tb-panel-divider::after { content:""; flex:1; height:1px; background: var(--border); }
    .tb-saveas { display:flex; flex-direction:column; gap:8px; }
    .tb-input { width:100%; box-sizing:border-box; padding:6px 9px; font:inherit; font-size:12px;
      border:1px solid var(--border-strong); border-radius:6px; color: var(--text); background: var(--surface); }
    .tb-input:focus { outline:none; border-color: var(--text-muted); }
    .tb-status { margin-top:10px; font-size:11px; line-height:1.4; }
    .tb-status.ok { color: var(--must); }
    .tb-status.warn { color:#b45309; }
    .tb-status.err { color:#b91c1c; }
    .tb-empty { font-size:12px; color: var(--text-muted); padding:4px 0; }
    .tb-cutlist { list-style:none; margin:0; padding:0; max-height:240px; overflow:auto; }
    .tb-cutlist li { display:flex; align-items:center; justify-content:space-between; gap:10px;
      padding:7px 0; border-bottom:1px solid var(--border); }
    .tb-cutlist li:last-child { border-bottom:none; }
    .tb-cutlist li.current { }
    .tb-cutname { font-size:12px; color: var(--text); display:flex; align-items:center; gap:7px; }
    .tb-current-tag { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.04em;
      color: var(--must); background: var(--must-soft); border-radius:8px; padding:1px 6px; }
    .tb-open-btn { font-size:11px; padding:3px 11px; }

    /* === M3 sub-header (active act · Creative context) === */
    /* Creative-context control — a compact "?" affordance tucked inside the Act
       bubble (after a hairline divider) so it reads as part of that unit. */
    .cc-inline { position:relative; display:inline-flex; align-items:center; }
    .cc-divider { width:1px; align-self:stretch; background: var(--border-strong); margin:1px 6px 1px 4px; }
    .cc-help-btn { display:inline-flex; align-items:center; justify-content:center;
      width:20px; height:20px; padding:0; border:1px solid var(--border-strong); border-radius:999px;
      background:transparent; font:inherit; font-size:12px; font-weight:600; line-height:1;
      color: var(--text-subtle); cursor:pointer; }
    .cc-help-btn:hover { color: var(--text); background: var(--surface-2); border-color: var(--text-muted); }
    .cc-help-btn.active { color:#fff; background: var(--text); border-color: var(--text); }
    .cc-caret { font-size:10px; }
    .cc-panel { position:absolute; top:calc(100% + 6px); left:0; z-index:70; max-width:560px; min-width:320px;
      background: var(--surface); border:1px solid var(--border-strong); border-radius:10px;
      box-shadow:0 12px 32px rgba(0,0,0,.16); padding:16px 18px; text-align:left; }
    /* Right-anchored variant — for a "?" that sits far right (the Speaker line),
       so the panel opens leftward and stays on-screen instead of clipping. */
    .cc-panel.cc-panel-right { left:auto; right:0; }
    .cc-block { margin-bottom:12px; }
    .cc-block:last-of-type { margin-bottom:0; }
    .cc-block-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
      color: var(--text-subtle); margin-bottom:3px; }
    .cc-roadmap { margin:0; font-size:13px; line-height:1.55; color: var(--text); white-space: pre-line; }
    .cc-empty { margin:0; font-size:13px; color: var(--text-muted); font-style:italic; }
    .cc-source { margin-top:14px; padding-top:10px; border-top:1px solid var(--border);
      font-size:11px; color: var(--text-subtle); }

    /* === M3 T2 §A — Review | Edit segmented toggle === */
    .tl-mode-toggle { display:inline-flex; border:1px solid var(--border-strong); border-radius:7px;
      overflow:hidden; margin-right:10px; }
    .tl-mode-toggle button { background: var(--surface); border:none; padding:4px 13px; font:inherit;
      font-size:12px; font-weight:500; color: var(--text-muted); cursor:pointer; line-height:1.3; }
    .tl-mode-toggle button + button { border-left:1px solid var(--border-strong); }
    .tl-mode-toggle button:hover { background: var(--surface-2); color: var(--text); }
    .tl-mode-toggle button.active { background: var(--text); color:#fff; }

    /* === M3 T2 §A — Review-mode read (clean serif read of the cut) === */
    .timeline-view.review-mode { max-width:760px; margin:0 auto; }
    .review-act { margin-bottom:30px; }
    .review-act-header { border-bottom:1px solid var(--border); padding-bottom:6px; margin-bottom:18px; }
    .review-act-title { font-size:15px; font-weight:700; letter-spacing:.02em; color: var(--text); }
    .review-card { margin:0 0 22px; }
    .review-speaker { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.07em;
      color: var(--text-subtle); margin-bottom:5px; }
    .review-quote { margin:0; font-family: Georgia, "Times New Roman", serif; font-size:19px;
      line-height:1.6; color: var(--text); }
    .review-quote.review-ins { font-style:italic; color: var(--text-muted); font-size:17px; }
    .review-interstitial { margin:0 0 22px; }

    /* === M5 — Review-mode seam-flags (Cardinal Rule 2 surface) === */
    .seam-flag { margin:0 0 18px; padding:10px 13px; border-left:3px solid #d97706;
      background:rgba(217,119,6,.07); border-radius:0 8px 8px 0; }
    .seam-flag-head { display:flex; align-items:center; gap:6px; margin-bottom:3px; }
    .seam-flag-glyph { color:#b45309; font-size:12px; }
    .seam-flag-kind { font-size:10px; font-weight:700; text-transform:uppercase;
      letter-spacing:.07em; color:#b45309; }
    .seam-flag-msg { font-size:13px; line-height:1.5; color: var(--text); }
    .seam-flag-fix { font-size:12px; line-height:1.5; color: var(--text-muted); margin-top:4px; }
    .seam-flag-fix-label { font-weight:700; color:#b45309; }

    /* === B2 — interior (mid-segment) cut fidelity warning === */
    .interior-cut-notice { margin:8px 0 2px; padding:8px 11px; border-left:3px solid #d97706;
      background:rgba(217,119,6,.07); border-radius:0 8px 8px 0; }
    .interior-cut-head { display:flex; align-items:center; gap:6px; margin-bottom:2px; }
    .interior-cut-glyph { color:#b45309; font-size:12px; }
    .interior-cut-kind { font-size:10px; font-weight:700; text-transform:uppercase;
      letter-spacing:.07em; color:#b45309; }
    .interior-cut-msg { font-size:12px; line-height:1.5; color: var(--text); }
    .interior-cut-badge { font-size:10px; font-weight:600; padding:1px 7px; border-radius:8px;
      background:rgba(217,119,6,.12); color:#b45309; letter-spacing:.02em; white-space:nowrap; }

    /* === M3 T2 §C/§D — Point at this + Rejoin + Split tag === */
    .split-tag { font-size:10px; font-weight:600; padding:1px 7px; border-radius:8px;
      background: var(--probable-soft); color: var(--probable); letter-spacing:.02em; }
    .btn-point { background: transparent; color: var(--text-muted); border:1px solid var(--border-strong); }
    .btn-point:hover { color: var(--text); border-color: var(--text-muted); }
    /* Push the agent-reference action to the right edge of the card action row,
       separating it from the disposition buttons (Cut / Rejoin / Drop). */
    .tl-actions .tl-action-right { margin-left: auto; }
    .lib-actions .lib-action-right { margin-left: auto; }
    .btn-rejoin { background: transparent; color: var(--probable); border:1px solid var(--probable); }
    .btn-rejoin:hover { background: var(--probable-soft); }
    /* Rejoin as a header control sitting next to Split (same shape, rejoin tint). */
    .tl-rejoin { color: var(--probable); border-color: var(--probable); background: transparent; }
    .tl-rejoin:hover { background: var(--probable-soft); border-color: var(--probable); color: var(--probable); }

    /* === M5 — Live-partner agent panel === */
    .send-panel.agent-panel.sync-behind { box-shadow:0 -2px 0 0 #d97706 inset, 0 -8px 24px rgba(0,0,0,.12); }
    .sp-dot { width:8px; height:8px; border-radius:50%; flex:0 0 auto; }
    .sp-stale { display:flex; align-items:flex-start; gap:8px; padding:9px 14px; font-size:12px;
      line-height:1.4; border-bottom:1px solid var(--border); }
    .sp-stale.sync-fresh { color:#15803d; background: rgba(21,128,61,.06); }
    .sp-stale.sync-behind { color:#b45309; background: rgba(217,119,6,.10); }
    .sp-stale.sync-idle { color: var(--text-muted); background: var(--surface-2); }
    .sp-stale-glyph { font-size:14px; line-height:1.2; }
    .sp-stale-text { line-height:1.4; }
    /* Point-at-this staged chips */
    .sp-points { display:flex; flex-direction:column; gap:5px; margin-bottom:8px; }
    .sp-point-chip { display:inline-flex; align-items:center; gap:6px; font-size:11px;
      background: var(--surface-2); border:1px solid var(--border); border-radius:999px;
      padding:3px 6px 3px 10px; color: var(--text-muted); }
    .sp-point-glyph { color: var(--probable); }
    .sp-point-x { margin-left:auto; border:none; background:transparent; cursor:pointer;
      color: var(--text-subtle); font-size:11px; padding:0 4px; line-height:1; }
    .sp-point-x:hover { color: var(--text); }
    /* Ongoing chat thread */
    .sp-thread { display:flex; flex-direction:column; gap:6px; max-height:220px; overflow-y:auto;
      padding:2px 2px 8px; margin-bottom:8px; }
    .sp-thread-empty { font-size:12px; color: var(--text-subtle); font-style:italic; padding:4px 2px 10px; }
    .sp-msg { display:flex; flex-direction:column; gap:3px; max-width:88%; border-radius:10px;
      padding:7px 10px; font-size:12px; line-height:1.45; }
    .sp-msg.mine { align-self:flex-end; background: var(--surface-2); border:1px solid var(--border);
      color: var(--text); border-bottom-right-radius:3px; }
    .sp-msg.theirs { align-self:flex-start; background: rgba(124,58,237,.07);
      border:1px solid rgba(124,58,237,.22); color: var(--text); border-bottom-left-radius:3px; }
    .sp-msg-text { white-space:pre-line; }
    .sp-msg-point { font-size:11px; color: var(--probable); }
    .sp-msg-ts { font-size:10px; color: var(--text-subtle); align-self:flex-end; }
    .sp-msg.theirs .sp-msg-ts { align-self:flex-start; }
    .sp-sendrow { display:flex; justify-content:flex-end; margin-top:6px; }
    .sp-send { border:1px solid var(--border); background: var(--surface-2); color: var(--text);
      font-size:12px; font-weight:600; border-radius:8px; padding:5px 16px; cursor:pointer; }
    .sp-send:hover:not(:disabled) { background: var(--surface-3, var(--surface-2)); border-color: var(--text-subtle); }
    .sp-send:disabled { opacity:.45; cursor:default; }

    /* === v5.12 — hierarchy header (Jeff's 2026-08-05 design pass) ===
       Strip = Client · Project (renamable) · work row = Edit ▾ / version chip /
       views / metric / Save (dirty dot) / Export · filters float on the page
       background below the elevated header. Shapes: rounded squares everywhere;
       the version chip is the one capsule. */
    .hdr { border-bottom:1px solid var(--border-strong); box-shadow:0 3px 10px rgba(0,0,0,.07); }
    .hdr-strip { background: var(--surface-2); border-bottom:1px solid var(--border);
      display:flex; align-items:center; gap:10px; padding:4px 20px; min-height:24px; }
    .strip-right { margin-left:auto; display:inline-flex; align-items:center; }
    .strip-pencil { background:none; border:none; cursor:pointer; color: var(--text-subtle);
      font:inherit; font-size:10px; padding:0 2px; margin-left:6px; flex-shrink:0; }
    .strip-pencil:hover { color: var(--accent); }
    .strip-form { display:inline-flex; align-items:center; gap:6px; }
    .strip-input { font:inherit; font-size:11px; border:1px solid var(--border-strong); border-radius:6px;
      padding:2px 7px; color: var(--text); background: var(--surface); width:190px; }
    .strip-sep { color: var(--text-subtle); }
    .strip-btn { font:inherit; font-size:10px; font-weight:700; border:1px solid var(--border-strong);
      border-radius:6px; background: var(--surface); padding:2px 8px; cursor:pointer; color: var(--text); }
    .strip-btn.quiet { border-color:transparent; color: var(--text-subtle); }
    .hdr-row1 { background: var(--surface); border-bottom:none; }
    .hdr-row1-inner { align-items:center; padding:10px 20px; }
    .edit-ident { position:relative; }
    .edit-name { background:none; border:none; cursor:pointer; padding:0; font-family:inherit;
      font-size:18px; font-weight:750; letter-spacing:-0.01em; color: var(--text);
      display:inline-flex; align-items:center; gap:6px; white-space:nowrap; }
    .edit-name:hover { color: var(--accent); }
    .edit-name .chev { font-size:9px; color: var(--text-subtle); margin-top:3px; }
    .edit-ident .tb-panel { left:0; right:auto; }
    .ver-wrap { position:relative; }
    .ver-wrap .tb-panel { left:0; right:auto; }
    .ver-chip { display:inline-flex; align-items:center; gap:5px; font-family:inherit; font-size:12.5px;
      font-weight:650; border:1px solid var(--border-strong); background: var(--surface);
      border-radius:999px; padding:3px 11px; cursor:pointer; color: var(--text-muted); white-space:nowrap; }
    .ver-chip:hover, .ver-chip.active { border-color: var(--accent); color: var(--accent); }
    .ver-chip .chev { font-size:8px; }
    .hdr-grow { flex:1; }
    .hdr-meta { font-size:12.5px; color: var(--text-subtle); font-variant-numeric:tabular-nums; white-space:nowrap; }
    .tb-btn:disabled { opacity:.45; cursor:default; }
    .tb-cutname { flex-direction:column; align-items:flex-start; gap:1px; }
    .tb-cutname-main { display:inline-flex; align-items:center; gap:7px; font-weight:600; }
    .tb-cutsub { font-size:11px; color: var(--text-subtle); }
    /* History panel (v5.15): the open edit's steps, newest first */
    .tb-panel-history { min-width:440px; }
    .tb-steps { list-style:none; margin:0; padding:0; max-height:380px; overflow:auto; }
    .tb-step { display:grid; grid-template-columns:22px 1fr auto; gap:0 10px; padding:7px 8px; border-radius:8px; align-items:start; }
    .tb-step:hover { background: var(--surface-2); }
    .tb-step.now { background: var(--must-soft); }
    .tb-step.current:not(.now) { background: var(--accent-soft, #e0f2fe); }
    .tb-who { width:22px; height:22px; border-radius:50%; font-size:10px; font-weight:800; display:inline-flex;
      align-items:center; justify-content:center; color:#fff; background:#78716c; }
    .tb-who.c { background:#7c3aed; }
    .tb-who.j { background:#0369a1; }
    .tb-who.n { background: var(--must); }
    .tb-step-main { display:flex; flex-direction:column; gap:1px; min-width:0; }
    .tb-step-label { font-size:12.5px; font-weight:600; color: var(--text); display:inline-flex; align-items:center; gap:6px; }
    .tb-step-meta { font-size:11px; color: var(--text-subtle); }
    .tb-step-actions { display:flex; gap:6px; align-items:center; }
    .tb-step-rename { border:none; background:none; cursor:pointer; font-size:11px; color: var(--text-subtle); padding:0 2px; opacity:0; }
    .tb-step:hover .tb-step-rename { opacity:1; }
    .tb-step-rename:hover { color: var(--accent); }
    /* Read-only history view */
    .main.readonly { pointer-events:none; opacity:.93; }
    .view-banner { background:#fef3c7; }
    .agent-banner { background: var(--probable-soft, #dbeafe); }
    .restore-banner button.primary { background: var(--accent); color:#fff; border-color: var(--accent); }
    .tb-footnote { font-size:11px; color: var(--text-subtle); padding-top:8px; line-height:1.4; }
    .hdr-right { align-items:center; }
    /* Filters float on the page background, outside the shadowed header */
    .hdr-filters { max-width:1100px; margin:0 auto; padding:14px 20px 0;
      display:flex; flex-direction:column; gap:8px; }
    .hdr-filters .filter-group { background: var(--surface); border-radius:10px; }
    .hdr-filters .chip { border-radius:7px; }
    .hdr-filters .cc-help-btn { border-radius:6px; }
    .speaker-select { font:inherit; font-size:12px; color: var(--text); background: var(--surface);
      border:1px solid var(--border-strong); border-radius:7px; padding:3px 8px; cursor:pointer; }
    /* Review|Edit + the Quotes tray: one container; the tray extends out of the
       Edit side in accent blue — options the Edit mode grants. */
    .mode-tray { display:inline-flex; align-items:stretch; border:1px solid var(--border-strong);
      border-radius:10px; background: var(--surface); overflow:hidden; }
    .mode-tray .tl-mode-toggle { border:none; border-radius:0; margin-right:0; }
    .mode-tray .tl-mode-toggle button.active { background: var(--accent); }
    .tray-ext { display:inline-flex; align-items:center; gap:4px; padding:3px 10px 3px 12px;
      background: var(--accent-soft); border-left:1px solid var(--border-strong); }
    .tray-lbl { font-size:10px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
      color: var(--accent); margin-right:6px; }
    .tray-btn { font-family:inherit; font-size:12.5px; font-weight:600; color: var(--accent);
      padding:3px 9px; border:none; background:none; border-radius:7px; cursor:pointer; }
    .tray-btn:hover { background:rgba(255,255,255,.7); }
    .tray-dot { color: var(--accent); opacity:.45; }

    /* Restore-on-load banner (checkpoint-versioning design) */
    .restore-banner { display:flex; align-items:center; gap:10px; padding:8px 16px;
      font-size:13px; background: var(--accent-soft); border-bottom:1px solid var(--border-strong); }
    .restore-banner button { font-family:inherit; font-size:12px; font-weight:600;
      padding:3px 10px; border:1px solid var(--border-strong); background:#fff;
      border-radius:7px; cursor:pointer; }
    .restore-banner button:hover { background: var(--accent-soft); }

    /* Creative-context side panel (pinned) */
    .body-row { display:flex; align-items:flex-start; }
    .body-row > .main { flex:1 1 auto; min-width:0; }
    .cc-side { flex:0 0 300px; position:sticky; top:0; max-height:100vh; overflow:auto;
      border-left:1px solid var(--border-strong); background:#fff; padding:14px 16px 24px; }
    .cc-side-head { display:flex; align-items:center; justify-content:space-between;
      margin-bottom:8px; gap:8px; }
    .cc-side-title { font-size:11px; font-weight:700; letter-spacing:.05em;
      text-transform:uppercase; color: var(--accent); }
    .cc-side-close { border:none; background:none; cursor:pointer; font-size:14px;
      opacity:.55; padding:2px 6px; }
    .cc-side-close:hover { opacity:1; }
    .cc-pin-btn { display:block; margin:0 0 10px; font-family:inherit; font-size:11.5px;
      font-weight:600; padding:3px 9px; border:1px solid var(--border-strong);
      background:none; border-radius:7px; cursor:pointer; color: var(--accent); }
    .cc-pin-btn:hover { background: var(--accent-soft); }
    @media (max-width: 1100px) { .cc-side { display:none; } }
  `;

  return (
    <div className="viewer">
      <style>{m2Styles}</style>
      {renderHeader()}
      {viewingStep && (
        <div className="restore-banner view-banner">
          <span>
            Viewing step {viewingStep.seq} · <b>{whoName(viewingStep.who)}: {viewingStep.label}</b>
            {" · "}{fmtWhen(viewingStep.created_at)} · read-only
          </span>
          <span className="hdr-grow"></span>
          <button onClick={restoreStep}>Restore as new step</button>
          <button className="primary" onClick={backToNow}>Back to now</button>
        </div>
      )}
      {agentUpdate && !viewingStep && (
        <div className="restore-banner agent-banner">
          <span>Claude updated this edit: <b>{agentUpdate.label}</b> — it is now your working state (the step before it is in History).</span>
          <span className="hdr-grow"></span>
          <button onClick={() => setAgentUpdate(null)}>OK</button>
        </div>
      )}
      <div className="body-row">
        <main className={`main${viewingStep ? " readonly" : ""}`}>
          {view === "library" && renderLibrary()}
          {view === "timeline" && renderTimeline()}
          {view === "cuts" && renderCuts()}
        </main>
        {ccPinned && (
          <aside className="cc-side">
            <div className="cc-side-head">
              <span className="cc-side-title">Creative context — {activeActLabel}</span>
              <button className="cc-side-close" onClick={toggleCcPinned} title="Unpin">✕</button>
            </div>
            <div className="cc-side-body">
              {renderCreativeContext()}
              <div className="cc-source">from Creative Context agent</div>
            </div>
          </aside>
        )}
      </div>
      {renderAgentPanel()}
      {renderExportModal()}
    </div>
  );
}
