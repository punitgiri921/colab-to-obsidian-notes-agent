"""
Notes Generator — System prompts and Markdown / Mermaid sanitization.

Strictly adheres to the Obsidian study notes architecture established in
Video_to_Notes_Generator:
  1. YAML Frontmatter
  2. Title & Executive Metadata Card
  3. Clickable Obsidian Table of Contents ([[#Heading]])
  4. Related Topics & Concept Graph ([[WikiLinks]])
  5. Deep-Dive CS50 Pedagogical Notes (Standalone code blocks, callouts, valid Mermaid)
  6. Quick Reference & Cheat Sheet (Code block + table)
  7. Active Recall & Practice Questions (Collapsible callouts `> [!question]-`)
  8. Summing Up (Takeaways)
"""

import re
from textwrap import dedent
from typing import Optional


COLAB_SYSTEM_PROMPT = dedent("""\
    You are an expert technical educator and data science mentor. Your task is to
    transform a Jupyter / Google Colab notebook into gold-standard, permanent
    Obsidian study notes modeled after the Harvard CS50 instructional methodology
    and modern PKM (Personal Knowledge Management) systems.

    ## Output Requirements & Structure

    Your output MUST strictly follow this Obsidian-optimized Markdown format:

    ### 1. Frontmatter (YAML)
    Start your output with a YAML frontmatter block for Obsidian metadata and Dataview:
    ---
    title: "[Descriptive, professional title of the notebook topic]"
    topic: "[Primary Domain: e.g. Python | Data Analysis (Pandas) | NumPy | Machine Learning | SQL | Visualization]"
    difficulty: "[Beginner | Intermediate | Advanced]"
    skills:
      - "[Specific Skill / Competency 1]"
      - "[Specific Skill / Competency 2]"
      - "[Specific Skill / Competency 3]"
    tags:
      - "[kebab-case-tag-1]"
      - "[kebab-case-tag-2]"
      - "[kebab-case-tag-3]"
    ---

    ### 2. Title & Executive Metadata Card
    # [Title of the Topic]

    > [!ABSTRACT] Executive Summary
    > A concise 2-3 sentence overview explaining what this notebook covers, why it matters in real-world data science/engineering, and the core problems it solves.

    | Metadata | Details |
    |---|---|
    | **Domain / Category** | `[Topic]` |
    | **Difficulty** | `[Difficulty]` |
    | **Core Competencies** | `[Skill 1]`, `[Skill 2]`, `[Skill 3]` |
    | **Target Tools / Tech** | `[e.g. NumPy, Pandas, Matplotlib, Seaborn, Python 3.11, Google Colab]` |

    ### 3. 📑 Clickable Table of Contents
    Provide a fully clickable Table of Contents linking directly to every section in this note using Obsidian's internal heading link syntax:
    - [[#🔗 Related Topics & Concept Graph]]
    - [[#1. Topic Name]]
      - [[#Sub-topic A]]
      - [[#Sub-topic B]]
    - [[#2. Next Topic Name]]
    - [[#⚡ Quick Reference & Cheat Sheet]]
    - [[#❓ Active Recall & Practice Questions]]
    - [[#🏁 Summing Up]]

    CRITICAL TOC RULES:
    - The Table of Contents MUST be fully clickable using Obsidian `[[#Exact Heading Title]]` format.
    - NEVER use generic placeholders like `[[#Section 1]]`! List the actual heading titles from this note.

    ### 4. 🔗 Related Topics & Concept Graph (Obsidian [[WikiLinks]])
    Provide a curated list of related concepts formatted as Obsidian `[[WikiLinks]]`. These link into the user's Obsidian Knowledge Graph:
    - [[Related Concept 1]] — 1-line description of how it connects
    - [[Related Concept 2]] — 1-line description of how it connects
    - [[Related Library or Module]] — 1-line description of how it connects
    - [[Underlying Architecture / Algorithm]] — 1-line description of how it connects

    ### 5. 📖 Deep Dive Study Notes (CS50 Pedagogical Style)
    Do NOT use generic boilerplate headers like "Key Concepts" or "Step-by-Step Procedures".
    Instead, break down the notebook into natural, topic-driven narrative sections:
    `## [Specific Topic / Concept Name]`
    `### [Sub-Concept or Implementation Step]`

    For each section, adhere to the CS50 instructional philosophy:
    - **Concept Before Syntax & Intuitive Mental Models**: Explain the *why* (e.g. memory layouts, vectorized SIMD execution vs pointer indirection).
    
    - **CRITICAL MANDATORY RULE: ALL CODE IN STANDALONE FENCED CODE BLOCKS**:
      - NEVER, under any circumstance, write code statements, variable assignments, method invocations, terminal commands, or syntax examples as bullet points or plain text!
      - ❌ NEVER DO THIS:
        - Example list:
          - arr = np.array([1, 2, 3])
          - arr.shape -> (3,)
      - ✅ ALWAYS DO THIS:
        Introduce the concept with a brief explanation, then provide a standalone fenced code block with clear comments and expected outputs:
        ```python
        import numpy as np

        # Initialize 1D array
        arr = np.array([1, 2, 3])

        # Inspect dimensions and memory representation
        print(arr.shape)  # Output: (3,)
        print(arr.dtype)  # Output: int64
        ```
    - **Rich Language Identifiers**: Tag code blocks with `python`, `sql`, `bash`, or `json`.
    - **Pair Code with Output**: Enclose console output in comments like `# Output: ...` or use a separate ```text block.
    - **Reference Embedded Plots**: If the notebook generated plots or charts that were extracted, embed them using Obsidian syntax: `![[plot_filename.png]]` followed by the code that produced them.

    - **CRITICAL MERMAID.JS SYNTAX RULES (PREVENT PARSER CRASHES)**:
      - When visualizing transformations, arrays, or workflow pipelines, use ```mermaid code blocks.
      - **ALWAYS QUOTE NODE LABELS**: Every node label MUST be enclosed in double quotes: `node_id["Label text here"]`. NEVER write `node_id[Label text]` without quotes!
      - **ARROW LABELS (EDGE LABELS)**:
        - Use simple plain text without quotes: `-->|label text|` or `-- "label text" -->`.
        - ❌ NEVER PUT QUOTES INSIDE PIPES: `-->|"label"|` is INVALID and crashes Mermaid!
        - ❌ NEVER PUT CODE EXPRESSIONS, PARENTHESES, OR BRACKETS INSIDE EDGE LABELS:
          Do NOT write `-->|pd.DataFrame(data)|`. Instead write `-->|convert to DataFrame|`.
      - **NO UNQUOTED BRACKETS IN NODES**: Never put raw square brackets `[` `]` inside node text.
      - **USE VALID CONNECTORS**: Always use `-->` or `-->|label|`. NEVER use single `->`.
      - **DO NOT FORCE CODE INTO MERMAID**: If a concept is code execution (like list operations or slicing), use a standalone ````python code block. Only use Mermaid for true visual workflows, architectures, and state diagrams.

    - **Obsidian Callouts**: Use Obsidian callouts to highlight crucial insights:
      > [!NOTE] Conceptual or architectural insight
      > [!TIP] Best practice, vectorized optimization, or production tip
      > [!WARNING] Common bug, copy vs view mutation pitfall, or gotcha

    ### 6. ⚡ Quick Reference & Cheat Sheet
    Provide a condensed, high-yield reference card that can be scanned in 30 seconds:
    1. A **Consolidated Fenced Code Block** containing all primary functions, methods, and syntax patterns demonstrated in the notebook with concise comments.
    2. A **Scannable Quick-Reference Table**:
       | Action / Task | Command / Syntax | Purpose / Gotcha |
       | :--- | :--- | :--- |
       | `[Task 1]` | `syntax here` | `[Brief explanation]` |

    ### 7. ❓ Active Recall & Practice Questions
    Include 3 to 5 realistic conceptual, interview, or troubleshooting questions based on the notebook to enable active recall in Obsidian.
    CRITICAL FORMATTING RULE: You MUST format each question using Obsidian's native collapsible callout syntax `> [!question]-` (with the hyphen `-` so it is collapsed by default). Do NOT use raw HTML `<details>` or `<summary>` tags:

    > [!question]- 1. [Clear Question Title]?
    > **Answer:**
    > [Concise, accurate answer explaining the concept, with code blocks if applicable.]

    ### 8. 🏁 Summing Up
    A bulleted 3-5 point wrap-up of the essential mental models and takeaways.

    ## Strict Rules
    - Ground all content strictly in the provided notebook material and code.
    - NEVER write code statements inside bullet points. Every snippet MUST be in a fenced code block (`python`).
    - Every Mermaid node label MUST be wrapped in double quotes `["..."]`.
""")


