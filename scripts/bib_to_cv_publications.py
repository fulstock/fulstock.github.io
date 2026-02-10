#!/usr/bin/env python3
"""Parse _bibliography/papers.bib and inject a Publications section into _data/cv.yml.

Uses only stdlib (re) + pyyaml (already in requirements.txt).
Designed to run at build time before ``rendercv render``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
BIB_PATH = REPO_ROOT / "_bibliography" / "papers.bib"
CV_PATH = REPO_ROOT / "_data" / "cv.yml"

# The CV owner's last name — used to add *emphasis* around their name.
# Include both Latin and Cyrillic variants.
OWNER_LAST_NAMES = ["Rozhkov", "Рожков"]

# ---------------------------------------------------------------------------
# Lightweight BibTeX parser
# ---------------------------------------------------------------------------

# Month abbreviations that BibTeX accepts without quotes
MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _strip_braces(value: str) -> str:
    """Remove outermost matching braces from *value*."""
    while value.startswith("{") and value.endswith("}"):
        value = value[1:-1]
    return value


def _clean_latex(value: str) -> str:
    r"""Normalise common LaTeX commands to plain Unicode."""
    value = value.replace(r"\flqq", "\u00ab")  # «
    value = value.replace(r"\frqq", "\u00bb")  # »
    value = value.replace(r"\dq", '"')
    value = value.replace("~", " ")
    value = value.replace("--", "\u2013")  # –
    # Strip remaining simple \cmd sequences (e.g. \textbf{...})
    value = re.sub(r"\\[a-zA-Z]+\s*", "", value)
    # Remove stray braces left over
    value = value.replace("{", "").replace("}", "")
    return value.strip()


def _parse_author_list(raw: str) -> list[str]:
    """Split a BibTeX ``author`` field into individual names.

    Handles ``Last, First and ...`` as well as ``First Last and ...`` forms.
    Filters out institutional / placeholder authors (those containing commas
    that look like addresses, e.g. "Lomonosov Moscow State University, Moscow,
    Russia").
    """
    parts = re.split(r"\s+and\s+", raw)
    names: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Heuristic: skip if the part contains two or more commas (institutional)
        if part.count(",") >= 2:
            continue
        # "Last, First" form
        if "," in part:
            last, first = part.split(",", 1)
            name = f"{first.strip()} {last.strip()}"
        else:
            name = part
        name = _clean_latex(name)
        if name:
            names.append(name)
    return names


def _parse_bib(text: str) -> list[dict[str, str]]:
    """Return a list of dicts, one per BibTeX entry, with lowercased field keys."""
    entries: list[dict[str, str]] = []

    # Match each @type{key, ... } block.
    # We need to handle nested braces in values properly.
    entry_pattern = re.compile(r"@(\w+)\s*\{([^,]+),", re.IGNORECASE)

    pos = 0
    while pos < len(text):
        m = entry_pattern.search(text, pos)
        if not m:
            break
        entry_type = m.group(1).lower()
        # Find the balanced closing brace for the whole entry
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start : i - 1]
        pos = i

        fields: dict[str, str] = {"_type": entry_type}

        # Parse key = value pairs from body
        field_re = re.compile(r"(\w+)\s*=\s*")
        fpos = 0
        while fpos < len(body):
            fm = field_re.search(body, fpos)
            if not fm:
                break
            key = fm.group(1).lower()
            vstart = fm.end()
            value, vend = _extract_value(body, vstart)
            fields[key] = value
            fpos = vend

        entries.append(fields)
    return entries


def _extract_value(body: str, start: int) -> tuple[str, int]:
    """Extract a BibTeX field value starting at *start*.

    Handles brace-delimited ``{...}``, quoted ``"..."``, and bare values
    (numbers, month abbreviations).
    """
    # Skip whitespace
    i = start
    while i < len(body) and body[i] in " \t\n\r":
        i += 1

    if i >= len(body):
        return "", i

    if body[i] == "{":
        # Brace-delimited: find matching close
        depth = 1
        j = i + 1
        while j < len(body) and depth > 0:
            if body[j] == "{":
                depth += 1
            elif body[j] == "}":
                depth -= 1
            j += 1
        value = body[i + 1 : j - 1]
        # Skip trailing comma / whitespace
        while j < len(body) and body[j] in " \t\n\r,":
            j += 1
        return value, j

    if body[i] == '"':
        # Quoted value
        j = i + 1
        while j < len(body) and body[j] != '"':
            if body[j] == "\\":
                j += 1  # skip escaped char
            j += 1
        value = body[i + 1 : j]
        j += 1  # skip closing quote
        while j < len(body) and body[j] in " \t\n\r,":
            j += 1
        return value, j

    # Bare value (number or month abbreviation)
    j = i
    while j < len(body) and body[j] not in " \t\n\r,}":
        j += 1
    value = body[i:j]
    while j < len(body) and body[j] in " \t\n\r,":
        j += 1
    return value, j


# ---------------------------------------------------------------------------
# Convert BibTeX entries → RenderCV PublicationEntry dicts
# ---------------------------------------------------------------------------


def _resolve_month(raw: str | None) -> str | None:
    """Convert a month field (abbrev or numeric) to two-digit string."""
    if raw is None:
        return None
    raw = raw.strip().lower()
    if raw in MONTH_MAP:
        return MONTH_MAP[raw]
    if raw.isdigit() and 1 <= int(raw) <= 12:
        return raw.zfill(2)
    return None


def _emphasise_owner(authors: list[str]) -> list[str]:
    """Wrap the CV owner's name with *...* for RenderCV bold emphasis."""
    out: list[str] = []
    for name in authors:
        if any(ln.lower() in name.lower() for ln in OWNER_LAST_NAMES):
            out.append(f"***{name}***")
        else:
            out.append(name)
    return out


def bib_entry_to_publication(entry: dict[str, str]) -> dict | None:
    """Convert one parsed BibTeX entry to a RenderCV PublicationEntry dict.

    Returns ``None`` if the entry lacks required data (title + year).
    """
    raw_title = entry.get("title")
    raw_year = entry.get("year")
    if not raw_title or not raw_year:
        return None

    title = _clean_latex(_strip_braces(raw_title))

    # Authors
    raw_authors = entry.get("author", "")
    authors = _parse_author_list(raw_authors)
    authors = _emphasise_owner(authors)

    # Venue: journal > booktitle
    venue = entry.get("journal") or entry.get("booktitle") or ""
    venue = _clean_latex(_strip_braces(venue))

    # Date
    month = _resolve_month(entry.get("month"))
    year = raw_year.strip()
    date = f"{year}-{month}" if month else year

    pub: dict = {
        "title": title,
        "authors": authors,
    }
    if venue:
        pub["journal"] = venue
    pub["date"] = date
    if entry.get("doi"):
        pub["doi"] = _strip_braces(entry["doi"])

    return pub


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not BIB_PATH.exists():
        print(f"ERROR: {BIB_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not CV_PATH.exists():
        print(f"ERROR: {CV_PATH} not found", file=sys.stderr)
        sys.exit(1)

    bib_text = BIB_PATH.read_text(encoding="utf-8")
    entries = _parse_bib(bib_text)

    publications: list[dict] = []
    for entry in entries:
        pub = bib_entry_to_publication(entry)
        if pub is not None:
            publications.append(pub)

    # Sort newest-first by date string (YYYY or YYYY-MM)
    publications.sort(key=lambda p: p["date"], reverse=True)

    # Read cv.yml
    cv_data = yaml.safe_load(CV_PATH.read_text(encoding="utf-8"))

    # Inject publications into sections
    if "cv" not in cv_data:
        print("ERROR: cv.yml missing top-level 'cv' key", file=sys.stderr)
        sys.exit(1)
    sections = cv_data["cv"].setdefault("sections", {})
    sections["Publications"] = publications

    # Write back
    CV_PATH.write_text(
        yaml.dump(cv_data, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )

    print(f"Injected {len(publications)} publications into {CV_PATH}")


if __name__ == "__main__":
    main()
