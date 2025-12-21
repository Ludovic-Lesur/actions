#!/usr/bin/env python3
#
# generate_flags_files.py
#
#  Created on: 20 dec. 2025
#      Author: Ludo & Copilot
#

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from typing import Any, List


Primitive = (str, int, float, bool, type(None))


def sanitize_value_for_filename(s: Any) -> str:
    """
    Transform a value for use inside the filename token:
      - lowercase
      - underscores replaced by hyphens
      - non-alphanumeric and non-hyphen characters replaced by hyphen
      - collapse multiple hyphens, strip leading/trailing hyphens
      - fallback to 'empty' or 'none' for empty/None
    This ensures underscores are only used to separate different tokens.
    """
    if s is None:
        return "none"
    s_str = str(s).strip().lower()
    if not s_str:
        return "empty"
    # Replace underscores by hyphens first
    s_str = s_str.replace("_", "-")
    # Replace any character not a-z, 0-9 or hyphen with hyphen
    s_str = re.sub(r'[^a-z0-9-]+', '-', s_str)
    # Collapse multiple hyphens
    s_str = re.sub(r'-{2,}', '-', s_str)
    # Strip leading/trailing hyphens
    s_str = s_str.strip('-')
    return s_str or "empty"


def stringify_primitive(v: Any) -> str:
    """Convert a primitive value to string; booleans become ON/OFF."""
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    if v is None:
        return ""
    return str(v)


def collect_dict_flags(d: Any) -> OrderedDict:
    """
    If d is a dict, return an OrderedDict sorted by key containing key -> stringified value.
    Non-primitive values are ignored. If d is not a dict, return an empty OrderedDict.
    """
    out = OrderedDict()
    if not isinstance(d, dict):
        return out
    for k in sorted(d.keys()):
        v = d[k]
        if isinstance(v, Primitive):
            out[k] = stringify_primitive(v)
        else:
            # Ignore non-primitive values
            continue
    return out


def merge_flags(hw_flags: OrderedDict, sw_flags: OrderedDict) -> OrderedDict:
    """
    Merge hw_flags and sw_flags; sw_flags keys override hw_flags keys.
    """
    merged = OrderedDict()
    for k, v in hw_flags.items():
        merged[k] = v
    for k, v in sw_flags.items():
        merged[k] = v
    return merged


def is_numeric_string(s: str) -> bool:
    """
    Returns True if the string represents an integer or floating point number,
    including optional exponent (scientific) notation.
    """
    if s == "":
        return False
    return bool(re.fullmatch(r'[+-]?\d+(\.\d+)?([eE][+-]?\d+)?', s))


def flags_to_lines(flags: OrderedDict) -> List[str]:
    """
    Convert OrderedDict into a list of flag lines, one flag per line:
      -DKEY=VALUE
      -DKEY   (when VALUE is empty)
    Notes:
    - Numeric values and ON/OFF are written as-is.
    - Other string values are written as-is (no surrounding quotes). If a value contains spaces,
      it will appear on the same line; callers should read the file line-by-line (e.g. mapfile -t)
      so each line becomes one argument.
    """
    parts: List[str] = []
    for k, v in flags.items():
        if v == "":
            parts.append(f"-D{k}")
        else:
            # Do not quote ON/OFF and numeric values; for other strings, write raw value (no quotes).
            if v in ("ON", "OFF") or is_numeric_string(v):
                parts.append(f"-D{k}={v}")
            else:
                # Write value as-is (no surrounding quotes). Keep original escaping of quotes/backslashes if any.
                parts.append(f"-D{k}={v}")
    return parts


def hw_filename_base_from_hw_flags(hw_flags: OrderedDict, hw_index: int) -> str:
    """
    Build the filename base by concatenating hw_flags values (deterministic by key order),
    joined with underscores between tokens. Each token is sanitized by sanitize_value_for_filename.
    If no values are available, return 'hw{index}'.
    """
    vals = [sanitize_value_for_filename(v) for v in hw_flags.values() if v is not None and str(v).strip() != ""]
    if vals:
        return "_".join(vals)
    return f"hw{hw_index}"


