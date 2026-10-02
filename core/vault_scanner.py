"""
Vault Scanner & Semantic Decision Gate for Obsidian Knowledge Base.

Features:
  - Smart semantic auto-routing based on notebook content DNA and vault taxonomy
  - Sequential numbered prefixing (01_, 02_, 03_) following curriculum order
  - Fast LLM-powered semantic decision gate (MERGE_EXISTING vs CREATE_NEW)
  - Vault organizer to batch-organize and number existing loose notes
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# Default Obsidian Vault path
DEFAULT_VAULT_PATH = Path(r"G:\My Drive\04_Obsedian")


def get_default_vault_path() -> Path:
    """Return default vault path if accessible, else current directory."""
    if DEFAULT_VAULT_PATH.exists() and DEFAULT_VAULT_PATH.is_dir():
        return DEFAULT_VAULT_PATH
    return Path.cwd()


def get_vault_subfolders(vault_path: Path) -> List[Path]:
    """Return all valid, non-hidden subfolders in the Obsidian vault."""
    if not vault_path.exists() or not vault_path.is_dir():
        return []

    subfolders: List[Path] = []
    for root, dirs, _ in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "99_Assets"]
        for d in dirs:
            subfolders.append(Path(root) / d)

    subfolders.sort(key=lambda p: str(p.relative_to(vault_path)).lower())
    return subfolders


def get_next_sequence_prefix(folder: Path) -> str:
    """
    Scan folder for existing numbered markdown files (e.g. 01_..., 02_...)
    and return the next two-digit prefix (e.g. '03_').
    """
    if not folder.exists() or not folder.is_dir():
        return "01_"

    highest = 0
    pattern = re.compile(r"^(\d+)_")
    for file_path in folder.glob("*.md"):
        m = pattern.match(file_path.name)
        if m:
            try:
                num = int(m.group(1))
                if num > highest:
                    highest = num
            except ValueError:
                pass

    return f"{highest + 1:02d}_"


def smart_semantic_route(
    vault_path: Path,
    notebook_title: str,
    notebook_content_preview: str = "",
    file_type: str = "notebook"
) -> Path:
    """
    Smart auto-router that maps a notebook or source file into its proper techstack subfolder
    based on comprehensive conceptual DNA (file type, title, imports, topic tags, markdown).
    """
    # Explicit SQL file routing
    if file_type.lower() == "sql":
        sql_base = vault_path / "01_SQL"
        if (sql_base / "01_Concepts").exists():
            return sql_base / "01_Concepts"
        elif sql_base.exists():
            # Return first available subfolder or base
            subdirs = [d for d in sql_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if subdirs:
                return subdirs[0]
            return sql_base
        return sql_base / "01_Concepts"

    text = f"{notebook_title} {notebook_content_preview}".lower()

    # 1. End-to-end projects
    if any(k in text for k in ["final project", "midcourse project", "mid-course project", "capstone project", "coffee project"]):
        pandas_folder = vault_path / "02_Python" / "02_Data Analysis (Pandas)"
        if pandas_folder.exists():
            return pandas_folder

    # 2. Data Analysis / Pandas / NumPy / Matplotlib / Seaborn / Time Series
    if any(k in text for k in [
        "pandas", "dataframe", "series", "read_csv", "matplotlib", "seaborn", 
        "numpy", "array", "vectorization", "plot", "charts", "eda", "data analysis",
        "groupby", "pivot", "transform", "resample", "rolling", "time series",
        "transactions", "oil prices", "filtering", "boolean masking"
    ]):
        pandas_folder = vault_path / "02_Python" / "02_Data Analysis (Pandas)"
        if pandas_folder.exists():
            return pandas_folder

    # 3. Core Python / Programming Basics
    if any(k in text for k in [
        "python", "list", "tuple", "dict", "dictionary", "set", "function", "lambda",
        "class", "oop", "loop", "string", "comprehension", "cs50p", "variables", "data types"
    ]):
        core_python = vault_path / "02_Python" / "01_Core Python"
        if core_python.exists():
            return core_python

    # 4. SQL / Database Concepts
    if any(k in text for k in [
        "sql", "select", "join", "window function", "cte", "group by", "database", "query",
        "subquery", "aggregate", "partition by", "indexes"
    ]):
        sql_folder = vault_path / "01_SQL" / "01_Concepts"
        if sql_folder.exists():
            return sql_folder

    # 5. Power BI / DAX / Power Query
    if any(k in text for k in [
        "power bi", "dax", "power query", "m code", "calculate", "filter context", "row context"
    ]):
        pbi_folder = vault_path / "03_Power_BI" / "01_Data Modeling"
        if pbi_folder.exists():
            return pbi_folder

    # 6. Azure Data Engineering / Cloud
    if any(k in text for k in [
        "azure", "data factory", "adf", "fabric", "lakehouse", "synapse", "blob", "databricks"
    ]):
        azure_folder = vault_path / "04_Azure_Data_Engineering" / "01_ADF (Data Factory)"
        if azure_folder.exists():
            return azure_folder

    # Default fallback: 00_Inbox if available, or vault root
    inbox = vault_path / "00_Inbox"
    if inbox.exists():
        return inbox

    return vault_path


# Maintain backwards compatibility
suggest_target_subfolder = smart_semantic_route


def scan_existing_notes(folder_path: Path) -> List[Dict[str, Any]]:
    """Scan a folder for all markdown notes and extract titles, YAML tags, and headings."""
    notes_info: List[Dict[str, Any]] = []
    if not folder_path.exists() or not folder_path.is_dir():
        return notes_info

    for file_path in folder_path.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        title = file_path.stem
        # Strip sequence prefix for title extraction if present (e.g. 01_Title -> Title)
        clean_title = re.sub(r"^\d+_", "", title).strip()

        topic = ""
        fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            yaml_text = fm_match.group(1)
            t_match = re.search(r'title:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
            if t_match:
                clean_title = t_match.group(1).strip()
            top_match = re.search(r'topic:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
            if top_match:
                topic = top_match.group(1).strip()

        headings = [h.strip() for h in re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)]

        notes_info.append({
            "path": file_path,
            "filename": file_path.name,
            "title": clean_title,
            "topic": topic,
            "headings": headings[:6],
            "char_count": len(content),
            "content": content,
        })

    return notes_info


def fast_semantic_decision_gate(
    notebook_title: str,
    notebook_summary: str,
    candidate_notes: List[Dict[str, Any]],
    ai_client: Any,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Fast LLM-based semantic decision gate (~1s, ~300 tokens):
    Determines whether an incoming notebook represents an expansion of an
    existing note (MERGE_EXISTING) or covers a distinct concept (CREATE_NEW).
    """
    if not candidate_notes:
        return {"action": "CREATE_NEW", "matched_path": None, "reasoning": "No candidate notes in target folder"}

    candidates_summary = []
    for c in candidate_notes:
        candidates_summary.append({
            "filename": c["filename"],
            "title": c["title"],
            "headings": c["headings"][:4],
        })

    prompt = f"""\
You are an expert technical curriculum classifier. Determine whether the incoming notebook should be merged into an existing study note or saved as a brand-new note.

## INCOMING NOTEBOOK:
- Title: {notebook_title}
- Overview & Code Snippets:
{notebook_summary[:1200]}

## EXISTING NOTES IN FOLDER:
{json.dumps(candidates_summary, indent=2)}

## DECISION RULES:
1. Return MERGE_EXISTING ONLY if the incoming notebook covers the exact same core topic/tool as an existing note and should expand it.
2. Return CREATE_NEW if the incoming notebook covers a different concept, different library, or a separate assignment/project (e.g. NumPy vs Pandas, Series vs DataFrame, Line Plots vs Aggregations).

Return strictly a JSON object:
{{
  "action": "CREATE_NEW" | "MERGE_EXISTING",
  "matched_filename": "filename.md" | null,
  "reasoning": "brief explanation"
}}
"""

    try:
        if progress_callback:
            progress_callback("Semantic Decision Gate: Evaluating topic boundaries...")

        raw_response = ai_client.generate_chat_completion(
            messages=[
                {"role": "system", "content": "You are a concise curriculum classifier. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=256
        )

        # Extract JSON
        clean_json = raw_response.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()

        data = json.loads(clean_json)
        action = data.get("action", "CREATE_NEW")
        matched_filename = data.get("matched_filename")

        matched_path = None
        if action == "MERGE_EXISTING" and matched_filename:
            for c in candidate_notes:
                if c["filename"].lower() == matched_filename.lower():
                    matched_path = c["path"]
                    break

        return {
            "action": action if matched_path else "CREATE_NEW",
            "matched_path": matched_path,
            "reasoning": data.get("reasoning", ""),
        }
    except Exception as e:
        # Fallback to fuzzy matcher if semantic call fails
        matched = find_matching_note(notebook_title, candidate_notes[0]["path"].parent)
        return {
            "action": "MERGE_EXISTING" if matched else "CREATE_NEW",
            "matched_path": matched,
            "reasoning": f"Semantic fallback: {e}",
        }


def find_matching_note(
    candidate_title: str, 
    target_folder: Path, 
    similarity_threshold: float = 0.65
) -> Optional[Path]:
    """Fuzzy fallback matcher for existing notes in target folder."""
    if not target_folder.exists() or not target_folder.is_dir():
        return None

    clean_candidate = re.sub(r"^\d+_", "", candidate_title).strip()
    candidate_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', clean_candidate.lower()))
    candidate_words -= {"section", "course", "exercise", "assignment", "solution", "solutions", "demo", "demos", "lecture"}
    
    if not candidate_words:
        return None

    best_match_path: Optional[Path] = None
    best_score = 0.0

    for note_file in target_folder.glob("*.md"):
        note_name_clean = re.sub(r"^\d+_", "", note_file.stem).lower()
        note_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', note_name_clean))
        note_words -= {"section", "course", "exercise", "assignment", "solution", "solutions", "demo", "demos", "lecture"}
        
        if not note_words:
            continue

        intersection = candidate_words & note_words
        union = candidate_words | note_words
        score = len(intersection) / len(union) if union else 0.0

        if score > best_score and score >= similarity_threshold:
            best_score = score
            best_match_path = note_file

    return best_match_path


def organize_and_number_vault_notes(
    vault_root: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Batch organizer for loose notes in root vault:
      1. Inspects structured DNA (YAML topic, skills, headings).
      2. Smart-routes each note to its proper techstack subfolder.
      3. Assigns clean sequential numbers (02_, 03_, 04_...).
      4. Moves files and updates tracker.json in place.
    """
    from core.file_manager import load_tracker, save_tracker

    if not vault_root.exists() or not vault_root.is_dir():
        return {"success": False, "moved_count": 0, "error": "Vault path invalid"}

    # Find loose markdown files directly in vault root
    loose_notes = [
        f for f in vault_root.glob("*.md")
        if f.is_file() and not f.name.startswith("00_Vault") and not f.name.startswith(".")
    ]

    if not loose_notes:
        if progress_callback:
            progress_callback("No loose notes found in root vault to organize.")
        return {"success": True, "moved_count": 0, "moved_files": []}

    if progress_callback:
        progress_callback(f"Found {len(loose_notes)} loose notes. Beginning smart routing & numbering...")

    # Load tracker for updating paths
    tracker = load_tracker()
    tracker_updated = False
    moved_records: List[Dict[str, str]] = []

    # Sort notes logically by curriculum order if detectable
    def sort_key(p: Path) -> Tuple[int, str]:
        name_lower = p.stem.lower()
        if "numpy" in name_lower:
            return (1, name_lower)
        if "series" in name_lower:
            return (2, name_lower)
        if "dataframe" in name_lower or "checkpoint" in name_lower:
            return (3, name_lower)
        if "aggregat" in name_lower or "group" in name_lower:
            return (4, name_lower)
        if "plot" in name_lower or "visual" in name_lower:
            return (5, name_lower)
        if "mid-course" in name_lower or "midcourse" in name_lower:
            return (6, name_lower)
        if "time series" in name_lower:
            return (7, name_lower)
        if "csv" in name_lower or "export" in name_lower or "ingestion" in name_lower:
            return (8, name_lower)
        if "combining" in name_lower or "join" in name_lower or "merge" in name_lower:
            return (9, name_lower)
        if "final project" in name_lower:
            return (10, name_lower)
        return (99, name_lower)

    loose_notes.sort(key=sort_key)

    for note_path in loose_notes:
        try:
            content = note_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Route based on content DNA
        dest_folder = smart_semantic_route(vault_root, note_path.stem, content[:1500])
        dest_folder.mkdir(parents=True, exist_ok=True)

        # Get next sequential prefix in destination folder
        clean_stem = re.sub(r"^\d+_", "", note_path.stem).strip()
        prefix = get_next_sequence_prefix(dest_folder)
        new_filename = f"{prefix}{clean_stem}.md"
        dest_path = dest_folder / new_filename

        # Move file safely
        shutil.move(str(note_path), str(dest_path))

        # Update tracker.json if path was referenced
        old_path_str = str(note_path.resolve())
        for file_hash, record in tracker.items():
            if record.get("note_path") == old_path_str:
                record["note_path"] = str(dest_path.resolve())
                tracker_updated = True

        rel_dest = dest_path.relative_to(vault_root)
        if progress_callback:
            progress_callback(f"  📦 Moved: {note_path.name} ➡️ {rel_dest}")

        moved_records.append({
            "original": note_path.name,
            "new_path": str(dest_path),
            "display": str(rel_dest),
        })

    if tracker_updated:
        save_tracker(tracker)

    return {
        "success": True,
        "moved_count": len(moved_records),
        "moved_files": moved_records,
    }
