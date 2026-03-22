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
