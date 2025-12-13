# ai_code/core/file_utils.py
from __future__ import annotations

from pathlib import Path


def read_file_safe(path_str: str) -> str:
    path = Path(path_str).resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
    return path.read_text(encoding="utf-8")


def list_files(pattern_or_path: str) -> list[Path]:
    """
    - 파일이면: 그 파일만 리스트로
    - 디렉토리면: 하위 모든 파일
    - 글롭 패턴이면: 매칭되는 모든 파일
    """
    path = Path(pattern_or_path)

    # 1) 그냥 파일인 경우
    if path.exists() and path.is_file():
        return [path.resolve()]

    # 2) 디렉토리인 경우
    if path.exists() and path.is_dir():
        return [
            p.resolve()
            for p in path.rglob("*")
            if p.is_file()
            and "node_modules" not in p.parts
            and "dist" not in p.parts
            and "build" not in p.parts
        ]

    # 3) 글롭 패턴으로 처리
    matches = list(Path(".").glob(pattern_or_path))
    if matches:
        return [
            m.resolve()
            for m in matches
            if m.is_file()
            and "node_modules" not in m.parts
            and "dist" not in m.parts
            and "build" not in m.parts
        ]

    raise FileNotFoundError(f"경로 또는 패턴에 해당하는 파일이 없습니다: {pattern_or_path}")
