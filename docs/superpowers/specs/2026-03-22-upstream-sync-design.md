# Upstream Sync Script — Design Spec

## Problem

This repo is a fork of [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) with a restructured README (reordered sections, added Top 15 table, Table of Contents, changed heading levels). The upstream repo actively receives community PRs adding new skills. Standard git merge produces massive conflicts due to the structural differences. We need a way to detect new upstream additions and slot them into our layout.

## Solution

A Python script (`scripts/sync_upstream.py`) that:
1. Fetches the upstream README
2. Parses skill entries from both READMEs
3. Diffs them to find new and removed skills
4. Inserts new skills into the matching local sections
5. Refreshes the Top 15 Most Popular Skills table using GitHub star counts

## Parsing

The script parses a README and extracts skill entries. Each entry is a tuple of:

- **url** — the GitHub link (unique key)
- **description** — the text description
- **section** — the section it belongs to (e.g., "Official Claude Skills", "Community Skills > Marketing")

How parsing works:

1. Walk the README line by line, tracking the current section via `<summary><h3...>` tags and `###` headings
2. For community subsections, prefix with "Community Skills > " (e.g., "Community Skills > Marketing")
3. Match table rows with a regex pattern `| [link](url) |` to extract skill entries
4. Skip non-skill table rows (headers, separators, the Top 15 table, the compatibility table)

The parser returns a `dict[url -> SkillEntry]` where `SkillEntry` has `url`, `description`, `section`, and `raw_line` (the original markdown row).

## Diffing

The script fetches the upstream README from `https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/main/README.md`, parses both files, and compares the two URL sets.

- **New skills** = URLs in upstream but not in local
- **Removed skills** = URLs in upstream's previous snapshot but no longer present

Tracking removals requires knowing what upstream looked like last time you synced. The script stores a snapshot of upstream URLs in `.upstream-snapshot.json` after each successful run. On the next run, it compares current upstream against that snapshot to detect removals. On first run (no snapshot exists), it only reports new additions.

The snapshot file format:
```json
{
  "urls": ["https://...", ...],
  "fetched_at": "2026-03-22T..."
}
```

## Insertion & Output

**Section matching:** When a new upstream skill is found, the script matches its upstream section name against local section names. Matching is case-insensitive and ignores leading/trailing whitespace. If a match is found, the new row is appended to the end of that section's table.

**Table format detection:** The README uses two table formats — two-column (`| Skill | Description |`) for team sections and three-column (`| Skill | Stars | Description |`) for community sections. The script detects which format the target section uses and generates the entry accordingly, adding a stars badge for three-column tables.

**Unmatched sections:** If upstream has a section that doesn't exist in the local README, those skills are printed to the terminal as "needs manual placement" with their full entry and upstream section name. They are not inserted into the README.

**Terminal report:** After running, the script prints:
- Count of new skills found and inserted (grouped by section)
- Count of new skills needing manual placement
- Count of removals detected upstream (with URLs and section names)
- A note to `git diff README.md` to review changes

No auto-commit. The script modifies `README.md` in place and updates `.upstream-snapshot.json`. The user reviews the diff and commits.

## Top 15 Most Popular Skills

After inserting/removing skills, the script refreshes the "Top 15 Most Popular Skills" table:

1. Collects all skill URLs from the local README (after insertions)
2. Queries the GitHub API for star counts — extracts `owner/repo` from each URL and hits `https://api.github.com/repos/{owner}/{repo}` (deduplicated, since many skills share a repo)
3. Ranks by stars, takes the top 15
4. Regenerates the Top 15 table in place

**Rate limiting:** GitHub's unauthenticated API allows 60 requests/hour. With ~100+ unique repos, that won't be enough. The script accepts an optional `--github-token` flag (or reads `GITHUB_TOKEN` env var) for authenticated requests (5,000/hr). Without a token, it skips the Top 15 refresh and prints a warning.

## Script Interface

**Location:** `scripts/sync_upstream.py`

**Usage:**
```
python scripts/sync_upstream.py                          # sync only, skip top 15
python scripts/sync_upstream.py --github-token ghp_xxx   # sync + refresh top 15
GITHUB_TOKEN=ghp_xxx python scripts/sync_upstream.py     # same via env var
```

**Flags:**
- `--dry-run` — print report, don't modify files
- `--upstream-url <url>` — override upstream URL (defaults to VoltAgent's main branch)
- `--github-token <token>` — GitHub PAT for star counts (or `GITHUB_TOKEN` env var)

**Dependencies:** Python 3.8+, standard library only (`urllib.request`, `re`, `json`, `pathlib`, `argparse`).

**Exit codes:**
- `0` — ran successfully, changes were made or nothing to do
- `1` — error (network failure, parse failure)

**Files touched:**
- `README.md` — modified in place with new entries
- `.upstream-snapshot.json` — created/updated with current upstream URLs (committed to repo)
