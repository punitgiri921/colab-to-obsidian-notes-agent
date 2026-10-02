"""
Unified Multi-Source AST & Text Parser, Image Extractor, and Pairer.

Supports:
  1. Jupyter / Google Colab Notebooks (.ipynb)
  2. SQL Scripts & Exercise Files (.sql)
  3. Python Source Files & Scripts (.py)

Features:
  - Format-specific block extraction (Comments/Docstrings -> Markdown, Queries/Code -> Code blocks)
  - Collision-safe pairing of companion exercise and solution files by extension
  - Base64 plot extraction for notebooks
  - Language-aware payload generation (```sql vs ```python)
"""

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import nbformat


def get_file_hash(filepath: Path | str) -> str:
    """Compute SHA-256 hash of a file for checkpointing."""
    p = Path(filepath)
    if not p.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def clean_source_code(source: str) -> str:
    """
    Clean Python code cells by commenting out or removing ephemeral notebook noise:
    - !pip install, !apt-get, %load_ext, %matplotlib inline, etc.
    """
    lines = source.splitlines()
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("!pip ") or stripped.startswith("!pip3 ") or stripped.startswith("pip install"):
            cleaned_lines.append(f"# {line}  # (installation omitted for study notes)")
        elif stripped.startswith("!") or stripped.startswith("%"):
            if stripped.startswith("%matplotlib inline"):
                continue  # Standard magic, unnecessary in notes
            cleaned_lines.append(f"# {line}")
        else:
            cleaned_lines.append(line)
            
    return "\n".join(cleaned_lines).strip()


def truncate_output_text(text: str, max_lines: int = 15, max_chars: int = 1200) -> str:
    """Truncate overly verbose stdout or array representations."""
    lines = text.strip().splitlines()
    if len(lines) > max_lines:
        half = max_lines // 2
        truncated_lines = lines[:half] + [f"\n... [{len(lines) - max_lines} lines truncated for clarity] ...\n"] + lines[-half:]
        text = "\n".join(truncated_lines)
    
    if len(text) > max_chars:
        text = text[:max_chars] + " ... [output truncated]"
    return text.strip()


class ExtractedImage:
    """Represents a plot/figure extracted from notebook output."""
    def __init__(self, filename: str, data_bytes: bytes, cell_index: int, description: str = ""):
        self.filename = filename
        self.data_bytes = data_bytes
        self.cell_index = cell_index
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "cell_index": self.cell_index,
            "description": self.description,
            "size_bytes": len(self.data_bytes),
        }


# =========================================================================
# 1. Jupyter Notebook (.ipynb) Parser
# =========================================================================

def parse_notebook(notebook_path: Path | str) -> Dict[str, Any]:
    """Parse a Jupyter / Google Colab notebook (.ipynb) into clean structured content."""
    path = Path(notebook_path)
    if not path.is_file():
        raise FileNotFoundError(f"Notebook not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    file_hash = get_file_hash(path)
    title_candidate = path.stem.replace("_", " ").replace("-", " ").title()
    
    structured_cells: List[Dict[str, Any]] = []
    extracted_images: List[ExtractedImage] = []
    
    img_counter = 1
    stem_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', path.stem)

    for idx, cell in enumerate(nb.cells):
        cell_type = cell.get("cell_type", "")
        source = cell.get("source", "").strip()

        if not source:
            continue

        if cell_type == "markdown":
            structured_cells.append({
                "type": "markdown",
                "cell_index": idx,
                "content": source,
            })
        elif cell_type == "code":
            cleaned_code = clean_source_code(source)
            outputs_summary: List[str] = []
            
            for out in cell.get("outputs", []):
                out_type = out.get("output_type", "")
                
                # Check for images (Matplotlib / Seaborn plots)
                data = out.get("data", {})
                if "image/png" in data:
                    png_b64 = data["image/png"]
                    try:
                        png_bytes = base64.b64decode(re.sub(r'\s+', '', png_b64))
                        img_hash = hashlib.md5(png_bytes).hexdigest()[:6]
                        asset_name = f"{stem_clean}_fig{img_counter}_{img_hash}.png"
                        
                        img_obj = ExtractedImage(
                            filename=asset_name,
                            data_bytes=png_bytes,
                            cell_index=idx,
                            description=f"Generated plot from cell {idx}"
                        )
                        extracted_images.append(img_obj)
                        outputs_summary.append(f"[Embedded Plot Asset: ![[{asset_name}]]]")
                        img_counter += 1
                    except Exception:
                        pass
                
                # Check for textual outputs
                if out_type == "stream":
                    text = out.get("text", "")
                    if text:
                        truncated = truncate_output_text(text)
                        if truncated:
                            outputs_summary.append(truncated)
                elif out_type in ("execute_result", "display_data"):
                    text_plain = data.get("text/plain", "")
                    if text_plain and not ("image/png" in data and len(text_plain) > 100):
                        truncated = truncate_output_text(text_plain)
                        if truncated:
                            outputs_summary.append(truncated)
                elif out_type == "error":
                    ename = out.get("ename", "Error")
                    evalue = out.get("evalue", "")
                    outputs_summary.append(f"[Expected/Observed Error: {ename}: {evalue}]")

            structured_cells.append({
                "type": "code",
                "language": "python",
                "cell_index": idx,
                "code": cleaned_code,
                "outputs": outputs_summary,
            })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_hash": file_hash,
        "file_type": "notebook",
        "language": "python",
        "suggested_title": title_candidate,
        "cells": structured_cells,
        "images": extracted_images,
        "cell_count": len(structured_cells),
        "image_count": len(extracted_images),
    }


