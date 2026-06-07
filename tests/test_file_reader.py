"""Unit tests for file_reader module."""

import os
import tempfile
from pathlib import Path
import pytest

from src.file_reader import FileReader, read_source_file, get_content_count


class TestFileReader:
    """Test cases for FileReader class."""

    def test_read_simple_text_file(self):
        """Test reading a simple text file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line 1\n")
            f.write("line 2\n")
            f.write("line 3\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read()

            assert len(lines) == 3
            assert lines[0] == "line 1"
            assert lines[1] == "line 2"
            assert lines[2] == "line 3"
        finally:
            os.unlink(temp_path)

    def test_read_utf8_file(self):
        """Test reading a UTF-8 encoded file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Hello 世界\n")
            f.write("Привет мир\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read()

            assert len(lines) == 2
            assert "世界" in lines[0]
            assert "мир" in lines[1]
        finally:
            os.unlink(temp_path)

    def test_normalize_crlf_line_endings(self):
        """Test that CRLF line endings are normalized to LF."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            # Write with CRLF line endings
            f.write(b"line 1\r\n")
            f.write(b"line 2\r\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read()

            assert len(lines) == 2
            # Lines should be normalized (no \r)
            assert "\r" not in lines[0]
            assert "\r" not in lines[1]
        finally:
            os.unlink(temp_path)

    def test_skip_header(self):
        """Test skipping Project Gutenberg header sections."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # Include actual header content pattern that triggers skipping
            # Use lowercase "author:" to match the PG_HEADER_START_PATTERNS regex
            f.write("The Project Gutenberg eBook of Test\n")
            f.write("author: Jane Doe\n")  # Lowercase to match "^author:" pattern
            f.write("*** BEGINNING OF THIS PUBLICATION ***\n")
            f.write("Project Gutenberg License\n")
            f.write("Table of Contents\n")
            # The "BEGINNING OF THIS PUBLICATION" line is the end marker and gets included
            # Content after this should be returned (3 lines total: 1 end marker + 2 content)
            f.write("line 1\n")
            f.write("line 2\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read(skip_header=True, skip_footer=False)

            # Header should be skipped (end marker + content lines remain)
            assert len(lines) == 3
            assert "BEGINNING" not in lines[1]
        finally:
            os.unlink(temp_path)

    def test_skip_footer(self):
        """Test skipping Project Gutenberg footer sections."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line 1\n")
            f.write("line 2\n")
            f.write("*** END OF THIS PUBLICATION ***\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read(skip_header=False, skip_footer=True)

            # Footer should be skipped
            assert len(lines) == 2
            assert "END" not in lines[1]
        finally:
            os.unlink(temp_path)

    def test_apply_start_line(self):
        """Test starting from a specific line number."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 11):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read(start_line=5, end_line=None)

            assert len(lines) == 6  # Lines 5-10
            assert lines[0] == "line 5"
            assert lines[-1] == "line 10"
        finally:
            os.unlink(temp_path)

    def test_apply_end_line(self):
        """Test stopping at a specific line number."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 11):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read(start_line=1, end_line=5)

            assert len(lines) == 5  # Lines 1-5
            assert lines[0] == "line 1"
            assert lines[-1] == "line 5"
        finally:
            os.unlink(temp_path)

    def test_invalid_start_end_range(self):
        """Test that start_line > end_line raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 11):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            with pytest.raises(ValueError, match="Invalid line range"):
                reader.read(start_line=10, end_line=5)
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        """Test that reading a non-existent file raises FileNotFoundError."""
        temp_path = Path("/nonexistent/file.txt")
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            FileReader(temp_path).read()


class TestGroupByInjectionMode:
    """Test cases for grouping content by injection mode."""

    def test_group_as_lines(self):
        """Test grouping as individual lines."""
        lines = ["line 1", "line 2", "line 3"]
        result = FileReader._group_as_lines(lines)

        assert len(result) == 3
        assert result[0] == "line 1"
        assert result[1] == "line 2"
        assert result[2] == "line 3"

    def test_group_as_paragraphs(self):
        """Test grouping consecutive non-empty lines into paragraphs."""
        lines = [
            "First paragraph line 1",
            "First paragraph line 2",
            "",
            "Second paragraph line 1",
            "Second paragraph line 2",
            "Second paragraph line 3",
            ""
        ]
        result = FileReader._group_as_paragraphs(lines)

        assert len(result) == 2
        assert result[0] == "First paragraph line 1\nFirst paragraph line 2"
        assert result[1] == "Second paragraph line 1\nSecond paragraph line 2\nSecond paragraph line 3"

    def test_group_as_character_scenes(self):
        """Test grouping character names and dialogue for plays."""
        lines = [
            "  HAMLET:",
            "To be, or not to be, that is the question.",
            "",
            "  POLONIUS:",
            "(aside) He seems determined."
        ]
        result = FileReader._group_as_character_scenes(lines)

        # Should have character markers and dialogue blocks
        assert "[CHARACTER: HAMLET]" in result
        assert "To be, or not to be" in result[1]
        assert "[CHARACTER: POLONIUS]" in result


class TestGetContentCount:
    """Test cases for get_content_count function."""

    def test_count_lines_mode(self):
        """Test counting content units with line mode."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i in range(1, 6):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            count = get_content_count(temp_path, injection_mode="line")
            assert count == 5
        finally:
            os.unlink(temp_path)

    def test_count_paragraphs_mode(self):
        """Test counting content units with paragraph mode."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("para 1 line 1\n")
            f.write("para 1 line 2\n")
            f.write("\n")
            f.write("para 2 line 1\n")
            temp_path = Path(f.name)

        try:
            count = get_content_count(temp_path, injection_mode="paragraph")
            assert count == 2
        finally:
            os.unlink(temp_path)


class TestReadSourceFile:
    """Test cases for read_source_file function."""

    def test_read_with_all_options(self):
        """Test reading with all configuration options."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("header line\n")
            for i in range(1, 6):
                f.write(f"line {i}\n")
            temp_path = Path(f.name)

        try:
            # Skip header, start at line 2, use paragraph mode
            result = read_source_file(
                temp_path,
                skip_header=True,
                skip_footer=False,
                start_line=2,
                end_line=None,
                injection_mode="paragraph"
            )

            assert len(result) == 1  # One paragraph from lines 2-5
            assert "line 2" in result[0]
        finally:
            os.unlink(temp_path)


class TestFileReaderEdgeCases:
    """Test edge cases for FileReader."""

    def test_empty_file(self):
        """Test reading an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read()

            assert len(lines) == 0
        finally:
            os.unlink(temp_path)

    def test_file_with_only_newlines(self):
        """Test reading a file with only newlines."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("\n\n\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            lines = reader.read()

            assert len(lines) == 3  # Three empty strings from newlines
        finally:
            os.unlink(temp_path)

    def test_injection_mode_validation(self):
        """Test that invalid injection mode raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line 1\n")
            temp_path = Path(f.name)

        try:
            reader = FileReader(temp_path)
            with pytest.raises(ValueError, match="Invalid injection_mode"):
                reader.group_by_injection_mode(["test"], "invalid_mode")
        finally:
            os.unlink(temp_path)
