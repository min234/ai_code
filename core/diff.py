from __future__ import annotations

from pathlib import Path
from difflib import unified_diff
import difflib

def apply_diff_to_file(path: str, diff_text: str):
    original = open(path).read().splitlines(keepends=True)
    diff = diff_text.splitlines(keepends=True)

    # diff를 이용해 새로운 파일 재구성
    patched = list(difflib.restore(diff, 2))  # 2 = new version

    with open(path, "w") as f:
        f.write("".join(patched))


def make_unified_diff(
    original_code: str,
    new_code: str,
    path: Path,
) -> str:
    """
    원본 코드와 새로운 코드를 unified diff 형식으로 반환.
    """
    original_lines = original_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)

    diff_lines = unified_diff(
        original_lines,
        new_lines,
        fromfile=str(path),
        tofile=str(path),
    )

    return "".join(diff_lines)
