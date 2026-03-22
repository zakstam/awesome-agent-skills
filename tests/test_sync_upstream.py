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
