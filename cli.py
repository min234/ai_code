# ai_code/cli.py
from __future__ import annotations

import sys

import typer

from .agent import route_user_request, run_tool_from_spec

app = typer.Typer(help="AI 기반 코드 분석 / 리팩터링 에이전트 CLI")


@app.command()
def agent():
    """
    자연어로 AI와 대화하면서,
    analyze / refactor_dead_code / refactor_simplify / partial_refactor 등을
    에이전트가 자동으로 선택해서 실행하는 모드.
    """
    typer.echo("AI Agent 대화 모드입니다. 'exit', 'quit'으로 종료합니다.\n")

    while True:
        try:
            user_text = typer.prompt(">>")
        except (EOFError, KeyboardInterrupt):
            typer.echo("\n[ai-code] 종료.")
            break

        # 종료 명령
        if user_text.strip().lower() in {"exit", "quit"}:
            typer.echo("[ai-code] 종료.")
            break

        # 빈 입력은 무시
        if not user_text.strip():
            continue

        try:
            # 1) 자연어 → 에이전트가 JSON spec 생성
            spec = route_user_request(user_text)

            # 2) 에이전트가 설명(explanation)을 내려줬다면 먼저 보여주기
            explanation = spec.get("explanation")
            if explanation:
                typer.echo(f"\n[agent] 설명:\n{explanation}\n")

            # 3) 계획 로그
            typer.echo(f"[agent] 계획: {spec}")

            # 4) 실제 툴 실행 (중간 y/N 확인은 run_tool_from_spec 안에서 처리)
            run_tool_from_spec(spec)

        except Exception as e:
            typer.echo(f"[agent] 에러: {e}", err=True)


def main():
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\n[ai-code] 중단됨 (Ctrl+C)")
        sys.exit(1)


if __name__ == "__main__":
    main()
