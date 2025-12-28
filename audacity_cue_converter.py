#!/usr/bin/env python3
"""
audacity_cue_converter.py: Bidirectional converter for .cue sheets and Audacity labels.

- Converts a single-file .cue sheet to an Audacity label tab-separated txt (point or region labels).
- Converts an Audacity label file back to a .cue file, copying metadata from the original .cue.

Usage:
  python audacity_cue_converter.py <filepath> [--shift N] [--force] [--region]

Examples:
  python audacity_cue_converter.py cd_image.cue
  python audacity_cue_converter.py labels.txt --force
  python audacity_cue_converter.py sync_issue.cue --shift 500
"""
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

class ParseError(Exception):
    """Raised when CUE parsing fails."""

@dataclass
class Track:
    """Single audio track parsed from a CUE sheet."""
    number: int
    title: str
    start_time: str
    metadata: List[str] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        """Parses 'mm:ss:ff' to float seconds."""
        try:
            mm, ss, ff = map(int, self.start_time.split(':'))
            return mm * 60 + ss + ff / 75.0
        except (ValueError, AttributeError, IndexError):
            raise ParseError(f"Malformed CUE timestamp: {self.start_time}")

@dataclass
class CueSheet:
    """Parsed CUE file datastructure."""
    header: List[str]
    tracks: List[Track]
    path: Path

def sec_to_cue(seconds: float) -> str:
    """Converts seconds to 'mm:ss:ff' using integer math to prevent drift."""
    frames = round(max(0, seconds) * 75)
    mm, frames = divmod(frames, 60 * 75)
    ss, ff = divmod(frames, 75)
    return f"{mm:02d}:{ss:02d}:{ff:02d}"

def get_dest_path(base_path: Path, suffix: str, force: bool) -> Path:
    """Generates unique output path; appends numeric suffix if file exists."""
    target = base_path.with_suffix(suffix)
    if force or not target.exists():
        return target
    count = 1
    while True:
        # compatible with python <3.9
        new_target = base_path.with_name(f"{base_path.stem}-{count}{suffix}")
        if not new_target.exists():
            return new_target
        count += 1

def load_cue(path: Path) -> CueSheet:
    """Parses a CUE file into a structured CueSheet object."""
    content = ""
    # 'utf-8-sig' handles both BOM/noBOM variants automatically
    # fallback to the most common legacy encoding
    for enc in ["utf-8-sig", "cp1252"]:
        try:
            content = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        raise ParseError(f"Error: File {path} is empty or unreadable.")

    # single-file cue image validation
    file_count = sum(1 for line in lines if line.lstrip().startswith("FILE "))
    if file_count != 1:
        raise ParseError(f"Unsupported cue format: expected 1 FILE line, found {file_count}.")

    header, tracks, current = [], [], None

    for line in lines:
        if line.startswith("TRACK"):
            parts = line.split()
            num = int(parts[1]) if len(parts) > 1 else 0
            current = Track(num, "Unknown", "00:00:00")
            tracks.append(current)
        elif current:
            if line.startswith("INDEX 01"): 
                current.start_time = line.split()[-1]
            elif line.startswith("TITLE"): 
                current.title = line.split(' ', 1)[1].strip('"')
                parts = line.split(' ', 1)
                # safeguard against an empty title
                current.title = parts[1].strip('"') if len(parts) > 1 else "Unknown"
            # store the rest of tags
            current.metadata.append(line)
        else:
            header.append(line)
            
    return CueSheet(header, tracks, path)

def compare_titles(ref_tracks: List[Track], label_parts: List[List[str]]):
    """Warns if labels differ from the original CUE metadata."""
    ref_map = {t.number: t.title for t in ref_tracks}
    for i, parts in enumerate(label_parts, 1):
        label_title = parts[2]
        original_title = ref_map.get(i)
        if original_title and original_title != label_title:
            print(f"[WARN] Title mismatch Track {i:02d}: CUE='{original_title}', TXT='{label_title}'", file=sys.stderr)
            
def convert(args):
    in_path = Path(args.filepath)
    shift = args.shift / 1000.0

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    # 1. cue -> labels
    if in_path.suffix.lower() == ".cue":
        cue = load_cue(in_path)
        out_path = get_dest_path(in_path, ".txt", args.force)
        with out_path.open("w", encoding="utf-8") as f:
            for i, t in enumerate(cue.tracks):
                ts_start = t.seconds + shift
                
                if args.region:
                    # use the next track's start as the end
                    if i + 1 < len(cue.tracks):
                        ts_end = cue.tracks[i + 1].seconds + shift
                    else:
                        ts_end = ts_start
                else:
                    ts_end = ts_start
                
                f.write(f"{ts_start:.6f}\t{ts_end:.6f}\t{t.title}\n")
        print(f"Saved: {out_path}")

    # 2. labels -> cue
    elif in_path.suffix.lower() == ".txt":
        label_lines = [
            l.split("\t")
            for l in in_path.read_text(encoding="utf-8").splitlines()
            if len(l.split('\t')) >= 3
            ]
        
        out_path = get_dest_path(in_path, ".cue", args.force)
        # load reference cue for metadata
        ref_path = in_path.with_suffix(".cue")
        ref = load_cue(ref_path) if ref_path.exists() else None
        
        if ref:
            compare_titles(ref.tracks, label_lines)
        
        with out_path.open("w", encoding="utf-8") as f:
            # global header
            if ref and ref.header:
                for line in ref.header:
                    f.write(f"{line}\n")
            else:
                # minimal header if no reference cue found
                f.write('PERFORMER "Unknown"\n')
                f.write('TITLE "Converted from Labels"\n')
                f.write(f'FILE "{in_path.with_suffix(".wav").name}" WAVE\n')

            for i, parts in enumerate(label_lines, 1):
                if len(parts) < 3:
                    print(f"[WARN] Skipping malformed label line: {parts}", file=sys.stderr)
                    continue
                title = parts[2].strip()
                # sanitize double quotes
                if '"' in title:
                    print(f"[WARN] Track {i:02d}: Double quotes in title sanitized to single quotes.", file=sys.stderr)
                safe_title = title.strip().replace('"', "'")
                
                time_str = sec_to_cue(float(parts[0]) + shift)
                
                f.write(f"  TRACK {i:02d} AUDIO\n")
                # restore tags from reference cue
                match = next((t for t in ref.tracks if t.number == i), None) if ref else None
                if match:
                    for m_line in match.metadata:
                        if m_line.startswith("TITLE"):
                            f.write(f'    TITLE "{safe_title}"\n')
                        elif not m_line.startswith("INDEX"):
                            f.write(f"    {m_line}\n")
                else:
                    f.write(f'    TITLE "{safe_title}"\n')
                    
                f.write(f"    INDEX 01 {time_str}\n")
                
        print(f"Saved: {out_path}")

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("filepath", help="Path to .cue or .txt file.")
    parser.add_argument("--shift", type=float, default=0.0, help="Shift in milliseconds.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--region", action="store_true", help="Export as region labels.")
    args = parser.parse_args()

    try:
        convert(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
