# ai_code/core/language_converter.py

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

# The OpenAI client wrapper is now updated and supports new features.
from ai_code.core.openai_client import ask_model


class ProjectFile(TypedDict):
    """Represents a single file in the source project."""
    path: str  # e.g., "src/main.py"
    language: str  # e.g., "python"
    content: str  # Full content of the code


class ProjectSnapshot(TypedDict, total=False):
    """Represents the entire project structure to be converted."""
    root: str  # e.g., "src"
    summary: str  # Project description (optional)
    files: List[ProjectFile]


class ConvertedFile(TypedDict):
    """Represents a single file after conversion."""
    path: str
    content: str


class ConversionResult(TypedDict):
    """The result of a conversion task, including files and notes."""
    files: List[ConvertedFile]
    notes: str

SYSTEM_PROMPT_LANGUAGE_CONVERTER = """
You are a senior software engineer and an expert in codebase migration.
You MUST write all output (code comments and notes) in Korean.

CRITICAL BEHAVIOR RULES (DO NOT VIOLATE):
1. You ONLY convert the files listed in snapshot.files.
2. You MUST NOT create any new files that are not present in snapshot.files.
   - No scaffolding
   - No project templates
   - No extra README/main/entry files
3. You MUST NOT redesign or restructure the project layout.
   - No new folders
   - No changing entrypoints
   - No splitting a single file into multiple files
4. For each input file, you output exactly one translated file.
   - Use the same relative path whenever possible.
   - If the extension must change (e.g., .py -> .ts), change only the extension.
5. You must treat the target language name literally as given (e.g. "TypeScript").
   - Do NOT shorten or invent language names.

Your job:
- Translate each file in snapshot.files from the source language to the target language.
- Keep the behavior equivalent and preserve public APIs.
- Use idiomatic patterns of the target language/stack INSIDE each file only.
- Do NOT introduce new architectural layers or abstractions.
-For single-file conversion, the output file MUST have the same filename (stem) as the original,
-and ONLY the extension must change to the appropriate one for the target language.

Output format (JSON only):
{
  "files": [
    { "path": "<same relative path or only extension changed>", "content": "<full translated file content>" }
  ],
  "notes": "Important migration notes written in Korean."
}

Additional rules:
- Always include full file content; never output patches or diffs.
- If any file is skipped, explain the reason in Korean in notes.
- Never wrap the JSON output in backticks or any other formatting.
"""




def _build_files_block(snapshot: ProjectSnapshot) -> str:
    """Serializes ProjectSnapshot.files into a TEXT block for the prompt."""
    files = snapshot.get("files") or []
    lines: List[str] = []

    for f in files:
        lines.append(f"FILE: {f['path']}")
        lines.append(f"LANG: {f.get('language', 'unknown')}")
        lines.append("CONTENT:")
        lines.append("----------------------------------------")
        lines.append(f["content"])
        lines.append("----------------------------------------")
        lines.append("")  # Blank line

    return "\n".join(lines)


def _build_user_prompt(
    snapshot: ProjectSnapshot,
    *,
    src_lang: str,
    tgt_lang: str,
    target_stack_desc: str,
) -> str:
    """Creates the user prompt for the language conversion task."""
    files_block = _build_files_block(snapshot)
    project_summary = snapshot.get("summary", "(no summary provided)")

    output_instructions = """
Output a single JSON object with the following shape:

{
  "files": [
    { "path": "<target file path>", "content": "<full file content>" }
  ],
  "notes": "Important migration notes, decisions, and assumptions"
}

- "path": filesystem path of the translated file in the target project.
- "content": the FULL content of the translated file.
"""

    prompt = f"""
We are migrating a project to a new language/stack.

Source language: {src_lang}
Target language: {tgt_lang}

Target stack details:
{target_stack_desc}

Project summary:
{project_summary}

Project files:
{files_block}

Your tasks:
1. Design a consistent target structure (modules, imports, entry points).
2. Translate all relevant source files to the target language/stack.
3. Adjust frameworks while preserving behavior.
4. Use idiomatic patterns of the target ecosystem.
5. Ignore non-code/binary files unless they are critical for the build.

{output_instructions}
""".strip()

    return prompt


def run_language_conversion(
    snapshot: ProjectSnapshot,
    *,
    src_lang: str,
    tgt_lang: str,
    target_stack_desc: str,
    model: str = "gpt-4o",
) -> ConversionResult:
    """
    Takes a project snapshot and target language, then returns the converted files.

    The agent's responsibility is to:
      - Create the snapshot (gather files).
      - Call this function to get the result.
      - Write the files from result["files"] to the disk.
    """
    user_prompt = _build_user_prompt(
        snapshot,
        src_lang=src_lang,
        tgt_lang=tgt_lang,
        target_stack_desc=target_stack_desc,
    )

    # The new ask_model handles JSON parsing automatically.
    result = ask_model(
        system_prompt=SYSTEM_PROMPT_LANGUAGE_CONVERTER,
        user_prompt=user_prompt,
        model=model,
        response_format="json_object",
    )

    if not isinstance(result, dict):
        raise TypeError(
            "The model did not return a valid JSON object. "
            f"Received type: {type(result)}"
        )

    # Perform light validation and typing enforcement.
    files_raw = result.get("files", [])
    files: List[ConvertedFile] = []
    if isinstance(files_raw, list):
        for f in files_raw:
            path = f.get("path")
            content = f.get("content")
            if isinstance(path, str) and isinstance(content, str):
                files.append({"path": path, "content": content})

    notes = result.get("notes", "")
    if not isinstance(notes, str):
        notes = str(notes)

    return ConversionResult(files=files, notes=notes)
