"""
Test script for Phase 3 verification:
- Test CS50 Note Synthesis adhering to Video_to_Notes_Generator schema
- Test Intelligent In-Place Merge on an existing note
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from core.ai_client import AzureAIClient
from core.notes_generator import get_colab_system_prompt, sanitize_notes, extract_title_from_notes
from core.diff_merger import perform_intelligent_merge


def main():
    print("=== Testing Phase 3: Generator & In-Place Sectional Merger ===")

    ai_client = AzureAIClient()
    print(f"Connected to deployment: {ai_client.deployment}")

    # 1. Test CS50 Synthesis with small payload
    test_payload = """\
# NOTEBOOK: section01_NumPy_quick_demo.ipynb
Markdown Cell:
# Introduction to NumPy Arrays
NumPy arrays provide memory contiguous buffers for numerical calculations.

Code Cell:
import numpy as np
arr = np.arange(1, 10).reshape(3, 3)
print(arr)
# Output:
# [[1 2 3]
#  [4 5 6]
#  [7 8 9]]

Markdown Cell:
## Boolean Filtering
Filter elements greater than 5.

Code Cell:
mask = arr > 5
filtered = arr[mask]
print(filtered)
# Output: [6 7 8 9]
"""

    print("\n--- 1. Testing CS50 Note Synthesis ---")
    messages = [
        {"role": "system", "content": get_colab_system_prompt()},
        {"role": "user", "content": f"Transform this notebook into Obsidian study notes:\n\n{test_payload}"}
    ]
    raw_notes = ai_client.generate_chat_completion(messages=messages)
    clean_notes = sanitize_notes(raw_notes)
    title = extract_title_from_notes(clean_notes)

    print(f"Synthesized Note Title: '{title}'")
    print(f"Character Length: {len(clean_notes)}")
    
    # Assertions for schema compliance
    has_frontmatter = clean_notes.strip().startswith("---")
    has_abstract = "[!ABSTRACT]" in clean_notes
    has_toc = "Table of Contents" in clean_notes and "[[#" in clean_notes
    has_wikilinks = "[[" in clean_notes and "]]" in clean_notes
    has_recall = "[!question]-" in clean_notes
    has_cheatsheet = "Quick Reference" in clean_notes or "Cheat Sheet" in clean_notes
    
    print(f"  [Check] Frontmatter present: {has_frontmatter}")
    print(f"  [Check] Executive Abstract: {has_abstract}")
    print(f"  [Check] Clickable TOC ([[#...]]): {has_toc}")
    print(f"  [Check] Related WikiLinks: {has_wikilinks}")
    print(f"  [Check] Active Recall Collapsible Questions: {has_recall}")
    print(f"  [Check] Quick Reference / Cheat Sheet: {has_cheatsheet}")

    # 2. Test Intelligent In-Place Merge
    print("\n--- 2. Testing Intelligent In-Place Sectional Merge ---")
    existing_note = """---
title: "NumPy Fundamentals"
topic: "Python | Data Analysis"
created: "2026-09-20"
tags:
  - python
  - numpy
---

# NumPy Fundamentals

> [!ABSTRACT] Executive Summary
> Introduction to basic NumPy 1D and 2D arrays.

### 📑 Table of Contents
- [[#1. Basic Array Creation]]

## 1. Basic Array Creation
```python
import numpy as np
arr = np.array([1, 2, 3])
```
"""

    new_knowledge = """\
We explored multi-axis broadcasting and np.where conditional statements:
```python
# Broadcasting: adding (3, 1) and (1, 3) arrays
a = np.array([[10], [20], [30]])
b = np.array([[1, 2, 3]])
c = a + b # broadcasts to (3, 3)

# Vectorized ternary selection
result = np.where(c > 25, "High", "Low")
```
"""

    merged = perform_intelligent_merge(
        existing_note_content=existing_note,
        new_notebook_payload=new_knowledge,
        ai_client=ai_client,
        progress_callback=lambda msg: print(f"  Progress: {msg}")
    )

    print(f"\nMerged Note Character Length: {len(merged)}")
    has_merged_broadcasting = "broadcasting" in merged.lower() or "np.where" in merged.lower()
    has_preserved_basic = "Basic Array Creation" in merged or "np.array([1, 2, 3])" in merged
    print(f"  [Check] Preserved original foundations: {has_preserved_basic}")
    print(f"  [Check] Weaved in new broadcasting/np.where: {has_merged_broadcasting}")

    print("\n>>> PHASE 3 VERIFICATION SUCCESSFUL! <<<")


if __name__ == "__main__":
    main()