# =========================================================================
# 2. SQL Script (.sql) Parser
# =========================================================================

def parse_sql_file(sql_path: Path | str) -> Dict[str, Any]:
    """
    Parse a .sql file into structured narrative blocks and SQL query blocks.
    
    Extracts:
      - Block comments (/* ... */) and line comments (-- ...) as Markdown/instructional cells
      - Clean SQL queries as code cells with language="sql"
    """
    path = Path(sql_path)
    if not path.is_file():
        raise FileNotFoundError(f"SQL file not found: {path}")

    # Read with UTF-8 encoding (fallback to latin-1 if needed)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")

    file_hash = get_file_hash(path)
    title_candidate = path.stem.replace("_", " ").replace("-", " ").title()

    structured_cells: List[Dict[str, Any]] = []
    lines = content.splitlines()

    current_comments: List[str] = []
    current_code: List[str] = []
    in_block_comment = False
    block_comment_lines: List[str] = []
    cell_idx = 0

    def flush_comments():
        nonlocal cell_idx
        if current_comments:
            comment_text = "\n".join(current_comments).strip()
            if comment_text:
                structured_cells.append({
                    "type": "markdown",
                    "cell_index": cell_idx,
                    "content": comment_text,
                })
                cell_idx += 1
            current_comments.clear()

    def flush_code():
        nonlocal cell_idx
        if current_code:
            code_text = "\n".join(current_code).strip()
            if code_text:
                structured_cells.append({
                    "type": "code",
                    "language": "sql",
                    "cell_index": cell_idx,
                    "code": code_text,
                    "outputs": [],
                })
                cell_idx += 1
            current_code.clear()

    for line in lines:
        stripped = line.strip()

        # Handle multi-line block comments /* ... */
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
                parts = stripped.split("*/", 1)
                block_comment_lines.append(parts[0].strip())
                # Add cleaned block comment to comments
                clean_block = "\n".join(block_comment_lines).strip()
                # Remove leading '*' from block comment formatting
                clean_lines = [re.sub(r'^\s*\*+\s?', '', l) for l in clean_block.splitlines()]
                current_comments.append("\n".join(clean_lines).strip())
                block_comment_lines = []
                # If there's trailing code on the same line after */
                if parts[1].strip():
                    current_code.append(parts[1].strip())
            else:
                block_comment_lines.append(stripped)
            continue

        if stripped.startswith("/*"):
            if "*/" in stripped:
                # Single-line /* ... */
                inner = stripped[2:stripped.index("*/")].strip()
                inner_clean = re.sub(r'^\s*\*+\s?', '', inner)
                flush_code()
                current_comments.append(inner_clean)
                after = stripped[stripped.index("*/") + 2:].strip()
                if after:
                    current_code.append(after)
            else:
                in_block_comment = True
                flush_code()
                block_comment_lines.append(stripped[2:].strip())
            continue

        # Handle single-line comments (-- ...)
        if stripped.startswith("--"):
            comment_body = stripped[2:].strip()
            # If we had pending code, flush it before switching to comments
            flush_code()
            current_comments.append(comment_body)
            continue

        # Regular SQL code line
        if stripped:
            # If we had pending comments, flush them before starting code
            flush_comments()
            current_code.append(line)
        else:
            # Blank line: if in code, preserve readability; if between queries ending in ;, flush code
            if current_code and current_code[-1].strip().endswith(";"):
                flush_code()
            elif current_code:
                current_code.append("")
            elif current_comments:
                current_comments.append("")

    flush_comments()
    flush_code()

    # If the file had no comments, wrap the entire SQL as one code cell
    if not structured_cells and content.strip():
        structured_cells.append({
            "type": "code",
            "language": "sql",
            "cell_index": 0,
            "code": content.strip(),
            "outputs": [],
        })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_hash": file_hash,
        "file_type": "sql",
        "language": "sql",
        "suggested_title": title_candidate,
        "cells": structured_cells,
        "images": [],
        "cell_count": len(structured_cells),
        "image_count": 0,
    }


