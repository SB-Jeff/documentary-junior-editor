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

// Round versions — each has its own timeline of entries. Latest round is
// the default landing view. Older rounds remain selectable via dropdown.
//
// Round shape:
//   {
//     round_number: 1, version: "v...", round_label: "Round 1",
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
//         text: "..."                                // for non-spoken entry types
//       }
//     ]
//   }
const ROUNDS = [
  // { round_number: 1, version: "v0", round_label: "Round 1", timeline: [] },
];

// The round to render on load (most recent). Build script sets this to the
// latest round's index.
const INITIAL_ROUND_INDEX = 0;

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
  let result = "";
  let pos = 0;
  for (const [s, e] of cuts) {
    result += original.slice(pos, s);
    pos = e;
  }
  result += original.slice(pos);
  return result.replace(/\s+/g, " ").trim();
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

const SAVE_HELPER_URL =
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

// ============================================================================
// InterstitialAddForm — inline editor for inserting a non-spoken entry
// (title card / text interstitial / context beat) between timeline entries.
// Interstitial/title-card text is NOT a verbatim quote, so it is freely
// editable (Cardinal Rule 1 governs spoken quotes only).
// ============================================================================

function InterstitialAddForm({ onAdd, onCancel, positions }) {
  // Default to a title card — the common case (interstitials/context beats are
  // rare). The act-header "Add title card" button opens this; the type select
  // still lets you switch. `positions` (when provided) is a list of
  // { value, label } insertion points so the act-level button can pick WHERE.
  const [type, setType] = useState("title_card");
  const [text, setText] = useState("");
  const [seconds, setSeconds] = useState(3);
  const [position, setPosition] = useState((positions && positions[0] && positions[0].value) || "start");
  const isContext = type === "context_beat";
  return (
    <div className="ins-add" onClick={(e) => e.stopPropagation()}>
      <div className="ins-add-row">
        <select className="ins-add-type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="title_card">Title card — short on-screen text</option>
          <option value="interstitial">Interstitial — factual bridge</option>
          <option value="context_beat">Context beat — research needed</option>
        </select>
        <label className="ins-secs">~<input
          type="number" min="1" max="60" value={seconds}
          onChange={(e) => setSeconds(Math.max(1, Number(e.target.value) || 1))}
        />s</label>
      </div>
      {positions && positions.length > 0 && (
        <select className="ins-add-pos" value={position} onChange={(e) => setPosition(e.target.value)}>
          {positions.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>
      )}
      <textarea
        className="ins-add-text"
        autoFocus
        placeholder={isContext
          ? "What context is needed? (the intent — Jeff/research fills the actual content before FCPXML)"
          : "On-screen / bridge text…"}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="ins-add-actions">
        <button className="btn btn-primary" disabled={!text.trim()}
          onClick={() => onAdd({ type, text: text.trim(), seconds, position })}>Add</button>
        <button className="btn" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

// ============================================================================
// Main component — QuotesView
// ============================================================================

export default function QuotesView() {
  // === Round + view state ===
  const [roundIndex, setRoundIndex] = useState(INITIAL_ROUND_INDEX);
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

  // === Saved cuts (live) ===
  // `cuts` starts as the rounds baked into the page at build time, but the Open
  // menu must reflect what's actually ON DISK — named deliverables saved this
  // session, in another tab, or by the pipeline. refreshDiskCuts() polls the app
  // server's /list and merges any not already present. Disk-only cuts carry
  // `_disk:true` and lazy-load their entries on Open.
  const [cuts, setCuts] = useState(ROUNDS);

  // === Per-round working timeline (deep-clone of canonical at first switch) ===
  const [workingByRound, setWorkingByRound] = useState(() => {
    const init = {};
    ROUNDS.forEach((r, i) => {
      init[i] = JSON.parse(JSON.stringify(r.timeline || []));
    });
    return init;
  });
  const [pendingOpsByRound, setPendingOpsByRound] = useState(() => {
    const init = {};
    ROUNDS.forEach((_, i) => { init[i] = []; });
    return init;
  });

  const getTimeline = () => workingByRound[roundIndex] || [];
  const getPendingOps = () => pendingOpsByRound[roundIndex] || [];

  // Fetch the on-disk saved cuts and merge any new ones into `cuts` so the Open
  // menu is live. Best-effort: if the app server isn't reachable, the baked
  // list still shows. Called on mount, after a save, and when opening Open.
  async function refreshDiskCuts() {
    if (typeof fetch !== "function") return;
    const rel = `handoffs/${PROJECT_META.slug}/editing-versions`;
    try {
      const res = await fetch(`${SAVE_HELPER_URL}/list?path=${encodeURIComponent(rel)}`);
      if (!res.ok) return;
      const data = await res.json();
      if (!data || !data.ok || !Array.isArray(data.cuts)) return;
      setCuts((prev) => {
        const known = new Set(prev.map((c) => c.version));
        const additions = data.cuts
          .filter((c) => !known.has(c.stem))
          .map((c) => ({
            round_number: c.round ?? null,
            version: c.stem,
            round_label: c.cut_name || (/^v\d+$/.test(c.stem) ? `Round ${c.round ?? c.stem.slice(1)}` : c.stem),
            cut_name: c.cut_name || null,
            timeline: [],          // lazy-loaded on Open
            _disk: true,
            _path: c.path,
            _entryCount: c.entry_count,
          }));
        return additions.length ? [...prev, ...additions] : prev;
      });
    } catch (_) { /* server down — keep the baked list */ }
  }

  useEffect(() => { refreshDiskCuts(); /* eslint-disable-next-line */ }, []);
  // Per-round Talk-to-agent batch counter. Each op is tagged with the batch it
  // was made in; Send advances the counter so the panel clears for the next
  // batch while the cumulative log keeps every batch.
  const [batchByRound, setBatchByRound] = useState(() => {
    const init = {}; ROUNDS.forEach((_, i) => { init[i] = 1; }); return init;
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
  // Insertion slot for a new interstitial: refId of the entry to insert after,
  // or `start:${act}` for the head of an act.
  const [addingAfterId, setAddingAfterId] = useState(null);

  // === Live-partner agent panel state (M5 redesign) ===
  // The old clipboard "Send batch" model is gone. The agent reads the viewer's
  // live state from disk (viewer-state.json) on its turn; Jeff just edits and
  // talks in chat. This panel is a STATUS surface, not a send surface.
  const [sendPanelOpen, setSendPanelOpen] = useState(false);
  // The note Jeff is composing for the agent right now ("tell me now" — it rides
  // in viewer-state.json and is consumed when the agent next reads). NOT a queue.
  const [batchNote, setBatchNote] = useState("");
  // Quotes Jeff tagged with "Point at this" — { entry_id, label }. Travel in the
  // live state alongside the note; cleared when the agent catches up.
  const [pointedAt, setPointedAt] = useState([]);

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

  // === Top-bar Save / Open / Export-to-Final-Cut menus (M3 §5 redesign) ===
  // The legacy "Round N" <select> is replaced by three header buttons, each
  // toggling a small inline panel. Only one is open at a time. The Open panel
  // lists saved cuts (ROUNDS — editing-versions v[N].json + any named saves) and
  // loads one (reusing the round-switch / roundIndex path). The Save panel
  // re-persists the current arrangement (overwrite) or writes a NEW NAMED
  // deliverable keyed on a typed name. The Export panel consolidates the two
  // FCPXML export flows (Timeline → -tight file, Full timeline → non-suffixed).
  const [topMenu, setTopMenu] = useState(null);   // "save" | "open" | "export" | null
  const [newCutName, setNewCutName] = useState("");  // typed name for "Save as new"
  const [saveStatus, setSaveStatus] = useState({ text: "", cls: "" });

  // === Live autosave / persistence status (M4 — persistent app shell) ===
  // The viewer is no longer a throwaway chat artifact: it runs as a persistent
  // local app and shares its working state with the Edit Agent through a single
  // file on disk, handoffs/<slug>/viewer-state.json, autosaved (debounced) on
  // every edit. SKILL-edit reads that file at the top of each of its turns to
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
        const card = el && el.closest ? el.closest(".tl-card") : null;
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

  // ====== Saved cuts (named deliverables) — Save / Save-as-new ======
  // A project has MANY named deliverables (long cut + social shorts), each a
  // snapshot of the current Timeline arrangement + trims + tier assignments in
  // handoffs/<slug>/editing-versions/<name>.json (SPEC §3.3). The current cut is
  // ROUNDS[roundIndex]; its on-disk file stem is `version` ("v3" or a slugified
  // name). "Save changes" overwrites that file; "Save as new" writes a NEW file
  // keyed on a typed NAME (slugified). Both reuse the persistFile() path.

  // Slugify a typed deliverable name for the on-disk file stem.
  function slugifyName(name) {
    return (name || "")
      .trim()
      .toLowerCase()
      .replace(/['"]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  // Build the editing-versions payload for the current Timeline arrangement.
  // `roundField` keeps the legacy numeric `round` for v[N] files; named saves
  // carry the human name in `cut_name` while leaving `round` as the source round
  // number so downstream tooling that reads `round` still works.
  function buildCutPayload(roundField, cutName) {
    const payload = {
      schema_version: 5,
      round: roundField,
      project_slug: PROJECT_META.slug,
      target_runtime_seconds: PROJECT_META.target_seconds,
      entries: getTimeline(),
    };
    if (cutName) payload.cut_name = cutName;
    return payload;
  }

  async function persistCut(relPath, downloadName, payload, okWord) {
    const json = JSON.stringify(payload, null, 2);
    setSaveStatus({ text: "Saving…", cls: "" });
    const { ok, method, detail } = await persistFile(relPath, json, { downloadName });
    if (!ok) {
      setSaveStatus({ text: `Save failed: ${detail}`, cls: "err" });
      return false;
    }
    if (method === "download") {
      setSaveStatus({ text: `Downloaded ${downloadName} — move it into ${relPath}, then reload.`, cls: "warn" });
    } else {
      setSaveStatus({ text: `${okWord} → ${detail}. Reload to see it under Open.`, cls: "ok" });
    }
    return true;
  }

  // Overwrite the CURRENT cut's editing-versions file with the current
  // arrangement. Keys on ROUNDS[roundIndex].version (the file stem), falling
  // back to v<round_number> for legacy rounds without an explicit version.
  async function saveChangesToCut() {
    const round = cuts[roundIndex];
    if (!round) { setSaveStatus({ text: "No cut to save into yet — use Save as new.", cls: "warn" }); return; }
    const stem = round.version || `v${round.round_number}`;
    const relPath = `handoffs/${PROJECT_META.slug}/editing-versions/${stem}.json`;
    const payload = buildCutPayload(round.round_number, round.cut_name || round.round_label);
    await persistCut(relPath, `${stem}.json`, payload, `Saved “${round.round_label}”`);
  }

  // Write a NEW named deliverable to editing-versions/<slug>.json, keyed on a
  // typed NAME (not v[N]). The source round number is preserved in `round`.
  async function saveAsNamedCut() {
    const name = newCutName.trim();
    const stem = slugifyName(name);
    if (!stem) { setSaveStatus({ text: "Type a name for the new cut first.", cls: "warn" }); return; }
    if (/^v\d+$/.test(stem)) { setSaveStatus({ text: "That name is reserved for numbered rounds — pick another.", cls: "warn" }); return; }
    if (cuts.some((r) => r.version === stem) && !confirm(`A saved cut named “${name}” already exists. Overwrite it?`)) return;
    const round = cuts[roundIndex];
    const relPath = `handoffs/${PROJECT_META.slug}/editing-versions/${stem}.json`;
    const payload = buildCutPayload(round ? round.round_number : cuts.length + 1, name);
    const ok = await persistCut(relPath, `${stem}.json`, payload, `Saved new cut “${name}”`);
    if (ok) { setNewCutName(""); refreshDiskCuts(); }
  }

  // Switch the viewer to a saved cut (Open panel). Disk-only cuts (saved this
  // session / in another tab / by the pipeline) lazy-load their entries from the
  // app server on first open. Keeps the unsynced-tweaks guard.
  async function openCut(nextIndex) {
    if (nextIndex === roundIndex) { setTopMenu(null); return; }
    if (getPendingOps().length > 0) {
      if (!confirm(`You have ${getPendingOps().length} unsynced tweaks on the current cut. Open another cut anyway? Unsynced tweaks stay scoped to their cut.`)) {
        return;
      }
    }
    const cut = cuts[nextIndex];
    // Lazy-load a disk-only cut's entries the first time it's opened.
    if (cut && cut._disk && !workingByRound[nextIndex]) {
      setSaveStatus({ text: `Opening “${cut.round_label}”…`, cls: "" });
      let entries = null;
      try {
        const res = await fetch(`${SAVE_HELPER_URL}/read?path=${encodeURIComponent(cut._path)}`);
        const data = res.ok ? await res.json() : null;
        if (data && data.ok && data.data) entries = data.data.entries || [];
      } catch (_) { /* fall through to error */ }
      if (!entries) {
        setSaveStatus({ text: `Couldn't load “${cut.round_label}” — is the app server running?`, cls: "err" });
        return;
      }
      setWorkingByRound((prev) => ({ ...prev, [nextIndex]: JSON.parse(JSON.stringify(entries)) }));
      setPendingOpsByRound((prev) => ({ ...prev, [nextIndex]: prev[nextIndex] || [] }));
      setSaveStatus({ text: "", cls: "" });
    }
    setRoundIndex(nextIndex);
    setTopMenu(null);
  }

  // ====== Live autosave → viewer-state.json (M4) ======

  // The single agent-readable snapshot of the viewer's current working state.
  // Shape is deliberately flat and self-describing so SKILL-edit can read the
  // whole cut, what is in/out, what Jeff just changed, and where his attention
  // is — from ONE file, on each of its turns. Membership lives on each entry
  // (tight = Timeline, loose = Cuts); not-used Library quotes are SOURCE_QUOTES
  // with no entry, so the agent reconstructs the Library from its baked-in pool
  // plus `source_act_overrides` (Jeff's Library recategorizations).
  function buildLiveState() {
    const round = cuts[roundIndex];
    const tl = getTimeline();
    const ops = getPendingOps();
    return {
      schema_version: 1,
      kind: "viewer-live-state",
      project_slug: PROJECT_META.slug,
      project_title: PROJECT_TITLE,
      generated_at: new Date().toISOString(),
      open_cut: round
        ? { round_number: round.round_number, version: round.version, label: round.round_label || `Round ${round.round_number}`, cut_name: round.cut_name || null }
        : null,
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
      // What Jeff is telling the agent right now — a free-text note plus any
      // quotes he tagged with "Point at this" (exact entry_id handles). This is
      // "tell me now," consumed when the agent next reads. Null when nothing.
      pending_message: (batchNote.trim() || pointedAt.length)
        ? {
            note: batchNote.trim() || null,
            pointed_at: pointedAt.map((p) => ({ entry_id: p.entry_id, ref: p.label })),
          }
        : null,
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
  // in-flight write if a newer change already superseded it.
  useEffect(() => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(async () => {
      const seq = ++autosaveSeq.current;
      setPersistState((p) => ({ ...p, state: "saving" }));
      const relPath = `handoffs/${PROJECT_META.slug}/viewer-state.json`;
      const json = JSON.stringify(buildLiveState(), null, 2);
      const res = await persistFile(relPath, json, { allowDownload: false });
      if (seq !== autosaveSeq.current) return;  // a newer write is already queued
      if (res.ok && (res.method === "cowork" || res.method === "helper")) {
        setPersistState({ state: "saved", at: Date.now(), detail: res.detail || relPath });
      } else {
        setPersistState({ state: "offline", at: Date.now(), detail: res.detail || "app server not running" });
      }
      // The old clipboard "Send" used to persist the tweak log (the Editing
      // Coach's training record). With Send gone, fold it into the autosave so
      // every correction + Jeff's live note still reach disk. Best-effort.
      writeTweakLog();
    }, 700);
    return () => { if (autosaveTimer.current) clearTimeout(autosaveTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workingByRound, pendingOpsByRound, roundIndex, view, timelineMode, actFilter, speakerFilter, batchNote, pointedAt, dirtySinceSend, sourceActOverrides]);

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
    const round = cuts[roundIndex];
    const filename = `trimmed-quotes-v${round.round_number}${win === "tight" ? "-tight" : ""}.json`;
    const relPath = `handoffs/${PROJECT_META.slug}/${filename}`;
    const payload = {
      schema_version: 5,
      round: round.round_number,
      project_slug: PROJECT_META.slug,
      window: win,
      target_runtime_seconds: PROJECT_META.target_seconds,
      entries: filtered,
    };
    const json = JSON.stringify(payload, null, 2);
    const prompt =
`You are the FCPXML Agent. Read documentary-junior-editor/SKILL-fcpxml-params.md and documentary-junior-editor/SKILL-fcpxml.md and follow them exactly. The project folder is mounted.

Build the ${label.toUpperCase()} cut for ${PROJECT_META.slug}. Read ${relPath} (just written from the viewer — ${win} window, ${filtered.length} entries) plus the project's handoff context (fcpxml-params, edit-handoff, act-structure) per handoffs/pipeline-state.json.

Cross-reference timecodes against the captioned FCPXMLs in XML/exports/, branch generation by per-interview clip_type, and emit one clip per source segment per timeline entry. Save to XML/imports/${PROJECT_META.slug}_${win}_cut_v${round.round_number}.fcpxml. Update handoffs/${PROJECT_META.slug}/pipeline-state.json.

Set model to Sonnet 4.6.`;
    setExportCopied(false);
    const res = await persistFile(relPath, json, { downloadName: filename });
    // Modal copy distinguishes only "written to disk" vs "downloaded" vs "fail".
    const wrote = res.method === "download" ? "download"
      : res.ok ? "disk" : "fail";
    if (res.ok && res.method !== "download") {
      await writeTweakLog();  // best-effort: persist the override log alongside the cut
    }
    setExportInfo({ win, label, count: filtered.length, time: fmtSec(totalSec), file: relPath, filename, prompt, wrote });
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
  // rides in viewer-state.json's pending_message so the agent knows exactly
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

  // ====== Agent read-acknowledgement (M5 live loop) ======
  // The Edit Agent drops handoffs/<slug>/agent-cursor.json each turn after it
  // reads viewer-state.json (see SKILL-edit). We poll it so the staleness cue
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

  // When the agent catches up (transition behind → caught-up), consume the
  // staged note + pointed-at chips — they were "tell me now," and now it knows.
  const prevBehindRef = useRef(false);
  useEffect(() => {
    if (prevBehindRef.current && agentConnected && !agentBehind) {
      setBatchNote("");
      setPointedAt([]);
    }
    prevBehindRef.current = agentBehind;
  }, [agentBehind, agentConnected]);

  // ====== Interstitial insertion ======

  // refId === null inserts at the head of `act`; otherwise after that entry.
  function insertInterstitial(refId, act, fields) {
    const newId = `ic-${Date.now().toString(36)}`;
    const newEntry = {
      entry_id: newId,
      _subLabel: null,
      source_quote_id: null,
      type: fields.type,
      part: act,
      membership: "tight",
      _editCuts: [],
      notes: "",
      estimated_seconds: fields.seconds,
    };
    if (fields.type === "context_beat") {
      newEntry.intent = fields.text;
      newEntry.research_needed = true;
      newEntry.text = "";
    } else {
      newEntry.text = fields.text;
    }
    const typeName = fields.type.replace("_", " ");
    applyLocalEdit("add_interstitial",
      (tl) => {
        if (refId === null) {
          const idx = tl.findIndex((e) => entryActOf(e) === act);
          if (idx < 0) tl.push(newEntry); else tl.splice(idx, 0, newEntry);
        } else {
          const idx = tl.findIndex((e) => e.entry_id === refId);
          if (idx < 0) tl.push(newEntry); else tl.splice(idx + 1, 0, newEntry);
        }
      },
      `Added ${typeName} "${(fields.text || "").slice(0, 40)}" in ${act}`,
      {
        change_type: "add",
        entry_id: newId,
        before: null,
        after: { entry_id: newId, type: fields.type, part: act, text: fields.text },
      }
    );
    setAddingAfterId(null);
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
    const round = cuts[roundIndex];
    if (!round) return { ok: false, reason: "no round" };
    const payload = {
      schema_version: 3,
      project_slug: PROJECT_META.slug,
      round: round.round_number,
      round_version: round.version,
      generated_at: new Date().toISOString(),
      baseline: `round ${round.round_number} (${round.version})`,
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
    const relPath = `handoffs/${PROJECT_META.slug}/tweak-log-v${round.round_number}.json`;
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
  const currentCut = cuts[roundIndex] || null;
  const toggleTopMenu = (m) => {
    setSaveStatus({ text: "", cls: "" });
    if (m === "open") refreshDiskCuts();  // make the Open list reflect disk
    setTopMenu((cur) => (cur === m ? null : m));
  };

  // Body of the act-scoped Creative-context panel. Reads PROJECT_META.acts
  // ([{ label, roadmap }]) and PROJECT_META.premise — both emitted by the build
  // script from the Creative Context handoffs (degrade to "" when absent).
  // M4 persistence indicator. Honest about whether the agent can see edits:
  // "saved" (green) = viewer-state.json written to disk; "saving" (amber pulse);
  // "offline" (grey) = no app server reachable, so the agent is blind to edits
  // until you start scripts/viewer_save_server.py; "error" (red) = a write tried
  // and failed.
  const renderPersistIndicator = () => {
    const s = persistState.state;
    const map = {
      idle:    { cls: "idle",    glyph: "○", text: "Live state" },
      saving:  { cls: "saving",  glyph: "◌", text: "Saving…" },
      saved:   { cls: "saved",   glyph: "●", text: "Saved" },
      offline: { cls: "offline", glyph: "○", text: "Offline" },
      error:   { cls: "error",   glyph: "▲", text: "Save failed" },
    };
    const v = map[s] || map.idle;
    const tip = s === "offline"
      ? "The viewer can't reach the app server, so the Edit Agent can't see your edits. Run: python3 scripts/viewer_save_server.py --serve <built index.html> --root <project root>"
      : s === "saved"
        ? `Working state autosaved to ${persistState.detail || "viewer-state.json"} — the Edit Agent reads it each turn.`
        : "Your working state is shared with the Edit Agent via viewer-state.json on disk.";
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

  const renderHeader = () => (
    <div className="hdr">
      <div className="hdr-row1">
       <div className="hdr-row1-inner">
        {/* Header identity (option 2): eyebrow "Client · Project" over the edit
            name (the open cut). Eyebrow falls back to PROJECT_TITLE when client/
            project aren't set; the headline names whichever cut is open so a
            window is identifiable when several deliverables share a project. */}
        <div className="hdr-identity">
          <div className="hdr-eyebrow">
            {[PROJECT_META.client, PROJECT_META.project].filter(Boolean).join(" · ") || PROJECT_TITLE}
          </div>
          <h1 className="hdr-title">
            {currentCut
              ? (currentCut.cut_name || currentCut.round_label || `Round ${currentCut.round_number}`)
              : PROJECT_TITLE}
          </h1>
        </div>
        {/* Top-bar actions (M3 §5): Save · Open · Export to Final Cut. Replaces
            the legacy Round <select> — its load/save jobs move to Open/Save. */}
        <div className="topbar-actions" data-topbar="1">
          <button
            className={`tb-btn${topMenu === "save" ? " active" : ""}`}
            onClick={() => toggleTopMenu("save")}
          >Save</button>
          <button
            className={`tb-btn${topMenu === "open" ? " active" : ""}`}
            onClick={() => toggleTopMenu("open")}
          >Open</button>
          {topMenu === "save" && (
            <div className="tb-panel" data-topbar="1">
              <div className="tb-panel-title">Save</div>
              <div className="tb-panel-sub">
                Current cut: <strong>{currentCut ? (currentCut.round_label || `Round ${currentCut.round_number}`) : "—"}</strong>
              </div>
              <button
                className="btn tb-panel-btn"
                disabled={!currentCut}
                onClick={saveChangesToCut}
              >Save changes to this cut</button>
              <div className="tb-panel-divider"><span>or</span></div>
              <div className="tb-saveas">
                <input
                  className="tb-input"
                  type="text"
                  placeholder="New cut name (e.g. Social short)"
                  value={newCutName}
                  onChange={(e) => setNewCutName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") saveAsNamedCut(); }}
                />
                <button
                  className="btn tb-panel-btn"
                  disabled={!newCutName.trim()}
                  onClick={saveAsNamedCut}
                >Save as new</button>
              </div>
              {saveStatus.text && <div className={`tb-status ${saveStatus.cls}`}>{saveStatus.text}</div>}
            </div>
          )}

          {topMenu === "open" && (
            <div className="tb-panel" data-topbar="1">
              <div className="tb-panel-title">Open a saved cut</div>
              {cuts.length === 0 ? (
                <div className="tb-empty">No saved cuts yet.</div>
              ) : (
                <ul className="tb-cutlist">
                  {cuts.map((r, i) => (
                    <li key={i} className={i === roundIndex ? "current" : ""}>
                      <span className="tb-cutname">
                        {r.round_label || `Round ${r.round_number}`}
                        {i === roundIndex && <span className="tb-current-tag">current</span>}
                      </span>
                      <button
                        className="btn tb-open-btn"
                        disabled={i === roundIndex}
                        onClick={() => openCut(i)}
                      >Open</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

        </div>
        {/* Autosave status — quiet, beside the save controls (M4). */}
        {renderPersistIndicator()}

        {/* RIGHT CLUSTER: the work — view tabs (dividers kept) + export the
            Timeline. Export lives here because it acts on the Timeline. */}
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
                {m.mode === "cuts" && looseEntries.length > 0 && (
                  <span className="cuts-count">{looseEntries.length}</span>
                )}
              </button>
            ))}
          </div>
          <span className="hdr-right-sep" aria-hidden="true"></span>
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
      {(
        <div className="hdr-row2">
         <div className="hdr-row2-inner">
          {/* Line 1: Act filter + Cut block */}
          <div className="hdr-filter-line">
            <div className="filter-group">
              <span className="group-label">Act</span>
              <button
                className={`chip${actFilter === "all" ? " active" : ""}`}
                onClick={() => setActFilter("all")}
              >All</button>
              {PROJECT_META.act_labels.filter((a) => a !== "Orphan").map((label, i) => (
                <button
                  key={label}
                  className={`chip${actFilter === label ? " active" : ""}`}
                  onClick={() => setActFilter(label)}
                  title={label}
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
                    {renderCreativeContext()}
                    <div className="cc-source">from Creative Context agent</div>
                  </div>
                )}
              </div>
            </div>
            {/* Timeline metric (Timeline view only), right-aligned on the Act
                line. Export moved to the top-bar "Export to Final Cut" menu
                (M3 §5) — both FCPXML flows (Timeline → -tight, Full timeline →
                non-suffixed) are consolidated there. */}
            {view === "timeline" && (
              <div className="win-block">
                <span className="win-metric tight">
                  <span className="val">{activeEntries}</span> entries · <span className="val">{fmtSec(activeSec)}</span>
                </span>
              </div>
            )}
          </div>
          {/* Line 2: Speaker filter, beneath Act */}
          <div className="hdr-filter-line">
            <div className="filter-group">
              <span className="group-label">Speaker</span>
              <button
                className={`chip${speakerFilter === "all" ? " active" : ""}`}
                onClick={() => setSpeakerFilter("all")}
              >All</button>
              {(PROJECT_META.speakers || []).map((s) => (
                <button
                  key={s.slug}
                  className={`chip${speakerFilter === s.slug ? " active" : ""}`}
                  onClick={() => setSpeakerFilter(s.slug)}
                >
                  {s.name}
                </button>
              ))}
            </div>
            {view === "timeline" && (
              <div className="reveal-block">
                {/* Review | Edit segmented toggle (M3 T2 §A) — Timeline only. */}
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
                {/* Open all / Collapse all live in Edit mode only. */}
                {timelineMode === "edit" && (
                  <>
                    <span className="group-label">Quotes</span>
                    <button onClick={() => revealAll(true)}>Open all</button>
                    <button onClick={() => revealAll(false)}>Collapse all</button>
                  </>
                )}
              </div>
            )}
          </div>
         </div>
        </div>
      )}
    </div>
  );

  // ============================================================================
  // Quote Library view
  // ============================================================================

  const renderLibrary = () => {
    const realActs = PROJECT_META.act_labels.filter((a) => a !== "Orphan");
    const inCutIds = hideInCut ? sourceIdsInCut() : null;
    const needle = librarySearch.trim().toLowerCase();
    const matchesSearch = (q) => !needle
      || (q.quote || "").toLowerCase().includes(needle)
      || (q.rationale || "").toLowerCase().includes(needle);
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
            placeholder="Search quote text or rationale…"
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
            <button
              className="btn btn-drop"
              onClick={() => {
                if (!confirm(`Drop ${typeLabel} ${entry.entry_id} back to the Library?`)) return;
                applyLocalEdit("drop_entry",
                  (tl) => { const i = tl.findIndex((x) => x.entry_id === entry.entry_id); if (i >= 0) tl.splice(i, 1); },
                  `Dropped ${typeLabel} ${entry.entry_id}`,
                  { change_type: "drop", entry_id: entry.entry_id, before: { entry_id: entry.entry_id, type: entry.type, part: entryActOf(entry) }, after: null }
                );
              }}
            >Drop <span className="verb-dest">→ Library</span></button>
          </div>
        </div>
      </div>
    );
  };

  // A short preview label for an entry, used in the "Add title card" position
  // picker ("After: Shane — So technology is not…").
  const entryPositionLabel = (entry) => {
    const src = findSourceQuote(entry.source_quote_id);
    const who = src?.speaker || entry.speaker
      || ({ title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "card");
    const txt = (trimmedQuoteText(entry) || entry.text || "").trim();
    const words = txt.split(/\s+/).filter(Boolean).slice(0, 5).join(" ");
    return `After: ${who}${words ? " — " + words + "…" : ""}`;
  };

  // Position options for inserting a card into an act: at the start, or after
  // any existing entry. `entries` is the act's entries in display order.
  const actInsertPositions = (entries) => [
    { value: "start", label: "At the start of this act" },
    ...entries.map((e) => ({ value: e.entry_id, label: entryPositionLabel(e) })),
  ];

  // Act-header "Add title card" control (option C). One button per act instead
  // of a "+ interstitial" row between every card. Opens the add form (which
  // defaults to a title card and includes a position picker) right under the
  // act header. `addingAfterId` doubles as the open-state key: `actadd:<act>`.
  const renderActAddControl = (act, entries) => {
    const slot = `actadd:${act}`;
    const open = addingAfterId === slot;
    return (
      <button
        className={`act-add-btn${open ? " active" : ""}`}
        onClick={() => setAddingAfterId(open ? null : slot)}
        title="Add a title card, interstitial, or context beat to this act"
      >+ Add title card</button>
    );
  };

  const renderActAddForm = (act, entries) => {
    if (addingAfterId !== `actadd:${act}`) return null;
    return (
      <div className="ins-slot" data-topbar="1">
        <InterstitialAddForm
          positions={actInsertPositions(entries)}
          onAdd={(fields) => {
            const refId = fields.position === "start" ? null : fields.position;
            insertInterstitial(refId, act, fields);
          }}
          onCancel={() => setAddingAfterId(null)}
        />
      </div>
    );
  };

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
              onClick={() => {
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
              }}
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
    const editBtn = (
      <span className="rc-tools">
        <button className="rc-tool edit" onClick={() => toggleReveal(entry.entry_id)}>✎ Edit</button>
      </span>
    );
    if (!isSpoken) {
      const typeLabel = { title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "Interstitial";
      const insText = entry.type === "context_beat" ? `[${entry.intent || "context needed"}]` : (entry.text || "");
      return (
        <div className={`read-card${markCls}`} id={entry.entry_id} key={entry.entry_id}>
          <div className="rc-head">
            <span className="ins-type-badge">{typeLabel}</span>
            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
            {chip}
            {editBtn}
          </div>
          <p className="rc-quote rc-interstitial">{insText}</p>
        </div>
      );
    }
    const src = findSourceQuote(entry.source_quote_id);
    const speakerC = (src && speakerColors[src.speakerSlug]) || { bg: COLORS.surface2, fg: COLORS.textMuted };
    const speakerLabel = src?.speaker || entry.speaker || "?";
    return (
      <div className={`read-card${markCls}`} id={entry.entry_id} key={entry.entry_id}>
        <div className="rc-head">
          <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>{speakerLabel}</span>
          <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
          {chip}
          {editBtn}
        </div>
        <p className="rc-quote">"{trimmedQuoteText(entry)}"</p>
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
                <span className="act-header-actions">{renderActAddControl(act, entries)}</span>
              </div>
              {renderActAddForm(act, entries)}
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
    const { win, label, count, time, file, filename, prompt, wrote } = exportInfo;
    const step1 = wrote === "disk"
      ? <><span className="export-ok">✓ Done</span> — wrote <code>{file}</code> (the {label} cut: {count} entries · {time}).</>
      : wrote === "download"
      ? <><span className="export-ok">✓ Downloaded</span> <code>{filename}</code> (the {label} cut: {count} entries · {time}). Drop it in at <code>{file}</code> in the project.</>
      : <span className="export-warn">⚠ Could not write the cut file automatically — paste the prompt and have the agent re-derive, or write {file} by hand.</span>;
    const copyPrompt = () => {
      const ta = document.getElementById("export-prompt-ta");
      if (ta) ta.select();
      try { navigator.clipboard.writeText(prompt); } catch (_) {}
      setExportCopied(true);
    };
    return (
      <div className="export-overlay" onClick={() => setExportInfo(null)}>
        <div className="export-modal" onClick={(e) => e.stopPropagation()}>
          <h3>Send the <span className={`export-win ${win}`}>{label}</span> cut to the FCPXML Agent</h3>
          <p className="export-sub">The viewer writes the cut to disk, then hands the build to the FCPXML Agent — the tool built to caption-match, branch by clip type, and handle FCP import issues. (The viewer doesn't build the XML itself; that step is failure-prone without the agent around it.)</p>
          <div className="export-step">
            <span className="export-num">1</span>
            <div className="export-step-body">{step1}</div>
          </div>
          <div className="export-step">
            <span className="export-num">2</span>
            <div className="export-step-body">
              Open a new Cowork task and paste this FCPXML Agent prompt:
              <div className="export-promptbox">
                <textarea className="export-prompt" id="export-prompt-ta" readOnly value={prompt} />
                <button className="export-copy" onClick={copyPrompt}>{exportCopied ? "Copied ✓" : "Copy"}</button>
              </div>
            </div>
          </div>
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
              <div className="sp-section">
                <div className="sp-section-head">
                  <span className="sp-section-title">Tell the agent now</span>
                  <span className="sp-optional">rides with your next message</span>
                </div>
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
                  placeholder="A note for the agent — it reads this next turn. Or just talk to it in chat."
                  value={batchNote}
                  onChange={(e) => setBatchNote(e.target.value)}
                />
              </div>
            </div>
            <div className="sp-foot">
              <span className="sp-batchnote">No Send button — your edits autosave to disk and the agent reads them when you message it in chat.</span>
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
    if (topMenu === null && !creativeOpen) return;
    const onDoc = (e) => {
      if (e.target.closest && e.target.closest('[data-topbar="1"]')) return;
      setTopMenu(null);
      setCreativeOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [topMenu, creativeOpen]);

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
    .cc-block { margin-bottom:12px; }
    .cc-block:last-of-type { margin-bottom:0; }
    .cc-block-label { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.06em;
      color: var(--text-subtle); margin-bottom:3px; }
    .cc-roadmap { margin:0; font-size:13px; line-height:1.55; color: var(--text); }
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

    /* === M3 T2 §C/§D — Point at this + Rejoin + Split tag === */
    .split-tag { font-size:10px; font-weight:600; padding:1px 7px; border-radius:8px;
      background: var(--probable-soft); color: var(--probable); letter-spacing:.02em; }
    .btn-point { background: transparent; color: var(--text-muted); border:1px solid var(--border-strong); }
    .btn-point:hover { color: var(--text); border-color: var(--text-muted); }
    /* Push the agent-reference action to the right edge of the card action row,
       separating it from the disposition buttons (Cut / Rejoin / Drop). */
    .tl-actions .tl-action-right { margin-left: auto; }
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
  `;

  return (
    <div className="viewer">
      <style>{m2Styles}</style>
      {renderHeader()}
      <main className="main">
        {view === "library" && renderLibrary()}
        {view === "timeline" && renderTimeline()}
        {view === "cuts" && renderCuts()}
      </main>
      {renderAgentPanel()}
      {renderExportModal()}
    </div>
  );
}
