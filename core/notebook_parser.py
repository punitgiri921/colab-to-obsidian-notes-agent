"""
Backward-compatibility bridge for notebook_parser.
All core parsing, pairing, and payload logic is now unified in core.source_parser.
"""

from core.source_parser import (
    ExtractedImage,
    build_dual_ingestion_payload,
    clean_source_code,
    find_notebook_pairs,
    find_source_pairs,
    get_file_hash,
    parse_notebook,
    parse_python_file,
    parse_source_file,
    parse_sql_file,
    truncate_output_text,
)

__all__ = [
    "get_file_hash",
    "clean_source_code",
    "truncate_output_text",
    "ExtractedImage",
    "parse_notebook",
    "parse_sql_file",
    "parse_python_file",
    "parse_source_file",
    "find_notebook_pairs",
    "find_source_pairs",
    "build_dual_ingestion_payload",
]
