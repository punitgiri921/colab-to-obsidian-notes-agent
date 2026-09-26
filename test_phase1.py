"""
Test script for Phase 1 verification:
- Test notebook parser on a notebook with plots
- Test exercise-solution pairer
- Test base64 image extraction
- Verify Azure OpenAI client connectivity
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.notebook_parser import parse_notebook, find_notebook_pairs, build_dual_ingestion_payload
from core.ai_client import AzureAIClient

def main():
    print("=== Testing Phase 1: Notebook Parser & Azure Client ===")
    
    # 1. Search for notebooks in the directory tree
    search_dir = Path("D:/01_Ex_Files_Intermediate_SQL_for_Data_Scientists")
    notebooks = list(search_dir.glob("**/*.ipynb"))
    
    print(f"Discovered {len(notebooks)} notebooks in directory tree.")
    
    # 2. Test pair detection
    pairs = find_notebook_pairs(notebooks)
    paired_count = sum(1 for p in pairs if p["is_pair"])
    print(f"\nGrouped {len(pairs)} notebook entities ({paired_count} detected pairs):")
    for pair in pairs[:6]:
        status = "PAIRED (Exercise + Solution)" if pair["is_pair"] else "STANDALONE"
        print(f" - [{status}] {pair['display_name']}")
        if pair["is_pair"]:
            print(f"     Exercise: {pair['exercise_path'].name}")
            print(f"     Solution: {pair['solution_path'].name}")

    # 3. Test parsing on a notebook containing plots
    test_nb = None
    for nb in notebooks:
        if "matplotlib_charts_demos" in nb.name:
            test_nb = nb
            break
    if not test_nb:
        test_nb = notebooks[0]

    print(f"\nParsing notebook with plots: {test_nb.name}")
    parsed = parse_notebook(test_nb)
    print(f"Title: {parsed['suggested_title']}")
    print(f"Cell count: {parsed['cell_count']}")
    print(f"Extracted image count: {parsed['image_count']}")
    for img in parsed['images'][:3]:
        print(f"  - Extracted Plot: {img.filename} ({len(img.data_bytes)} bytes)")
    
    # 4. Test Azure OpenAI Client Connectivity with adequate reasoning token budget
    print("\nVerifying Azure OpenAI Client connectivity...")
    try:
        client = AzureAIClient()
        print(f"Connected to deployment: {client.deployment} at {client.endpoint}")
        test_response = client.generate_chat_completion(
            messages=[
                {"role": "system", "content": "You are a concise data science educator."},
                {"role": "user", "content": "Summarize what NumPy vectorization is in 2 sentences."}
            ],
            max_tokens=2048
        )
        print(f"\nAzure OpenAI Response:\n{test_response}\n")
        print(">>> PHASE 1 VERIFICATION SUCCESSFUL! <<<")
    except Exception as e:
        print(f"Azure OpenAI test warning/error: {e}")

if __name__ == "__main__":
    main()