# =========================================================================
# 3. Python Script (.py) Parser
# =========================================================================

def parse_python_file(py_path: Path | str) -> Dict[str, Any]:
    """
    Parse a standalone .py script into structured narrative (docstrings/comments)
    and executable Python code blocks.
    """
    path = Path(py_path)
    if not path.is_file():
        raise FileNotFoundError(f"Python file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")

    file_hash = get_file_hash(path)
    title_candidate = path.stem.replace("_", " ").replace("-", " ").title()

    structured_cells: List[Dict[str, Any]] = []
    lines = content.splitlines()

    current_comments: List[str] = []
    current_code: List[str] = []
    in_docstring = False
    docstring_delimiter = ""
    docstring_lines: List[str] = []
    cell_idx = 0

    def flush_comments():
        nonlocal cell_idx
        if current_comments:
            comment_text = "\n".join(current_comments).strip()
            if comment_text:
                structured_cells.append({
                    "type": "markdown",
                    "cell_index": cell_idx,
                    "content": comment_text,
                })
                cell_idx += 1
            current_comments.clear()

    def flush_code():
        nonlocal cell_idx
        if current_code:
            code_text = clean_source_code("\n".join(current_code).strip())
            if code_text:
                structured_cells.append({
                    "type": "code",
                    "language": "python",
                    "cell_index": cell_idx,
                    "code": code_text,
                    "outputs": [],
                })
                cell_idx += 1
            current_code.clear()

    for line in lines:
        stripped = line.strip()

        # Handle multi-line docstrings """ or '''
        if in_docstring:
            if docstring_delimiter in stripped:
                in_docstring = False
                parts = stripped.split(docstring_delimiter, 1)
                docstring_lines.append(parts[0].strip())
                clean_doc = "\n".join(docstring_lines).strip()
                current_comments.append(clean_doc)
                docstring_lines = []
                if parts[1].strip():
                    current_code.append(parts[1].strip())
            else:
                docstring_lines.append(line)
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = stripped[:3]
            remainder = stripped[3:]
            if delim in remainder:
                # Single-line docstring
                inner = remainder[:remainder.index(delim)].strip()
                flush_code()
                current_comments.append(inner)
            else:
                in_docstring = True
                docstring_delimiter = delim
                flush_code()
                docstring_lines.append(remainder)
            continue

        # Handle consecutive # comment blocks
        if stripped.startswith("#"):
            # Omit shebang or coding comments
            if stripped.startswith("#!") or "coding:" in stripped:
                continue
            comment_body = stripped.lstrip("#").strip()
            flush_code()
            current_comments.append(comment_body)
            continue

        if stripped:
            flush_comments()
            current_code.append(line)
        else:
            if current_code:
                current_code.append("")
            elif current_comments:
                current_comments.append("")

    flush_comments()
    flush_code()

    if not structured_cells and content.strip():
        structured_cells.append({
            "type": "code",
            "language": "python",
            "cell_index": 0,
            "code": clean_source_code(content.strip()),
            "outputs": [],
        })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_hash": file_hash,
        "file_type": "python",
        "language": "python",
        "suggested_title": title_candidate,
        "cells": structured_cells,
        "images": [],
        "cell_count": len(structured_cells),
        "image_count": 0,
    }


# =========================================================================
# 4. Master Parser Dispatcher
# =========================================================================

