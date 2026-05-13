#!/usr/bin/env python3
"""
Generate FCPXML from Paper Cut spreadsheet tab.
Extracts quotes from source interview FCPXMLs and assembles them into a new FCPXML edit.

USAGE:
This script is designed to be adapted per-project. The main() function at the bottom
contains project-specific file paths and speaker configurations that should be updated
for each new project.

REQUIREMENTS:
- Source FCPXML files for each interview (with captions for timing)
- A reference FCPXML (like a Sample Narrative) that contains the resources section
- An Excel workbook with a "Paper Cut" tab containing the selected quotes in sequence

The Paper Cut tab should have columns:
  Seq #, Quote #, Speaker, Section, Quote, Start TC, End TC, Notes
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import openpyxl
from pathlib import Path
from fractions import Fraction
import re
import difflib
import bisect
from typing import List, Dict, Tuple, Optional


class FractionTime:
    """Helper class for managing time in fraction format (e.g., '435435/24000s')"""

    def __init__(self, numerator: int, denominator: int = 24000):
        self.numerator = numerator
        self.denominator = denominator

    @classmethod
    def from_string(cls, s: str) -> "FractionTime":
        """Parse from string like '435435/24000s'"""
        s = s.rstrip('s')
        if '/' in s:
            num, denom = s.split('/')
            return cls(int(num), int(denom))
        else:
            # Assume it's in seconds
            return cls(int(s) * 24000, 24000)

    def to_string(self) -> str:
        """Convert to FCPXML format like '435435/24000s'"""
        return f"{self.numerator}/{self.denominator}s"

    def to_frames(self) -> float:
        """Convert to frame count at 23.98fps (1001/24000s per frame)"""
        return (self.numerator / self.denominator) / (1001 / 24000)

    def __add__(self, other: "FractionTime") -> "FractionTime":
        """Add two times"""
        if self.denominator == other.denominator:
            return FractionTime(self.numerator + other.numerator, self.denominator)
        else:
            # Find common denominator
            common = self.denominator * other.denominator // self._gcd(self.denominator, other.denominator)
            return FractionTime(
                self.numerator * (common // self.denominator) + other.numerator * (common // other.denominator),
                common
            )

    def __sub__(self, other: "FractionTime") -> "FractionTime":
        """Subtract two times"""
        if self.denominator == other.denominator:
            return FractionTime(self.numerator - other.numerator, self.denominator)
        else:
            common = self.denominator * other.denominator // self._gcd(self.denominator, other.denominator)
            return FractionTime(
                self.numerator * (common // self.denominator) - other.numerator * (common // other.denominator),
                common
            )

    @staticmethod
    def _gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a


class Caption:
    """Represents a caption from source FCPXML"""

    def __init__(self, element: ET.Element):
        self.offset = FractionTime.from_string(element.get('offset'))
        self.duration = FractionTime.from_string(element.get('duration'))
        self.name = element.get('name')
        self.element = element

    def get_text(self) -> str:
        """Extract caption text from element"""
        text_elem = self.element.find('.//text-style')
        if text_elem is not None:
            return text_elem.text or ""
        return self.name or ""

    def end_offset(self) -> FractionTime:
        """Calculate end offset"""
        return self.offset + self.duration


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching"""
    text = text.lower()
    # Replace em-dash and en-dash with space
    text = text.replace('\u2014', ' ').replace('\u2013', ' ')
    # Remove punctuation and extra whitespace
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _tc_string_to_seconds(tc_str: str) -> Optional[float]:
    """
    Parse a timecode string into float seconds. Tolerant of:

      "HH:MM:SS"        — 3-part (most common in tagged-quotes JSON)
      "HH:MM:SS:FF"     — 4-part FCP timecode (frames at 23.98 fps)
      "HH:MM:SS.fff"    — decimal seconds
      "MM:SS" / "SS"    — short forms (assume hours=0 if shorter)

    Returns None if the string is empty/None or doesn't parse, so callers
    can fall back to full-range search without raising.
    """
    if not tc_str:
        return None
    s = tc_str.strip()
    if not s:
        return None
    # Decimal-seconds variant: "HH:MM:SS.fff" → split into "HH:MM:SS" + ".fff"
    decimal = 0.0
    if "." in s:
        # Only treat as decimal if the dot is to the right of the last colon.
        last_colon = s.rfind(":")
        last_dot = s.rfind(".")
        if last_dot > last_colon:
            try:
                decimal = float("0." + s[last_dot + 1:])
                s = s[:last_dot]
            except ValueError:
                pass
    parts = s.split(":")
    try:
        ints = [int(p) for p in parts]
    except ValueError:
        return None
    if len(ints) == 4:
        h, m, sec, frames = ints
        return h * 3600 + m * 60 + sec + frames * (1001.0 / 24000.0)
    elif len(ints) == 3:
        h, m, sec = ints
        return h * 3600 + m * 60 + sec + decimal
    elif len(ints) == 2:
        m, sec = ints
        return m * 60 + sec + decimal
    elif len(ints) == 1:
        return ints[0] + decimal
    return None


