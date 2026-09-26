"""
Intelligent In-Place Sectional Merger for Obsidian Notes.

Uses Azure OpenAI to analyze existing notes and newly ingested notebook content,
seamlessly weaving new explanations, code examples, edge cases, and flashcards
into existing sections without destroying custom user edits or [[WikiLinks]].
"""

from textwrap import dedent
from typing import Callable, Optional

from core.ai_client import AzureAIClient
from core.notes_generator import sanitize_notes


MERGE_SYSTEM_PROMPT = dedent("""\
    You are an expert technical curriculum designer and knowledge management specialist.
    Your task is to perform an INTELLIGENT IN-PLACE SECTIONAL MERGE of new notebook knowledge
    into an EXISTING Obsidian study note.

    ## Critical Merging Philosophy & Non-Destructive Invariant:
    1. **NON-DESTRUCTIVE PRESERVATION**:
       - NEVER delete, downgrade, or overwrite valuable insights, mental models, explanations, or code examples that already exist in the target note.
       - NEVER delete or break existing Obsidian `[[WikiLinks]]`! Retain all existing links and add new ones where relevant.
       
    2. **AVOID REDUNDANCY**:
       - Do NOT repeat concepts, basic syntax, or code patterns that the existing note already explains clearly.
       - Focus strictly on adding **INCREMENTAL VALUE**: deeper architectural nuances, alternative syntax methods, real-world edge cases, and additional exercises.

    3. **SEAMLESS WEAVING INTO SECTIONS**:
       - **Frontmatter**: Preserve existing tags/metadata and append new relevant tags or skills.
       - **Executive Summary & Metadata Card**: Update to encompass the expanded breadth of the topic.
       - **Deep-Dive Narrative Sections**: Integrate new concepts into existing headings or introduce new logical sub-headings (`## [Topic]`, `### [Sub-topic]`).
       - **Standalone Fenced Code Blocks**: ALL new code snippets MUST be standalone fenced code blocks (`python`) with outputs commented `# Output: ...`. NEVER use bullet points for code!
       - **Quick Reference & Cheat Sheet**: Append new methods/patterns to the reference table and consolidated code block.
       - **Active Recall Questions**: Add 2-3 new non-redundant collapsible callouts (`> [!question]-`) testing the newly introduced concepts.
       - **Summing Up**: Refine takeaways to cover both original foundations and new extensions.

    4. **MERMAID.JS RULES**:
       - Quote all node labels: `node_id["Label"]`. No code in edge labels.

    Output the entire, unified, merged note in complete, gold-standard Obsidian Markdown.
""")


def perform_intelligent_merge(
    existing_note_content: str,
    new_notebook_payload: str,
    ai_client: AzureAIClient,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Perform an AI-powered sectional merge of new notebook concepts into an existing note.
    """
    if progress_callback:
        progress_callback("Analyzing existing note and weaving in new notebook concepts...")

    user_prompt = dedent(f"""\
        ## EXISTING OBSIDIAN NOTE:
        ```markdown
        {existing_note_content}
        ```

        ## NEW NOTEBOOK KNOWLEDGE TO INTEGRATE:
        {new_notebook_payload}

        Please synthesize and return the complete merged Obsidian note according to the system instructions.
    """)

    messages = [
        {"role": "system", "content": MERGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    merged_output = ai_client.generate_chat_completion(
        messages=messages,
        progress_callback=progress_callback,
    )

    # Sanitize Mermaid syntax and refresh clickable TOC
    clean_merged = sanitize_notes(merged_output)
    return clean_merged