def parse_source_file(file_path: Path | str) -> Dict[str, Any]:
    """Dispatch file to the appropriate parser based on extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".ipynb":
        return parse_notebook(path)
    elif suffix == ".sql":
        return parse_sql_file(path)
    elif suffix == ".py":
        return parse_python_file(path)
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Supported: .ipynb, .sql, .py")


# =========================================================================
# 5. Extension-Safe Exercise & Solution Pairing
# =========================================================================

def find_source_pairs(file_paths: List[Path]) -> List[Dict[str, Any]]:
    """
    Analyze source file paths and group exercise files with their corresponding
    solution files, strictly partitioned by extension to prevent cross-extension collisions.

    Supports: .ipynb, .sql, .py
    Patterns:
      - `foo_solutions.ext` paired with `foo.ext`
      - `foo_solution.ext` paired with `foo.ext`
      - `foo_solved.ext` paired with `foo.ext`
      - `foo_final.ext` paired with `foo.ext` or `foo_begin.ext`
      - `foo - Solution.ext` paired with `foo.ext`
    """
    solution_suffixes = [
        "_solutions", "_solution", "_solved", "_final", "_end", "_completed",
        " - solutions", " - solution", " - solved", " - final", " - completed"
    ]
    begin_suffixes = ["_begin", "_start", "_exercise", " - begin", " - exercise"]

    # Partition file paths by extension
    ext_groups: Dict[str, List[Path]] = {}
    for p in file_paths:
        ext = p.suffix.lower()
        if ext in (".ipynb", ".sql", ".py"):
            ext_groups.setdefault(ext, []).append(p)

    pairs: List[Dict[str, Any]] = []

    for ext, files in ext_groups.items():
        stem_map: Dict[str, Path] = {}
        for p in files:
            stem_map[p.stem.lower()] = p

        processed_stems = set()

        # Pass 1: Match solution files with base/exercise files
        for p in files:
            stem_lower = p.stem.lower()
            if stem_lower in processed_stems:
                continue

            matched_suffix = None
            base_stem = None
            for suffix in solution_suffixes:
                if stem_lower.endswith(suffix):
                    matched_suffix = suffix
                    base_stem = stem_lower[:-len(suffix)]
                    break

            if base_stem:
                exercise_candidate = None
                # Check for exact base stem
                if base_stem in stem_map:
                    exercise_candidate = stem_map[base_stem]
                else:
                    # Check for begin suffixes like base_stem + "_begin"
                    for b_suf in begin_suffixes:
                        if (base_stem + b_suf) in stem_map:
                            exercise_candidate = stem_map[base_stem + b_suf]
                            break

                if exercise_candidate and exercise_candidate != p:
                    processed_stems.add(stem_lower)
                    processed_stems.add(exercise_candidate.stem.lower())
                    
                    clean_display = exercise_candidate.stem.replace("_", " ").replace("-", " ").title()
                    for b_suf in begin_suffixes:
                        clean_display = re.sub(rf'\b{b_suf.replace("_", "")}\b', '', clean_display, flags=re.IGNORECASE).strip()

                    file_type = "notebook" if ext == ".ipynb" else "sql" if ext == ".sql" else "python"
                    pairs.append({
                        "display_name": clean_display,
                        "is_pair": True,
                        "file_type": file_type,
                        "extension": ext,
                        "exercise_path": exercise_candidate,
                        "solution_path": p,
                        "primary_path": p,
                    })

        # Pass 2: Standalone files
        for p in files:
            stem_lower = p.stem.lower()
            if stem_lower not in processed_stems:
                processed_stems.add(stem_lower)
                clean_display = p.stem.replace("_", " ").replace("-", " ").title()
                is_sol = any(stem_lower.endswith(s) for s in solution_suffixes)
                file_type = "notebook" if ext == ".ipynb" else "sql" if ext == ".sql" else "python"

                pairs.append({
                    "display_name": clean_display,
                    "is_pair": False,
                    "file_type": file_type,
                    "extension": ext,
                    "exercise_path": p if not is_sol else None,
                    "solution_path": p if is_sol else None,
                    "primary_path": p,
                })

    # Sort pairs alphabetically by display name
    pairs.sort(key=lambda x: (x["extension"], x["display_name"].lower()))
    return pairs


# Maintain backward compatibility
find_notebook_pairs = find_source_pairs


# =========================================================================
# 6. Language-Aware Dual Ingestion Payload
# =========================================================================

def build_dual_ingestion_payload(exercise_data: Optional[Dict[str, Any]], solution_data: Dict[str, Any]) -> str:
    """
    Construct a coherent narrative combining prompts from exercise files with
    working implementations from solution files. Automatically formats code blocks
    with ```sql or ```python based on the file language.
    """
    lang = solution_data.get("language", "python")
    source_type = solution_data.get("file_type", "notebook").upper()

    lines: List[str] = []
    lines.append(f"# SOURCE {source_type}: {solution_data['file_name']}")
    if exercise_data:
        lines.append(f"# PAIRED EXERCISE: {exercise_data['file_name']}")
    lines.append(f"# PRIMARY LANGUAGE: {lang.upper()}")
    lines.append("")

    # Extract markdown prompt descriptions from exercise if present
    if exercise_data:
        exercise_prompts = []
        for cell in exercise_data.get("cells", []):
            if cell["type"] == "markdown":
                exercise_prompts.append(cell["content"])
        if exercise_prompts:
            lines.append("## EXERCISE CHALLENGES & PROMPTS GIVEN TO STUDENTS:")
            for prompt in exercise_prompts:
                lines.append(prompt)
                lines.append("---")
            lines.append("")

    # Step through the complete solution
    lines.append("## COMPLETE WORKTHROUGH & SOLUTION IMPLEMENTATION:")
    for cell in solution_data.get("cells", []):
        if cell["type"] == "markdown":
            lines.append(f"\n{cell['content']}\n")
        elif cell["type"] == "code":
            cell_lang = cell.get("language", lang)
            lines.append(f"```{cell_lang}")
            lines.append(cell["code"])
            lines.append("```")
            if cell.get("outputs"):
                lines.append("Console / Cell Output:")
                for out in cell["outputs"]:
                    lines.append(f"  {out}")
            lines.append("")

    return "\n".join(lines)