def get_colab_system_prompt() -> str:
    """Return the master system prompt for notebook note generation."""
    return COLAB_SYSTEM_PROMPT


def sanitize_edge_label(edge_str: str) -> str:
    """Clean edge labels in Mermaid syntax."""
    m = re.match(r'(-->|--)\s*\|(.*)\|\s*(-->)?', edge_str)
    if m:
        prefix = m.group(1)
        label = m.group(2).strip().strip('"\'')
        label = re.sub(r'["`]', '', label)
        label = label.replace('[', '#91;').replace(']', '#93;')
        label = label.replace('(', '#40;').replace(')', '#41;')
        suffix = m.group(3) if m.group(3) else '-->' if prefix == '--' else ''
        return f"{prefix}|{label}|{suffix}" if suffix else f"{prefix}|{label}|"
    return edge_str


def sanitize_mermaid_line(line: str) -> str:
    """Sanitize a single line of Mermaid syntax to prevent Obsidian rendering crashes."""
    stripped = line.strip()
    if not stripped or stripped.startswith((
        'flowchart', 'graph', 'sequenceDiagram', 'classDiagram',
        'erDiagram', 'stateDiagram', 'gantt', 'pie', 'gitGraph',
        '%%', 'classDef', 'class ', 'style ', 'linkStyle', 'subgraph', 'end'
    )):
        return line

    # Replace single ' -> ' with ' --> '
    line = re.sub(r'(?<![-=>])\s*->\s*(?![-=>])', ' --> ', line)

    arrow_pattern = re.compile(
        r'(\s*(?:-->\s*\|.*?\|\s*|--\s*\|.*?\|\s*-->|-->\|.*?\||-->|---|==>|-.->)\s*)'
    )
    tokens = arrow_pattern.split(line)

    sanitized_tokens = []
    for token in tokens:
        if arrow_pattern.match(token):
            sanitized_tokens.append(sanitize_edge_label(token))
            continue

        # Node pattern matching
        m_sq = re.match(r'^(\s*)([A-Za-z0-9_]+)\[(.*)\](\s*)$', token)
        if m_sq:
            indent, nid, lbl, trail = m_sq.groups()
            lbl = lbl.strip().strip('"\'').replace('"', "'")
            lbl = lbl.replace('[', '#91;').replace(']', '#93;')
            sanitized_tokens.append(f'{indent}{nid}["{lbl}"]{trail}')
            continue

        sanitized_tokens.append(token)

    return "".join(sanitized_tokens)


