"""
Notebook AST parser, cleaner, image extractor, and exercise-solution pairer.

Extracts structured conceptual knowledge from Jupyter / Google Colab (.ipynb) files:
  - Markdown instructional cells
  - Cleaned executable Python code (purging !pip, ephemeral commands)
  - Meaningful textual output (truncating repetitive arrays/logs)
  - Embedded Base64 plots and figures for Obsidian 99_Assets extraction
  - Automatic pairing of exercise and solution notebooks
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
        # Comment out shell commands or notebook magics
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


def parse_notebook(notebook_path: Path | str) -> Dict[str, Any]:
    """
    Parse a Jupyter / Google Colab notebook (.ipynb) into clean structured content:
    - title / inferred topic
    - structured cells (markdown narrative, cleaned code, concise outputs)
    - extracted Base64 images ready to be written to Obsidian 99_Assets
    """
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
            
            # Inspect cell outputs
            for out in cell.get("outputs", []):
                out_type = out.get("output_type", "")
                
                # Check for images (Matplotlib / Seaborn plots)
                data = out.get("data", {})
                if "image/png" in data:
                    png_b64 = data["image/png"]
                    try:
                        # Clean whitespace from base64 if present
                        png_bytes = base64.b64decode(re.sub(r'\s+', '', png_b64))
                        # Use 6-char hash of image content for unique asset naming matching vault standard
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
                "cell_index": idx,
                "code": cleaned_code,
                "outputs": outputs_summary,
            })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_hash": file_hash,
        "suggested_title": title_candidate,
        "cells": structured_cells,
        "images": extracted_images,
        "cell_count": len(structured_cells),
        "image_count": len(extracted_images),
    }


def find_notebook_pairs(file_paths: List[Path]) -> List[Dict[str, Any]]:
    """
    Analyze a list of notebook paths and group problem/exercise notebooks
    with their corresponding solutions notebook.

    Patterns detected:
      - `foo_solutions.ipynb` paired with `foo.ipynb`
      - `foo_solution.ipynb` paired with `foo.ipynb`
      - `foo_solved.ipynb` paired with `foo.ipynb`
      - `foo - Solution.ipynb` paired with `foo.ipynb`
    """
    # Normalize path mapping
    stem_map: Dict[str, Path] = {}
    solution_suffixes = ["_solutions", "_solution", "_solved", " - solutions", " - solution", " - solved"]

    for p in file_paths:
        stem_map[p.stem.lower()] = p

    processed_stems = set()
    pairs: List[Dict[str, Any]] = []

    # First pass: find explicit solution files
    for p in file_paths:
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

        if base_stem and base_stem in stem_map:
            # Found pair!
            exercise_path = stem_map[base_stem]
            solution_path = p
            processed_stems.add(stem_lower)
            processed_stems.add(base_stem)
            
            clean_display_name = exercise_path.stem.replace("_", " ").replace("-", " ").title()
            pairs.append({
                "display_name": clean_display_name,
                "is_pair": True,
                "exercise_path": exercise_path,
                "solution_path": solution_path,
                "primary_path": solution_path,  # Use solution as primary conceptual source
            })

    # Second pass: standalone notebooks
    for p in file_paths:
        stem_lower = p.stem.lower()
        if stem_lower not in processed_stems:
            processed_stems.add(stem_lower)
            clean_display_name = p.stem.replace("_", " ").replace("-", " ").title()
            pairs.append({
                "display_name": clean_display_name,
                "is_pair": False,
                "exercise_path": p if not any(stem_lower.endswith(s) for s in solution_suffixes) else None,
                "solution_path": p if any(stem_lower.endswith(s) for s in solution_suffixes) else None,
                "primary_path": p,
            })

    return pairs


def build_dual_ingestion_payload(exercise_data: Optional[Dict[str, Any]], solution_data: Dict[str, Any]) -> str:
    """
    Construct a coherent, condensed narrative combining problem statements/prompts
    from the exercise notebook with full working implementations from the solution notebook.
    """
    lines: List[str] = []
    lines.append(f"# SOURCE NOTEBOOK: {solution_data['file_name']}")
    if exercise_data:
        lines.append(f"# PAIRED EXERCISE: {exercise_data['file_name']}")
    lines.append("")

    # Extract all markdown prompt descriptions from exercise if present
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

    # Now step through the complete solution
    lines.append("## COMPLETE WORKTHROUGH & SOLUTION IMPLEMENTATION:")
    for cell in solution_data.get("cells", []):
        if cell["type"] == "markdown":
            lines.append(f"\n{cell['content']}\n")
        elif cell["type"] == "code":
            lines.append("```python")
            lines.append(cell["code"])
            lines.append("```")
            if cell.get("outputs"):
                lines.append("Console / Cell Output:")
                for out in cell["outputs"]:
                    lines.append(f"  {out}")
            lines.append("")

    return "\n".join(lines)
