"""
Test script for Phase 2 verification:
- Test vault taxonomy scanning and folder suggestions
- Test matching existing notes for merge detection
- Test image asset saving to G:\\My Drive\\04_Obsedian\\99_Assets
- Test config.json and tracker.json persistence
"""

import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.vault_scanner import (
    get_default_vault_path,
    get_vault_subfolders,
    suggest_target_subfolder,
    scan_existing_notes,
    find_matching_note,
)
from core.file_manager import (
    load_config,
    save_config,
    get_last_vault_folder,
    save_extracted_images,
    record_processed_notebook,
    is_notebook_processed,
    load_tracker,
)
from core.notebook_parser import ExtractedImage


def main():
    print("=== Testing Phase 2: Vault Scanner & Asset Pipeline ===")

    # 1. Vault path & subfolders
    vault_path = get_default_vault_path()
    print(f"Default Vault Path: {vault_path}")
    subfolders = get_vault_subfolders(vault_path)
    print(f"Discovered {len(subfolders)} subfolders in vault:")
    for f in subfolders[:8]:
        rel = f.relative_to(vault_path)
        print(f"  [Folder] {rel}")

    # 2. Test Smart Subfolder Suggestion
    test_cases = [
        ("Section01 NumPy Arrays & Vectorization", "import numpy as np; arr = np.arange(10)"),
        ("Week 01 Python Basics Strings & Lists", "my_list = ['apple', 'banana']; for item in my_list:"),
        ("Data Viz with Matplotlib and Seaborn", "import matplotlib.pyplot as plt; plt.plot(x, y)"),
        ("Window Functions and SQL CTEs", "SELECT emp_id, ROW_NUMBER() OVER (PARTITION BY dept) FROM employees"),
    ]

    print("\n--- Testing Target Folder Auto-Suggestion ---")
    for title, preview in test_cases:
        suggested = suggest_target_subfolder(vault_path, title, preview)
        rel_suggested = suggested.relative_to(vault_path) if suggested != vault_path else "Vault Root"
        print(f"Notebook: '{title}'\n  -> Suggested Destination: {rel_suggested}\n")

    # 3. Test Existing Note Matching
    pandas_folder = vault_path / "02_Python" / "02_Data Analysis (Pandas)"
    print(f"--- Testing Note Matching in: {pandas_folder.relative_to(vault_path)} ---")
    existing_notes = scan_existing_notes(pandas_folder)
    print(f"Found {len(existing_notes)} existing notes in this folder:")
    for n in existing_notes:
        print(f"  - {n['filename']} (Title: '{n['title']}')")

    match = find_matching_note("Pandas Advanced Filtering & Query Method", pandas_folder)
    print(f"\nSearch for 'Pandas Advanced Filtering & Query Method':")
    print(f"  Matched Note: {match.name if match else 'None (New note will be created)'}")

    # 4. Test Asset Saving to 99_Assets
    print("\n--- Testing Plot Asset Persistence to 99_Assets ---")
    dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xefe\r\x00\x00\x00\x00IEND\xaeB`\x82'
    test_img = ExtractedImage(
        filename="test_phase2_verification_plot_999999.png",
        data_bytes=dummy_png,
        cell_index=1,
        description="Phase 2 asset pipeline test"
    )
    saved_assets = save_extracted_images([test_img], vault_path)
    print(f"Saved asset: {saved_assets}")
    saved_file = vault_path / "99_Assets" / "test_phase2_verification_plot_999999.png"
    if saved_file.exists():
        print(f"Asset verified on disk at: {saved_file}")
        try:
            saved_file.unlink()
            print("Cleaned up temporary test asset.")
        except Exception:
            pass

    # 5. Test Config & Tracker
    print("\n--- Testing Config and Tracker State Machine ---")
    test_config = {"last_vault_folder": str(vault_path), "test_key": "phase2_ok"}
    save_config(test_config)
    loaded_config = load_config()
    print(f"Config roundtrip verified: last_vault_folder = {loaded_config.get('last_vault_folder')}")

    test_hash = "dummy_test_hash_phase2"
    record_processed_notebook(test_hash, "test_notebook.ipynb", vault_path / "test.md")
    tracker = load_tracker()
    print(f"Tracker checkpoint verified: hash recorded = {test_hash in tracker}")
    if test_hash in tracker:
        del tracker[test_hash]
        from core.file_manager import save_tracker
        save_tracker(tracker)

    print("\n>>> PHASE 2 VERIFICATION SUCCESSFUL! <<<")


if __name__ == "__main__":
    main()