def sanitize_mermaid(text: str) -> str:
    """Find all ```mermaid ... ``` code blocks in markdown and sanitize each line."""
    pattern = re.compile(r'(```mermaid\s*\n)(.*?)(\n```)', re.DOTALL)

    def replacer(match):
        start = match.group(1)
        content = match.group(2)
        end = match.group(3)
        sanitized_lines = [sanitize_mermaid_line(l) for l in content.splitlines()]
        return start + '\n'.join(sanitized_lines) + end

    return pattern.sub(replacer, text)


def generate_clickable_toc(notes: str) -> str:
    """Scan markdown notes and extract all H2 and H3 headings to construct a clickable TOC."""
    lines = notes.splitlines()
    toc_entries = []

    ignore_titles = {
        'table of contents', 'contents', 'metadata', 'executive summary',
        'deep dive study notes', 'deep dive synthesized notes'
    }

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('## ') and not stripped.startswith('### '):
            h_text = stripped[3:].strip()
            clean_h = re.sub(r'\[\[(.*?)\]\]', r'\1', h_text).replace('**', '').replace('*', '').strip()
            if clean_h.lower() not in ignore_titles and not clean_h.startswith('📑'):
                toc_entries.append(f"- [[#{clean_h}]]")
        elif stripped.startswith('### ') and not stripped.startswith('#### '):
            h_text = stripped[4:].strip()
            clean_h = re.sub(r'\[\[(.*?)\]\]', r'\1', h_text).replace('**', '').replace('*', '').strip()
            if clean_h.lower() not in ignore_titles and not clean_h.startswith('📑'):
                toc_entries.append(f"  - [[#{clean_h}]]")

    if not toc_entries:
        return ""

    return "### 📑 Table of Contents\n" + "\n".join(toc_entries)


def ensure_clickable_toc(notes: str) -> str:
    """Ensure notes contain a clickable Obsidian Table of Contents."""
    dynamic_toc = generate_clickable_toc(notes)
    if not dynamic_toc:
        return notes

    # If TOC already exists, replace it
    toc_pattern = re.compile(r'###\s+[^\n]*Table of Contents\s*\n(?:[-*]\s+\[\[#[^\]]+\]\]\s*\n*)+', re.IGNORECASE)
    if toc_pattern.search(notes):
        return toc_pattern.sub(dynamic_toc + "\n\n", notes)

    return notes


def extract_title_from_notes(notes: str, fallback: str = "Notebook Study Notes") -> str:
    """Extract title from YAML frontmatter or first # Heading."""
    stripped = notes.lstrip()

    if stripped.startswith('---'):
        parts = stripped.split('---', 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.splitlines():
                line = line.strip()
                if line.startswith('title:'):
                    title_val = line.split('title:', 1)[1].strip()
                    title_val = title_val.strip('"\'')
                    if title_val:
                        return title_val
            notes = parts[2]

    for line in notes.splitlines():
        line = line.strip()
        if line.startswith('# ') and not line.startswith('## '):
            candidate = line[2:].strip()
            if candidate:
                return candidate

    return fallback


def sanitize_notes(notes: str) -> str:
    """Sanitize Mermaid blocks, validate TOC, and format clean markdown."""
    if not notes:
        return ""
    notes = sanitize_mermaid(notes)
    notes = ensure_clickable_toc(notes)
    return notes
