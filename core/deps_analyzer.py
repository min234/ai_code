# ai_code/core/deps_analyzer.py

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List

from .file_utils import read_file_safe
from .openai_client import ask_model
import typer
from ..core.diff import make_unified_diff

DEPS_ANALYZER_SYSTEM_PROMPT = """
You are a senior build/devops engineer.
You MUST write all explanatory text in Korean.

You will receive multiple files from a single project.
Some of them are dependency-related config files
(e.g., pyproject.toml, requirements.txt, Pipfile, package.json, lockfiles, etc.),
and many others may be regular source code or unrelated configs.

YOUR JOB:
1. First, decide by yourself which of the given files are actually
   "dependency configuration files" (패키지/의존성 정보를 정의하는 파일).
2. Ignore all other files that are not dependency configs.
3. Based ONLY on the dependency-related files you selected, analyze the project's dependencies:
   - unused dependencies
   - missing dependencies (when clearly inferable)
   - version conflicts or risky ranges
   - obviously outdated or risky libraries
4. For each issue, propose a concrete and actionable suggestion that a developer can apply.
5. If the provided files are insufficient to determine any concrete issue, say so clearly in the summary.
6. Never put ```json ``` in it. It should be ready to use.
Output format (JSON only, no backticks):
{
  "summary": "프로젝트 의존성 상태를 한 문단 정도로 요약 (한국어)",
  "issues": [
    {
      "type": "string, one of: \"missing\", \"unused\", \"conflict\", \"outdated\", \"other\"",
      "file": "문제가 관찰된 설정 파일의 상대 경로 (예: \"requirements.txt\")",
      "detail": "문제가 무엇인지 한국어로 자세히 설명",
      "suggestion": "어떤 패키지를 어떻게 수정/업데이트/제거해야 하는지 한국어로 제안"
    }
  ],
  "notes": "추가적인 메모 또는 전반적인 코멘트 (한국어)"
}

Rules:
- Do not output anything outside of the single JSON object.
- All human-readable explanations (summary, detail, suggestion, notes) MUST be in Korean.
- If you cannot find any clear issue, return an empty 'issues' array and explain that in 'summary'.
- You MUST decide yourself which files are dependency configs; do not assume the caller filtered them.
"""


def collect_text_files(root: Path, max_files: int = 40, max_bytes: int = 200_000) -> Dict[str, str]:
    """
    root 아래의 '텍스트 기반' 파일을 넓게 수집한다.
    어떤 파일이 의존성 파일인지는 전적으로 LLM이 판단.
    - 너무 큰 파일은 잘라서 보내거나 스킵.
    - .git, node_modules, .venv, dist, build 등은 기본적으로 스킵 (성능 보호용).
    """
    root = root.expanduser().resolve()
    found: Dict[str, str] = {}

    skipped_dirs = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}

    count = 0
    for p in root.rglob("*"):
        if count >= max_files:
            break

        if not p.is_file():
            continue

        # 불필요한 디렉터리 스킵 (이건 "의존성 판단"이 아니라 그냥 성능/잡음 필터)
        if any(part in skipped_dirs for part in p.parts):
            continue

        # 너무 큰 파일은 스킵 (바이너리/덩치 큰 로그 등)
        try:
            if p.stat().st_size > max_bytes:
                continue
        except OSError:
            continue

        try:
            content = read_file_safe(str(p))
        except UnicodeDecodeError:
            # 바이너리/이상한 인코딩이면 스킵
            continue

        rel = str(p.relative_to(root))
        found[rel] = content
        count += 1

    return found


