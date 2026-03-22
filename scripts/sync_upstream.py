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

def fetch_star_counts(
    skills: dict[str, SkillEntry],
    token: str | None,
) -> dict[str, int]:
    """Fetch star counts for all unique repos. Returns dict of owner/repo -> star_count."""
    repos: set[str] = set()
    for url in skills:
        owner_repo = _extract_owner_repo(url)
        if owner_repo:
            repos.add(owner_repo)

    star_counts: dict[str, int] = {}

    for repo in sorted(repos):
        api_url = f"https://api.github.com/repos/{repo}"
        req = urllib.request.Request(api_url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "awesome-agent-skills-sync")
        if token:
            req.add_header("Authorization", f"token {token}")

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                star_counts[repo] = data.get("stargazers_count", 0)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"WARNING: Rate limited by GitHub API. {len(repos) - len(star_counts)} repos not queried.", file=sys.stderr)
                break
            elif e.code == 404:
                print(f"WARNING: Repo not found: {repo}", file=sys.stderr)
                star_counts[repo] = 0
            else:
                print(f"WARNING: API error for {repo}: {e.code}", file=sys.stderr)
                star_counts[repo] = 0
        except Exception as e:
            print(f"WARNING: Failed to fetch {repo}: {e}", file=sys.stderr)
            star_counts[repo] = 0

    return star_counts

DEFAULT_UPSTREAM_URL = "https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/main/README.md"

def fetch_upstream_readme(url: str) -> str:
    """Fetch the upstream README content."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "awesome-agent-skills-sync")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")

def _build_star_data(
    skills: dict[str, SkillEntry],
    star_counts: dict[str, int],
) -> dict[str, tuple[int, str, str]]:
    """Build star_data dict for refresh_top15."""
    by_repo: dict[str, list[SkillEntry]] = {}
    for url, entry in skills.items():
        owner_repo = _extract_owner_repo(url)
        if owner_repo:
            by_repo.setdefault(owner_repo, []).append(entry)

    result: dict[str, tuple[int, str, str]] = {}
    for owner_repo, entries in by_repo.items():
        stars = star_counts.get(owner_repo, 0)
        representative = sorted(entries, key=lambda e: e.url)[0]
        result[representative.url] = (stars, representative.description, owner_repo)

    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="Sync skills from upstream VoltAgent repo")
    parser.add_argument("--dry-run", action="store_true", help="Print report without modifying files")
    parser.add_argument("--upstream-url", default=DEFAULT_UPSTREAM_URL, help="Override upstream README URL")
    parser.add_argument("--github-token", default=None, help="GitHub PAT for star counts")
    args = parser.parse_args()

    token = args.github_token or os.environ.get("GITHUB_TOKEN")

    repo_root = Path(__file__).resolve().parent.parent
    readme_path = repo_root / "README.md"
    snapshot_path = repo_root / ".upstream-snapshot.json"

    local_text = readme_path.read_text(encoding="utf-8")
    local_skills = parse_readme(local_text)
    print(f"Local skills found: {len(local_skills)}")

    print(f"Fetching upstream from {args.upstream_url}...")
    try:
        upstream_text = fetch_upstream_readme(args.upstream_url)
    except Exception as e:
        print(f"ERROR: Failed to fetch upstream: {e}", file=sys.stderr)
        return 1
    upstream_skills = parse_readme(upstream_text)
    print(f"Upstream skills found: {len(upstream_skills)}")

    snapshot_urls = load_snapshot(str(snapshot_path))

    new_skills, removed_urls = diff_skills(upstream_skills, local_skills, snapshot_urls)

    modified_text, inserted, unmatched = insert_skills(local_text, new_skills)

    print(f"\n--- Sync Report ---")
    if inserted:
        print(f"\nInserted {len(inserted)} new skill(s):")
        by_section: dict[str, list[SkillEntry]] = {}
        for entry in inserted:
            by_section.setdefault(entry.section, []).append(entry)
        for section, entries in sorted(by_section.items()):
            print(f"  [{section}]")
            for e in entries:
                print(f"    + {e.url}")
    else:
        print("\nNo new skills to insert.")

    if unmatched:
        print(f"\n{len(unmatched)} skill(s) need manual placement:")
        for entry in unmatched:
            print(f"  Section: {entry.section}")
            print(f"    {entry.url} — {entry.description}")

    if removed_urls:
        print(f"\n{len(removed_urls)} skill(s) removed upstream:")
        for url in sorted(removed_urls):
            print(f"  - {url}")
    elif snapshot_urls is not None:
        print("\nNo upstream removals detected.")

    if snapshot_urls is None:
        print("\nFirst run — no snapshot to compare for removals.")

    if token:
        print("\nFetching star counts for Top 15 refresh...")
        all_skills_after = parse_readme(modified_text)
        star_counts = fetch_star_counts(all_skills_after, token)
        star_data = _build_star_data(all_skills_after, star_counts)
        modified_text = refresh_top15(modified_text, star_data)
        print(f"Top 15 table refreshed ({len(star_counts)} repos queried).")
    else:
        print("\nNo GitHub token provided — skipping Top 15 refresh.")
        print("Use --github-token or GITHUB_TOKEN env var to enable.")

    if not args.dry_run:
        readme_path.write_text(modified_text, encoding="utf-8")
        save_snapshot(str(snapshot_path), set(upstream_skills.keys()))
        if inserted or token:
            print(f"\nFiles updated. Run `git diff README.md` to review changes.")
    else:
        print("\n(dry run — no files modified)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
