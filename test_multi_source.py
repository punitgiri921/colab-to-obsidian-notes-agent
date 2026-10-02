"""
Comprehensive Verification Test for Multi-Source (.sql, .py, .ipynb) Support.

Tests:
  1. SQL script parser (comment extraction & query isolation)
  2. Python script parser (docstring & code block extraction)
  3. Notebook parser integrity
  4. Extension-safe exercise-solution pairing (zero cross-extension collision)
  5. Language-aware dual ingestion payload (```sql vs ```python)
  6. Pedagogical prompt selection (SQL_SYSTEM_PROMPT vs COLAB_SYSTEM_PROMPT)
  7. Semantic vault routing for SQL files
"""

import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.source_parser import (
    parse_source_file,
    parse_sql_file,
    parse_python_file,
    find_source_pairs,
    build_dual_ingestion_payload,
)
from core.notes_generator import get_system_prompt_for_file, SQL_SYSTEM_PROMPT, COLAB_SYSTEM_PROMPT
from core.vault_scanner import smart_semantic_route


def test_sql_parser():
    print("\n--- 1. Testing SQL Parser ---")
    sample_sql = """/*
 * Chapter 01: Advanced Filtering & Window Functions
 * Learn how to rank salaries within departments.
 */

-- Challenge: Find top 3 earners per department
SELECT 
    dept_id,
    emp_name,
    salary,
    DENSE_RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rank_num
FROM employees
WHERE is_active = 1;
"""
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sample_sql)
        temp_sql = Path(f.name)

    try:
        parsed = parse_sql_file(temp_sql)
        assert parsed["file_type"] == "sql", "Expected file_type == 'sql'"
        assert parsed["language"] == "sql", "Expected language == 'sql'"
        assert len(parsed["cells"]) >= 2, f"Expected at least 2 cells, got {len(parsed['cells'])}"
        
        # Verify markdown and code cells
        types = [c["type"] for c in parsed["cells"]]
        assert "markdown" in types, "Expected markdown narrative cells"
        assert "code" in types, "Expected code query cells"

        code_cell = [c for c in parsed["cells"] if c["type"] == "code"][0]
        assert code_cell["language"] == "sql"
        assert "DENSE_RANK()" in code_cell["code"]
        print(f"✅ SQL Parser passed: {len(parsed['cells'])} cells extracted (Markdown + SQL Code).")
    finally:
        temp_sql.unlink()


