"""Tests for core/chuck.py — chunk_by_chars, chunk_with_line_info"""

import pytest
from ai_code.core.chuck import chunk_by_chars, chunk_with_line_info


# ─── chunk_by_chars ──────────────────────────────────────────


class TestChunkByChars:
    def test_short_text_returns_single_chunk(self):
        text = "hello world"
        result = chunk_by_chars(text, max_chars=100)
        assert result == [text]

    def test_empty_string_returns_single_empty_chunk(self):
        result = chunk_by_chars("")
        assert result == [""]

    def test_exact_max_chars_returns_single_chunk(self):
        text = "a" * 100
        result = chunk_by_chars(text, max_chars=100)
        assert result == [text]

    def test_long_text_produces_multiple_chunks(self):
        text = "a" * 250
        result = chunk_by_chars(text, max_chars=100, overlap=0)
        assert len(result) == 3
        assert result[0] == "a" * 100
        assert result[1] == "a" * 100
        assert result[2] == "a" * 50

    def test_overlap_between_chunks(self):
        text = "abcdefghij" * 3  # 30 chars
        result = chunk_by_chars(text, max_chars=15, overlap=5)
        # first chunk: 0..15, next starts at 15-5=10
        assert len(result) >= 2
        # overlap region: last 5 chars of chunk[0] == first 5 chars of chunk[1]
        assert result[0][-5:] == result[1][:5]

    def test_all_text_is_covered(self):
        text = "x" * 500
        result = chunk_by_chars(text, max_chars=120, overlap=20)
        reconstructed = result[0]
        for chunk in result[1:]:
            reconstructed += chunk[20:]  # skip overlap portion
        assert len(reconstructed) == len(text)

    def test_max_chars_zero_raises(self):
        with pytest.raises(ValueError, match="max_chars must be > 0"):
            chunk_by_chars("abc", max_chars=0)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="overlap must be >= 0"):
            chunk_by_chars("abc", overlap=-1)


# ─── chunk_with_line_info ────────────────────────────────────


class TestChunkWithLineInfo:
    def test_short_text_single_chunk_starts_at_line_1(self):
        text = "line1\nline2\nline3\n"
        result = chunk_with_line_info(text, max_chars=1000)
        assert len(result) == 1
        start_line, chunk = result[0]
        assert start_line == 1
        assert chunk == text

    def test_empty_string_returns_empty_list(self):
        result = chunk_with_line_info("")
        # splitlines("") → [], so no lines to process
        assert result == []

    def test_multiple_chunks_have_correct_start_lines(self):
        # 10 lines, each 10 chars → 100 chars total
        lines = [f"line{i:05d}\n" for i in range(10)]
        text = "".join(lines)
        result = chunk_with_line_info(text, max_chars=50, overlap=0)
        assert len(result) >= 2
        # first chunk starts at line 1
        assert result[0][0] == 1

    def test_chunks_cover_all_content(self):
        lines = [f"row-{i}\n" for i in range(20)]
        text = "".join(lines)
        result = chunk_with_line_info(text, max_chars=40, overlap=0)
        combined = "".join(chunk for _, chunk in result)
        assert combined == text

    def test_result_type(self):
        text = "a\nb\nc\n"
        result = chunk_with_line_info(text)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], int)
            assert isinstance(item[1], str)
