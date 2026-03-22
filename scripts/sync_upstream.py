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
