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
// Architecture (v5.0):
//   - Three top-level views: Quote Library / Timeline / Review
//   - Quote Library shows every source quote + orphans; segments backend-only
//   - Timeline uses v4.0.1-style quote-block cards with character-range trim,
//     scissors split, drag, ↑/↓, two-tier recommendation toggle
//   - Rough/Tight sub-toggle filters Timeline by must-keep+probable-keep vs
//     must-keep only; Export button is contextual to the active cut
//   - Round dropdown loads from baked-in rounds; "Save as new round" writes
//     directly to disk via window.cowork.callMcpTool (graceful no-op outside
//     Cowork)
//   - Send-to-agent panel: pending tweaks + editorial commentary in one
//     surface; clipboard-based send (paste into chat)
//   - Per-card Comment-on-this routes to the panel's commentary textarea
//   - Export writes current working state to the round file then invokes
//     build_fcpxml.py — self-contained, no Sync required first
//
// ============================================================================
// DATA BLOCK — Replaced per-project by build_quotes_viewer.py at build time.
// ============================================================================

const PROJECT_TITLE = "Subject Name — Project Name";

// Project metadata (act labels, target runtime, speakers).
const PROJECT_META = {
  slug: "project-slug",
  ssd_root: "/Volumes/PROJECT_SSD",  // for callMcpTool save/export paths
  target_seconds: 120,
  // Order matters — drives section ordering. "Orphan" should not appear here.
  act_labels: ["Act 1", "Act 2", "Act 3"],
  // Speaker list — used by the Speaker filter chips. slug values must match
  // source_quote.speakerSlug for filtering to work.
  speakers: [
    // { name: "Speaker Name", slug: "speaker-slug", role: "patient", primary: true },
  ],
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
//         runtime_recommendation: "must-keep" | "probable-keep",
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

// Recommendation cycle order for the clickable rec badge. Item 7 inserts
// "tight-candidate" between must-keep and probable-keep.
const REC_CYCLE = {
  "must-keep": "probable-keep",
  "probable-keep": "must-keep",
};

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
  const words = [];
  const re = /(\S+)(\s*)/g;
  let m;
  while ((m = re.exec(original)) !== null) {
    words.push({ word: m[1], boundaryAfter: m.index + m[0].length });
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
              <span>{w.word}</span>
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

function InterstitialAddForm({ onAdd, onCancel }) {
  const [type, setType] = useState("interstitial");
  const [text, setText] = useState("");
  const [seconds, setSeconds] = useState(3);
  const isContext = type === "context_beat";
  return (
    <div className="ins-add" onClick={(e) => e.stopPropagation()}>
      <div className="ins-add-row">
        <select className="ins-add-type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="interstitial">Interstitial — factual bridge</option>
          <option value="title_card">Title card — short on-screen text</option>
          <option value="context_beat">Context beat — research needed</option>
        </select>
        <label className="ins-secs">~<input
          type="number" min="1" max="60" value={seconds}
          onChange={(e) => setSeconds(Math.max(1, Number(e.target.value) || 1))}
        />s</label>
      </div>
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
          onClick={() => onAdd({ type, text: text.trim(), seconds })}>Add</button>
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
  const [view, setView] = useState("timeline");
  const [cutFilter, setCutFilter] = useState("rough");
  const [speakerFilter, setSpeakerFilter] = useState("all");
  const [actFilter, setActFilter] = useState("all");
  const [reviewScope, setReviewScope] = useState("All");

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
    setPendingOpsByRound((prev) => {
      const list = prev[roundIndex] || [];
      const op = {
        seq: list.length + 1,
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
  }, [roundIndex]);

  // Within-act position of an entry — used to record reorder before/after.
  function actLocalIndex(tl, entryId) {
    const e = tl.find((x) => x.entry_id === entryId);
    if (!e) return -1;
    const act = entryActOf(e);
    return tl.filter((x) => entryActOf(x) === act).findIndex((x) => x.entry_id === entryId);
  }

  function discardAllTweaks() {
    if (getPendingOps().length === 0) return;
    if (!confirm(`Discard ${getPendingOps().length} pending tweak(s) and restore canonical state?`)) return;
    setWorkingByRound((prev) => ({
      ...prev,
      [roundIndex]: JSON.parse(JSON.stringify(ROUNDS[roundIndex].timeline || [])),
    }));
    setPendingOpsByRound((prev) => ({ ...prev, [roundIndex]: [] }));
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

  // === Send-to-agent panel state ===
  const [sendPanelOpen, setSendPanelOpen] = useState(false);
  const [commentary, setCommentary] = useState("");
  const [sendStatus, setSendStatus] = useState({ text: "", cls: "" });

  // === Drag-to-reorder state (pointer-events based) ===
  // Native HTML5 drag-and-drop is unreliable inside Cowork's sandboxed artifact
  // iframe (the regression Jeff hit). Pointer events + setPointerCapture work in
  // every context — plain browser, sandboxed iframe — and are synthetically
  // testable. Reorder is constrained to within an act (cross-act moves use the
  // act-reassign dropdown); ↑/↓ buttons remain as a fallback.
  const [dragId, setDragId] = useState(null);
  const [dragOverId, setDragOverId] = useState(null);
  const dragIdRef = useRef(null);
  const dragOverRef = useRef(null);

  function clearPointerDrag() {
    dragIdRef.current = null;
    dragOverRef.current = null;
    setDragId(null);
    setDragOverId(null);
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

  // ====== Round + save-as-new ======

  async function saveAsNewRound() {
    const newRoundNum = ROUNDS.length + 1;
    const tl = getTimeline();
    const payload = {
      schema_version: 5,
      round: newRoundNum,
      project_slug: PROJECT_META.slug,
      target_runtime_seconds: PROJECT_META.target_seconds,
      entries: tl,
    };
    if (!hasCallMcpTool()) {
      alert("Save new round is only available when the viewer is running inside Cowork.\n\nThe file would have been written to:\n" +
        `${PROJECT_META.ssd_root}/handoffs/${PROJECT_META.slug}/editing-versions/v${newRoundNum}.json`);
      return;
    }
    const json = JSON.stringify(payload, null, 2);
    const dir = `${PROJECT_META.ssd_root}/handoffs/${PROJECT_META.slug}/editing-versions`;
    const filepath = `${dir}/v${newRoundNum}.json`;
    const cmd = `mkdir -p "${dir}" && cat > "${filepath}" <<'__JSON_EOF__'\n${json}\n__JSON_EOF__`;
    const { ok, reason } = await callBash(cmd);
    if (ok) {
      alert(`Round ${newRoundNum} saved to ${filepath}.\n\nReload the viewer to see it in the round dropdown.`);
    } else {
      alert(`Save failed: ${reason}`);
    }
  }

  // ====== Export ======

  async function exportToFCPXML() {
    const tl = getTimeline();
    const filtered = cutFilter === "tight"
      ? tl.filter((e) => e.runtime_recommendation === "must-keep")
      : tl;
    const totalSec = filtered.reduce((a, e) => a + entrySeconds(e), 0);
    if (!hasCallMcpTool()) {
      alert(`Export to FCPXML (${cutFilter} cut, ${filtered.length} clips, ${fmtSec(totalSec)}) is only available when the viewer is running inside Cowork.`);
      return;
    }
    // Self-contained: write current working state, then invoke build_fcpxml.py.
    const round = ROUNDS[roundIndex];
    const payload = {
      schema_version: 5,
      round: round.round_number,
      project_slug: PROJECT_META.slug,
      target_runtime_seconds: PROJECT_META.target_seconds,
      entries: tl,
    };
    const filename = `trimmed-quotes-v${round.round_number}.json`;
    const handoffPath = `${PROJECT_META.ssd_root}/handoffs/${PROJECT_META.slug}/${filename}`;
    const writeCmd = `cat > "${handoffPath}" <<'__JSON_EOF__'\n${JSON.stringify(payload, null, 2)}\n__JSON_EOF__`;
    setSendStatus({ text: "Writing state…", cls: "" });
    const { ok: writeOk, reason: writeReason } = await callBash(writeCmd);
    if (!writeOk) {
      alert(`Export failed at write step: ${writeReason}`);
      setSendStatus({ text: "", cls: "" });
      return;
    }
    setSendStatus({ text: "Running build_fcpxml.py…", cls: "" });
    const buildCmd =
      `cd "${PROJECT_META.ssd_root}/handoffs/${PROJECT_META.slug}" && ` +
      `python3 "${PROJECT_META.ssd_root}/documentary-junior-editor/scripts/build_fcpxml.py" ` +
      `--mode=${cutFilter} --input="${handoffPath}" 2>&1`;
    const { ok: buildOk, result: buildResult, reason: buildReason } = await callBash(buildCmd);
    if (buildOk) {
      await writeTweakLog();  // best-effort: persist override log alongside the export
      const head = typeof buildResult === "string" ? buildResult.slice(0, 800) : "Build succeeded.";
      alert(`Export complete (${cutFilter} cut, ${filtered.length} clips):\n\n${head}`);
      setSendStatus({ text: `Exported ${cutFilter} cut`, cls: "ok" });
      setTimeout(() => setSendStatus({ text: "", cls: "" }), 4000);
    } else {
      alert(`Export build failed: ${buildReason}`);
      setSendStatus({ text: "Export failed", cls: "warn" });
    }
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
    const subEntries = [];
    for (let i = 0; i < boundaries.length - 1; i++) {
      const subText = original.slice(boundaries[i], boundaries[i + 1]).trim();
      if (!subText) continue;
      const sub = letters[i];
      const newId = `${entry.source_quote_id}${sub}`;
      subEntries.push({
        ...entry,
        entry_id: newId,
        _subLabel: sub,
        _editCuts: [],
        notes: (entry.notes ? entry.notes + " " : "") + `(split ${sub} of ${boundaries.length - 1})`,
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
      runtime_recommendation: "probable-keep",
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

  // ====== Send-to-agent panel ======

  function focusCommentary(prefix) {
    setSendPanelOpen(true);
    setCommentary((cur) => {
      if (cur.includes(prefix)) return cur;
      return (cur && !cur.endsWith("\n") ? cur + "\n\n" : cur) + prefix;
    });
    requestAnimationFrame(() => {
      const ta = document.getElementById("send-textarea");
      if (ta) {
        ta.focus();
        ta.setSelectionRange(ta.value.length, ta.value.length);
      }
    });
  }

  function composeSendMessage() {
    const ops = getPendingOps();
    const tl = getTimeline();
    const round = ROUNDS[roundIndex];
    const lines = [];
    if (ops.length > 0) {
      lines.push("I made these tweaks in the viewer:", "");
      ops.forEach((o, i) => lines.push(`${i + 1}. ${o.description}`));
      lines.push("");
    }
    if (commentary.trim()) {
      lines.push(ops.length > 0 ? "Editorial commentary:" : "Editorial feedback from viewer:", "");
      lines.push(commentary.trim(), "");
    }
    if (ops.length > 0) {
      lines.push(`Resulting timeline state (${tl.length} entries) — apply canonically and push update_artifact:`, "");
      lines.push("```json");
      lines.push(JSON.stringify(tl, null, 2));
      lines.push("```", "");
    }
    lines.push(`Baseline: round ${round.round_number} (${round.version})`);
    return lines.join("\n");
  }

  // Persist the round's override log to disk for the Editing Coach Agent.
  // Writes handoffs/[slug]/tweak-log-v[N].json via callBash; no-ops gracefully
  // outside Cowork. Called on Send and Export — the points where the session's
  // tweaks leave the viewer. pendingOps is cumulative (never auto-cleared), so
  // each write captures the full ordered history, reversal pairs included.
  async function writeTweakLog() {
    const ops = getPendingOps();
    if (ops.length === 0 && !commentary.trim()) return { ok: false, reason: "nothing to log" };
    if (!hasCallMcpTool()) return { ok: false, reason: "not in Cowork" };
    const round = ROUNDS[roundIndex];
    const payload = {
      schema_version: 1,
      project_slug: PROJECT_META.slug,
      round: round.round_number,
      round_version: round.version,
      generated_at: new Date().toISOString(),
      baseline: `round ${round.round_number} (${round.version})`,
      commentary: commentary.trim(),
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
    const dir = `${PROJECT_META.ssd_root}/handoffs/${PROJECT_META.slug}`;
    const filepath = `${dir}/tweak-log-v${round.round_number}.json`;
    const json = JSON.stringify(payload, null, 2);
    const cmd = `mkdir -p "${dir}" && cat > "${filepath}" <<'__TWEAKLOG_EOF__'\n${json}\n__TWEAKLOG_EOF__`;
    return await callBash(cmd);
  }

  async function sendToAgent() {
    const text = composeSendMessage();
    let copied = false;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch {
      setSendStatus({ text: "Auto-copy blocked — copy manually", cls: "warn" });
    }
    const logResult = await writeTweakLog();
    if (copied) {
      const suffix = logResult && logResult.ok ? " · tweak log saved" : "";
      setSendStatus({ text: "Copied ✓ — paste into chat" + suffix, cls: "ok" });
      setTimeout(() => setSendStatus({ text: "", cls: "" }), 3500);
    }
  }

  // ====== Filter passes ======

  function passesSourceFilters(q) {
    if (speakerFilter !== "all" && q.speakerSlug !== speakerFilter) return false;
    if (actFilter !== "all" && q.part !== actFilter) return false;
    return true;
  }
  function passesTimelineFilters(e) {
    if (speakerFilter !== "all") {
      const src = findSourceQuote(e.source_quote_id);
      if (!src || src.speakerSlug !== speakerFilter) return false;
    }
    if (actFilter !== "all" && entryActOf(e) !== actFilter) return false;
    if (cutFilter === "tight" && e.runtime_recommendation !== "must-keep") return false;
    return true;
  }

  // ====== Runtime totals ======
  const allEntries = getTimeline();
  const tightEntries = allEntries.filter((e) => e.runtime_recommendation === "must-keep");
  const roughSec = allEntries.reduce((a, e) => a + entrySeconds(e), 0);
  const tightSec = tightEntries.reduce((a, e) => a + entrySeconds(e), 0);
  const activeEntries = cutFilter === "tight" ? tightEntries.length : allEntries.length;
  const activeSec = cutFilter === "tight" ? tightSec : roughSec;

  // ============================================================================
  // Header
  // ============================================================================

  const renderHeader = () => (
    <div className="hdr">
      <div className="hdr-row1">
       <div className="hdr-row1-inner">
        <h1 className="hdr-title">{PROJECT_TITLE}</h1>
        <select
          className="round-select"
          value={roundIndex}
          onChange={(e) => {
            const next = parseInt(e.target.value, 10);
            if (next === -1) {
              saveAsNewRound();
              e.target.value = String(roundIndex);
              return;
            }
            if (getPendingOps().length > 0) {
              if (!confirm(`You have ${getPendingOps().length} unsynced tweaks on the current round. Switch rounds anyway? Unsynced tweaks stay scoped to their round.`)) {
                e.target.value = String(roundIndex);
                return;
              }
            }
            setRoundIndex(next);
          }}
        >
          {ROUNDS.map((r, i) => (
            <option key={i} value={i}>{r.round_label || `Round ${r.round_number}`}</option>
          ))}
          <option value="-1">+ Save current as new round</option>
        </select>
        <div className="mode-toggle">
          {[
            { mode: "timeline", label: "Edit" },
            { mode: "review", label: "Review" },
            { mode: "library", label: "Quote Library" },
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
       </div>
      </div>
      {view !== "review" && (
        <div className="hdr-row2">
         <div className="hdr-row2-inner">
          {/* Act filter */}
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
                Act {i + 1}
              </button>
            ))}
          </div>
          {/* Speaker filter */}
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
          {/* Cut block (Edit view only) */}
          {view === "timeline" && (
            <div className="cut-block">
              <span className="group-label">Cut</span>
              <div className="cut-toggle">
                <button
                  className={cutFilter === "rough" ? "active rough" : ""}
                  onClick={() => setCutFilter("rough")}
                >Rough</button>
                <button
                  className={cutFilter === "tight" ? "active tight" : ""}
                  onClick={() => setCutFilter("tight")}
                >Tight</button>
              </div>
              <span className={`cut-metric cut-metric-${cutFilter}`}>
                <span className="val">{activeEntries}</span> entries · <span className="val">{fmtSec(activeSec)}</span>
              </span>
              <button className="cut-export" onClick={exportToFCPXML}>Export XML</button>
            </div>
          )}
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
    const inScope = SOURCE_QUOTES.filter((q) => !q.is_orphan && passesSourceFilters(q));
    const orphans = SOURCE_QUOTES.filter((q) => q.is_orphan && passesSourceFilters(q));
    const acts = realActs.map((act) => ({
      name: act,
      list: inScope.filter((q) => q.part === act),
    })).filter((a) => a.list.length > 0);

    const renderQuoteCard = (q) => {
      const useCount = getTimeline().filter((e) => e.source_quote_id === q.num).length;
      const inTimeline = useCount > 0;
      const speakerC = speakerColors[q.speakerSlug] || { bg: COLORS.surface2, fg: COLORS.textMuted };
      return (
        <div key={q.num} id={`q-${q.num}`} className={`lib-card${q.is_orphan ? " orphan" : ""}${inTimeline ? " in-tl" : ""}`}>
          <div className="card-head">
            <span className="qid">#{q.num}</span>
            <span className="speaker-tag" style={{ background: speakerC.bg, color: speakerC.fg }}>
              {q.speaker}
            </span>
            <span className="act-tag-static">{q.part}</span>
            <span className="tc">{tcFmt(q.startTC, q.endTC)}</span>
            {inTimeline && <span className="in-tl-pill">in timeline{useCount > 1 ? ` ×${useCount}` : ""}</span>}
            {q.is_orphan && <span className="orphan-pill">orphan</span>}
          </div>
          <p className="quote-text">{q.quote}</p>
          {q.rationale && (
            <div className="rationale">
              <span className="rationale-label">Why:</span> {q.rationale}
            </div>
          )}
          <div className="lib-actions">
            <button
              className="btn btn-primary"
              disabled={inTimeline}
              onClick={() => {
                if (inTimeline) return;
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
                      runtime_recommendation: "probable-keep",
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
                setView("timeline");
              }}
            >
              {inTimeline ? "✓ In timeline" : `Add #${q.num} to timeline`}
            </button>
            <button
              className="btn btn-comment"
              onClick={() => focusCommentary(`About #${q.num} (${q.speaker} — ${q.part}): `)}
            >💬 Comment on this</button>
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
        {acts.map((a) => (
          <section key={a.name} className="act-section">
            <div className="act-header">
              <h2 className="act-title">{a.name}</h2>
              <span className="act-sub">{a.list.length} quote{a.list.length === 1 ? "" : "s"}</span>
            </div>
            {a.list.map(renderQuoteCard)}
          </section>
        ))}
        {orphans.length > 0 && (
          <section className="act-section orphans-section">
            <div className="act-header">
              <h2 className="act-title">Orphans</h2>
              <span className="act-sub">
                {orphans.length} quote{orphans.length === 1 ? "" : "s"} · agent recommends excluding
              </span>
            </div>
            {orphans.map(renderQuoteCard)}
          </section>
        )}
        {acts.length === 0 && orphans.length === 0 && (
          <div className="empty">
            <h3>No quotes match the current filters.</h3>
            <p>Loosen Speaker / Act filters above.</p>
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

  // Shared left-edge drag handle (pointer-events based) — used by both spoken
  // and interstitial cards so reorder behaves identically for every entry type.
  const renderDragHandle = (entry) => (
    <div
      className="tl-drag"
      title="Drag to reorder"
      onPointerDown={(e) => {
        e.preventDefault();
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}
        dragIdRef.current = entry.entry_id;
        dragOverRef.current = entry.entry_id;
        setDragId(entry.entry_id);
        setDragOverId(entry.entry_id);
      }}
      onPointerMove={(e) => {
        if (!dragIdRef.current) return;
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
      }}
      onPointerUp={(e) => {
        try { e.currentTarget.releasePointerCapture(e.pointerId); } catch (_) {}
        finishPointerDrag();
      }}
      onPointerCancel={clearPointerDrag}
    >
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
    const rec = entry.runtime_recommendation || "probable-keep";
    const typeLabel = { title_card: "Title card", interstitial: "Interstitial", context_beat: "Context beat" }[entry.type] || "Interstitial";
    const isContext = entry.type === "context_beat";
    const fieldVal = isContext ? (entry.intent || "") : (entry.text || "");
    return (
      <div
        key={entry.entry_id}
        id={entry.entry_id}
        className={`tl-card tl-interstitial ins-${entry.type} is-${rec}${dragId === entry.entry_id ? " dragging" : ""}${dragOverId === entry.entry_id && dragId !== entry.entry_id ? " drag-over" : ""}`}
      >
        {renderDragHandle(entry)}
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
            </span>
            <button
              className={`rec-badge ${rec}`}
              onClick={() => {
                const next = REC_CYCLE[rec] || "must-keep";
                applyLocalEdit("set_rec",
                  (tl) => { const e2 = tl.find((x) => x.entry_id === entry.entry_id); if (e2) e2.runtime_recommendation = next; },
                  `${entry.entry_id} (${typeLabel}): ${rec} → ${next}`,
                  { change_type: "status_flip", entry_id: entry.entry_id, before: { runtime_recommendation: rec }, after: { runtime_recommendation: next } }
                );
              }}
              title="Click to toggle recommendation"
            >{rec.replace("-", " ")}</button>
            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
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
            <button
              className="btn btn-comment"
              onClick={() => focusCommentary(`About ${entry.entry_id} (${typeLabel}, ${entryActOf(entry)}): `)}
            >💬 Comment on this</button>
            <button
              className="btn btn-danger"
              onClick={() => {
                if (!confirm(`Drop ${typeLabel} ${entry.entry_id}?`)) return;
                applyLocalEdit("drop_entry",
                  (tl) => { const i = tl.findIndex((x) => x.entry_id === entry.entry_id); if (i >= 0) tl.splice(i, 1); },
                  `Dropped ${typeLabel} ${entry.entry_id}`,
                  { change_type: "drop", entry_id: entry.entry_id, before: { entry_id: entry.entry_id, type: entry.type, part: entryActOf(entry) }, after: null }
                );
              }}
            >Drop entry</button>
          </div>
        </div>
      </div>
    );
  };

  // Slim "+ interstitial" insertion control rendered between timeline entries.
  const renderInsertControl = (refId, act, key) => {
    const slot = refId === null ? `start:${act}` : refId;
    const open = addingAfterId === slot;
    return (
      <div className="ins-slot" key={key}>
        {open ? (
          <InterstitialAddForm
            onAdd={(fields) => insertInterstitial(refId, act, fields)}
            onCancel={() => setAddingAfterId(null)}
          />
        ) : (
          <button className="ins-add-btn" onClick={() => setAddingAfterId(slot)}>+ interstitial</button>
        )}
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
    const speakerC = src ? speakerColors[src.speakerSlug] : { bg: COLORS.surface2, fg: COLORS.textMuted };
    const rec = entry.runtime_recommendation || "probable-keep";

    // Drag is only initiated from the .tl-drag handle on the left edge of the
    // card — otherwise text selection inside the card (especially in the trim
    // editor) gets hijacked into a card-drag. The whole card still accepts
    // drops; only dragstart/dragend live on the handle.
    return (
      <div
        key={entry.entry_id}
        id={entry.entry_id}
        className={`tl-card is-${rec}${dragId === entry.entry_id ? " dragging" : ""}${dragOverId === entry.entry_id && dragId !== entry.entry_id ? " drag-over" : ""}`}
      >
        {renderDragHandle(entry)}
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
            <button
              className={`rec-badge ${rec}`}
              onClick={() => {
                const next = REC_CYCLE[rec] || "must-keep";
                applyLocalEdit("set_rec",
                  (tl) => {
                    const e2 = tl.find((x) => x.entry_id === entry.entry_id);
                    if (e2) e2.runtime_recommendation = next;
                  },
                  `${entry.entry_id} (#${entry.source_quote_id}): ${rec} → ${next}`,
                  {
                    change_type: "status_flip",
                    entry_id: entry.entry_id,
                    before: { runtime_recommendation: rec },
                    after: { runtime_recommendation: next },
                  }
                );
              }}
              title="Click to toggle between must-keep and probable-keep"
            >{rec.replace("-", " ")}</button>
            <span className="tc">~{fmtSec(entrySeconds(entry))}</span>
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
            <button
              className="btn btn-comment"
              onClick={() => focusCommentary(`About ${entry.entry_id} (#${entry.source_quote_id}, ${entryActOf(entry)}): `)}
            >💬 Comment on this</button>
            <button
              className="btn btn-danger"
              onClick={() => {
                if (!confirm(`Drop entry ${entry.entry_id} (#${entry.source_quote_id})? Source quote stays in the Library and can be re-added.`)) return;
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
                      runtime_recommendation: entry.runtime_recommendation,
                    },
                    after: null,
                  }
                );
              }}
            >Drop entry</button>
          </div>
        </div>
      </div>
    );
  };

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
              </div>
              {entries.flatMap((entry, idx) => {
                const isSpoken = entry.type === "spoken" || entry.source_quote_id != null;
                const card = isSpoken ? renderTimelineCard(entry) : renderInterstitialCard(entry);
                const els = [];
                if (idx === 0) els.push(renderInsertControl(null, act, `ins-start-${act}`));
                els.push(card);
                els.push(renderInsertControl(entry.entry_id, act, `ins-after-${entry.entry_id}`));
                return els;
              })}
            </section>
          );
        })}
      </div>
    );
  };

  // ============================================================================
  // Review view
  // ============================================================================

  const renderReview = () => {
    const tl = getTimeline().filter((e) =>
      cutFilter === "tight" ? e.runtime_recommendation === "must-keep" : true
    );
    if (tl.length === 0) {
      return <div className="empty"><h3>Nothing to review yet.</h3></div>;
    }
    const realActs = PROJECT_META.act_labels.filter((a) => a !== "Orphan");
    const tabs = [...realActs, "All"];
    const inScope = tl.filter((e) => reviewScope === "All" || entryActOf(e) === reviewScope);
    return (
      <div className="review-view">
        <div className="review-tabs">
          {tabs.map((name) => {
            const count = name === "All" ? tl.length : tl.filter((e) => entryActOf(e) === name).length;
            return (
              <button
                key={name}
                className={`review-tab${reviewScope === name ? " active" : ""}`}
                onClick={() => setReviewScope(name)}
              >{name}<span className="count">({count})</span></button>
            );
          })}
        </div>
        {(() => {
          const actsToShow = reviewScope === "All" ? realActs : [reviewScope];
          return actsToShow.map((act) => {
            const entries = inScope.filter((e) => entryActOf(e) === act);
            if (entries.length === 0) return null;
            const secs = entries.reduce((a, e) => a + entrySeconds(e), 0);
            let lastSp = null;
            return (
              <div key={act} className="review-act">
                <h2>{act}<span className="meta">~{fmtSec(secs)} · {entries.length} beat{entries.length === 1 ? "" : "s"}</span></h2>
                {entries.map((e) => {
                  const isSpoken = e.type === "spoken" || e.source_quote_id != null;
                  if (!isSpoken) {
                    lastSp = null;  // an interstitial breaks the flow; re-show next speaker
                    const insLabel = { title_card: "TITLE CARD", interstitial: "INTERSTITIAL", context_beat: "CONTEXT BEAT" }[e.type] || "INTERSTITIAL";
                    const insText = e.type === "context_beat" ? `[${e.intent || "context needed"}]` : (e.text || "");
                    return (
                      <div key={e.entry_id} className="review-interstitial">
                        <span className="ri-label">{insLabel}</span>
                        <div className="ri-text">{insText}</div>
                      </div>
                    );
                  }
                  const src = findSourceQuote(e.source_quote_id);
                  const speakerLabel = src?.speaker || e.speaker || "?";
                  const showSpeaker = speakerLabel !== lastSp;
                  lastSp = speakerLabel;
                  return (
                    <div key={e.entry_id} className="review-block">
                      {showSpeaker && <div className="speaker">— {speakerLabel}</div>}
                      <div className="review-text">"{trimmedQuoteText(e)}"</div>
                    </div>
                  );
                })}
              </div>
            );
          });
        })()}
      </div>
    );
  };

  // ============================================================================
  // Send-to-agent panel
  // ============================================================================

  const renderSendPanel = () => {
    const ops = getPendingOps();
    const round = ROUNDS[roundIndex];
    const hasContent = ops.length > 0 || commentary.trim().length > 0;
    return (
      <div className={`send-panel${sendPanelOpen ? "" : " collapsed"}${ops.length > 0 ? " has-pending" : ""}`}>
        <div className="sp-head" onClick={() => setSendPanelOpen(!sendPanelOpen)}>
          <span className="sp-title">Talk to agent</span>
          <span className={`sp-count${ops.length === 0 ? " zero" : ""}`}>{ops.length}</span>
          <span className="sp-toggle">{sendPanelOpen ? "▼" : "▲"}</span>
        </div>
        {sendPanelOpen && (
          <>
            <div className="sp-body">
              <div className="sp-section">
                <div className="sp-section-head">
                  <span className="sp-section-title">Pending tweaks</span>
                  <button
                    className="sp-discard"
                    onClick={(e) => { e.stopPropagation(); discardAllTweaks(); }}
                    disabled={ops.length === 0}
                  >Discard all</button>
                </div>
                <ul className="sp-ops">
                  {ops.length === 0 ? (
                    <li className="empty">No tweaks yet. Edit in the timeline to start.</li>
                  ) : (
                    ops.map((o, i) => <li key={i}>{o.description}</li>)
                  )}
                </ul>
              </div>
              <div className="sp-section">
                <div className="sp-section-head">
                  <span className="sp-section-title">Editorial commentary</span>
                  <span className="sp-optional">optional</span>
                </div>
                <textarea
                  id="send-textarea"
                  className="sp-textarea"
                  placeholder="Why these changes? Or: what's your editorial read on a specific entry? The agent learns from this — it's the 'why,' not just the 'what.'"
                  value={commentary}
                  onChange={(e) => setCommentary(e.target.value)}
                />
                <div className="sp-hint">
                  Tip: click <strong>💬 Comment</strong> on any card to focus here with that entry pre-filled.
                </div>
              </div>
            </div>
            <div className="sp-foot">
              <button className="sp-send" disabled={!hasContent} onClick={sendToAgent}>Send</button>
              {sendStatus.text && <span className={`sp-status ${sendStatus.cls}`}>{sendStatus.text}</span>}
              <span className="sp-version">Round {round.round_number} · {round.version}</span>
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

  // Close reassign popup on outside click
  useEffect(() => {
    if (!reassigningEntryId) return;
    const onDoc = () => setReassigningEntryId(null);
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [reassigningEntryId]);

  return (
    <div className="viewer">
      {renderHeader()}
      <main className="main">
        {view === "library" && renderLibrary()}
        {view === "timeline" && renderTimeline()}
        {view === "review" && renderReview()}
      </main>
      {renderSendPanel()}
    </div>
  );
}