def _narrow_caption_search_window(captions: List[Caption],
                                  start_tc: Optional[str],
                                  end_tc: Optional[str],
                                  buffer_secs: float = 15.0
                                  ) -> Tuple[int, int]:
    """
    Compute (search_start_idx, search_end_idx) over `captions` based on a
    source-TC window, with a buffer on each side to absorb timing slop.

    Caption offsets (in FCPXML rational time) are interpreted as seconds
    from the captioned source's timeline origin. The TC strings on v5
    segments / v4 quotes come from the transcript and reference the same
    origin, so the comparison is direct.

    On any parse failure or missing TC strings, returns (0, len(captions))
    — full-range search — so the matcher behaves exactly as it did
    pre-narrowing.

    The ±buffer absorbs the small drift that can exist between transcript
    timestamps and caption offsets without losing real matches. The SKILL
    documents 15s as the validated default that keeps match scores at
    0.85-1.00 for long interviews while bringing match time from "timeout"
    to ~2 seconds.
    """
    if not captions:
        return 0, 0
    tc_start = _tc_string_to_seconds(start_tc) if start_tc else None
    tc_end   = _tc_string_to_seconds(end_tc)   if end_tc   else None

    full = (0, len(captions))
    if tc_start is None and tc_end is None:
        return full

    # If only one of the two TCs parsed, use it on both sides — better than
    # full search, still safe with the buffer.
    if tc_start is None:
        tc_start = tc_end
    if tc_end is None:
        tc_end = tc_start

    lo_secs = tc_start - buffer_secs
    hi_secs = tc_end + buffer_secs

    # Pre-compute caption offsets in seconds (already sorted by offset in
    # parse_source_fcpxml). bisect against the seconds list.
    offsets_secs = [c.offset.numerator / c.offset.denominator for c in captions]
    start_idx = bisect.bisect_left(offsets_secs, lo_secs)
    end_idx   = bisect.bisect_right(offsets_secs, hi_secs)
    # Always include at least one window-worth of captions on each side
    # so the matcher has room to anchor — even if the TC is slightly off.
    # max_span at sentence level is 15; pad by 15 on each side as well.
    start_idx = max(0, start_idx - 15)
    end_idx   = min(len(captions), end_idx + 15)
    # Guard against zero-width windows on bad TC pairs.
    if end_idx <= start_idx:
        return full
    return start_idx, end_idx


def find_captions_for_sentence(sentence_text: str, captions: List[Caption],
                               search_start: int = 0, search_end: int = None,
                               max_span: int = 15) -> Tuple[Optional[int], Optional[int], float]:
    """
    Fuzzy match a single sentence to a sequence of captions.
    Returns (start_caption_index, end_caption_index, match_score) or (None, None, 0.0).

    search_start/search_end: narrow the search window (useful for sequential sentences)
    max_span: maximum number of captions a single sentence can span
    """
    normalized = normalize_text(sentence_text)
    if not normalized or len(normalized.split()) < 2:
        return None, None, 0.0

    if search_end is None:
        search_end = len(captions)

    best_score = 0
    best_start = None
    best_end = None

    for start_idx in range(search_start, search_end):
        for end_idx in range(start_idx, min(start_idx + max_span, search_end)):
            concat_text = " ".join(
                normalize_text(captions[i].get_text())
                for i in range(start_idx, end_idx + 1)
            )
            matcher = difflib.SequenceMatcher(None, normalized, concat_text)
            score = matcher.ratio()

            if score > best_score:
                best_score = score
                best_start = start_idx
                best_end = end_idx

    if best_score > 0.55:
        return best_start, best_end, best_score

    return None, None, best_score


def split_into_sentences(text: str) -> List[str]:
    """
    Split a quote into sentences for individual matching.
    Handles common patterns like '. ', '? ', '! ' while avoiding splits on
    abbreviations or mid-sentence periods.
    """
    # Split on sentence-ending punctuation followed by space and capital letter
    # or on period-space patterns
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

    # Filter out very short fragments (under ~4 words) and merge them with neighbors
    merged = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if merged and len(part.split()) < 4:
            merged[-1] = merged[-1] + ' ' + part
        else:
            merged.append(part)

    return merged if merged else [text]


