# ai_code/core/refactor_engine.py

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, List

from ai_code.core.openai_client import ask_model

RefactorKind = Literal[
    "style",
    "bugfix",
    "performance",
    "readability",
    "cleanup",
    "custom",
]


@dataclass
class Selection:
    """
    Represents a selection of a file (a line range) for refactoring.
    Line numbers are 1-based, inclusive, to match editor lines.
    """
    file_path: Path  # Path relative to the repository root
    start_line: int  # Inclusive, 1-based
    end_line: int    # Inclusive, 1-based
    kind: RefactorKind = "custom"
    user_instruction: str = ""  # Specific instruction for this selection (optional)


# -------------------- Common File I/O Utils --------------------

def _read_file_lines(path: Path) -> List[str]:
    """Reads a file and splits it into lines."""
    return path.read_text(encoding="utf-8").splitlines()


def _write_file_lines(path: Path, lines: List[str]) -> None:
    """Writes a list of lines to a file, ensuring a trailing newline."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# -------------------- Text Processing Utils --------------------

def _strip_code_fences(text: str) -> str:
    """Removes Markdown code fences (```) from a string."""
    content = text.strip()
    if content.startswith("```") and content.endswith("```"):
        lines = content.splitlines()
        if len(lines) > 1:
            # Return content between the first and last lines
            return "\n".join(lines[1:-1]).strip()
    return content


def _postprocess_snippet(original: str, new: str) -> str:
    """
    If the LLM returns the original code plus the refactored code,
    this function attempts to extract only the changed part.
    """
    new = new.strip()
    original_stripped = original.strip()

    if new == original_stripped:
        return new

    if original_stripped in new:
        # Take the part that comes after the last occurrence of the original code
        parts = new.split(original_stripped)
        candidate = parts[-1].strip()
        if candidate:
            return candidate

    return new

# -------------------- Partial Refactoring: Snippet-based --------------------

def _call_model_for_snippet(
    snippet: str,
    kind: RefactorKind,
    global_instruction: str,
    user_instruction: str,
    file_path: Path | None = None,
) -> str:
    """
    Sends a selected code snippet to the LLM for refactoring.
    """
    location = f"File: {file_path}" if file_path is not None else "File: <snippet>"

    system_prompt = (
        "You are a senior software engineer specializing in code refactoring.\n"
        "Your task is to refactor the code snippet provided by the user."
    )
    
    user_prompt = (
        "Refactor the following code snippet.\n\n"
        f"{location}\n"
        f"Refactor kind: {kind}\n"
        f"Global instruction: {global_instruction or 'N/A'}\n"
        f"User note: {user_instruction or 'N/A'}\n\n"
        "Requirements:\n"
        "- Keep the external behavior of this snippet the same unless 'bugfix' explicitly applies.\n"
        "- Improve style/readability/cleanliness according to the refactor kind.\n"
        "- Do NOT add unrelated new functions or classes.\n"
        "- Return ONLY the rewritten code snippet.\n"
        "- Do NOT include explanations, comments about the change, or markdown fences.\n\n"
        "Original snippet:\n"
        "----- SNIPPET START -----\n"
        f"{snippet}\n"
        "----- SNIPPET END -----\n\n"
        "Now return ONLY the refactored snippet:"
    )

    raw = ask_model(system_prompt=system_prompt, user_prompt=user_prompt, model="gpt-4o-mini")
    cleaned = _strip_code_fences(raw)
    return _postprocess_snippet(snippet, cleaned)


def _merge_snippet_back(
    all_lines: List[str],
    start_line: int,
    end_line: int,
    new_snippet: str,
) -> List[str]:
    """Merges the refactored snippet back into the list of full file lines."""
    new_lines = new_snippet.splitlines()
    before = all_lines[: start_line - 1]
    after = all_lines[end_line:]
    return before + new_lines + after


def partial_refactor(
    repo_root: Path,
    selections: List[Selection],
    global_instruction: str = "",
    dry_run: bool = True,
) -> dict:
    """
    Performs refactoring on a list of selected code ranges.
    """
    results: List[dict] = []

    for sel in selections:
        abs_path = (repo_root / sel.file_path).resolve()

        if not abs_path.exists():
            results.append({
                "file_path": str(sel.file_path),
                "error": f"File not found: {abs_path}",
                "applied": False,
            })
            continue

        all_lines = _read_file_lines(abs_path)
        original_snippet = "\n".join(all_lines[sel.start_line - 1: sel.end_line])

        try:
            new_snippet = _call_model_for_snippet(
                snippet=original_snippet,
                kind=sel.kind,
                global_instruction=global_instruction,
                user_instruction=sel.user_instruction,
                file_path=sel.file_path,
            )
        except Exception as e:
            results.append({
                "file_path": str(sel.file_path),
                "error": f"Model error: {e}",
                "applied": False,
            })
            continue
        
        # Merge the snippet back into the full code
        new_all_lines = _merge_snippet_back(
            all_lines,
            start_line=sel.start_line,
            end_line=sel.end_line,
            new_snippet=new_snippet,
        )

        if not dry_run:
            _write_file_lines(abs_path, new_all_lines)

        results.append({
            "file_path": str(sel.file_path),
            "start_line": sel.start_line,
            "end_line": sel.end_line,
            "original_snippet": original_snippet,
            "refactored_snippet": new_snippet,
            "applied": not dry_run,
            "error": None,
        })

    return {"results": results}


# ============================================================
# Full File Refactoring Functions
# - refactor_dead_code
# - refactor_simplify
# ============================================================

def _call_model_for_full_refactor(system_prompt: str, user_prompt: str) -> str:
    """Wrapper for full-file refactoring model calls."""
    # The new ask_model takes separate system and user prompts
    return ask_model(system_prompt=system_prompt, user_prompt=user_prompt, model="gpt-4o-mini")

def _build_dead_code_prompt(file_path: Path, code: str) -> str:
    """Builds the user prompt for the dead-code removal task."""
    return (
        f"Your task is to remove dead code from the following file:\n"
        f"- Unused imports\n"
        f"- Unused variables\n"
        f"- Unused functions/classes (if you are confident they are not used in this file).\n\n"
        f"Keep the external behavior and public API of this file the same.\n"
        f"Do NOT change business logic. Do NOT introduce new dependencies.\n\n"
        f"File path: {file_path}\n\n"
        f"----- CODE START -----\n"
        f"{code}\n"
        f"----- CODE END -----\n\n"
        f"Return ONLY the full updated code for this file."
    )

def _build_simplify_prompt(file_path: Path, code: str) -> str:
    """Builds the user prompt for the code simplification task."""
    return (
        f"Your task is to simplify and clean up the following file:\n"
        f"- Improve readability\n"
        f"- Remove obvious duplication\n"
        f"- Use idiomatic patterns (for this language)\n"
        f"- Keep the same behavior and API\n\n"
        f"Do NOT introduce breaking changes.\n"
        f"Do NOT change external behavior or side effects.\n\n"
        f"File path: {file_path}\n\n"
        f"----- CODE START -----\n"
        f"{code}\n"
        f"----- CODE END -----\n\n"
        f"Return ONLY the full updated code for this file."
    )

def refactor_dead_code(file_path: Path, code: str) -> str:
    """
    Entry point for full-file dead-code removal.
    """
    user_prompt = _build_dead_code_prompt(file_path, code)
    system_prompt = (
        "You are a careful refactoring assistant focused on removing dead code safely. "
        "Return only the full, updated code inside markdown code fences."
    )
    raw_result = _call_model_for_full_refactor(system_prompt, user_prompt)
    return _strip_code_fences(raw_result)

def refactor_simplify(file_path: Path, code: str) -> str:
    """
    Entry point for full-file code simplification.
    """
    user_prompt = _build_simplify_prompt(file_path, code)
    system_prompt = (
        "You are a careful refactoring assistant focused on simplifying code without changing behavior. "
        "Return only the full, updated code inside markdown code fences."
    )
    raw_result = _call_model_for_full_refactor(system_prompt, user_prompt)
    return _strip_code_fences(raw_result)