def analyze_dependencies(root: Path) -> Dict[str, Any]:
    """
    주어진 프로젝트 루트(root) 아래의 여러 파일을 수집하고,
    LLM에게 "어떤 파일이 의존성 설정인지"를 스스로 판단하게 맡긴 뒤,
    의존성 분석 결과(JSON)를 반환한다.
    """
    root = root.expanduser().resolve()
    files = collect_text_files(root)

    if not files:
        return {
            "summary": "프로젝트에서 분석 가능한 텍스트 파일을 찾지 못했습니다.",
            "issues": [],
            "notes": "루트 경로가 맞는지 또는 폴더가 비어있는지 확인해 주세요.",
        }

    # 프롬프트 구성: 파일 경로 + 내용 그대로 넘김
    dump_lines: List[str] = []
    for rel, content in files.items():
        dump_lines.append(f"=== {rel} ===")
        dump_lines.append(content)
        dump_lines.append("")

    user_prompt = (
        "다음은 하나의 프로젝트에서 가져온 여러 파일입니다.\n"
        "- 이 중 어떤 파일이 '의존성/패키지 설정 파일'인지 스스로 판별한 뒤,\n"
        "- 그 파일들만 기반으로 의존성 상태를 분석해 주세요.\n\n"
        "절대로 ```json ``` 넣지마세요 바로 사용 할 수 있어야 합니다.\n\n"
        + "\n".join(dump_lines)
    )

    response = ask_model(
        system_prompt=DEPS_ANALYZER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model="gpt-4o",
        response_format="json_object",
    )

    if isinstance(response, dict):
        return response

    return {
        "summary": "의존성 분석 중 예기치 못한 응답 형식이 반환되었습니다.",
        "issues": [],
        "notes": f"raw response: {response!r}",
    }
def apply_dependency_changes(root: Path, analysis_result: Dict[str, Any]) -> None:
    """
    분석 결과(issues)를 기반으로 실제 설정 파일들을 수정한다.
    - 각 파일별로 LLM에게 '이 제안들을 반영한 새 버전'을 생성하게 하고
    - diff 보여주고
    - 사용자 확인 후 덮어쓴다.
    """
    issues = analysis_result.get("issues") or []
    if not issues:
        return

    # 어떤 파일들을 고쳐야 하는지 모음
    target_files = sorted({iss.get("file") for iss in issues if iss.get("file")})
    if not target_files:
        typer.echo("[agent] 수정할 설정 파일이 지정되지 않았습니다.")
        return

    for rel_path in target_files:
        rel = Path(rel_path)
        abs_path = (root / rel).expanduser().resolve()
        if not abs_path.exists():
            typer.echo(f"[agent] Skipping (file not found): {abs_path}")
            continue

        try:
            original_content = read_file_safe(str(abs_path))
        except UnicodeDecodeError:
            typer.echo(f"[agent] Skipping non-text file: {abs_path}")
            continue

        # 이 파일에 해당하는 이슈들만 추려서 프롬프트에 전달
        file_issues = [iss for iss in issues if iss.get("file") == rel_path]

        if not file_issues:
            continue

        issues_text_lines = []
        for i, iss in enumerate(file_issues, start=1):
            issues_text_lines.append(f"[{i}] type={iss.get('type')}")
            issues_text_lines.append(f"detail: {iss.get('detail')}")
            issues_text_lines.append(f"suggestion: {iss.get('suggestion')}")
            issues_text_lines.append("")

        user_prompt = (
            "다음은 한 설정 파일의 현재 내용과, 이 파일에 대해 적용해야 할 의존성 수정 제안들입니다.\n"
            "- 제안들을 반영한 새 버전의 파일 전체 내용을 출력해 주세요.\n"
            "- 포맷(예: JSON, TOML, requirements 형식 등)을 깨뜨리지 말고 유지해야 합니다.\n\n"
            f"=== 현재 파일 경로 ===\n{rel_path}\n\n"
            "=== 현재 파일 내용 ===\n"
            f"{original_content}\n\n"
            "=== 적용해야 할 제안들 ===\n"
            + "\n".join(issues_text_lines)
        )

        system_prompt = """
You are a senior build/devops engineer.
You MUST write the new file content in Korean comments if needed,
but preserve the original config format (JSON, TOML, INI, requirements.txt, etc.).

Never put ```json ``` in it. It should be ready to use.
Please do not add comments
Task:
- Apply the given suggestions to the file.
- Return ONLY the full new file content (no explanation, no JSON wrapper).
"""

        new_content: str = ask_model(  # type: ignore[assignment]
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o",
            response_format=None,  # 순수 텍스트
        )

        # diff 보여주고 사용자에게 적용 여부 확인
        diff = make_unified_diff(original_content, new_content, abs_path)
        typer.echo(f"\n[agent] Proposed changes for {abs_path}:\n")
        typer.echo(diff)

        if not typer.confirm(f"Apply these changes to {abs_path}?", default=False):
            typer.echo("  ✗ Skipped.")
            continue

        abs_path.write_text(new_content, encoding="utf-8")
        typer.echo("  ✓ Changes applied.")