def find_captions_for_quote(quote_text: str, captions: List[Caption],
                            gap_threshold_secs: float = 5.0,
                            start_tc: Optional[str] = None,
                            end_tc: Optional[str] = None,
                            ) -> List[Tuple[int, int, float]]:
    """
    Match a (possibly trimmed) quote to caption ranges, splitting at gaps.

    When the editor trims content from the middle of a quote, the surviving phrases
    live at non-contiguous points in the timeline. This function matches each sentence
    independently and splits into separate ranges when gaps exceed the threshold.

    gap_threshold_secs: minimum gap (in seconds) between matched caption ranges to
        trigger a clip split. Gaps below this are kept in one clip — the editor will
        clean up small filler in Final Cut Pro. Default: 5.0 seconds.

    Step 8 — TC-window narrowing (SKILL Phase 2.3):
      start_tc / end_tc:  optional source-timecode strings (HH:MM:SS or
        HH:MM:SS:FF). When provided, the caption search is narrowed to the
        index range whose offsets fall within [start_tc - 15s, end_tc + 15s]
        — same matcher, dramatically smaller scan window. On long
        interviews (e.g. 700+ caption Tyanna interview), this brings
        per-quote match time from "timeout" to ~2s while keeping match
        scores at 0.85–1.00. If TCs are missing or unparseable, the
        function falls back to the legacy full-range search.

    Returns a list of (start_idx, end_idx, score) tuples — one per clip segment.
    Returns empty list if no match found.
    """
    sentences = split_into_sentences(quote_text)

    # Narrow the search window once per quote — same window for every
    # sentence in the quote. Sentences are by definition contiguous in the
    # source, so the same buffered window covers all of them.
    search_start_idx, search_end_idx = _narrow_caption_search_window(
        captions, start_tc, end_tc
    )

    # Match each sentence to captions
    sentence_matches = []
    search_hint = search_start_idx  # Advances as we match within the window

    for sentence in sentences:
        start_idx, end_idx, score = find_captions_for_sentence(
            sentence, captions,
            search_start=max(search_start_idx, search_hint - 10),
            search_end=search_end_idx,
        )
        if start_idx is not None:
            sentence_matches.append((start_idx, end_idx, score))
            search_hint = end_idx + 1
        # If a sentence doesn't match, skip it — don't break the chain

    if not sentence_matches:
        # Fallback: try matching the entire quote as one block. Still
        # respect the TC window — it's a much bigger max_span but still
        # bounded to the buffered range.
        start_idx, end_idx, score = find_captions_for_sentence(
            quote_text, captions, max_span=40,
            search_start=search_start_idx, search_end=search_end_idx,
        )
        if start_idx is not None:
            return [(start_idx, end_idx, score)]
        return []

    # Merge sentence matches into clip segments, splitting at large gaps
    segments = []
    seg_start = sentence_matches[0][0]
    seg_end = sentence_matches[0][1]
    seg_scores = [sentence_matches[0][2]]

    for i in range(1, len(sentence_matches)):
        prev_end = seg_end
        curr_start = sentence_matches[i][0]

        # Calculate gap in seconds between end of previous match and start of current
        prev_end_time = captions[prev_end].end_offset()
        curr_start_time = captions[curr_start].offset
        gap_secs = (curr_start_time.numerator / curr_start_time.denominator -
                    prev_end_time.numerator / prev_end_time.denominator)

        if gap_secs >= gap_threshold_secs:
            # Gap exceeds threshold — split here
            avg_score = sum(seg_scores) / len(seg_scores)
            segments.append((seg_start, seg_end, avg_score))
            seg_start = curr_start
            seg_end = sentence_matches[i][1]
            seg_scores = [sentence_matches[i][2]]
        else:
            # Gap is small — extend current segment
            seg_end = sentence_matches[i][1]
            seg_scores.append(sentence_matches[i][2])

    # Don't forget the last segment
    avg_score = sum(seg_scores) / len(seg_scores)
    segments.append((seg_start, seg_end, avg_score))

    return segments


