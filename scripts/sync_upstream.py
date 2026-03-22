"""Sync upstream awesome-agent-skills into our restructured README."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def extract_section_name(line: str) -> str | None:
    """Extract a section name from a heading or <summary> tag. Returns None if not a section line."""
    m = re.search(r'<summary>\s*<h3[^>]*>(.*?)</h3>\s*</summary>', line)
    if m:
        return m.group(1).strip()
    m = re.match(r'^#{2,3}\s+(.+)$', line)
    if m:
        return re.sub(r'[^\w\s&\'-]', '', m.group(1)).strip()
    return None


@dataclass
class SkillEntry:
    url: str
    description: str
    section: str
    raw_line: str

SKIP_SECTIONS = {
    "top 15 most popular skills",
    "skills paths for other ai coding assistants",
}


def parse_readme(text: str) -> dict[str, SkillEntry]:
    """Parse a README and return a dict of url -> SkillEntry."""
    skills: dict[str, SkillEntry] = {}
    current_section = ""
    in_community = False
    skip_current = False

    skill_link_re = re.compile(
        r'\|\s*(?:\d+\s*\|)?\s*\[([^\]]+)\]\((https?://(?:github\.com|www\.notion\.so)[^\)]+)\)'
    )

    for line in text.splitlines():
        section_name = extract_section_name(line)
        if section_name is not None:
            normalized = section_name.strip().lower()
            is_h2 = bool(re.match(r'^##\s', line)) and not re.match(r'^###', line)
            if normalized == "community skills":
                in_community = True
                current_section = ""
                skip_current = False
                continue
            if is_h2:
                skip_current = normalized in SKIP_SECTIONS
                in_community = False
                if not skip_current:
                    current_section = section_name
                continue

            if not skip_current:
                if in_community:
                    current_section = f"Community Skills > {section_name}"
                else:
                    current_section = section_name
            continue

        if skip_current or not current_section:
            continue

        if re.match(r'\|\s*[-:]+\s*\|', line) or re.match(r'\|\s*Skill\s*\|', line):
            continue

        m = skill_link_re.search(line)
        if m:
            url = m.group(2)
            cells = [c.strip() for c in line.split('|') if c.strip()]
            description = cells[-1] if cells else ""
            skills[url] = SkillEntry(
                url=url,
                description=description,
                section=current_section,
                raw_line=line,
            )

    return skills


def diff_skills(
    upstream: dict[str, SkillEntry],
    local: dict[str, SkillEntry],
    snapshot_urls: set[str] | None,
) -> tuple[dict[str, SkillEntry], set[str]]:
    """Return (new_skills, removed_urls)."""
    new = {url: entry for url, entry in upstream.items() if url not in local}
    if snapshot_urls is None:
        removed = set()
    else:
        removed = snapshot_urls - set(upstream.keys())
    return new, removed


def load_snapshot(path: str) -> set[str] | None:
    """Load snapshot URLs from a JSON file. Returns None if file doesn't exist."""
    try:
        with open(path) as f:
            data = json.load(f)
        return set(data["urls"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError, TypeError):
        return None

def save_snapshot(path: str, urls: set[str]) -> None:
    """Save snapshot URLs to a JSON file."""
    data = {
        "urls": sorted(urls),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def _extract_owner_repo(url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub URL."""
    m = re.match(r'https?://github\.com/([^/]+/[^/]+)', url)
    return m.group(1) if m else None

def _build_table_row(entry: SkillEntry, three_column: bool) -> str:
    """Build a markdown table row for a skill entry."""
    owner_repo = _extract_owner_repo(entry.url)

    if not three_column and entry.raw_line.startswith('|'):
        cells = [c.strip() for c in entry.raw_line.split('|') if c.strip()]
        if len(cells) == 2:
            return entry.raw_line

    parts = entry.url.rstrip('/').split('/')
    if 'tree' in parts or 'blob' in parts:
        org = parts[3]
        name = parts[-1]
        display = f"{org}/{name}"
    else:
        display = owner_repo or parts[-1]

    link = f"[{display}]({entry.url})"
    if three_column and owner_repo:
        stars = f"![GitHub Stars](https://img.shields.io/github/stars/{owner_repo}?style=flat-square&logo=github&label=★)"
        return f"| {link} | {stars} | {entry.description} |"
    else:
        return f"| {link} | {entry.description} |"

def _find_local_sections(text: str) -> dict[str, dict]:
    """Find all sections in the local README with their line positions and table format."""
    lines = text.splitlines()
    sections: dict[str, dict] = {}
    current_section = None
    in_community = False
    in_table = False
    table_end_line = None
    three_column = False

    for i, line in enumerate(lines):
        section_name = extract_section_name(line)
        if section_name is not None:
            if current_section and table_end_line is not None:
                key = current_section.lower()
                sections[key] = {
                    "name": current_section,
                    "table_end": table_end_line,
                    "three_column": three_column,
                }

            is_h2 = bool(re.match(r'^##\s', line)) and not re.match(r'^###', line)
            normalized_section = section_name.strip().lower()

            if normalized_section == "community skills":
                in_community = True
                current_section = None
                in_table = False
                table_end_line = None
                three_column = False
                continue

            if is_h2:
                in_community = False
                current_section = None
                in_table = False
                table_end_line = None
                three_column = False
                continue

            if in_community:
                current_section = f"Community Skills > {section_name}"
            else:
                current_section = section_name
            in_table = False
            table_end_line = None
            three_column = False
            continue

        if current_section:
            if re.match(r'\|\s*Skill\s*\|', line):
                in_table = True
                three_column = '| Stars |' in line or '| Stars|' in line
                continue
            if re.match(r'\|\s*[-:]+', line):
                continue
            if in_table and line.startswith('|') and '|' in line[1:]:
                table_end_line = i + 1
                continue
            if in_table and table_end_line is not None:
                in_table = False

    if current_section and table_end_line is not None:
        key = current_section.lower()
        sections[key] = {
            "name": current_section,
            "table_end": table_end_line,
            "three_column": three_column,
        }

    return sections

def insert_skills(
    readme_text: str,
    new_skills: dict[str, SkillEntry],
) -> tuple[str, list[SkillEntry], list[SkillEntry]]:
    """Insert new skills into the README text."""
    if not new_skills:
        return readme_text, [], []

    sections = _find_local_sections(readme_text)
    lines = readme_text.splitlines()

    inserted: list[SkillEntry] = []
    unmatched: list[SkillEntry] = []

    by_section: dict[str, list[SkillEntry]] = {}
    for entry in new_skills.values():
        by_section.setdefault(entry.section, []).append(entry)

    insertions: list[tuple[int, str]] = []

    for section_name, entries in by_section.items():
        key = section_name.lower()
        if key not in sections:
            unmatched.extend(entries)
            continue
        sec = sections[key]
        for entry in entries:
            row = _build_table_row(entry, sec["three_column"])
            insertions.append((sec["table_end"], row))
            inserted.append(entry)
            sec["table_end"] += 1

    insertions.sort(key=lambda x: x[0], reverse=True)
    for line_idx, row_text in insertions:
        lines.insert(line_idx, row_text)

    return '\n'.join(lines), inserted, unmatched

def refresh_top15(
    readme_text: str,
    star_data: dict[str, tuple[int, str, str]],
) -> str:
    """Regenerate the Top 15 table in the README.
    star_data: url -> (star_count, description, owner_repo)
    """
    ranked = sorted(star_data.items(), key=lambda x: x[1][0], reverse=True)[:15]

    header = "| # | Skill | Stars | Description |"
    separator = "|---|-------|-------|-------------|"
    rows = [header, separator]
    for i, (url, (stars, description, owner_repo)) in enumerate(ranked, 1):
        parts = url.rstrip('/').split('/')
        if 'tree' in parts or 'blob' in parts:
            org = parts[3]
            name = parts[-1]
            display = f"{org}/{name}"
        else:
            display = owner_repo
        link = f"[{display}]({url})"
        badge = f"![GitHub Stars](https://img.shields.io/github/stars/{owner_repo}?style=flat-square&logo=github&label=★)"
        rows.append(f"| {i} | {link} | {badge} | {description} |")

    lines = readme_text.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if re.match(r'^##\s+.*Top 15', line):
            start = i
        elif start is not None and start != i:
            if line.startswith('| #') or line.startswith('|--') or line.startswith('|---'):
                if end is None or i > end:
                    end = i
            elif line.startswith('| ') and re.match(r'\|\s*\d+\s*\|', line):
                end = i
            elif end is not None and not line.startswith('|'):
                break

    if start is not None and end is not None:
        table_start = None
        for i in range(start + 1, len(lines)):
            if lines[i].startswith('|'):
                table_start = i
                break
        if table_start is not None:
            result_lines = lines[:table_start] + rows + lines[end + 1:]
            return '\n'.join(result_lines)

    return readme_text
