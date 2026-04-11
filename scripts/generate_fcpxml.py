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
                            gap_threshold_secs: float = 5.0
                            ) -> List[Tuple[int, int, float]]:
    """
    Match a (possibly trimmed) quote to caption ranges, splitting at gaps.

    When the editor trims content from the middle of a quote, the surviving phrases
    live at non-contiguous points in the timeline. This function matches each sentence
    independently and splits into separate ranges when gaps exceed the threshold.

    gap_threshold_secs: minimum gap (in seconds) between matched caption ranges to
        trigger a clip split. Gaps below this are kept in one clip — the editor will
        clean up small filler in Final Cut Pro. Default: 5.0 seconds.

    Returns a list of (start_idx, end_idx, score) tuples — one per clip segment.
    Returns empty list if no match found.
    """
    sentences = split_into_sentences(quote_text)

    # Match each sentence to captions
    sentence_matches = []
    search_hint = 0  # Start searching from here, advances as we match

    for sentence in sentences:
        start_idx, end_idx, score = find_captions_for_sentence(
            sentence, captions, search_start=max(0, search_hint - 10)
        )
        if start_idx is not None:
            sentence_matches.append((start_idx, end_idx, score))
            search_hint = end_idx + 1
        # If a sentence doesn't match, skip it — don't break the chain

    if not sentence_matches:
        # Fallback: try matching the entire quote as one block
        start_idx, end_idx, score = find_captions_for_sentence(
            quote_text, captions, max_span=40
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


def parse_source_fcpxml(filepath: str, speaker_name: str) -> Dict[str, List[Caption]]:
    """
    Parse a source FCPXML and extract all captions.
    Returns dict with 'captions' key containing list of Caption objects.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    captions = []

    # Find all caption elements (they're inside mc-clip > mc-angle or similar)
    for caption_elem in root.findall('.//caption'):
        caption = Caption(caption_elem)
        captions.append(caption)

    # Sort by offset for easier searching
    captions.sort(key=lambda c: c.offset.numerator / c.offset.denominator)

    return {'captions': captions}


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
                           title_effect_ref: str, text_style_counter: int
                           ) -> Tuple[ET.Element, FractionTime, int]:
    """
    Create a section divider: a ~1 second gap with a title overlay displaying
    the section name. Returns (gap_element, new_offset, new_text_style_counter).

    Section name mapping: "Opening" -> "Intro", others stay as-is.
    """
    display_name = "Intro" if section_name == "Opening" else section_name
    gap_duration = FractionTime(24024, 24000)  # ~1 second

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


def build_spine(paper_cuts: List[Dict], source_fcpxmls: Dict[str, Dict],
                speaker_refs: Dict[str, str], speaker_angles: Dict[str, str],
                gap_threshold_secs: float = 5.0,
                title_effect_ref: str = "r2") -> Tuple[List[ET.Element], int]:
    """
    Build spine elements (mc-clip nodes and section divider gaps) from paper cut quotes.
    Returns (list of spine elements, final text_style_counter).

    When a trimmed quote has content removed from the middle, this produces multiple
    mc-clip elements for that quote — one per contiguous segment. Gaps under
    gap_threshold_secs are kept in a single clip for the editor to clean up in FCP.

    Inserts section divider gaps (with title overlays) between narrative sections.

    speaker_refs: maps speaker name to media ref id (e.g., {"Rob Manion": "r2"})
    speaker_angles: maps speaker name to angleID (e.g., {"Rob Manion": "6qdCZ2zfRbqgFeGrlSbgog"})
    gap_threshold_secs: minimum gap to trigger a clip split (default: 5.0s)
    title_effect_ref: ref id for the Basic Title effect in resources (e.g., "r2")
    """
    spine_clips = []
    offset = FractionTime(0, 24000)  # Cumulative offset
    text_style_counter = 1
    padding = FractionTime(2002, 24000)  # ~2 frames padding on each side
    current_section = None

    for quote_info in paper_cuts:
        speaker = quote_info['speaker']
        quote_text = quote_info['quote']
        section = quote_info.get('section', '')

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

        # Find matching caption segments (may be multiple if trimmed from middle)
        segments = find_captions_for_quote(quote_text, captions, gap_threshold_secs)

        if not segments:
            print(f"Warning: could not match quote '{quote_text[:50]}...' for {speaker}")
            continue

        quote_num = quote_info.get('quote_num', '?')
        section = quote_info.get('section', '?')
        if len(segments) > 1:
            print(f"  Quote #{quote_num} [{section}]: {len(segments)} clips (split at gaps)")
        else:
            print(f"  Quote #{quote_num} [{section}]: 1 clip (score={segments[0][2]:.2f})")

        # Create an mc-clip for each segment
        ref = speaker_refs.get(speaker, "r2")
        name = speaker.split()[0]  # First name only
        angle_id = speaker_angles.get(speaker, "")

        for seg_idx, (start_idx, end_idx, score) in enumerate(segments):
            start_caption = captions[start_idx]
            end_caption = captions[end_idx]

            clip_start = start_caption.offset - padding
            if clip_start.numerator < 0:
                clip_start = FractionTime(0, 24000)

            clip_end = end_caption.end_offset() + padding
            clip_duration = clip_end - clip_start

            mc_clip = ET.Element('mc-clip')
            mc_clip.set('ref', ref)
            mc_clip.set('offset', offset.to_string())
            mc_clip.set('name', name)
            mc_clip.set('start', clip_start.to_string())
            mc_clip.set('duration', clip_duration.to_string())

            mc_source = ET.SubElement(mc_clip, 'mc-source')
            mc_source.set('angleID', angle_id)
            mc_source.set('srcEnable', 'all')

            # Add captions from source for this segment
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
                mc_clip.append(caption_elem)

            spine_clips.append(mc_clip)
            offset = offset + clip_duration

            if len(segments) > 1:
                seg_dur = clip_duration.numerator / clip_duration.denominator
                print(f"    Segment {seg_idx + 1}: captions {start_idx}-{end_idx}, {seg_dur:.1f}s")

    return spine_clips, text_style_counter


def generate_fcpxml(paper_cuts: List[Dict], source_fcpxmls: Dict[str, Dict],
                   reference_path: str, output_path: str,
                   speaker_refs: Dict[str, str], speaker_angles: Dict[str, str],
                   project_name: str = "Generated Edit"):
    """
    Generate the output FCPXML file.

    paper_cuts: list of quote dicts from read_paper_cut_tab()
    source_fcpxmls: dict mapping speaker name to parsed FCPXML data
    reference_path: path to a reference FCPXML (for resources section)
    output_path: where to write the generated FCPXML
    speaker_refs: maps speaker name to media ref id
    speaker_angles: maps speaker name to angleID
    project_name: name for the project in the FCPXML
    """

    # Parse reference file
    ref_tree = ET.parse(reference_path)
    ref_root = ref_tree.getroot()

    # Extract resources
    ref_resources = ref_root.find('resources')

    # Add Basic Title effect to resources if not already present
    # Find the next available ref ID
    existing_ids = [el.get('id', '') for el in ref_resources]
    max_r = 0
    for rid in existing_ids:
        if rid.startswith('r') and rid[1:].isdigit():
            max_r = max(max_r, int(rid[1:]))
    title_effect_ref = f"r{max_r + 1}"

    title_effect = ET.SubElement(ref_resources, 'effect')
    title_effect.set('id', title_effect_ref)
    title_effect.set('name', 'Basic Title')
    title_effect.set('uid', '.../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti')

    # Find sequence element to get the proper format
    ref_sequence = ref_root.find('.//sequence')
    sequence_format = ref_sequence.get('format') if ref_sequence is not None else 'r1'

    # Build spine (with section dividers)
    spine_clips, final_ts_count = build_spine(
        paper_cuts, source_fcpxmls, speaker_refs, speaker_angles,
        title_effect_ref=title_effect_ref
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

    # Copy resources from reference
    new_resources = ET.fromstring(ET.tostring(ref_resources))
    new_root.append(new_resources)

    # Create library/event/project/sequence structure
    # Copy from reference file
    ref_library = ref_root.find('.//library')
    ref_event = ref_root.find('.//event')
    ref_project = ref_root.find('.//project')

    library = ET.SubElement(new_root, 'library')
    library.set('location', ref_library.get('location', ''))

    event = ET.SubElement(library, 'event')
    event.set('name', ref_event.get('name', ''))
    event.set('uid', ref_event.get('uid', ''))

    project = ET.SubElement(event, 'project')
    project.set('name', project_name)
    project.set('uid', ref_project.get('uid', ''))
    project.set('modDate', ref_project.get('modDate', ''))

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