def parse_source_fcpxml(filepath: str, speaker_name: str) -> Dict:
    """
    Parse a source FCPXML and extract captions + resources.

    Returns a dict with:
      'captions':  list of Caption objects (sorted by offset)
      'resources': the source's <resources> ET.Element (or None if absent).
                   Needed by merge_speaker_resources() so multi-speaker
                   projects can be assembled with dynamic ID remapping.

    Both multicam and single_clip source FCPXMLs are supported — captions
    are found recursively (`.//caption`) so they're discovered whether
    they're nested under `<mc-clip>/<mc-angle>` or directly under
    `<asset-clip>`.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    captions = []
    for caption_elem in root.findall('.//caption'):
        caption = Caption(caption_elem)
        captions.append(caption)
    captions.sort(key=lambda c: c.offset.numerator / c.offset.denominator)

    resources = root.find('resources')

    return {'captions': captions, 'resources': resources}


# ---------------------------------------------------------------------------
# Multi-speaker resource-ID dynamic remap (Phase 2.1 of SKILL-fcpxml.md)
# ---------------------------------------------------------------------------

def _remap_ids_in_subtree(element: ET.Element, id_map: Dict[str, str]) -> None:
    """
    Recursively rewrite resource-ID-style attributes inside an XML subtree.

    Rewrites `id`, `ref`, `src`, and `format` attributes whose values appear
    as keys in `id_map`. Operates in-place. Used to "shift" a copied
    speaker's resource subtree so its IDs sit above another speaker's
    high-water mark.

    Note: `src` is included because some source FCPXMLs reference
    sub-assets via `src="r3"` style refs inside a parent media element.
    """
    for attr in ("id", "ref", "src", "format"):
        val = element.get(attr)
        if val and val in id_map:
            element.set(attr, id_map[val])
    for child in element:
        _remap_ids_in_subtree(child, id_map)


def _format_signature(format_el: ET.Element) -> Tuple:
    """
    A stable signature for a `<format>` element so we can detect duplicates
    across speakers without comparing IDs. Captures the attributes FCP uses
    to identify a format (width, height, frameDuration, colorSpace, name).
    """
    return (
        format_el.get('frameDuration', ''),
        format_el.get('width', ''),
        format_el.get('height', ''),
        format_el.get('colorSpace', ''),
        format_el.get('name', ''),
    )


def merge_speaker_resources(source_fcpxmls: Dict[str, Dict],
                            speaker_refs: Optional[Dict[str, str]] = None,
                            asset_refs: Optional[Dict[str, str]] = None
                            ) -> Tuple[ET.Element, Dict[str, str],
                                       Dict[str, str],
                                       Dict[str, Dict[str, str]], int]:
    """
    Build a merged `<resources>` element from per-speaker source FCPXMLs,
    with dynamic ID remapping to avoid r2/r3/etc. collisions across
    speakers. Implements the strategy described in SKILL-fcpxml.md Phase
    2.1 (multi-speaker resource-ID collision).

    Strategy:
      1. Iterate speakers in a stable, sorted order so the same project
         always produces the same merged resources.
      2. The first speaker's resources are copied as-is. Their IDs stay
         exactly as they were in the source FCPXML. Track the highest ID
         number seen so far (high-water mark).
      3. For each subsequent speaker:
         - Skip their `<format>` element if it duplicates a format we
           already accepted (same signature). All single-NLE projects
           ship with identical formats per interview, so this is the
           common case. If a speaker's format is genuinely different, it
           gets remapped to a fresh ID and included.
         - Remap every other resource ID to start above the high-water
           mark. Build a per-speaker `old_id → new_id` dict and apply it
           recursively to the copied resource subtree before appending
           it to the merged element.

    Args:
      source_fcpxmls: {speaker: {"resources": <ET.Element>, "captions": ...}}
      speaker_refs:   {multicam speaker: source-side media ref id}
      asset_refs:     {single_clip speaker: source-side asset ref id}

    Returns:
      merged_resources:       the assembled `<resources>` element
      speaker_refs_remapped:  speaker_refs with values rewritten to the
                              post-merge IDs
      asset_refs_remapped:    asset_refs with values rewritten to the
                              post-merge IDs
      per_speaker_remap:      {speaker: {old_id: new_id, ...}} — useful
                              for callers that need to remap additional
                              attributes (currently unused, returned for
                              future use)
      max_id_used:            highest ID number consumed by any merged
                              resource (caller can place effects at
                              max_id_used + 1)
    """
    speaker_refs = speaker_refs or {}
    asset_refs = asset_refs or {}

    merged = ET.Element('resources')
    per_speaker_remap: Dict[str, Dict[str, str]] = {}
    speaker_refs_remapped: Dict[str, str] = {}
    asset_refs_remapped: Dict[str, str] = {}

    high_water = 0
    seen_format_signatures: Dict[Tuple, str] = {}
    speaker_count = 0

    # Speakers in a stable order — sort alphabetically so the same input
    # always produces the same output IDs.
    speakers_sorted = sorted(source_fcpxmls.keys())

    for speaker in speakers_sorted:
        src = source_fcpxmls[speaker]
        src_resources = src.get('resources')
        if src_resources is None:
            print(f"Warning: speaker {speaker!r} source has no <resources>; "
                  "skipping in merge")
            continue

        speaker_count += 1
        is_first_speaker = (speaker_count == 1)
        id_map: Dict[str, str] = {}
        aliased_ids: set = set()  # ids whose element should NOT be re-emitted

        # Pass 1: decide a remap for every id-bearing element in the
        # speaker's source resources.
        for el in src_resources:
            old_id = el.get('id', '')
            if not old_id:
                continue
            if not (old_id.startswith('r') and old_id[1:].isdigit()):
                # Non-canonical id (rare) — preserve verbatim, no remap.
                id_map[old_id] = old_id
                continue

            if is_first_speaker:
                # First speaker contributes everything as-is. Their IDs
                # define the initial high-water mark.
                id_map[old_id] = old_id
                high_water = max(high_water, int(old_id[1:]))
                if el.tag == 'format':
                    seen_format_signatures[_format_signature(el)] = old_id
                continue

            # Subsequent speakers: detect duplicate formats first.
            if el.tag == 'format':
                sig = _format_signature(el)
                existing = seen_format_signatures.get(sig)
                if existing is not None:
                    # Alias this speaker's format id to the existing one.
                    id_map[old_id] = existing
                    aliased_ids.add(old_id)
                    continue

            # Allocate the next available id above the high-water mark.
            high_water += 1
            new_id = f"r{high_water}"
            id_map[old_id] = new_id
            if el.tag == 'format':
                seen_format_signatures[_format_signature(el)] = new_id

        # Pass 2: deep-copy each resource element, apply the remap to all
        # id/ref/src/format attributes inside it, append to merged unless
        # this id was aliased to an already-merged format (skip those).
        for el in src_resources:
            old_id = el.get('id', '')
            if old_id in aliased_ids:
                continue
            new_el = ET.fromstring(ET.tostring(el))
            _remap_ids_in_subtree(new_el, id_map)
            merged.append(new_el)

        per_speaker_remap[speaker] = id_map

        # Remap the inbound speaker_refs / asset_refs for this speaker.
        if speaker in speaker_refs:
            old = speaker_refs[speaker]
            speaker_refs_remapped[speaker] = id_map.get(old, old)
        if speaker in asset_refs:
            old = asset_refs[speaker]
            asset_refs_remapped[speaker] = id_map.get(old, old)

    return merged, speaker_refs_remapped, asset_refs_remapped, \
           per_speaker_remap, high_water


def read_paper_cut_tab(excel_path: str, tab_name: str) -> List[Dict]:
    """
    Read a Paper Cut tab from the Excel workbook.
    Returns list of quote dictionaries.

    Tab should have columns: Seq #, Quote #, Speaker, Section, Quote, Start TC, End TC, Notes
    """
    wb = openpyxl.load_workbook(excel_path)
    ws = wb[tab_name]

    quotes = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        seq_num, quote_num, speaker, section, quote_text, start_tc, end_tc, notes = row

        if seq_num is None or quote_text is None:
            continue

        quotes.append({
            'seq_num': seq_num,
            'quote_num': quote_num,
            'speaker': speaker,
            'section': section,
            'quote': quote_text,
            'start_tc': start_tc,
            'end_tc': end_tc,
            'notes': notes,
        })

    return quotes


def timecode_to_frames(tc_str: str) -> int:
    """Convert HH:MM:SS:FF timecode to frame count at 23.98fps"""
    parts = tc_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    frames = int(parts[3])

    # Total seconds
    total_seconds = hours * 3600 + minutes * 60 + seconds

    # Convert to frame count (23.98fps = 24000/1001 frames per second)
    frame_count = int(total_seconds * 24000 / 1001 + frames)

    return frame_count


def create_section_divider(section_name: str, offset: FractionTime,
                           title_effect_ref: str, text_style_counter: int,
                           duration: Optional[FractionTime] = None,
                           ) -> Tuple[ET.Element, FractionTime, int]:
    """
    Create a section divider: a short gap with a title overlay displaying
    the section name. Returns (gap_element, new_offset, new_text_style_counter).

    This is the act-boundary title card described in SKILL-fcpxml.md
    Phase 2.1.5 — required on every emission, used by the editor as a
    structural anchor in the FCP timeline. Stripped at finishing.

    Section name mapping: "Opening" -> "Intro", others stay as-is.

    Args:
      duration: optional FractionTime override. Defaults to 0.67s
                (16016/24000s = 16 frames at 23.98 fps) — the SKILL's
                established default. Pre-step-6 code used 1s; that was
                long enough to feel like a beat instead of a marker.
    """
    display_name = "Intro" if section_name == "Opening" else section_name
    # SKILL Phase 2.1.5: 0.67s default. 16 frames at 23.98 fps =
    # 16 * 1001 / 24000 = 16016/24000 = ~0.667s.
    gap_duration = duration if duration is not None else FractionTime(16016, 24000)

    gap = ET.Element('gap')
    gap.set('name', 'Gap')
    gap.set('offset', offset.to_string())
    gap.set('start', '86400314/24000s')
    gap.set('duration', gap_duration.to_string())

    title = ET.SubElement(gap, 'title')
    title.set('ref', title_effect_ref)
    title.set('lane', '1')
    title.set('offset', '86400314/24000s')
    title.set('name', f'{display_name} - Basic Title')
    title.set('start', '86486400/24000s')
    title.set('duration', '120120/120000s')

    # Title parameters
    flatten = ET.SubElement(title, 'param')
    flatten.set('name', 'Flatten')
    flatten.set('key', '9999/999166631/999166633/2/351')
    flatten.set('value', '1')

    alignment = ET.SubElement(title, 'param')
    alignment.set('name', 'Alignment')
    alignment.set('key', '9999/999166631/999166633/2/354/999169573/401')
    alignment.set('value', '1 (Center)')

    # Title text
    ts_id = f"ts{text_style_counter}"
    text_style_counter += 1

    text_elem = ET.SubElement(title, 'text')
    text_style = ET.SubElement(text_elem, 'text-style')
    text_style.set('ref', ts_id)
    text_style.text = display_name

    text_style_def = ET.SubElement(title, 'text-style-def')
    text_style_def.set('id', ts_id)
    ts_inner = ET.SubElement(text_style_def, 'text-style')
    ts_inner.set('font', 'Helvetica Neue')
    ts_inner.set('fontSize', '144')
    ts_inner.set('fontFace', 'UltraLight')
    ts_inner.set('fontColor', '1 1 1 1')
    ts_inner.set('alignment', 'center')

    new_offset = offset + gap_duration
    return gap, new_offset, text_style_counter


def _canonicalize_section(section: str, act_labels: List[str]) -> str:
    """
    Map a quote's `section` (the v5 `part` field, copied through by
    adapt_quote) to a canonical act label from act-structure.md.

    Strategy: exact case-insensitive match first, then bidirectional
    substring match (handles "Act 1: Intro" matching against "Intro", or
    vice versa). Returns the canonical label on a match, or the original
    `section` string on miss (with the original casing preserved).
    """
    if not section or not act_labels:
        return section or ""
    sl = section.strip().lower()
    if not sl:
        return ""
    # Exact, case-insensitive
    for label in act_labels:
        if label.lower() == sl:
            return label
    # Bidirectional substring
    for label in act_labels:
        ll = label.lower()
        if sl in ll or ll in sl:
            return label
    return section


def build_spine(paper_cuts: List[Dict], source_fcpxmls: Dict[str, Dict],
                speaker_refs: Dict[str, str], speaker_angles: Dict[str, str],
                gap_threshold_secs: float = 5.0,
                title_effect_ref: str = "r2",
                clip_types: Optional[Dict[str, str]] = None,
                asset_refs: Optional[Dict[str, str]] = None,
                asset_names: Optional[Dict[str, str]] = None,
                format_ref: str = "r1",
                act_labels: Optional[List[str]] = None,
                ) -> Tuple[List[ET.Element], int]:
    """
    Build spine elements (mc-clip / asset-clip nodes and section divider gaps)
    from paper cut quotes. Returns (list of spine elements, final
    text_style_counter).

    When a trimmed quote has content removed from the middle, this produces
    multiple clip elements for that quote — one per contiguous segment. Gaps
    under gap_threshold_secs are kept in a single clip for the editor to
    clean up in FCP.

    Inserts section divider gaps (with title overlays) between narrative
    sections.

    Args:
      speaker_refs:    maps multicam speaker name → media ref id
                       (e.g., {"Rob Manion": "r2"})
      speaker_angles:  maps multicam speaker name → angleID
      gap_threshold_secs: minimum gap to trigger a clip split (default 5.0s)
      title_effect_ref:   ref id for the Basic Title effect in resources

      v5.2 — per-interview clip_type branching:
      clip_types:  maps speaker name → "multicam" | "single_clip". When a
                   speaker's clip_type is "single_clip", this function emits
                   `<asset-clip>` instead of `<mc-clip>` for that speaker's
                   clips. Defaults to multicam for any speaker not listed
                   (preserves legacy behavior).
      asset_refs:  maps single_clip speaker name → asset ref id (required for
                   each single_clip speaker).
      asset_names: maps single_clip speaker name → asset name string
                   (populates the asset-clip's `name` attribute; falls back
                   to the speaker's first name if missing).
      format_ref:  format ref id used on emitted asset-clip elements
                   (default "r1").
    """
    clip_types = clip_types or {}
    asset_refs = asset_refs or {}
    asset_names = asset_names or {}
    act_labels = act_labels or []

    spine_clips = []
    offset = FractionTime(0, 24000)  # Cumulative offset
    text_style_counter = 1
    padding = FractionTime(2002, 24000)  # ~2 frames padding on each side
    current_section = None

    for quote_info in paper_cuts:
        speaker = quote_info['speaker']
        quote_text = quote_info['quote']
        section = quote_info.get('section', '')

        # SKILL Phase 2.1.5 — auto act-boundary title cards. When the
        # act-structure labels are available, normalize each quote's
        # section to its canonical act label so a card is emitted exactly
        # once per declared act regardless of how the Edit Agent labeled
        # individual quotes (the section field can drift from the
        # canonical wording across rounds).
        if act_labels:
            section = _canonicalize_section(section, act_labels)

        # Insert section divider when the section changes
        if section and section != current_section:
            divider, offset, text_style_counter = create_section_divider(
                section, offset, title_effect_ref, text_style_counter
            )
            spine_clips.append(divider)
            current_section = section
            print(f"\n  --- {section} ---")

        if speaker not in source_fcpxmls:
            print(f"Warning: speaker '{speaker}' not in source FCPXMLs, skipping")
            continue

        captions = source_fcpxmls[speaker]['captions']

        # Find matching caption segments (may be multiple if trimmed from
        # middle). Step 8 — pass start_tc/end_tc so the matcher narrows
        # its scan window to the ±15s buffered TC range. For long
        # interviews this is the difference between completing in seconds
        # and hitting the shell timeout.
        segments = find_captions_for_quote(
            quote_text, captions, gap_threshold_secs,
            start_tc=quote_info.get('start_tc') or None,
            end_tc=quote_info.get('end_tc') or None,
        )

        if not segments:
            print(f"Warning: could not match quote '{quote_text[:50]}...' for {speaker}")
            continue

        # Per-interview clip_type — multicam (default) vs single_clip
        clip_type = clip_types.get(speaker, "multicam")
        if clip_type not in {"multicam", "single_clip"}:
            print(f"Warning: unknown clip_type {clip_type!r} for {speaker!r}; "
                  "falling back to multicam")
            clip_type = "multicam"

        # Resolve per-clip-type attributes BEFORE logging, so a config error
        # (e.g. single_clip speaker without an asset_ref) produces a single
        # skip warning rather than a misleading "1 clip" log followed by a
        # silent drop.
        if clip_type == "single_clip":
            ref = asset_refs.get(speaker)
            if not ref:
                print(f"Warning: speaker {speaker!r} is single_clip but has "
                      "no asset ref id; skipping its quotes")
                continue
            # The asset name from params is preferable (matches the
            # captioned interview filename); fall back to the speaker's
            # first name if absent.
            name = asset_names.get(speaker) or speaker.split()[0]
            angle_id = ""  # Not used for asset-clip
        else:
            ref = speaker_refs.get(speaker, "r2")
            name = speaker.split()[0]  # First name only
            angle_id = speaker_angles.get(speaker, "")

        quote_num = quote_info.get('quote_num', '?')
        section_print = quote_info.get('section', '?')
        type_tag = "asset-clip" if clip_type == "single_clip" else "mc-clip"
        if len(segments) > 1:
            print(f"  Quote #{quote_num} [{section_print}] ({type_tag}): "
                  f"{len(segments)} clips (split at gaps)")
        else:
            print(f"  Quote #{quote_num} [{section_print}] ({type_tag}): "
                  f"1 clip (score={segments[0][2]:.2f})")

        for seg_idx, (start_idx, end_idx, score) in enumerate(segments):
            start_caption = captions[start_idx]
            end_caption = captions[end_idx]

            clip_start = start_caption.offset - padding
            if clip_start.numerator < 0:
                clip_start = FractionTime(0, 24000)

            clip_end = end_caption.end_offset() + padding
            clip_duration = clip_end - clip_start

            # Branch on clip_type to emit the right spine element.
            if clip_type == "single_clip":
                clip = ET.Element('asset-clip')
                clip.set('ref', ref)
                clip.set('offset', offset.to_string())
                clip.set('name', name)
                clip.set('start', clip_start.to_string())
                clip.set('duration', clip_duration.to_string())
                clip.set('format', format_ref)
                clip.set('tcFormat', 'NDF')
                clip.set('audioRole', 'dialogue')
                # No <mc-source> child — single_clip is not multicam.
            else:
                clip = ET.Element('mc-clip')
                clip.set('ref', ref)
                clip.set('offset', offset.to_string())
                clip.set('name', name)
                clip.set('start', clip_start.to_string())
                clip.set('duration', clip_duration.to_string())
                mc_source = ET.SubElement(clip, 'mc-source')
                mc_source.set('angleID', angle_id)
                mc_source.set('srcEnable', 'all')

            # Add captions from source for this segment. Caption structure is
            # identical for both clip types — they become direct children of
            # whichever clip element we built above.
            for i in range(start_idx, end_idx + 1):
                caption = captions[i]
                caption_elem = ET.fromstring(ET.tostring(caption.element))

                text_style_def = caption_elem.find('.//text-style-def')
                if text_style_def is not None:
                    new_ts_id = f"ts{text_style_counter}"
                    text_style_counter += 1
                    text_style_def.set('id', new_ts_id)
                    text_style_ref = caption_elem.find('.//text-style')
                    if text_style_ref is not None:
                        text_style_ref.set('ref', new_ts_id)

                caption_elem.set('lane', '1')
                caption_elem.set('role', 'iTT?captionFormat=ITT.en-US')
                clip.append(caption_elem)

            spine_clips.append(clip)
            offset = offset + clip_duration

            if len(segments) > 1:
                seg_dur = clip_duration.numerator / clip_duration.denominator
                print(f"    Segment {seg_idx + 1}: captions {start_idx}-{end_idx}, {seg_dur:.1f}s")

    return spine_clips, text_style_counter


def generate_fcpxml(paper_cuts: List[Dict], source_fcpxmls: Dict[str, Dict],
                   reference_path: str, output_path: str,
                   speaker_refs: Dict[str, str], speaker_angles: Dict[str, str],
                   project_name: str = "Generated Edit",
                   clip_types: Optional[Dict[str, str]] = None,
                   asset_refs: Optional[Dict[str, str]] = None,
                   asset_names: Optional[Dict[str, str]] = None,
                   act_labels: Optional[List[str]] = None,
                   library_location: Optional[str] = None,
                   event_name: Optional[str] = None,
                   event_uid: Optional[str] = None,
                   format_ref: Optional[str] = None):
    """
    Generate the output FCPXML file.

    paper_cuts:      list of quote dicts from read_paper_cut_tab() or
                     build_fcpxml.load_quotes()
    source_fcpxmls:  dict mapping speaker name to parsed FCPXML data
    reference_path:  path to a reference FCPXML (for resources section)
    output_path:     where to write the generated FCPXML
    speaker_refs:    maps multicam speaker name → media ref id
    speaker_angles:  maps multicam speaker name → angleID
    project_name:    name for the project in the FCPXML

    v5.2 — per-interview clip_type branching:
      clip_types:  maps speaker name → "multicam" | "single_clip". When a
                   speaker is "single_clip", build_spine() emits
                   `<asset-clip>` instead of `<mc-clip>` for that speaker.
                   Speakers not listed default to multicam.
      asset_refs:  maps single_clip speaker name → asset ref id (required
                   when a speaker is configured as single_clip).
      asset_names: maps single_clip speaker name → asset name string
                   (populates the asset-clip's `name` attribute).
    """

    # Parse reference file — used for the library/event/project skeleton.
    # Resources come from merging the per-speaker source FCPXMLs below;
    # the reference file's resources are no longer copied.
    ref_tree = ET.parse(reference_path)
    ref_root = ref_tree.getroot()

    # Build merged resources from speaker sources with dynamic ID remap.
    # Multi-speaker projects ship as separate captioned FCPXMLs that all
    # use overlapping `r2`/`r3` IDs in their own files — merge_speaker_resources
    # resolves the collisions and returns post-merge speaker_refs /
    # asset_refs so the spine clips can reference the right resources.
    #
    # SKILL Phase 2.1.6 — library-multicam UID references. The merge does
    # a deep copy of each speaker's `<media>` element which PRESERVES the
    # multicam's `uid` attribute verbatim. Combined with a `<library
    # location>` and `<event uid>` that match the destination FCP library
    # (from params, below), this lets FCP recognize the multicam as the
    # one already in the library on re-import rather than creating a
    # duplicate. Do not strip `uid` from the merged `<media>` block — it
    # is the multicam identity FCP keys on.
    merged_resources, speaker_refs_remapped, asset_refs_remapped, \
        _per_speaker_remap, max_id = merge_speaker_resources(
            source_fcpxmls, speaker_refs, asset_refs
        )

    # Basic Title effect lives at the next available id above all merged
    # resource ids.
    title_effect_ref = f"r{max_id + 1}"
    title_effect = ET.SubElement(merged_resources, 'effect')
    title_effect.set('id', title_effect_ref)
    title_effect.set('name', 'Basic Title')
    title_effect.set('uid', '.../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti')

    # Resolve sequence format. Prefer the params-provided format_ref (which
    # the FCPXML Params Agent extracted from the source FCPXMLs directly);
    # fall back to the reference file's sequence format; final fallback "r1".
    # After the merge, the first speaker's format id is preserved verbatim,
    # so this typically lines up with that id.
    ref_sequence = ref_root.find('.//sequence')
    if format_ref:
        sequence_format = format_ref
    elif ref_sequence is not None:
        sequence_format = ref_sequence.get('format', 'r1')
    else:
        sequence_format = 'r1'

    # Build spine (with act-boundary title cards + per-interview clip_type
    # branching). Note: pass the POST-MERGE speaker_refs/asset_refs so each
    # spine clip references the correct (post-remap) resource id, and pass
    # act_labels so the section dividers use canonical wording from
    # act-structure.md (SKILL Phase 2.1.5).
    spine_clips, final_ts_count = build_spine(
        paper_cuts, source_fcpxmls,
        speaker_refs_remapped, speaker_angles,
        title_effect_ref=title_effect_ref,
        clip_types=clip_types,
        asset_refs=asset_refs_remapped,
        asset_names=asset_names,
        format_ref=sequence_format,
        act_labels=act_labels,
    )

    # Calculate total duration
    total_duration = FractionTime(0, 24000)
    for clip in spine_clips:
        duration_str = clip.get('duration')
        duration = FractionTime.from_string(duration_str)
        total_duration = total_duration + duration

    # Create new root element
    new_root = ET.Element('fcpxml')
    new_root.set('version', '1.14')

    # Use merged speaker resources (with Basic Title effect already appended)
    # rather than copying from the reference file — see merge_speaker_resources.
    new_root.append(merged_resources)

    # Create library/event/project/sequence structure.
    #
    # SKILL Phase 2.1.6 — library_location, event_name, and event_uid
    # MUST match the destination FCP library so multicam UIDs are
    # recognized as the existing ones rather than imported as duplicates.
    # The FCPXML Params Agent reads these from the source FCPXMLs and
    # writes them into fcpxml-params-v[N].md; prefer the params values
    # when provided, fall back to the reference file otherwise. The
    # reference fallback existed before step 7 and is preserved so older
    # projects (whose params md lacks these fields) keep working.
    ref_library = ref_root.find('.//library')
    ref_event = ref_root.find('.//event')
    ref_project = ref_root.find('.//project')

    resolved_lib_loc = library_location or (
        ref_library.get('location', '') if ref_library is not None else '')
    resolved_event_name = event_name or (
        ref_event.get('name', '') if ref_event is not None else '')
    resolved_event_uid = event_uid or (
        ref_event.get('uid', '') if ref_event is not None else '')

    library = ET.SubElement(new_root, 'library')
    library.set('location', resolved_lib_loc)

    event = ET.SubElement(library, 'event')
    event.set('name', resolved_event_name)
    if resolved_event_uid:
        event.set('uid', resolved_event_uid)

    project = ET.SubElement(event, 'project')
    project.set('name', project_name)
    # Project uid/modDate are not load-bearing for multicam recognition
    # (the multicam UIDs in <resources> are what FCP keys on) but a stable
    # project uid keeps re-imports tidy. Pull from reference if available;
    # otherwise omit — FCP will assign on import.
    if ref_project is not None:
        if ref_project.get('uid'):
            project.set('uid', ref_project.get('uid'))
        if ref_project.get('modDate'):
            project.set('modDate', ref_project.get('modDate'))

    sequence = ET.SubElement(project, 'sequence')
    sequence.set('format', sequence_format)
    sequence.set('duration', total_duration.to_string())
    sequence.set('tcStart', '0s')
    sequence.set('tcFormat', 'NDF')
    sequence.set('audioLayout', 'stereo')
    sequence.set('audioRate', '48k')

    spine = ET.SubElement(sequence, 'spine')

    # Add clips to spine
    for clip in spine_clips:
        spine.append(clip)

    # Convert to string with proper formatting
    xml_str = ET.tostring(new_root, encoding='unicode')

    # Pretty print
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='    ')

    # Remove extra blank lines and fix DOCTYPE
    lines = pretty_xml.split('\n')
    output_lines = []
    for i, line in enumerate(lines):
        if line.strip() and not (line.strip() == '<?xml version="1.0" ?>'):
            output_lines.append(line)
        elif '<?xml' in line:
            output_lines.insert(0, '<?xml version="1.0" encoding="UTF-8"?>')

    # Insert DOCTYPE after XML declaration
    output_lines.insert(1, '<!DOCTYPE fcpxml>')

    final_xml = '\n'.join(output_lines)

    # Write to file
    with open(output_path, 'w') as f:
        f.write(final_xml)

    print(f"Generated FCPXML with {len(spine_clips)} clips")
    print(f"Total duration: {total_duration.to_string()}")


# ============================================================================
# PROJECT-SPECIFIC CONFIGURATION (update for each new project)
# ============================================================================

def main():
    """
    Example main() from the Epicor/Manion's project.
    Adapt file paths, speaker names, refs, and angles for each new project.
    """

    # --- File paths (project-specific) ---
    rob_fcpxml = "Rob Manion.fcpxml"
    dave_fcpxml = "Dave Carlson.fcpxml"
    gary_fcpxml = "Gary Tabor.fcpxml"
    excel_path = "epicor_manions_quotes.xlsx"
    reference_path = "Sample Narrative.fcpxml"
    output_path = "generated_edit.fcpxml"

    # --- Speaker media refs (from reference FCPXML resources section) ---
    # These map speaker names to the media id in the resources section
    speaker_refs = {
        "Rob Manion": "r10",
        "Dave Carlson": "r2",
        "Gary Tabor": "r7",
    }

    # --- Speaker angle IDs (from reference FCPXML mc-angle elements) ---
    # These select which camera angle (tele vs wide) to use
    speaker_angles = {
        "Rob Manion": "6qdCZ2zfRbqgFeGrlSbgog",
        "Dave Carlson": "svco9FhKQmC/YCvKnhznyg",
        "Gary Tabor": "2HhjKpy7QzyY2CeXSpBnCA",
    }

    # --- Paper Cut tab name ---
    tab_name = "Paper Cut - Rob & Dave"

    # Parse source FCPXMLs
    print("Parsing source FCPXMLs...")
    source_fcpxmls = {
        "Rob Manion": parse_source_fcpxml(rob_fcpxml, "Rob Manion"),
        "Dave Carlson": parse_source_fcpxml(dave_fcpxml, "Dave Carlson"),
        "Gary Tabor": parse_source_fcpxml(gary_fcpxml, "Gary Tabor"),
    }

    for name, data in source_fcpxmls.items():
        print(f"  {name}: {len(data['captions'])} captions")

    # Read Paper Cut tab
    print(f"\nReading Paper Cut tab: '{tab_name}'...")
    paper_cuts = read_paper_cut_tab(excel_path, tab_name)
    print(f"  Found {len(paper_cuts)} quotes")

    # Generate FCPXML
    print("\nGenerating FCPXML...")
    generate_fcpxml(
        paper_cuts, source_fcpxmls, reference_path, output_path,
        speaker_refs, speaker_angles,
        project_name="Generated Paper Cut"
    )

    print(f"\nOutput written to {output_path}")


if __name__ == '__main__':
    main()
