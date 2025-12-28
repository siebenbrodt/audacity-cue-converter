# Audacity CUE Converter

Bidirectional Python utility for converting between .cue sheets and Audacity labels, preserving metadata.

## Features

- **Bidirectional** `.cue` ↔ `.txt` (Audacity labels) conversion.
- **Metadata preservation:** Restores tags when converting back to CUE (if the original file is present).
- **Drift-free** CD frames ↔ seconds conversion.
- **Timestamp shift:** add or subtract a user‑specified offset (ms).
- **Label type:** *Point labels* (default) or *Region labels*.
- **Safe overwriting:** a numbered copy is created.

## Usage

```
python audacity_cue_converter.py <filepath> [options]
```

`<filepath>`: a `.cue` file or a `.txt` Audacity label file.

**Options:**

- `--shift N`: Shift all timestamps by *N* milliseconds (e.g., `200` or `-500`).
- `--region`: Export Audacity labels as regions (start of track to start of next) instead of points.
- `--force`: Overwrite existing files instead of creating a numbered copy.

## Examples

**CUE to Audacity labels (with +200ms shift):**

`python audacity_cue_converter.py cd_image.cue --shift 200`

*Creates `cd_image.txt` in the same folder.*

**Labels to CUE:**

`python audacity_cue_converter.py cd_image.txt`

*Creates `cd_image-1.cue` (to prevent overwrite) and restores metadata from the original `.cue` if found.*

**Export Region labels** instead of points:

`python audacity_cue_converter.py cd_image.cue --region`

## Requirements

- Python 3.7+ (no external dependencies)

## Notes

- Single-file cue sheets only: designed for fixing CUE sheets that reference a single audio file (WAV, FLAC, etc.).
- The utility is not intended to be a fully-compliant parser - it will faithfully copy any bullshit contained in cue file. Only double quotes in titles are sanitized for CUE compatibility.
- Semi-auto encoding: handles UTF-8 (with or without BOM); falls back to the most reasonably safe cp1252. If your cue file uses a special encoding, convert it manually.

## License

MIT - modify, redistribute, or incorporate as you wish.