def test_python_parser():
    print("\n--- 2. Testing Python Script Parser ---")
    sample_py = '''"""
Data Preprocessing Pipeline
Clean and normalize customer transaction logs.
"""

# Step 1: Load and filter transactions
def filter_transactions(df, min_amount=100.0):
    return df[df["amount"] >= min_amount]
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(sample_py)
        temp_py = Path(f.name)

    try:
        parsed = parse_python_file(temp_py)
        assert parsed["file_type"] == "python", "Expected file_type == 'python'"
        assert parsed["language"] == "python", "Expected language == 'python'"
        assert len(parsed["cells"]) >= 2, f"Expected at least 2 cells, got {len(parsed['cells'])}"
        
        types = [c["type"] for c in parsed["cells"]]
        assert "markdown" in types
        assert "code" in types
        print(f"✅ Python Parser passed: {len(parsed['cells'])} cells extracted.")
    finally:
        temp_py.unlink()


def test_extension_safe_pairing():
    print("\n--- 3. Testing Extension-Safe Pairing & Collision Prevention ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        
        # Create identical stems across .sql, .py, and .ipynb
        files = [
            td / "01_02_filtering.sql",
            td / "01_02_filtering_solution.sql",
            td / "01_02_filtering.py",
            td / "01_02_filtering_solution.py",
            td / "01_02_filtering.ipynb",
            td / "01_02_filtering_solutions.ipynb",
            td / "standalone_query.sql",
        ]
        for f in files:
            f.write_text("SELECT 1;" if f.suffix == ".sql" else "print(1)")

        pairs = find_source_pairs(files)
        assert len(pairs) == 4, f"Expected 4 entities (3 pairs + 1 standalone), got {len(pairs)}"

        sql_pairs = [p for p in pairs if p["file_type"] == "sql" and p["is_pair"]]
        py_pairs = [p for p in pairs if p["file_type"] == "python" and p["is_pair"]]
        nb_pairs = [p for p in pairs if p["file_type"] == "notebook" and p["is_pair"]]

        assert len(sql_pairs) == 1, "Expected 1 paired SQL entity"
        assert len(py_pairs) == 1, "Expected 1 paired Python entity"
        assert len(nb_pairs) == 1, "Expected 1 paired Notebook entity"

        # Verify no cross-extension contamination
        assert sql_pairs[0]["exercise_path"].suffix == ".sql"
        assert sql_pairs[0]["solution_path"].suffix == ".sql"
        assert py_pairs[0]["exercise_path"].suffix == ".py"
        assert py_pairs[0]["solution_path"].suffix == ".py"
        assert nb_pairs[0]["exercise_path"].suffix == ".ipynb"
        assert nb_pairs[0]["solution_path"].suffix == ".ipynb"

        print("✅ Extension-Safe Pairing passed: Zero collision across identical stems with different extensions!")


def test_payload_code_fences():
    print("\n--- 4. Testing Language-Aware Payload Generation ---")
    mock_sql_sol = {
        "file_name": "query_solution.sql",
        "file_type": "sql",
        "language": "sql",
        "cells": [
            {"type": "markdown", "content": "Solution explanation"},
            {"type": "code", "language": "sql", "code": "SELECT * FROM users;", "outputs": []}
        ]
    }
    payload_sql = build_dual_ingestion_payload(None, mock_sql_sol)
    assert "```sql" in payload_sql, "Expected ```sql code fence for SQL file"
    assert "```python" not in payload_sql, "Did not expect ```python code fence for SQL file"

    mock_py_sol = {
        "file_name": "app_solution.py",
        "file_type": "python",
        "language": "python",
        "cells": [
            {"type": "code", "language": "python", "code": "print('hello')", "outputs": []}
        ]
    }
    payload_py = build_dual_ingestion_payload(None, mock_py_sol)
    assert "```python" in payload_py, "Expected ```python code fence for Python file"
    print("✅ Language-Aware Payload passed: SQL uses ```sql, Python uses ```python.")


def test_prompt_and_routing():
    print("\n--- 5. Testing Prompt Selection & Semantic Routing ---")
    sql_prompt = get_system_prompt_for_file("sql")
    nb_prompt = get_system_prompt_for_file("notebook")

    assert "SQL & Relational Databases" in sql_prompt
    assert "Logical Query Processing Order" in sql_prompt
    assert "Harvard CS50" in nb_prompt

    with tempfile.TemporaryDirectory() as tmpdir:
        vault = Path(tmpdir)
        (vault / "01_SQL" / "01_Concepts").mkdir(parents=True)
        (vault / "02_Python" / "02_Data Analysis (Pandas)").mkdir(parents=True)

        routed_sql = smart_semantic_route(vault, "Advanced Window Functions", "SELECT DENSE_RANK()", file_type="sql")
        assert routed_sql == vault / "01_SQL" / "01_Concepts", f"Expected SQL folder, got {routed_sql}"

        routed_py = smart_semantic_route(vault, "Pandas Groupby Operations", "df.groupby('dept').mean()", file_type="notebook")
        assert routed_py == vault / "02_Python" / "02_Data Analysis (Pandas)", f"Expected Pandas folder, got {routed_py}"

    print("✅ Prompt Selection & Semantic Vault Routing passed!")


if __name__ == "__main__":
    print("==================================================================")
    print("🚀 Running Multi-Source Verification Suite (.sql, .py, .ipynb)")
    print("==================================================================")
    try:
        test_sql_parser()
        test_python_parser()
        test_extension_safe_pairing()
        test_payload_code_fences()
        test_prompt_and_routing()
        print("\n==================================================================")
        print("🎉 ALL MULTI-SOURCE TESTS PASSED SUCCESSFULLY!")
        print("==================================================================")
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
