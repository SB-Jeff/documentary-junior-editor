#!/usr/bin/env python3
"""
Extract Info.fcpxml files from .fcpxmld packages.

Usage:
    python3 extract_fcpxml.py <xml-files-folder>

For each .fcpxmld directory found:
  1. Copies Info.fcpxml out
  2. Renames it to match the package name (e.g. "My Project.fcpxmld" -> "My Project.fcpxml")
  3. Moves the original .fcpxmld directory into an "original fcpxmld files" subfolder
"""

import os
import sys
import shutil


def extract_fcpxml(xml_folder: str) -> None:
    if not os.path.isdir(xml_folder):
        print(f"Error: '{xml_folder}' is not a directory.")
        sys.exit(1)

    packages = [
        entry for entry in os.listdir(xml_folder)
        if entry.endswith(".fcpxmld") and os.path.isdir(os.path.join(xml_folder, entry))
    ]

    if not packages:
        print("No .fcpxmld packages found.")
        return

    # Create subfolder for originals
    originals_folder = os.path.join(xml_folder, "original fcpxmld files")
    os.makedirs(originals_folder, exist_ok=True)

    extracted = []
    skipped = []
    warnings = []

    for pkg_name in sorted(packages):
        pkg_path = os.path.join(xml_folder, pkg_name)
        info_path = os.path.join(pkg_path, "Info.fcpxml")

        # Derive output name: strip .fcpxmld, add .fcpxml
        base_name = pkg_name[: -len(".fcpxmld")]
        out_name = base_name + ".fcpxml"
        out_path = os.path.join(xml_folder, out_name)

        if not os.path.isfile(info_path):
            warnings.append(f"  Skipped '{pkg_name}' — no Info.fcpxml inside")
            continue

        if os.path.exists(out_path):
            skipped.append(f"  Skipped '{pkg_name}' — '{out_name}' already exists")
            continue

        # Copy the file out, then move the original package to the originals folder
        shutil.copy2(info_path, out_path)
        dest_path = os.path.join(originals_folder, pkg_name)
        try:
            shutil.move(pkg_path, dest_path)
            extracted.append(f"  {pkg_name}  ->  {out_name}")
        except (PermissionError, OSError) as e:
            extracted.append(f"  {pkg_name}  ->  {out_name}  (extracted, but could not move original: {e})")

    # Report
    if extracted:
        print(f"Extracted {len(extracted)} file(s):")
        print("\n".join(extracted))
    if skipped:
        print(f"\nSkipped {len(skipped)} (already exist):")
        print("\n".join(skipped))
    if warnings:
        print(f"\nWarnings:")
        print("\n".join(warnings))
    if not extracted and not skipped and not warnings:
        print("Nothing to do.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <xml-files-folder>")
        sys.exit(1)
    extract_fcpxml(sys.argv[1])
