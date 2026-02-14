# ai_code/agent.py

from pathlib import Path
import json
from typing import List
import typer

from .core.file_utils import list_files, read_file_safe
from .core.refactor_engine import (
    refactor_dead_code,
    refactor_simplify,
    Selection,
    partial_refactor,
)
from .core.language_converter import ProjectFile, ProjectSnapshot, run_language_conversion
from .core.openai_client import ask_model
from .core.diff import make_unified_diff

from .core.deps_analyzer import analyze_dependencies,apply_dependency_changes

AGENT_SYSTEM_PROMPT = """
You are a command router for an AI code CLI tool.

Your job:
- Read the user's natural language request.
- Decide WHICH TOOL to use and WITH WHAT ARGUMENTS.
- Respond ONLY with a JSON object, nothing else.

Available tools:

1) analyze
   - Description: Analyze code or project structure.
   - Params:
       - path (string): file or folder
       - summary (bool, optional, default true)

2) refactor_dead_code
   - Description: Remove dead code (unused imports, vars, etc.) for whole files.
   - Params:
       - path (string): file or folder

3) refactor_simplify
   - Description: Simplify code while keeping behavior, for whole files.
   - Params:
       - path (string): file or folder

4) refactor_partial
   - Description: Refactor ONLY a specific line range inside a single file.
   - Params:
       - path (string): single file path
       - start_line (int): 1-based start line (inclusive)
       - end_line (int): 1-based end line (inclusive)
       - kind (string, optional): one of [style, bugfix, performance, readability, cleanup, custom]
       - instruction (string, optional): extra user note for this selection
       - global_instruction (string, optional): global refactoring guidance

5) convert_language
    - Description: Translate an entire project from a source language to a target language.
    - Params:
        - path (string): The root directory of the project to convert.
        - src_lang (string): The source language (e.g., "python", "javascript").
        - tgt_lang (string): The target language (e.g., "go", "rust").
        - target_stack_desc (string): A detailed description of the target stack, including frameworks, libraries, and architectural patterns.

6) deps_analyze
   - Description: Analyze dependency issues in the project.
   - Params:
       - path (string): folder path

Routing rules:

- If the user asks for "dead code removal" on a file or folder -> use refactor_dead_code.
- If the user wants to "simplify/clean/refactor" a file without specifying lines -> use refactor_simplify.
- If the user explicitly mentions a line range or "partial refactor",
  and provides line numbers (e.g. 10~20), prefer refactor_partial with appropriate start_line/end_line.
- If the user asks to "convert", "translate", or "migrate" a project from one language to another -> use convert_language.
- If the user wants a high-level explanation or analysis of a file or project -> use analyze.
- If the user talks about dependency/version/package problems -> use deps_analyze.

Always reply with JSON like:
{
  "tool": "<tool_name>",
  "path": "<path>",
  ...
}

Do NOT add any explanation outside of the JSON. JSON only.
"""


def route_user_request(user_text: str) -> dict:
    """
    Sends a natural language request to the LLM to get a JSON spec
    for which tool to use with which parameters.
    """
    system_prompt = AGENT_SYSTEM_PROMPT
    user_prompt = f"User request:\n{user_text}\n\nJSON only response:"

    response = ask_model(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="gpt-4o",
        response_format="json_object",
    )

    if not isinstance(response, dict):
        raise RuntimeError(f"Agent response was not a valid JSON object: {response!r}")

    return response


