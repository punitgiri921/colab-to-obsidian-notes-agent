"""
Vault Scanner for Obsidian Knowledge Base.

Indexes folder hierarchy, categorizes topics, and searches for existing
notes to enable intelligent in-place merging.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Default Obsidian Vault path
DEFAULT_VAULT_PATH = Path(r"G:\My Drive\04_Obsedian")


def get_default_vault_path() -> Path:
    """Return the default vault path if accessible, else current directory."""
    if DEFAULT_VAULT_PATH.exists() and DEFAULT_VAULT_PATH.is_dir():
        return DEFAULT_VAULT_PATH
    return Path.cwd()


def get_vault_subfolders(vault_path: Path) -> List[Path]:
    """
    Return all valid, non-hidden subfolders in the Obsidian vault
    sorted in natural hierarchical order.
    """
    if not vault_path.exists() or not vault_path.is_dir():
        return []

    subfolders: List[Path] = []
    
    # We walk the vault, ignoring hidden folders (e.g. .obsidian, .git)
    for root, dirs, _ in os.walk(vault_path):
        # Filter out hidden directories in place
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "99_Assets"]
        for d in dirs:
            p = Path(root) / d
            subfolders.append(p)

    # Sort folders alphabetically by relative path
    subfolders.sort(key=lambda p: str(p.relative_to(vault_path)).lower())
    return subfolders


def suggest_target_subfolder(vault_path: Path, notebook_title: str, notebook_content_preview: str = "") -> Path:
    """
    Intelligently suggest the destination subfolder in the Obsidian vault based on
    keywords in the notebook title, imports, and content.
    """
    combined_text = f"{notebook_title} {notebook_content_preview}".lower()

    # 1. Check for Pandas / Data Analysis / NumPy / Data Viz
    if any(k in combined_text for k in [
        "pandas", "dataframe", "series", "read_csv", "matplotlib", "seaborn", 
        "numpy", "array", "vectorization", "plot", "charts", "eda", "data analysis"
    ]):
        pandas_folder = vault_path / "02_Python" / "02_Data Analysis (Pandas)"
        if pandas_folder.exists():
            return pandas_folder

    # 2. Check for Core Python / Basics
    if any(k in combined_text for k in [
        "python", "list", "tuple", "dict", "dictionary", "set", "function", "lambda",
        "class", "oop", "loop", "string", "comprehension", "cs50p"
    ]):
        core_python = vault_path / "02_Python" / "01_Core Python"
        if core_python.exists():
            return core_python

    # 3. Check for SQL / Database concepts
    if any(k in combined_text for k in [
        "sql", "select", "join", "window function", "cte", "group by", "database", "query"
    ]):
        sql_folder = vault_path / "01_SQL" / "01_Concepts"
        if sql_folder.exists():
            return sql_folder

    # 4. Check for Power BI / DAX
    if any(k in combined_text for k in [
        "power bi", "dax", "power query", "m code", "calculate", "filter context"
    ]):
        pbi_folder = vault_path / "03_Power_BI" / "01_Data Modeling"
        if pbi_folder.exists():
            return pbi_folder

    # 5. Check for Azure / Cloud Data Engineering
    if any(k in combined_text for k in [
        "azure", "data factory", "adf", "fabric", "lakehouse", "synapse", "blob"
    ]):
        azure_folder = vault_path / "04_Azure_Data_Engineering" / "01_ADF (Data Factory)"
        if azure_folder.exists():
            return azure_folder

    # Default fallback: 00_Inbox if it exists, or Python Core
    inbox = vault_path / "00_Inbox"
    if inbox.exists():
        return inbox

    return vault_path


def scan_existing_notes(folder_path: Path) -> List[Dict[str, Any]]:
    """
    Scan a folder for all markdown notes and extract their title, headings, and metadata.
    """
    notes_info: List[Dict[str, Any]] = []
    if not folder_path.exists() or not folder_path.is_dir():
        return notes_info

    for file_path in folder_path.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract title from YAML frontmatter or first # Heading
        title = file_path.stem
        fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            yaml_text = fm_match.group(1)
            t_match = re.search(r'title:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
            if t_match:
                title = t_match.group(1).strip()
        else:
            h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()

        # Extract primary headings
        headings = [h.strip() for h in re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)]

        notes_info.append({
            "path": file_path,
            "filename": file_path.name,
            "title": title,
            "headings": headings,
            "char_count": len(content),
            "content": content,
        })

    return notes_info


def find_matching_note(
    candidate_title: str, 
    target_folder: Path, 
    similarity_threshold: float = 0.6
) -> Optional[Path]:
    """
    Check if a note closely matching the given title/topic exists in the target folder.
    Returns the file path if a strong match is found, otherwise None.
    """
    if not target_folder.exists() or not target_folder.is_dir():
        return None

    # Clean words in candidate title
    candidate_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', candidate_title.lower()))
    # Remove generic keywords
    candidate_words -= {"section", "course", "exercise", "assignment", "solution", "solutions", "demo", "demos", "lecture"}
    
    if not candidate_words:
        return None

    best_match_path: Optional[Path] = None
    best_score = 0.0

    for note_file in target_folder.glob("*.md"):
        note_name_clean = note_file.stem.lower()
        note_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', note_name_clean))
        note_words -= {"section", "course", "exercise", "assignment", "solution", "solutions", "demo", "demos", "lecture"}
        
        if not note_words:
            continue

        # Jaccard overlap
        intersection = candidate_words & note_words
        union = candidate_words | note_words
        score = len(intersection) / len(union) if union else 0.0

        if score > best_score and score >= similarity_threshold:
            best_score = score
            best_match_path = note_file

    return best_match_path
