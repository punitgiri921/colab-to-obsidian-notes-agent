"""
File Manager for saving notes, image assets, and persisting configuration.

Handles:
  - Saving extracted Matplotlib/Seaborn plots to 99_Assets/
  - Generating and merging Obsidian YAML frontmatter
  - Writing/updating markdown files safely in the target vault folder
  - Persisting GUI preferences (config.json)
  - Tracking processed notebook hashes (tracker.json)
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.notebook_parser import ExtractedImage


# Config file path
CONFIG_FILE = Path(__file__).parent.parent / "config.json"
# State tracking file
TRACKER_FILE = Path(__file__).parent.parent / "tracker.json"


def load_config() -> Dict[str, Any]:
    """Load saved preferences from config.json."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save preferences to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def get_last_vault_folder() -> str:
    """Get the last chosen vault folder, or default to G:\\My Drive\\04_Obsedian."""
    cfg = load_config()
    default_vault = r"G:\My Drive\04_Obsedian"
    if "last_vault_folder" in cfg and Path(cfg["last_vault_folder"]).exists():
        return cfg["last_vault_folder"]
    if Path(default_vault).exists():
        return default_vault
    return str(Path.cwd())


def set_last_vault_folder(folder: str) -> None:
    """Save the chosen vault folder to config."""
    cfg = load_config()
    cfg["last_vault_folder"] = folder
    save_config(cfg)


def get_last_notebook_folder() -> str:
    """Get the last chosen notebook folder."""
    cfg = load_config()
    default_nb = r"D:\01_Ex_Files_Intermediate_SQL_for_Data_Scientists"
    if "last_notebook_folder" in cfg and Path(cfg["last_notebook_folder"]).exists():
        return cfg["last_notebook_folder"]
    if Path(default_nb).exists():
        return default_nb
    return str(Path.cwd())


def set_last_notebook_folder(folder: str) -> None:
    """Save the chosen notebook folder to config."""
    cfg = load_config()
    cfg["last_notebook_folder"] = folder
    save_config(cfg)


# --- Checkpoint State Tracker ---

def load_tracker() -> Dict[str, Any]:
    """Load tracker.json checkpoint data."""
    if TRACKER_FILE.exists():
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_tracker(tracker_data: Dict[str, Any]) -> None:
    """Save tracker.json checkpoint data."""
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker_data, f, indent=2)
    except Exception:
        pass


def is_notebook_processed(notebook_hash: str) -> bool:
    """Check if notebook has already been processed without changes."""
    tracker = load_tracker()
    return notebook_hash in tracker


def record_processed_notebook(notebook_hash: str, notebook_name: str, target_note_path: Path) -> None:
    """Record notebook hash in tracker.json with metadata."""
    tracker = load_tracker()
    tracker[notebook_hash] = {
        "notebook_name": notebook_name,
        "note_path": str(target_note_path.resolve()),
        "processed_at": datetime.now().isoformat(),
    }
    save_tracker(tracker)


# --- Asset Storage & Frontmatter ---

def save_extracted_images(images: List[ExtractedImage], vault_path: Path) -> List[str]:
    """
    Save extracted notebook plot images directly into the Obsidian vault's 99_Assets folder.
    Returns list of saved image filenames.
    """
    if not images:
        return []

    assets_folder = vault_path / "99_Assets"
    assets_folder.mkdir(parents=True, exist_ok=True)

    saved_names: List[str] = []
    for img in images:
        target_file = assets_folder / img.filename
        try:
            target_file.write_bytes(img.data_bytes)
            saved_names.append(img.filename)
        except Exception as e:
            print(f"Warning: Failed to save image asset {img.filename}: {e}")

    return saved_names


def generate_frontmatter(
    title: str = "",
    topic: str = "Python | Data Analysis",
    difficulty: str = "Intermediate",
    skills: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    source_file: str = "",
    extra_yaml: str = "",
) -> str:
    """Generate standard Obsidian YAML frontmatter block."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    system_lines = [
        f'title: "{title}"',
        'source: "Colab Notebook"',
        f'source_file: "{source_file}"',
        f'topic: "{topic}"',
        f'difficulty: "{difficulty}"',
        f'created: "{today}"',
    ]

    skills_lines = []
    if skills:
        skills_lines.append("skills:")
        for s in skills:
            skills_lines.append(f'  - "{s}"')

    tags_lines = []
    if tags:
        tags_lines.append("tags:")
        for t in tags:
            clean_tag = re.sub(r'[^a-zA-Z0-9_-]', '-', t.lower().strip())
            tags_lines.append(f'  - "{clean_tag}"')
    else:
        tags_lines.extend(["tags:", '  - "python"', '  - "colab-notebook"', '  - "study-notes"'])

    if extra_yaml.strip():
        cleaned_extra = extra_yaml.strip()
        if cleaned_extra.startswith("---"):
            cleaned_extra = cleaned_extra[3:].lstrip()
        if cleaned_extra.endswith("---"):
            cleaned_extra = cleaned_extra[:-3].rstrip()
        return f"---\n{cleaned_extra}\n---\n\n"

    all_blocks = system_lines + skills_lines + tags_lines
    return f"---\n{chr(10).join(all_blocks)}\n---\n\n"


def merge_content_with_frontmatter(
    notes: str,
    source_file: str = "",
    title: str = "",
) -> str:
    """
    Ensure the note has a single, valid YAML frontmatter block.
    Extracts any AI-generated frontmatter and unifies with system metadata.
    """
    stripped = notes.lstrip()
    if not stripped:
        raise ValueError("Cannot format empty note content.")

    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            existing_yaml = parts[1].strip()
            rest = parts[2].lstrip()
            
            # Ensure source and source_file are present in YAML
            if "source_file:" not in existing_yaml:
                existing_yaml += f'\nsource: "Colab Notebook"\nsource_file: "{source_file}"'
            if "created:" not in existing_yaml:
                today = datetime.now().strftime("%Y-%m-%d")
                existing_yaml += f'\ncreated: "{today}"'
                
            return f"---\n{existing_yaml}\n---\n\n{rest}"

    # Prepend default frontmatter if not present
    return generate_frontmatter(title=title, source_file=source_file) + notes


def make_safe_filename(title: str) -> str:
    """Convert title to safe Windows filename."""
    safe = re.sub(r'[\\/*?:"<>|]', "", title)
    safe = re.sub(r'\s+', " ", safe).strip()
    return safe[:120] if safe else "Untitled Note"


def save_note(
    folder: Path,
    filename: str,
    notes_content: str,
    source_file: str = "",
    is_inplace_update: bool = False,
    existing_file_path: Optional[Path] = None,
) -> Path:
    """
    Save or in-place update a note in the target vault folder.
    """
    if not notes_content or not notes_content.strip():
        raise ValueError("Cannot save empty note content.")

    # Sanitize notes content
    from core.notes_generator import sanitize_notes
    notes_content = sanitize_notes(notes_content)

    clean_content = merge_content_with_frontmatter(
        notes=notes_content,
        source_file=source_file,
        title=filename,
    )

    if is_inplace_update and existing_file_path and existing_file_path.is_file():
        # Update existing note in place
        existing_file_path.write_text(clean_content, encoding="utf-8")
        return existing_file_path

    # New note creation
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = make_safe_filename(filename)
    target_path = folder / f"{safe_name}.md"

    # Avoid unintended overwrites
    if target_path.exists():
        counter = 1
        while target_path.exists():
            target_path = folder / f"{safe_name} ({counter}).md"
            counter += 1

    target_path.write_text(clean_content, encoding="utf-8")
    return target_path
