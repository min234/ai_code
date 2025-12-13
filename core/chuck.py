# ai_code/core/chunk_utils.py
from typing import List, Tuple


def chunk_by_chars(
    text: str,
    max_chars: int = 8000,
    overlap: int = 200,
) -> List[str]:
    """
    긴 문자열을 max_chars 기준으로 잘라서 여러 청크로 나눕니다.
    청크 사이에는 overlap 만큼의 겹치는 부분을 넣어서
    문맥이 완전히 끊기지 않도록 합니다.

    - text: 원본 문자열 (코드 전체 등)
    - max_chars: 청크 하나당 최대 문자 수
    - overlap: 이전 청크의 끝부분을 다음 청크의 앞부분에 얼마나 겹쳐 넣을지
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    length = len(text)
    if length <= max_chars:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < length:
        end = start + max_chars
        chunk = text[start:end]

        chunks.append(chunk)

        if end >= length:
            break

        # 다음 청크 시작 위치: 이번 청크 끝 - overlap
        start = max(0, end - overlap)

    return chunks


def chunk_with_line_info(
    text: str,
    max_chars: int = 8000,
    overlap: int = 200,
) -> List[Tuple[int, str]]:
    """
    chunk_by_chars와 동일하지만,
    각 청크가 '원본에서 대략 몇 번째 라인부터 시작하는지' 정보도 함께 리턴합니다.

    반환값: [(start_line_number, chunk_text), ...]
    - start_line_number는 1부터 시작하는 라인 번호
    """
    # 라인 기준으로 한 번 쪼갠 뒤, 다시 문자열로 합쳐가며 청크를 만든다.
    lines = text.splitlines(keepends=True)
    current_chunk_lines: List[str] = []
    current_len = 0
    current_start_line = 1
    result: List[Tuple[int, str]] = []

    line_index = 0
    total_lines = len(lines)

    while line_index < total_lines:
        line = lines[line_index]
        line_len = len(line)

        # 새 라인을 추가했을 때 max_chars를 넘지 않으면 그냥 추가
        if current_len + line_len <= max_chars or not current_chunk_lines:
            current_chunk_lines.append(line)
            current_len += line_len
            line_index += 1
            continue

        # 여기까지가 하나의 청크
        chunk_text = "".join(current_chunk_lines)
        result.append((current_start_line, chunk_text))

        # overlap 라인만큼 뒤로 물러나서 다음 청크 시작
        overlap_lines = max(0, min(len(current_chunk_lines), overlap // 10))  # 대략 10자/라인 가정
        if overlap_lines > 0:
            # 겹칠 라인만 남기고 나머지는 버림
            current_chunk_lines = current_chunk_lines[-overlap_lines:]
            current_len = sum(len(l) for l in current_chunk_lines)
            current_start_line = max(1, current_start_line + len(current_chunk_lines) - overlap_lines)
        else:
            current_chunk_lines = []
            current_len = 0
            current_start_line = line_index + 1

    # 남은 라인 처리
    if current_chunk_lines:
        chunk_text = "".join(current_chunk_lines)
        result.append((current_start_line, chunk_text))

    return result
