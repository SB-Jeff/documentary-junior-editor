import { useState, useCallback, useRef, useEffect } from "react";

// ============================================================================
// DATA BLOCK — Replace this section with project-specific data.
// The React component below should NOT be modified when populating project data.
// When baking in editor edits, only update this data block.
// ============================================================================

const PROJECT_TITLE = "Subject Name — Company Name";

// Quotes array — grouped by section, ordered by editor's preferred sequence.
// Each quote needs: num, speaker, quote (full verbatim text), startTC, endTC,
// part (section name), rationale, selected (boolean).
const initialQuotes = [
  // Quotes are grouped by section. Section names come from act-structure.md.
  // Do not hardcode section names — they are derived dynamically from the data.
  // Example: { num: 1, speaker: "Speaker Name", quote: "Full verbatim quote text...", startTC: "0:15", endTC: "0:45", part: "Section Name", rationale: "Why this quote belongs here.", selected: false },
];

// Pre-baked trims — keyed by quote number. Populated as the editor trims quotes.
// Example: { 5: "Trimmed version of quote #5...", 8: "Trimmed version of quote #8..." }
const initialTrims = {};

// Text interstitials — factual titles, credentials, or context lines that appear
// between spoken quotes. These are NOT spoken quotes — they are on-screen text cards.
// Each interstitial has: id (string, "T1", "T2", ...), text (the on-screen text),
// part (section name), and afterId (the quote id it appears after, or null for start).
// Example: [{ id: "T1", text: "Dr. Pan attended the University of Cincinnati College of Medicine.", part: "The Legacy", afterId: "3" }]
const initialInterstitials = [];

// ============================================================================
// RESTORED STATE — If resuming from a saved session, paste saved JSON here.
// Leave as null for a fresh start. Claude can also populate this automatically
// when regenerating the artifact with preserved editorial state.
// ============================================================================
// NOTE: When baking state, also populate initialInterstitials above with any
// text interstitials created during the session.
const RESTORED_STATE = null;

// Section configuration — populated from act-structure.md approved labels.
// Order determines display order in filters and section headers.
// If empty or null, sections are derived dynamically from quote data (first appearance order).
// Example: [{ name: "The Need" }, { name: "The Work" }, { name: "The Impact" }]
const SECTION_CONFIG = null;

// ============================================================================
// REACT COMPONENT — Universal UI code. Same across all projects.
// Do not modify this section when updating project data.
// To fix bugs or add features, update this section without touching the data above.
// ============================================================================

