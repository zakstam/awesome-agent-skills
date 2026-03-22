import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from sync_upstream import extract_section_name

def test_extract_section_from_summary_h3():
    line = '<summary><h3 style="display:inline">Official Claude Skills </h3></summary>'
    assert extract_section_name(line) == "Official Claude Skills"

def test_extract_section_from_summary_h3_no_style():
    line = '<summary><h3>Skills by Stripe Team</h3></summary>'
    assert extract_section_name(line) == "Skills by Stripe Team"

def test_extract_section_from_h3_heading():
    line = '### Community Skills'
    assert extract_section_name(line) == "Community Skills"

def test_extract_section_from_h2_heading():
    line = '## ⭐ Top 15 Most Popular Skills'
    assert extract_section_name(line) == "Top 15 Most Popular Skills"

def test_extract_section_from_h2_plain():
    line = '## Skills Paths for Other AI Coding Assistants'
    assert extract_section_name(line) == "Skills Paths for Other AI Coding Assistants"

def test_no_section_in_regular_line():
    line = '| [foo](https://github.com/foo/bar) | description |'
    assert extract_section_name(line) is None


from sync_upstream import SkillEntry, parse_readme

def test_parse_two_column_table():
    readme = """<details>
<summary><h3 style="display:inline">Official Claude Skills </h3></summary>

| Skill | Description |
|-------|-------------|
| [anthropics/docx](https://github.com/anthropics/skills/tree/main/skills/docx) | Create Word documents |

</details>"""
    skills = parse_readme(readme)
    url = "https://github.com/anthropics/skills/tree/main/skills/docx"
    assert url in skills
    assert skills[url].description == "Create Word documents"
    assert skills[url].section == "Official Claude Skills"

def test_parse_three_column_table():
    readme = """### Community Skills

<details>
<summary><h3 style="display:inline">Marketing</h3></summary>

| Skill | Stars | Description |
|-------|-------|-------------|
| [foo/bar](https://github.com/foo/bar) | ![GitHub Stars](https://img.shields.io/github/stars/foo/bar) | SEO tool |

</details>"""
    skills = parse_readme(readme)
    url = "https://github.com/foo/bar"
    assert url in skills
    assert skills[url].description == "SEO tool"
    assert skills[url].section == "Community Skills > Marketing"

def test_skip_top15_table():
    readme = """## ⭐ Top 15 Most Popular Skills

| # | Skill | Stars | Description |
|---|-------|-------|-------------|
| 1 | [foo/bar](https://github.com/foo/bar) | ![stars] | Top skill |

## Next Section"""
    skills = parse_readme(readme)
    assert len(skills) == 0

def test_skip_compatibility_table():
    readme = """## Skills Paths for Other AI Coding Assistants

| Tool | Project Path | Global Path | Official Docs |
|------|-------------|-------------|---------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | [Docs](https://docs.anthropic.com) |"""
    skills = parse_readme(readme)
    assert len(skills) == 0