def run_tool_from_spec(spec: dict):
    """
    Executes the tool specified in the spec (JSON dict) returned by route_user_request.
    This is where file I/O, diff printing, and user confirmation are handled.
    """
    tool = spec.get("tool")
    path_str = spec.get("path", ".")
    path = Path(path_str)

    # ---------- analyze ----------
    if tool == "analyze":
        summary = bool(spec.get("summary", True))
        typer.echo(f"[agent] Running analyze: path={path_str}, summary={summary}")

        try:
            target_files = list_files(path_str)
        except FileNotFoundError as e:
            typer.echo(f"[agent] Error: {e}", err=True)
            return

        if not target_files:
            typer.echo("[agent] No files to analyze.")
            return

        first_file = target_files[0]
        code = read_file_safe(str(first_file))

        system_prompt = "You are an expert software architect. Analyze this file."
        user_prompt = (
            f"File path: {first_file}\n\n"
            "----- CODE START -----\n"
            f"{code[:8000]}\n"
            "----- CODE END -----\n"
        )
        result = ask_model(system_prompt=system_prompt, user_prompt=user_prompt, model="gpt-4o-mini")
        typer.echo("\n[agent] Analysis Result:\n")
        typer.echo(result)
        return

    # ---------- refactor_dead_code (whole file) ----------
    if tool == "refactor_dead_code":
        typer.echo(f"[agent] Running refactor_dead_code: path={path_str}")

        try:
            files = list_files(path_str)
        except FileNotFoundError as e:
            typer.echo(f"[agent] Error: {e}", err=True)
            return

        if not files:
            typer.echo("[agent] No files to refactor.")
            return

        for f in files:
            typer.echo(f"\n[agent] ▶ {f}")
            original = read_file_safe(str(f))
            new_code = refactor_dead_code(f, original)

            diff = make_unified_diff(original, new_code, f)
            if not diff.strip():
                typer.echo("  - No changes.")
                continue

            typer.echo("  - Diff:")
            typer.echo(diff)

            confirm = typer.confirm(
                f"Apply this change to {f}?", default=False
            )
            if not confirm:
                typer.echo("  ✗ Aborted.")
                continue

            f.write_text(new_code, encoding="utf-8")
            typer.echo("  ✓ Applied.")
        return

    # ---------- refactor_simplify (whole file) ----------
    if tool == "refactor_simplify":
        typer.echo(f"[agent] Running refactor_simplify: path={path_str}")

        try:
            files = list_files(path_str)
        except FileNotFoundError as e:
            typer.echo(f"[agent] Error: {e}", err=True)
            return

        if not files:
            typer.echo("[agent] No files to refactor.")
            return

        for f in files:
            typer.echo(f"\n[agent] ▶ {f}")
            original = read_file_safe(str(f))
            new_code = refactor_simplify(f, original)

            diff = make_unified_diff(original, new_code, f)
            if not diff.strip():
                typer.echo("  - No changes.")
                continue

            typer.echo("  - Diff:")
            typer.echo(diff)

            confirm = typer.confirm(
                f"Apply this change to {f}?", default=False
            )
            if not confirm:
                typer.echo("  ✗ Aborted.")
                continue

            f.write_text(new_code, encoding="utf-8")
            typer.echo("  ✓ Applied.")
        return
    
        
     # ---------- deps_analyze ----------
    if tool == "deps_analyze":
        typer.echo(f"[agent] deps_analyze: path={path_str}")

        root = Path(path_str).expanduser().resolve()
        if not root.exists():
            typer.echo(f"[agent] Error: path not found: {root}", err=True)
            return
        if not root.is_dir():
            root = root.parent

        

        # 1) 분석만 먼저 실행
        result = analyze_dependencies(root)

        typer.echo("\n[agent] Dependency analysis result:\n")
        typer.echo(f"- 요약: {result.get('summary','')}")
    
        issues = result.get("issues") or []
        for i, iss in enumerate(issues, start=1):
            typer.echo(f"\n[{i}] type={iss.get('type')}")
            typer.echo(f"    file: {iss.get('file')}")
            typer.echo(f"    detail: {iss.get('detail')}")
            typer.echo(f"    suggestion: {iss.get('suggestion')}")

        notes = result.get("notes")
        if notes:
            typer.echo("\n[notes]")
            typer.echo(notes)

        # 2) 여기서 직접 사용자에게 물어본다
        if issues:
            apply = typer.confirm(
                "\n이 제안들을 실제로 파일에 적용할까요?", default=False
            )
        else:
            apply = False

        typer.echo(f"[agent] apply={apply}")

        # 3) apply=True일 때만 실제 수정 실행
        if apply:
            # 실제 수정 로직 여기서 구현 (예: requirements.txt 업데이트)
            # 일단 뼈대만:
            typer.echo("[agent] 실제 파일 수정 기능은 여기서 구현됩니다.")
            # TODO: 각 suggestion을 기반으로 파일 업데이트
            apply_dependency_changes(root, result)
        typer.echo("\n[agent] deps_analyze 완료.")
        return



    # ---------- refactor_partial ----------
    if tool == "refactor_partial":
        start_line = int(spec.get("start_line", 1))
        end_line = int(spec.get("end_line", start_line))
        kind = spec.get("kind", "custom")
        instruction = spec.get("instruction", "")
        global_instruction = spec.get("global_instruction", "")

        file_path = Path(path_str).resolve()
        repo_root = Path(".").resolve()

        if not file_path.exists():
            typer.echo(f"[agent] File not found: {file_path}", err=True)
            return

        try:
            rel_path = file_path.relative_to(repo_root)
        except ValueError:
            rel_path = Path(path_str)

        typer.echo(f"[agent] Running refactor_partial: path={file_path}")
        typer.echo(f"  Line range: {start_line} to {end_line}")
        typer.echo(f"  kind={kind}, instruction={instruction!r}")

        sel = Selection(
            file_path=rel_path,
            start_line=start_line,
            end_line=end_line,
            kind=kind,
            user_instruction=instruction,
        )

        preview = partial_refactor(
            repo_root=repo_root,
            selections=[sel],
            global_instruction=global_instruction,
            dry_run=True,
        )

        res = preview["results"][0]

        if res["error"]:
            typer.echo(f"[agent] Error: {res['error']}", err=True)
            return

        diff = make_unified_diff(
            res["original_snippet"],
            res["refactored_snippet"],
            file_path,
        )

        typer.echo("  - Partial diff:")
        typer.echo(diff)

        confirm = typer.confirm(
            f"Apply this partial change to {file_path}?", default=False
        )
        if not confirm:
            typer.echo("  ✗ User aborted.")
            return

        applied = partial_refactor(
            repo_root=repo_root,
            selections=[sel],
            global_instruction=global_instruction,
            dry_run=False,
        )

        applied_res = applied["results"][0]
        if applied_res["error"]:
            typer.echo(f"[agent] Error applying changes: {applied_res['error']}", err=True)
            return

        typer.echo("  ✓ Partial refactoring applied.")
        return

    # ---------- convert_language ----------
    if tool == "convert_language":
        typer.echo(f"[agent] Running convert_language: path={path_str}")
        src_lang = spec.get("src_lang")
        tgt_lang = spec.get("tgt_lang")
        target_stack_desc = spec.get("target_stack_desc")
        scope = spec.get("scope", "auto")  # "file" | "project" | "auto"
        
        if not src_lang or not tgt_lang:
            typer.echo("[agent] Error: 'src_lang' and 'tgt_lang' are required for conversion.", err=True)
            return

        if not target_stack_desc:
            target_stack_desc = f"An idiomatic project in {tgt_lang} using standard libraries."
            typer.echo(f"[agent] No target stack description provided. Using default: '{target_stack_desc}'")
        
        raw_path = Path(path_str).expanduser().resolve()

        # --- scope / source_files 결정 ---
        if scope == "file":
            if not raw_path.is_file():
                typer.echo(f"[agent] Error: scope='file' but path is not a file: {raw_path}", err=True)
                return
            project_root = raw_path.parent
            source_files = [raw_path]
            single_file_mode = True
            typer.echo(f"[agent] Scope=file → converting ONLY: {raw_path}")
        elif scope == "project":
            project_root = raw_path if raw_path.is_dir() else raw_path.parent
            try:
                source_files = list_files(str(project_root))
            except FileNotFoundError as e:
                typer.echo(f"[agent] Error: {e}", err=True)
                return
            single_file_mode = False
            typer.echo(f"[agent] Scope=project → converting under root: {project_root}")
        else:  # scope == "auto"
            if raw_path.is_file():
                project_root = raw_path.parent
                source_files = [raw_path]
                single_file_mode = True
                typer.echo(f"[agent] Scope=auto, path is file → converting ONLY: {raw_path}")
            else:
                project_root = raw_path
                try:
                    source_files = list_files(str(project_root))
                except FileNotFoundError as e:
                    typer.echo(f"[agent] Error: {e}", err=True)
                    return
                single_file_mode = False
                typer.echo(f"[agent] Scope=auto, path is dir → converting under root: {project_root}")

        if not source_files:
            typer.echo("[agent] No files found in the specified path.")
            return

        typer.echo(f"Found {len(source_files)} files to analyze for conversion.")
        
        project_files: List[ProjectFile] = []
        original_rel_paths: List[str] = []
        original_contents: List[str] = []

        for file_path in source_files:
            file_path = Path(file_path).resolve()
            try:
                content = read_file_safe(str(file_path))
            except UnicodeDecodeError:
                typer.echo(f"  - Skipping non-UTF8 file: {file_path}")
                continue

            try:
                rel_path = file_path.relative_to(project_root)
            except ValueError:
                rel_path = Path(file_path.name)

            rel_str = str(rel_path)
            original_rel_paths.append(rel_str)
            original_contents.append(content)

            project_files.append({
                "path": rel_str,
                "language": "unknown",
                "content": content,
            })

        snapshot: ProjectSnapshot = {
            "root": str(project_root),
            "files": project_files,
            "summary": f"Project to be converted from {src_lang} to {tgt_lang}.",
        }

        typer.echo("Starting language conversion with the AI model...")
        conversion_result = run_language_conversion(
            snapshot,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            target_stack_desc=target_stack_desc,
        )

        files_out = conversion_result.get("files") or []

        # ---------------------------
        # 💥 단일 파일 모드: test.py → test.<AI가 정한 확장자> 로 갈아끼우기
        # ---------------------------
        if single_file_mode:
            if not original_rel_paths or not original_contents:
                typer.echo("[agent] Error: no source file info recorded.", err=True)
                return
            if not files_out:
                typer.echo("[agent] Error: model returned no files for single-file conversion.", err=True)
                return

            # 원래 파일
            orig_rel = Path(original_rel_paths[0])   # 예: ai_code/test.py
            orig_abs = project_root / orig_rel
            orig_code = original_contents[0]

            # AI가 뱉은 첫 번째 결과만 사용
            first = files_out[0]
            ai_path_str = first.get("path") or orig_rel.name
            ai_path = Path(ai_path_str)

            # 파일명(stem)은 그대로 두고, 확장자만 AI가 준 suffix 로 교체
            ai_suffix = ai_path.suffix
            if ai_suffix:
                target_rel = orig_rel.with_suffix(ai_suffix)   # ai_code/test.ts 같은 형태
            else:
                # AI가 확장자를 안 주면 기존 확장자 유지
                target_rel = orig_rel

            target_path = project_root / target_rel
            new_code = first.get("content", "")

            # diff 보여주고 적용 여부 확인
            diff = make_unified_diff(orig_code, new_code, target_path)
            typer.echo("\n[agent] Preview diff (single file):")
            typer.echo(diff)

            confirm = typer.confirm(
                f"Apply this conversion to {target_path} (and replace {orig_abs})?",
                default=False,
            )
            if not confirm:
                typer.echo("  ✗ User aborted.")
                return

            # 새 파일(이름은 test.<AI확장자>)에 쓰기
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(new_code, encoding="utf-8")
            typer.echo(f"  ✓ Wrote converted code to {target_path}")

            # 경로가 다르면 원래 파일 삭제 → 이름 변경 효과
            if target_path != orig_abs and orig_abs.exists():
                orig_abs.unlink()
                typer.echo(f"  ✓ Removed old file {orig_abs}")

            notes = conversion_result.get("notes")
            if notes:
                typer.echo("\n--- Migration Notes ---")
                typer.echo(notes)
                typer.echo("-----------------------\n")

            return

        # ---------------------------
        # 📦 프로젝트 모드: 기존처럼 별도 디렉토리에 생성
        # ---------------------------
        typer.echo("\n[agent] Conversion complete. Review the results below.")
        
        notes = conversion_result.get("notes")
        if notes:
            typer.echo("\n--- Migration Notes ---")
            typer.echo(notes)
            typer.echo("-----------------------\n")
            
        safe_tgt = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(tgt_lang))
        output_dir = project_root.parent / f"{project_root.name}_converted_to_{safe_tgt}"
        typer.echo(f"Converted files will be written to: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for converted_file in files_out:
            out_path = output_dir / converted_file["path"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            typer.echo(f"\n[agent] ▶ New file: {out_path}")
            typer.echo("----- START OF CONTENT -----")
            typer.echo(converted_file["content"])
            typer.echo("----- END OF CONTENT -----")

            confirm = typer.confirm(f"Write this content to {out_path}?", default=False)
            if confirm:
                out_path.write_text(converted_file["content"], encoding="utf-8")
                typer.echo(f"  ✓ Saved {out_path}")
            else:
                typer.echo(f"  ✗ Skipped {out_path}")
        
        typer.echo("\n[agent] All files processed.")
        return