// Dynamic color palette — assigned to sections in order of appearance.
const COLOR_PALETTE = [
  { bg: "bg-blue-50", border: "border-blue-200", badge: "bg-blue-100 text-blue-800", stripe: "bg-blue-400", btnActive: "bg-blue-500 text-white" },
  { bg: "bg-amber-50", border: "border-amber-200", badge: "bg-amber-100 text-amber-800", stripe: "bg-amber-400", btnActive: "bg-amber-500 text-white" },
  { bg: "bg-emerald-50", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-800", stripe: "bg-emerald-400", btnActive: "bg-emerald-500 text-white" },
  { bg: "bg-purple-50", border: "border-purple-200", badge: "bg-purple-100 text-purple-800", stripe: "bg-purple-400", btnActive: "bg-purple-500 text-white" },
  { bg: "bg-rose-50", border: "border-rose-200", badge: "bg-rose-100 text-rose-800", stripe: "bg-rose-400", btnActive: "bg-rose-500 text-white" },
  { bg: "bg-cyan-50", border: "border-cyan-200", badge: "bg-cyan-100 text-cyan-800", stripe: "bg-cyan-400", btnActive: "bg-cyan-500 text-white" },
];
const ORPHAN_COLOR = { bg: "bg-gray-50", border: "border-gray-200", badge: "bg-gray-100 text-gray-800", stripe: "bg-gray-400", btnActive: "bg-gray-500 text-white" };

// === Character-range cut helpers ===
// editCuts is now a sorted array of [start, end] ranges marking cut characters.

// Compute cut ranges from an existing trim (kept substring of original)
function computeCutRanges(original, trimmed) {
  if (!trimmed || trimmed === original) return [];
  const trimIdx = original.indexOf(trimmed);
  if (trimIdx < 0) return [];
  const ranges = [];
  if (trimIdx > 0) ranges.push([0, trimIdx]);
  const trimEnd = trimIdx + trimmed.length;
  if (trimEnd < original.length) ranges.push([trimEnd, original.length]);
  return ranges;
}

// Merge overlapping/adjacent ranges and sort
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

// Toggle a range: cut chars become kept, kept chars become cut
function toggleRange(existingCuts, selStart, selEnd) {
  // Build a per-character cut map
  const isCut = new Array(selEnd).fill(false);
  existingCuts.forEach(([s, e]) => {
    for (let i = Math.max(s, selStart); i < Math.min(e, selEnd); i++) isCut[i] = true;
  });
  // Invert within selection
  const newCuts = existingCuts.map(r => [...r]); // clone
  // Remove the selection range from existing cuts (restore cut parts)
  // Then add the non-cut parts of the selection as new cuts
  const toRemove = [[selStart, selEnd]];
  // Subtract selection from existing cuts
  let result = [];
  for (const [cs, ce] of existingCuts) {
    if (ce <= selStart || cs >= selEnd) {
      result.push([cs, ce]); // no overlap
    } else {
      if (cs < selStart) result.push([cs, selStart]);
      if (ce > selEnd) result.push([selEnd, ce]);
    }
  }
  // Add inverted parts: chars in selection that were NOT cut become cut
  let pos = selStart;
  for (const [cs, ce] of existingCuts) {
    const overlapStart = Math.max(cs, selStart);
    const overlapEnd = Math.min(ce, selEnd);
    if (overlapStart >= overlapEnd) continue;
    if (pos < overlapStart) result.push([pos, overlapStart]);
    pos = overlapEnd;
  }
  if (pos < selEnd) result.push([pos, selEnd]);
  return normalizeRanges(result);
}

// Build render segments: array of { text, cut } for display
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

// Reconstruct kept text from original + cuts
function buildKeptText(original, cuts) {
  if (cuts.length === 0) return original;
  let result = '';
  let pos = 0;
  for (const [s, e] of cuts) {
    result += original.slice(pos, s);
    pos = e;
  }
  result += original.slice(pos);
  return result.replace(/\s+/g, ' ').trim();
}

function buildSectionColors(quotes, config) {
  const colors = {};
  if (config && config.length > 0) {
    config.forEach((s, i) => { colors[s.name] = COLOR_PALETTE[i % COLOR_PALETTE.length]; });
  } else {
    const seen = [];
    quotes.forEach(q => { if (q.part && q.part !== "Orphan" && !seen.includes(q.part)) seen.push(q.part); });
    seen.forEach((name, i) => { colors[name] = COLOR_PALETTE[i % COLOR_PALETTE.length]; });
  }
  colors["Orphan"] = ORPHAN_COLOR;
  return colors;
}

// Snap a character range to word boundaries within the original text
function snapToWordBounds(text, start, end) {
  // Expand start backward to beginning of word
  while (start > 0 && text[start - 1] !== ' ') start--;
  // Expand end forward to end of word
  while (end < text.length && text[end] !== ' ') end++;
  // Consume trailing spaces so cuts don't leave orphaned gaps
  while (end < text.length && text[end] === ' ') end++;
  // If we consumed trailing space but hit the end, also consume leading space
  // so a cut at the start or end of text stays clean
  if (start > 0 && end === text.length) {
    while (start > 0 && text[start - 1] === ' ') start--;
  }
  return [start, end];
}

// === Edit Panel sub-component (handles Selection API + Delete key) ===
function EditPanel({ editOriginal, editCuts, setEditCuts, onSave, onCancel }) {
  const textRef = useRef(null);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key !== 'Delete' && e.key !== 'Backspace') return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !textRef.current) return;
      if (!textRef.current.contains(sel.anchorNode) || !textRef.current.contains(sel.focusNode)) return;
      e.preventDefault();

      // Walk the text container to compute character offsets from the selection
      const container = textRef.current;
      let charOffset = 0;
      let selStart = null, selEnd = null;
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const len = node.textContent.length;
        if (node === sel.anchorNode || node === sel.focusNode) {
          const isAnchor = node === sel.anchorNode;
          const isFocus = node === sel.focusNode;
          if (isAnchor) {
            const aOff = charOffset + sel.anchorOffset;
            if (selStart === null) selStart = aOff; else selEnd = aOff;
          }
          if (isFocus) {
            const fOff = charOffset + sel.focusOffset;
            if (selStart === null) selStart = fOff; else selEnd = fOff;
          }
        }
        charOffset += len;
      }
      if (selStart === null || selEnd === null) return;
      if (selStart > selEnd) { const tmp = selStart; selStart = selEnd; selEnd = tmp; }
      if (selStart === selEnd) return;

      // Snap to word boundaries so partial words can't be cut
      [selStart, selEnd] = snapToWordBounds(editOriginal, selStart, selEnd);

      setEditCuts(prev => toggleRange(prev, selStart, selEnd));
      sel.removeAllRanges();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [setEditCuts]);

  const segments = buildRenderSegments(editOriginal, editCuts);

  return (
    <div className="mt-2" onClick={(e) => e.stopPropagation()}>
      <p className="text-xs text-gray-400 mb-1">Select text, then press Delete to cut or restore it.</p>
      <div
        ref={textRef}
        className="text-sm leading-relaxed p-3 bg-gray-50 border border-gray-200 rounded mb-2 select-text cursor-text"
        style={{ userSelect: 'text', WebkitUserSelect: 'text' }}
      >
        {segments.map((seg, i) => (
          <span
            key={i}
            className={seg.cut
              ? "text-red-400 line-through"
              : "text-gray-800"
            }
          >{seg.text}</span>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          onClick={onSave}
          className="text-xs px-3 py-1.5 rounded bg-gray-900 text-white hover:bg-gray-700"
        >
          Save
        </button>
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// === Split Panel sub-component (shows word boundaries to place split markers) ===
function SplitPanel({ text, markers, setMarkers, onSplit, onCancel }) {
  // Parse text into words with their character positions
  const words = [];
  let pos = 0;
  const regex = /(\S+)(\s*)/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    words.push({
      word: match[1],
      space: match[2],
      start: match.index,
      end: match.index + match[1].length,
      boundaryAfter: match.index + match[0].length, // char position after word+space
    });
  }

  const toggleMarker = (charPos) => {
    setMarkers(prev =>
      prev.includes(charPos) ? prev.filter(m => m !== charPos) : [...prev, charPos].sort((a, b) => a - b)
    );
  };

  // Build display: words with clickable split zones between them
  const sortedMarkers = [...markers].sort((a, b) => a - b);

  return (
    <div className="mt-2" onClick={(e) => e.stopPropagation()}>
      <p className="text-xs text-gray-400 mb-1">Click between words to place split markers. Click a marker again to remove it.</p>
      <div className="text-sm leading-loose p-3 bg-gray-50 border border-gray-200 rounded mb-2">
        {words.map((w, i) => (
          <span key={i}>
            <span className="text-gray-800">{w.word}</span>
            {i < words.length - 1 && (
              <span
                onClick={() => toggleMarker(w.boundaryAfter)}
                className={`inline-block cursor-pointer px-0.5 mx-0.5 rounded select-none ${
                  sortedMarkers.includes(w.boundaryAfter)
                    ? "bg-blue-500 text-white font-bold"
                    : "text-gray-300 hover:bg-blue-100 hover:text-blue-500"
                }`}
                title={sortedMarkers.includes(w.boundaryAfter) ? "Remove split point" : "Add split point here"}
              >
                {sortedMarkers.includes(w.boundaryAfter) ? "✂" : "|"}
              </span>
            )}
            {i < words.length - 1 && !sortedMarkers.includes(w.boundaryAfter) && (
              <span> </span>
            )}
          </span>
        ))}
      </div>
      {sortedMarkers.length > 0 && (
        <p className="text-xs text-gray-500 mb-2">
          Will create {sortedMarkers.length + 1} sub-quotes
        </p>
      )}
      <div className="flex gap-2">
        <button
          onClick={onSplit}
          disabled={sortedMarkers.length === 0}
          className={`text-xs px-3 py-1.5 rounded ${
            sortedMarkers.length > 0
              ? "bg-blue-600 text-white hover:bg-blue-500"
              : "bg-gray-200 text-gray-400 cursor-default"
          }`}
        >
          Split into {sortedMarkers.length + 1} quotes
        </button>
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// Apply restored state to initial data if available
function getInitialQuotes() {
  if (!RESTORED_STATE) return initialQuotes.map(q => ({ ...q, id: String(q.num) }));
  const { quoteOrder, selections, sectionAssignments } = RESTORED_STATE;
  const orderMap = {};
  quoteOrder.forEach((num, idx) => { orderMap[num] = idx; });
  const sorted = [...initialQuotes].sort((a, b) => {
    const aIdx = orderMap[a.num] !== undefined ? orderMap[a.num] : 9999;
    const bIdx = orderMap[b.num] !== undefined ? orderMap[b.num] : 9999;
    return aIdx - bIdx;
  });
  return sorted.map(q => ({
    ...q,
    id: String(q.num),
    selected: selections.includes(q.num),
    part: sectionAssignments[q.num] || q.part,
  }));
}

function getInitialTrims() {
  if (!RESTORED_STATE) return initialTrims;
  return { ...initialTrims, ...RESTORED_STATE.trims };
}

export default function QuotesView() {
  const sectionColors = buildSectionColors(initialQuotes, SECTION_CONFIG);
  const sectionNames = Object.keys(sectionColors).filter(s => s !== "Orphan");

  const [filter, setFilter] = useState("All");
  const [showSelectedOnly, setShowSelectedOnly] = useState(false);
  const [quotes, setQuotes] = useState(getInitialQuotes);
  const [editedQuotes, setEditedQuotes] = useState(getInitialTrims);
  const [editingNum, setEditingNum] = useState(null);
  const [editOriginal, setEditOriginal] = useState("");
  const [editCuts, setEditCuts] = useState([]);
  const [reassigningNum, setReassigningNum] = useState(null);

  // Save/Restore state
  const [showSavePanel, setShowSavePanel] = useState(false);
  const [savedJson, setSavedJson] = useState("");
  const [restoreText, setRestoreText] = useState("");
  const [saveConfirmation, setSaveConfirmation] = useState("");
  const [showSelectedBar, setShowSelectedBar] = useState(false);

  // Split quote state
  const [splittingId, setSplittingId] = useState(null);
  const [splitMarkers, setSplitMarkers] = useState([]); // char positions where splits occur

  // Interstitial state — text cards between spoken quotes
  const [interstitials, setInterstitials] = useState(initialInterstitials);
  const [placingInterstitial, setPlacingInterstitial] = useState(false); // toolbar placement mode
  const [pendingInterstitialAfter, setPendingInterstitialAfter] = useState(null); // clicked placement target
  const [newInterstitialText, setNewInterstitialText] = useState("");
  const [editingInterstitialId, setEditingInterstitialId] = useState(null);
  const [editInterstitialText, setEditInterstitialText] = useState("");

  const sections = ["All", ...sectionNames, "Orphan"];

  const toggleSelect = (id) => {
    setQuotes(prev => prev.map(q => q.id === id ? { ...q, selected: !q.selected } : q));
  };

  const [dragNum, setDragNum] = useState(null);
  const [dropTarget, setDropTarget] = useState(null); // { num, half: "top"|"bottom" }

  const handleDragStart = (id, e) => {
    setDragNum(id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
  };

  const handleDragOver = (id, e) => {
    e.preventDefault();
    if (dragNum == null || id === dragNum) { setDropTarget(null); return; }
    const dragQ = quotes.find(q => q.id === dragNum);
    const overQ = quotes.find(q => q.id === id);
    if (dragQ.part !== overQ.part) { setDropTarget(null); return; }
    e.dataTransfer.dropEffect = "move";
    const rect = e.currentTarget.getBoundingClientRect();
    const half = (e.clientY - rect.top) < rect.height / 2 ? "top" : "bottom";
    setDropTarget({ id, half });
  };

  const handleDrop = (id, e) => {
    e.preventDefault();
    if (dragNum == null || id === dragNum) { setDragNum(null); setDropTarget(null); return; }
    const rect = e.currentTarget.getBoundingClientRect();
    const half = (e.clientY - rect.top) < rect.height / 2 ? "top" : "bottom";
    setQuotes(prev => {
      const arr = [...prev];
      const fromIdx = arr.findIndex(q => q.id === dragNum);
      const toIdx = arr.findIndex(q => q.id === id);
      if (arr[fromIdx].part !== arr[toIdx].part) return arr;
      const [moved] = arr.splice(fromIdx, 1);
      const newToIdx = arr.findIndex(q => q.id === id);
      const insertIdx = half === "bottom" ? newToIdx + 1 : newToIdx;
      arr.splice(insertIdx, 0, moved);
      return arr;
    });
    setDragNum(null);
    setDropTarget(null);
  };

  const handleDragEnd = () => { setDragNum(null); setDropTarget(null); };

  const moveQuote = (id, direction, e) => {
    if (e) e.stopPropagation();
    setQuotes(prev => {
      const arr = [...prev];
      const idx = arr.findIndex(q => q.id === id);
      const current = arr[idx];

      if (direction === "up") {
        for (let i = idx - 1; i >= 0; i--) {
          if (arr[i].part === current.part) {
            const temp = arr[idx];
            arr[idx] = arr[i];
            arr[i] = temp;
            return arr;
          }
        }
      } else {
        for (let i = idx + 1; i < arr.length; i++) {
          if (arr[i].part === current.part) {
            const temp = arr[idx];
            arr[idx] = arr[i];
            arr[i] = temp;
            return arr;
          }
        }
      }
      return arr;
    });
  };

  const isFirstInSection = (id) => {
    const q = quotes.find(q => q.id === id);
    const idx = quotes.findIndex(q => q.id === id);
    for (let i = idx - 1; i >= 0; i--) {
      if (quotes[i].part === q.part) return false;
    }
    return true;
  };

  const isLastInSection = (id) => {
    const q = quotes.find(q => q.id === id);
    const idx = quotes.findIndex(q => q.id === id);
    for (let i = idx + 1; i < quotes.length; i++) {
      if (quotes[i].part === q.part) return false;
    }
    return true;
  };

  const reassignSection = (id, newSection, e) => {
    e.stopPropagation();
    setQuotes(prev => {
      const quoteIdx = prev.findIndex(q => q.id === id);
      const quote = { ...prev[quoteIdx], part: newSection };
      const withoutQuote = [...prev.slice(0, quoteIdx), ...prev.slice(quoteIdx + 1)];

      let insertIdx = withoutQuote.length;
      for (let i = withoutQuote.length - 1; i >= 0; i--) {
        if (withoutQuote[i].part === newSection) {
          insertIdx = i + 1;
          break;
        }
        if (i === 0) {
          const sectionOrder = [...sectionNames, "Orphan"];
          const newIdx = sectionOrder.indexOf(newSection);
          insertIdx = 0;
          for (let j = 0; j < withoutQuote.length; j++) {
            if (sectionOrder.indexOf(withoutQuote[j].part) > newIdx) {
              insertIdx = j;
              break;
            }
            insertIdx = j + 1;
          }
        }
      }

      return [...withoutQuote.slice(0, insertIdx), quote, ...withoutQuote.slice(insertIdx)];
    });
    setReassigningNum(null);
  };

  const startEditing = (id, e) => {
    e.stopPropagation();
    const q = quotes.find(q => q.id === id);
    if (!q) return;
    setEditingNum(id);
    setEditOriginal(q.quote);
    setEditCuts(computeCutRanges(q.quote, editedQuotes[id]));
  };

  const saveEdit = (id) => {
    const original = quotes.find(q => q.id === id).quote;
    const kept = buildKeptText(original, editCuts);
    if (kept === original || kept === '') {
      setEditedQuotes(prev => { const next = { ...prev }; delete next[id]; return next; });
    } else {
      setEditedQuotes(prev => ({ ...prev, [id]: kept }));
    }
    setEditingNum(null);
  };

  const resetEdit = (id, e) => {
    e.stopPropagation();
    setEditedQuotes(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    setEditingNum(null);
  };

  // === SPLIT QUOTE ===
  const startSplit = (id, e) => {
    e.stopPropagation();
    setSplittingId(id);
    setSplitMarkers([]);
  };

  const executeSplit = () => {
    if (!splittingId || splitMarkers.length === 0) { setSplittingId(null); return; }
    const q = quotes.find(q => q.id === splittingId);
    if (!q) { setSplittingId(null); return; }

    const original = q.quote;
    const existingCuts = editedQuotes[q.id]
      ? computeCutRanges(original, editedQuotes[q.id])
      : [];

    // Sort markers and create split boundaries
    const sorted = [...splitMarkers].sort((a, b) => a - b);
    const boundaries = [0, ...sorted, original.length];
    const labels = "abcdefghijklmnopqrstuvwxyz";

    const subQuotes = [];
    const newEdits = {};

    for (let i = 0; i < boundaries.length - 1; i++) {
      const start = boundaries[i];
      const end = boundaries[i + 1];
      const subText = original.slice(start, end).trim();
      if (!subText) continue;

      const subId = `${q.num}${labels[i] || i}`;

      // Adjust existing cuts to be relative to this sub-quote's portion
      const subCuts = [];
      for (const [cs, ce] of existingCuts) {
        const overlapStart = Math.max(cs, start);
        const overlapEnd = Math.min(ce, end);
        if (overlapStart < overlapEnd) {
          subCuts.push([overlapStart - start, overlapEnd - start]);
        }
      }

      // If there are cuts for this sub-quote, compute the kept text
      const subOriginal = original.slice(start, end);
      if (subCuts.length > 0) {
        const kept = buildKeptText(subOriginal, subCuts);
        if (kept !== subOriginal) {
          newEdits[subId] = kept;
        }
      }

      subQuotes.push({
        ...q,
        id: subId,
        num: q.num,
        subLabel: labels[i] || String(i),
        originalNum: q.num,
        quote: subOriginal,
        rationale: q.rationale + ` (split ${labels[i] || i} of ${boundaries.length - 1})`,
      });
    }

    // Replace the original quote with sub-quotes in the array
    setQuotes(prev => {
      const idx = prev.findIndex(q => q.id === splittingId);
      if (idx < 0) return prev;
      return [...prev.slice(0, idx), ...subQuotes, ...prev.slice(idx + 1)];
    });

    // Update edited quotes: remove original, add sub-edits
    setEditedQuotes(prev => {
      const next = { ...prev };
      delete next[splittingId];
      Object.assign(next, newEdits);
      return next;
    });

    setSplittingId(null);
    setSplitMarkers([]);
  };

  // === INTERSTITIAL MANAGEMENT ===
  const nextInterstitialId = () => {
    const existing = interstitials.map(t => parseInt(t.id.replace("T", ""), 10)).filter(n => !isNaN(n));
    const max = existing.length > 0 ? Math.max(...existing) : 0;
    return `T${max + 1}`;
  };

  const placeInterstitial = (afterId) => {
    // User clicked a drop zone — show the text input
    setPendingInterstitialAfter(afterId);
  };

  const confirmInterstitial = () => {
    if (!newInterstitialText.trim() || pendingInterstitialAfter === null) return;
    const afterQuote = quotes.find(q => q.id === pendingInterstitialAfter);
    const section = afterQuote ? afterQuote.part : (sectionNames[0] || "Orphan");
    const newItem = {
      id: nextInterstitialId(),
      text: newInterstitialText.trim(),
      part: section,
      afterId: pendingInterstitialAfter === "__START__" ? null : pendingInterstitialAfter,
    };
    setInterstitials(prev => [...prev, newItem]);
    setNewInterstitialText("");
    setPendingInterstitialAfter(null);
    setPlacingInterstitial(false);
  };

  const cancelPlacement = () => {
    setPlacingInterstitial(false);
    setPendingInterstitialAfter(null);
    setNewInterstitialText("");
  };

  const removeInterstitial = (id) => {
    setInterstitials(prev => prev.filter(t => t.id !== id));
  };

  const startEditInterstitial = (id) => {
    const t = interstitials.find(t => t.id === id);
    if (!t) return;
    setEditingInterstitialId(id);
    setEditInterstitialText(t.text);
  };

  const saveEditInterstitial = (id) => {
    if (!editInterstitialText.trim()) return;
    setInterstitials(prev => prev.map(t =>
      t.id === id ? { ...t, text: editInterstitialText.trim() } : t
    ));
    setEditingInterstitialId(null);
    setEditInterstitialText("");
  };

  // Get interstitials that appear after a given quote id (or at the start if afterId is null)
  const getInterstitialsAfter = (quoteId) => {
    return interstitials.filter(t => t.afterId === quoteId);
  };
  const getInterstitialsAtStart = () => {
    return interstitials.filter(t => t.afterId === null || t.afterId === "__START__");
  };

  // === SAVE STATE ===
  const handleSaveState = useCallback(() => {
    const state = {
      quoteOrder: quotes.map(q => q.id),
      selections: quotes.filter(q => q.selected).map(q => q.id),
      trims: editedQuotes,
      sectionAssignments: {},
      interstitials: interstitials,
    };
    quotes.forEach(q => {
      const original = initialQuotes.find(oq => oq.num === q.num);
      if (original && original.part !== q.part) {
        state.sectionAssignments[q.id] = q.part;
      }
    });
    const json = JSON.stringify(state);
    setSavedJson(json);
    setShowSavePanel(true);
    navigator.clipboard.writeText(json).then(() => {
      setSaveConfirmation("Copied to clipboard!");
      setTimeout(() => setSaveConfirmation(""), 3000);
    }).catch(() => {
      setSaveConfirmation("Select all and copy manually");
    });
  }, [quotes, editedQuotes, interstitials]);

  // === RESTORE STATE ===
  const handleRestoreState = useCallback(() => {
    try {
      const state = JSON.parse(restoreText);
      if (!state.quoteOrder || !state.selections) {
        alert("Invalid save data — missing required fields.");
        return;
      }
      const orderMap = {};
      state.quoteOrder.forEach((id, idx) => { orderMap[id] = idx; });
      setQuotes(prev => {
        const sorted = [...prev].sort((a, b) => {
          const aIdx = orderMap[a.id] !== undefined ? orderMap[a.id] : 9999;
          const bIdx = orderMap[b.id] !== undefined ? orderMap[b.id] : 9999;
          return aIdx - bIdx;
        });
        return sorted.map(q => ({
          ...q,
          selected: state.selections.includes(q.id),
          part: (state.sectionAssignments && state.sectionAssignments[q.id]) || q.part,
        }));
      });
      if (state.trims) {
        setEditedQuotes(prev => ({ ...prev, ...state.trims }));
      }
      if (state.interstitials) {
        setInterstitials(state.interstitials);
      }
      setRestoreText("");
      setShowSavePanel(false);
      setSaveConfirmation("State restored!");
      setTimeout(() => setSaveConfirmation(""), 3000);
    } catch (e) {
      alert("Could not parse save data. Make sure you pasted the full JSON string.");
    }
  }, [restoreText]);

  const selectedQuotes = quotes.filter(q => q.selected);
  const filtered = quotes
    .filter(q => filter === "All" || q.part === filter)
    .filter(q => !showSelectedOnly || q.selected);

  let lastSection = "";

  return (
    <div className="max-w-4xl mx-auto p-4 font-sans">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-900 mb-1">{PROJECT_TITLE}</h1>
        <p className="text-sm text-gray-500">{quotes.length} quotes total  •  {selectedQuotes.length} selected  •  {Object.keys(editedQuotes).length} trimmed{interstitials.length > 0 ? `  •  ${interstitials.length} interstitial${interstitials.length !== 1 ? "s" : ""}` : ""}</p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={handleSaveState}
          className="px-3 py-1.5 rounded text-xs font-medium bg-green-100 text-green-800 hover:bg-green-200 transition-colors"
        >
          Save State
        </button>
        <button
          onClick={() => setShowSavePanel(!showSavePanel)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 hover:bg-yellow-200 transition-colors"
        >
          Restore State
        </button>
        {placingInterstitial ? (
          <button
            onClick={cancelPlacement}
            className="px-3 py-1.5 rounded text-xs font-medium bg-indigo-500 text-white hover:bg-indigo-600 transition-colors ring-2 ring-indigo-300"
          >
            Cancel Placement
          </button>
        ) : (
          <button
            onClick={() => { setPlacingInterstitial(true); setShowSelectedOnly(true); }}
            className="px-3 py-1.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800 hover:bg-indigo-200 transition-colors"
          >
            + Interstitial
          </button>
        )}
        {saveConfirmation && (
          <span className="text-xs text-green-700 font-medium">{saveConfirmation}</span>
        )}
        {placingInterstitial && (
          <span className="text-xs text-indigo-600 font-medium animate-pulse">Click a drop zone between quotes to place it</span>
        )}
      </div>

      {/* Save/Restore panel */}
      {showSavePanel && (
        <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
          {savedJson && (
            <div>
              <label className="text-xs font-bold text-gray-600 block mb-1">Saved State (auto-copied to clipboard)</label>
              <textarea
                readOnly
                value={savedJson}
                className="w-full text-xs font-mono p-2 border border-gray-300 rounded bg-white resize-y"
                rows={3}
                onClick={(e) => e.target.select()}
              />
            </div>
          )}
          <div>
            <label className="text-xs font-bold text-gray-600 block mb-1">Paste saved state to restore</label>
            <textarea
              value={restoreText}
              onChange={(e) => setRestoreText(e.target.value)}
              placeholder='Paste your saved JSON here...'
              className="w-full text-xs font-mono p-2 border border-gray-300 rounded bg-white resize-y"
              rows={3}
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleRestoreState}
                disabled={!restoreText.trim()}
                className={`text-xs px-3 py-1.5 rounded font-medium ${
                  restoreText.trim()
                    ? "bg-yellow-500 text-white hover:bg-yellow-600"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed"
                }`}
              >
                Restore
              </button>
              <button
                onClick={() => { setShowSavePanel(false); setRestoreText(""); }}
                className="text-xs px-3 py-1.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Section filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        {sections.map(s => {
          const count = s === "All" ? quotes.length : quotes.filter(q => q.part === s).length;
          const selCount = s === "All"
            ? selectedQuotes.length
            : quotes.filter(q => q.part === s && q.selected).length;
          const sColors = sectionColors[s];
          const activeStyle = s === "All"
            ? "bg-gray-900 text-white"
            : sColors ? sColors.btnActive : "bg-gray-900 text-white";
          const inactiveStyle = sColors && s !== "All"
            ? `${sColors.badge} hover:ring-2 hover:ring-gray-300`
            : "bg-gray-100 text-gray-600 hover:bg-gray-200";
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filter === s ? activeStyle : inactiveStyle
              }`}
            >
              {s} ({selCount}/{count})
            </button>
          );
        })}
        <div className="ml-auto">
          <button
            onClick={() => setShowSelectedOnly(!showSelectedOnly)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              showSelectedOnly ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {showSelectedOnly ? "Show all" : "Selected only"}
          </button>
        </div>
      </div>

      {/* Quotes list */}
      <div className="space-y-2">
        {/* Interstitials at the very start (before first quote) */}
        {getInterstitialsAtStart().map(t => (
          <div key={t.id} className="border border-dashed border-indigo-300 bg-indigo-50 rounded-lg overflow-hidden">
            <div className="flex">
              <div className="w-1 flex-shrink-0 bg-indigo-400" />
              <div className="flex-1 p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-indigo-700">{t.id}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">TEXT INTERSTITIAL</span>
                  </div>
                  <button onClick={() => removeInterstitial(t.id)} className="text-xs text-red-400 hover:text-red-600" title="Remove interstitial">{"\u2715"}</button>
                </div>
                {editingInterstitialId === t.id ? (
                  <div>
                    <textarea value={editInterstitialText} onChange={e => setEditInterstitialText(e.target.value)} className="w-full text-sm p-2 border border-indigo-200 rounded bg-white resize-y" rows={2} />
                    <div className="flex gap-2 mt-1">
                      <button onClick={() => saveEditInterstitial(t.id)} className="text-xs px-3 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-500">Save</button>
                      <button onClick={() => setEditingInterstitialId(null)} className="text-xs px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-indigo-900 leading-relaxed italic cursor-pointer hover:text-indigo-700" onClick={() => startEditInterstitial(t.id)}>"{t.text}"</p>
                )}
              </div>
            </div>
          </div>
        ))}
        {/* Placement drop zone at top of sequence */}
        {placingInterstitial && (
          <div>
            {pendingInterstitialAfter === "__START__" ? (
              <div className="border border-dashed border-indigo-300 bg-indigo-50 rounded-lg p-3">
                <label className="text-xs font-bold text-indigo-600 block mb-1">New text interstitial at start of sequence</label>
                <textarea value={newInterstitialText} onChange={e => setNewInterstitialText(e.target.value)} placeholder="Factual text for on-screen display..." className="w-full text-sm p-2 border border-indigo-200 rounded bg-white resize-y" rows={2} autoFocus />
                <div className="flex gap-2 mt-1">
                  <button onClick={confirmInterstitial} disabled={!newInterstitialText.trim()} className={`text-xs px-3 py-1 rounded ${newInterstitialText.trim() ? "bg-indigo-600 text-white hover:bg-indigo-500" : "bg-gray-200 text-gray-400"}`}>Add</button>
                  <button onClick={cancelPlacement} className="text-xs px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300">Cancel</button>
                </div>
              </div>
            ) : (
              <div onClick={() => placeInterstitial("__START__")} className="h-6 mx-4 my-1 flex items-center justify-center rounded border-2 border-dashed border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50 cursor-pointer transition-colors group">
                <span className="text-xs text-indigo-300 group-hover:text-indigo-500 font-medium">+ place interstitial here</span>
              </div>
            )}
          </div>
        )}
        {filtered.map((q, filteredIdx) => {
          const colors = sectionColors[q.part] || ORPHAN_COLOR;
          const isSelected = q.selected;
          const isEditing = editingNum === q.id;
          const hasEdit = editedQuotes[q.id] !== undefined;
          const displayText = editedQuotes[q.id] || q.quote;

          let sectionHeader = null;
          if (filter === "All" && q.part !== lastSection) {
            lastSection = q.part;
            sectionHeader = (
              <div className="flex items-center gap-3 pt-4 pb-1" key={`header-${q.part}`}>
                <div className={`w-3 h-3 rounded-full ${colors.stripe}`} />
                <span className="text-xs font-bold uppercase tracking-wider text-gray-500">{q.part}</span>
                <div className="flex-1 h-px bg-gray-200" />
              </div>
            );
          }

          return (
            <div key={q.id}>
              {sectionHeader}
              {/* Drop indicator line — top */}
              {dropTarget && dropTarget.id === q.id && dropTarget.half === "top" && (
                <div className="h-0.5 bg-blue-500 rounded-full mx-2 -mb-px" />
              )}
              <div
                className={`border rounded-lg overflow-hidden transition-all ${
                  isSelected
                    ? "border-gray-900 bg-white ring-1 ring-gray-900"
                    : `${colors.border} ${colors.bg} hover:shadow-sm`
                } ${dragNum === q.id ? "opacity-40" : ""}`}
                onDragOver={(e) => handleDragOver(q.id, e)}
                onDrop={(e) => handleDrop(q.id, e)}
                onDragLeave={() => setDropTarget(null)}
              >
                <div className="flex">
                  <div className={`w-1 flex-shrink-0 ${colors.stripe}`} />

                  {isSelected && (
                    <div
                      className="flex items-center px-2 cursor-grab active:cursor-grabbing text-gray-400 hover:text-gray-700 select-none border-r border-gray-200 bg-gray-50"
                      draggable
                      onDragStart={(e) => handleDragStart(q.id, e)}
                      onDragEnd={handleDragEnd}
                      title="Drag to reorder"
                    >
                      <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor">
                        <circle cx="2" cy="2" r="1.5"/><circle cx="8" cy="2" r="1.5"/>
                        <circle cx="2" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/>
                        <circle cx="2" cy="14" r="1.5"/><circle cx="8" cy="14" r="1.5"/>
                      </svg>
                    </div>
                  )}

                  <div className="flex-1 p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-gray-900">#{q.num}{q.subLabel || ""}</span>
                        <span className="text-xs font-medium text-gray-600">{q.speaker}</span>
                        <div className="relative">
                          <button
                            onClick={(e) => { e.stopPropagation(); setReassigningNum(reassigningNum === q.id ? null : q.id); }}
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors.badge} hover:ring-2 hover:ring-gray-400`}
                          >
                            {q.part} <span className="text-[10px] opacity-60">&#9662;</span>
                          </button>
                          {reassigningNum === q.id && (
                            <div className="absolute top-6 left-0 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]">
                              {[...sectionNames, "Orphan"].filter(s => s !== q.part).map(s => (
                                <button
                                  key={s}
                                  onClick={(e) => reassignSection(q.id, s, e)}
                                  className={`w-full text-left px-3 py-1.5 text-xs font-medium hover:bg-gray-50 flex items-center gap-2`}
                                >
                                  <div className={`w-2 h-2 rounded-full ${(sectionColors[s] || ORPHAN_COLOR).stripe}`} />
                                  {s}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                        <span className="text-xs text-gray-400">{q.startTC} → {q.endTC}</span>
                        {hasEdit && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
                            trimmed
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {isSelected && !isEditing && splittingId !== q.id && (
                          <button
                            onClick={(e) => startSplit(q.id, e)}
                            className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                            title="Split this quote into sub-quotes"
                          >
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" d="M6 4l3 6M18 4l-3 6M9 10c0 3 6 3 6 0M9 10l-4 10M15 10l4 10"/>
                            </svg>
                          </button>
                        )}
                        <div
                          className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                            isSelected ? "bg-gray-900 border-gray-900" : "border-gray-300 bg-white"
                          }`}
                          onClick={(e) => { e.stopPropagation(); toggleSelect(q.id); }}
                        >
                          {isSelected && (
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </div>
                    </div>

                    <div>
                      <p className="text-sm text-gray-800 leading-relaxed mb-1">"{displayText}"</p>
                      {hasEdit && !isEditing && (
                        <span
                          onClick={(e) => startEditing(q.id, e)}
                          className="text-xs text-gray-400 cursor-pointer hover:text-gray-600"
                        >&#9654; show original &amp; edit</span>
                      )}
                      {hasEdit && isEditing && (
                        <span
                          onClick={(e) => { e.stopPropagation(); setEditingNum(null); }}
                          className="text-xs text-gray-400 cursor-pointer hover:text-gray-600"
                        >&#9660; show original &amp; edit</span>
                      )}
                      {!hasEdit && isSelected && !isEditing && (
                        <span
                          onClick={(e) => startEditing(q.id, e)}
                          className="text-xs text-gray-400 cursor-pointer hover:text-gray-600"
                        >&#9654; trim quote</span>
                      )}
                      {!hasEdit && isSelected && isEditing && (
                        <span
                          onClick={(e) => { e.stopPropagation(); setEditingNum(null); }}
                          className="text-xs text-gray-400 cursor-pointer hover:text-gray-600"
                        >&#9660; trim quote</span>
                      )}
                    </div>

                    {isEditing && (
                      <EditPanel
                        editOriginal={editOriginal}
                        editCuts={editCuts}
                        setEditCuts={setEditCuts}
                        onSave={() => saveEdit(q.id)}
                        onCancel={() => setEditingNum(null)}
                      />
                    )}

                    {splittingId === q.id && (
                      <SplitPanel
                        text={q.quote}
                        markers={splitMarkers}
                        setMarkers={setSplitMarkers}
                        onSplit={executeSplit}
                        onCancel={() => setSplittingId(null)}
                      />
                    )}

                    <p className="text-xs text-gray-500 italic mt-2">{q.rationale}</p>
                  </div>
                </div>
              </div>
              {/* Drop indicator line — bottom */}
              {dropTarget && dropTarget.id === q.id && dropTarget.half === "bottom" && (
                <div className="h-0.5 bg-blue-500 rounded-full mx-2 -mt-px" />
              )}

              {/* Interstitials placed after this quote */}
              {getInterstitialsAfter(q.id).map(t => (
                <div key={t.id} className="border border-dashed border-indigo-300 bg-indigo-50 rounded-lg overflow-hidden mt-1">
                  <div className="flex">
                    <div className="w-1 flex-shrink-0 bg-indigo-400" />
                    <div className="flex-1 p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-indigo-700">{t.id}</span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">TEXT INTERSTITIAL</span>
                          <span className="text-xs text-gray-400">after #{q.num}{q.subLabel || ""}</span>
                        </div>
                        <button onClick={() => removeInterstitial(t.id)} className="text-xs text-red-400 hover:text-red-600" title="Remove interstitial">✕</button>
                      </div>
                      {editingInterstitialId === t.id ? (
                        <div>
                          <textarea value={editInterstitialText} onChange={e => setEditInterstitialText(e.target.value)} className="w-full text-sm p-2 border border-indigo-200 rounded bg-white resize-y" rows={2} />
                          <div className="flex gap-2 mt-1">
                            <button onClick={() => saveEditInterstitial(t.id)} className="text-xs px-3 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-500">Save</button>
                            <button onClick={() => setEditingInterstitialId(null)} className="text-xs px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300">Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-indigo-900 leading-relaxed italic cursor-pointer hover:text-indigo-700" onClick={() => startEditInterstitial(t.id)}>"{t.text}"</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Interstitial placement drop zone — visible during placement mode */}
              {placingInterstitial && isSelected && (
                <div className="mt-1">
                  {pendingInterstitialAfter === q.id ? (
                    <div className="border border-dashed border-indigo-300 bg-indigo-50 rounded-lg p-3">
                      <label className="text-xs font-bold text-indigo-600 block mb-1">New text interstitial after #{q.num}{q.subLabel || ""}</label>
                      <textarea
                        value={newInterstitialText}
                        onChange={e => setNewInterstitialText(e.target.value)}
                        placeholder="Factual text for on-screen display (credentials, titles, context)..."
                        className="w-full text-sm p-2 border border-indigo-200 rounded bg-white resize-y"
                        rows={2}
                        autoFocus
                      />
                      <div className="flex gap-2 mt-1">
                        <button onClick={confirmInterstitial} disabled={!newInterstitialText.trim()} className={`text-xs px-3 py-1 rounded ${newInterstitialText.trim() ? "bg-indigo-600 text-white hover:bg-indigo-500" : "bg-gray-200 text-gray-400"}`}>Add</button>
                        <button onClick={cancelPlacement} className="text-xs px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300">Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div
                      onClick={() => placeInterstitial(q.id)}
                      className="h-6 mx-4 my-1 flex items-center justify-center rounded border-2 border-dashed border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50 cursor-pointer transition-colors group"
                    >
                      <span className="text-xs text-indigo-300 group-hover:text-indigo-500 font-medium">+ place interstitial here</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Selected quotes summary bar — collapsed by default */}
      {selectedQuotes.length > 0 && (
        <div className="mt-6 bg-gray-900 rounded-lg text-white sticky bottom-4">
          <button
            onClick={() => setShowSelectedBar(prev => !prev)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-bold hover:bg-gray-800 rounded-lg transition-colors"
          >
            <span>Selected Quotes ({selectedQuotes.length})</span>
            <span className="text-xs text-gray-400">{showSelectedBar ? "\u25BE" : "\u25B8"}</span>
          </button>
          {showSelectedBar && (
            <div className="flex flex-wrap gap-2 px-4 pb-3">
              {selectedQuotes.map(q => {
                const trailingInterstitials = getInterstitialsAfter(q.id);
                return [
                  <span key={q.id} className={`text-xs px-2 py-1 rounded-full ${(sectionColors[q.part] || ORPHAN_COLOR).badge}`}>
                    #{q.num}{q.subLabel || ""} — {q.part}{editedQuotes[q.id] !== undefined ? " (trimmed)" : ""}
                  </span>,
                  ...trailingInterstitials.map(t => (
                    <span key={t.id} className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-700">
                      {t.id} — TEXT
                    </span>
                  ))
                ];
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