def main() -> None:
    
    parser = argparse.ArgumentParser(description="Generate flag files from hw_flags / sw_flags in JSON.")
    parser.add_argument('-i', '--input', required=True, help='Input JSON file (required)')
    parser.add_argument('-o', '--outdir', required=True, help='Output directory (required)')
    parser.add_argument('--dry-run', action='store_true', help="Do not write files; print what would be created.")
    args = parser.parse_args()

    # Read input JSON
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: failed to parse JSON in '{args.input}': {e}", file=sys.stderr)
        sys.exit(2)

    hw_list = data.get('hw_configuration_list')
    if not isinstance(hw_list, list):
        print("Error: 'hw_configuration_list' not found or is not a list in the input JSON.", file=sys.stderr)
        sys.exit(2)

    # Try to create the output directory.
    try:
        os.makedirs(args.outdir, exist_ok=True)
    except OSError as e:
        print(f"Error: failed to create output directory '{args.outdir}': {e}", file=sys.stderr)
        try:
            print("CWD:", os.getcwd(), file=sys.stderr)
            parent = os.path.dirname(os.path.abspath(args.outdir)) or os.path.abspath(args.outdir)
            st = os.stat(parent)
            print(f"Parent dir: {parent} mode={oct(st.st_mode)} uid={st.st_uid} gid={st.st_gid}", file=sys.stderr)
        except Exception:
            pass
        sys.exit(3)

    created_files: List[str] = []
    fixed_ext = ".txt"

    for hw_index, hw in enumerate(hw_list):
        if not isinstance(hw, dict):
            continue

        # Extract hw_flags dict (if present)
        hw_flags_raw = hw.get('hw_flags', {}) if isinstance(hw.get('hw_flags', {}), dict) else {}
        hw_flags = collect_dict_flags(hw_flags_raw)

        # Filename base from hw_flags values (values sanitized/lowercased & underscores->hyphens)
        hw_base = hw_filename_base_from_hw_flags(hw_flags, hw_index)

        sw_list = hw.get('sw_configuration_list')
        if sw_list and isinstance(sw_list, list):
            for sw_index, sw in enumerate(sw_list):
                if not isinstance(sw, dict):
                    continue
                sw_name_raw = sw.get('name')
                sw_flags_raw = sw.get('sw_flags', {}) if isinstance(sw.get('sw_flags', {}), dict) else {}
                sw_flags = collect_dict_flags(sw_flags_raw)

                merged = merge_flags(hw_flags, sw_flags)

                # Construct filename: <hw_base>_<sw_name> or <hw_base>_sw{index}
                if sw_name_raw is not None and str(sw_name_raw).strip() != "":
                    sw_name_token = sanitize_value_for_filename(sw_name_raw)
                    filename = f"{hw_base}_{sw_name_token}{fixed_ext}"
                else:
                    # No suffix for the first configuration without name.
                    if sw_index == 0:
                        filename = f"{hw_base}{fixed_ext}"
                    else:
                    	filename = f"{hw_base}_sw-conf{sw_index}{fixed_ext}"

                out_path = os.path.join(args.outdir, filename)
                lines = flags_to_lines(merged)

                if args.dry_run:
                    combined = "\n".join(lines) if lines else "(no flags)"
                    print(f"[DRY RUN] {out_path} -> {combined}")
                else:
                    try:
                        with open(out_path, 'w', encoding='utf-8') as out_f:
                            # write one flag per line; ensure file ends with a newline
                            out_f.write("\n".join(lines) + "\n")
                        created_files.append(out_path)
                    except OSError as e:
                        print(f"Error: failed to write file '{out_path}': {e}", file=sys.stderr)
        else:
            filename = f"{hw_base}{fixed_ext}"
            out_path = os.path.join(args.outdir, filename)
            lines = flags_to_lines(hw_flags)
            if args.dry_run:
                combined = "\n".join(lines) if lines else "(no flags)"
                print(f"[DRY RUN] {out_path} -> {combined}")
            else:
                try:
                    with open(out_path, 'w', encoding='utf-8') as out_f:
                        out_f.write("\n".join(lines) + "\n")
                    created_files.append(out_path)
                except OSError as e:
                    print(f"Error: failed to write file '{out_path}': {e}", file=sys.stderr)

    if args.dry_run:
        print("Dry run completed.")
    else:
        if created_files:
            print(f"Created files ({len(created_files)}):")
            for p in created_files:
                print(" -", p)
        else:
            print("No files were created.")

if __name__ == '__main__':
    main()
