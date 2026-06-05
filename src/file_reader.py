"""Source text file reading with filtering and grouping capabilities."""

from pathlib import Path
from typing import List, Optional


class FileReader:
    """Read UTF-8 encoded text files with filtering and grouping capabilities."""

    # Project Gutenberg header/footer markers for detection (word-based matching)
    PG_HEADER_MARKERS = [
        "beginning of this publication",
        "project gutenberg license",
        "terms of use",
        "table of contents",
        "start of this project gutenberg ebook",
    ]

    PG_FOOTER_MARKERS = [
        "end of this publication",
        "project gutenberg license",
        "terms of use",
        "*** end of project gutenberg source file ***",
    ]

    def __init__(self, path: Path):
        """Initialize with the path to the source text file.

        Args:
            path: Path object pointing to the UTF-8 encoded text file.
        """
        self.path = path
        self._lines: List[str] = []
        self._content_units: Optional[List[str]] = None
        self._injection_mode: str = "line"

    def read(
        self,
        skip_header: bool = True,
        skip_footer: bool = True,
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> List[str]:
        """Read and parse source text file with optional filtering.

        Args:
            skip_header: Skip Project Gutenberg header sections (license, title page).
            skip_footer: Skip Project Gutenberg footer markers.
            start_line: Start reading from this 1-based line number. Defaults to 1.
            end_line: Stop at this 1-based line number, or None to read to end.

        Returns:
            List of raw lines (before grouping by injection mode).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If start_line > end_line or values are invalid.
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Source file not found: {self.path}")

        # Read file content with UTF-8 encoding
        with open(self.path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Normalize line endings (CRLF -> LF)
        normalized_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")

        # Split into lines, preserving empty lines for paragraph grouping
        self._lines = normalized_content.split("\n")
        if self._lines and self._lines[-1] == "":
            self._lines.pop()

        # Filter header/footer sections if requested
        filtered_lines = self._filter_header_footer(self._lines, skip_header, skip_footer)

        # Apply start/end line filtering with validation
        filtered_lines = self._apply_line_range(filtered_lines, start_line, end_line)

        return filtered_lines

    def _filter_header_footer(
        self, lines: List[str], skip_header: bool, skip_footer: bool
    ) -> List[str]:
        """Filter out header/footer sections based on markers.

        Args:
            lines: List of raw lines from the file.
            skip_header: Whether to skip header sections.
            skip_footer: Whether to skip footer sections.

        Returns:
            Filtered list of lines with headers/footers removed.
        """
        if not (skip_header or skip_footer):
            return lines

        result = []
        in_header = False

        for line in lines:
            is_header_marker = skip_header and self._is_pg_header(line)
            is_footer_marker = skip_footer and self._is_pg_footer(line)

            if is_header_marker:
                line_lower = line.lower()
                if "start of this" in line_lower or "beginning of" in line_lower:
                    in_header = False
                continue

            if is_footer_marker:
                break

            if in_header:
                continue

            result.append(line)

        return result

    def _is_pg_header(self, line: str) -> bool:
        """Check if a line is a Project Gutenberg header marker.

        Args:
            line: A single line from the file.

        Returns:
            True if the line matches a known PG header pattern.
        """
        # Use word boundary matching to avoid false positives
        line_lower = " ".join(line.lower().split())  # Normalize whitespace
        for marker in self.PG_HEADER_MARKERS:
            if marker in line_lower:
                return True
        return False

    def _is_pg_footer(self, line: str) -> bool:
        """Check if a line is a Project Gutenberg footer marker.

        Args:
            line: A single line from the file.

        Returns:
            True if the line matches a known PG footer pattern.
        """
        # Use word boundary matching to avoid false positives
        line_lower = " ".join(line.lower().split())  # Normalize whitespace
        for marker in self.PG_FOOTER_MARKERS:
            if marker in line_lower:
                return True
        return False

    def _apply_line_range(
        self, lines: List[str], start_line: int, end_line: Optional[int]
    ) -> List[str]:
        """Apply start/end line filtering to the list of lines.

        Args:
            lines: List of filtered lines (before range application).
            start_line: Start reading from this 1-based line number.
            end_line: Stop at this 1-based line number, or None for no limit.

        Returns:
            Lines within the specified range.

        Raises:
            ValueError: If start_line > end_line (when both are specified).
        """
        if not lines:
            return []

        # Validate start/end relationship
        if end_line is not None and start_line > end_line:
            raise ValueError(
                f"Invalid line range: start_line ({start_line}) > end_line ({end_line})"
            )

        # Convert to 0-based indexing for slicing
        start_idx = start_line - 1
        if end_line is not None:
            end_idx = end_line - 1
            return lines[start_idx:end_idx + 1]
        return lines[start_idx:]

    def group_by_injection_mode(self, lines: List[str], mode: str) -> List[str]:
        """Group content based on injection mode.

        Args:
            lines: List of raw lines from the source file.
            mode: Injection mode - "line", "paragraph", or "character_scene".

        Returns:
            List of content units ready for injection.

        Raises:
            ValueError: If an invalid injection mode is specified.
        """
        if mode == "line":
            return self._group_as_lines(lines)
        elif mode == "paragraph":
            return self._group_as_paragraphs(lines)
        elif mode == "character_scene":
            return self._group_as_character_scenes(lines)
        else:
            raise ValueError(
                f"Invalid injection_mode: {mode}. "
                "Must be 'line', 'paragraph', or 'character_scene'."
            )

    @classmethod
    def _group_as_lines(cls, lines: List[str]) -> List[str]:
        """Return each line as a separate content unit.

        Args:
            lines: List of raw lines from the source file.

        Returns:
            List where each element is a single line.
        """
        return list(lines)

    @classmethod
    def _group_as_paragraphs(cls, lines: List[str]) -> List[str]:
        """Group consecutive non-empty lines into paragraphs.

        Args:
            lines: List of raw lines from the source file.

        Returns:
            List where each element is a paragraph (consecutive non-empty lines).
        """
        if not lines:
            return []

        paragraphs: List[str] = []
        current_paragraph: List[str] = []

        for line in lines:
            stripped = line.strip()
            # Empty line signals end of paragraph
            if not stripped:
                if current_paragraph:
                    paragraphs.append("\n".join(current_paragraph))
                    current_paragraph.clear()
            else:
                current_paragraph.append(line)

        # Don't forget the last paragraph if file doesn't end with newline
        if current_paragraph:
            paragraphs.append("\n".join(current_paragraph))

        return paragraphs

    @classmethod
    def _group_as_character_scenes(cls, lines: List[str]) -> List[str]:
        """Group content into character scenes (for play format).

        This separates character names from dialogue and stage directions.
        Format expected:
            - Character name on its own line (centered or capitalized)
            - Dialogue following the character name
            - Stage directions in parentheses or brackets

        Args:
            lines: List of raw lines from a play script.

        Returns:
            List where each element is either:
            - A character name marker for dialogue injection
            - A block of dialogue/stage direction content
        """
        if not lines:
            return []

        result: List[str] = []
        current_scene: List[str] = []
        in_dialogue_block = False

        for line in lines:
            stripped = line.strip()

            # Check if this is a character name (typically centered or all caps)
            # Character names are usually on their own line and capitalized
            if cls._looks_like_character_name(line):
                if current_scene:
                    result.append("\n".join(current_scene))
                    current_scene.clear()

                # Add character name as separate unit for dialogue injection
                char_name = stripped.rstrip(":")
                result.append(f"[CHARACTER: {char_name}]")
                in_dialogue_block = True
            elif stripped.startswith("(") or stripped.startswith("["):
                # Stage direction - add to current scene if we're in a dialogue block
                if in_dialogue_block and current_scene:
                    current_scene.append(stripped)
            else:
                # Regular text - could be dialogue continuation
                if in_dialogue_block:
                    current_scene.append(stripped)

        # Add final content if any
        if current_scene:
            result.append("\n".join(current_scene))

        return result

    @classmethod
    def _looks_like_character_name(cls, line: str) -> bool:
        """Check if a line looks like a character name in a play script.

        Character names typically:
        - Are on their own line
        - Start with capital letter(s)
        - May be centered (surrounded by spaces or dashes)
        - Don't contain dialogue markers like quotes

        Args:
            line: A single line to check.

        Returns:
            True if the line looks like a character name.
        """
        stripped = line.strip()

        # Skip empty lines, stage directions, and special formatting
        if not stripped or stripped.startswith("(") or stripped.startswith("["):
            return False

        # Character names are typically 1-3 words, capitalized
        words = stripped.split()
        if not words or len(words) > 3:
            return False

        # First word should be capitalized (character name pattern)
        first_word = words[0]
        if not first_word[0].isupper():
            return False

        # Check that it doesn't look like dialogue or narration
        if any(c in stripped for c in '"\''):
            return False

        # Common character name patterns: centered with dashes, or just capitalized
        # (Note: check original line parameter for leading spaces)
        if line.startswith("  ") or stripped.startswith("-"):
            return True

        return True

    def get_content_count(self) -> int:
        """Return total number of content units available after processing.

        Returns:
            Number of lines/paragraphs/scenes ready for injection.
        """
        if self._content_units is None:
            # Group the stored lines by injection mode (lazy evaluation)
            self._content_units = self.group_by_injection_mode(
                self._lines, self._injection_mode
            )
        return len(self._content_units)

    def get_content_unit(self, index: int) -> Optional[str]:
        """Get a specific content unit by index.

        Args:
            index: Zero-based index of the content unit.

        Returns:
            The content unit string at the given index, or None if out of range.
        """
        if self._content_units is None:
            # Group the stored lines by injection mode (lazy evaluation)
            self._content_units = self.group_by_injection_mode(
                self._lines, self._injection_mode
            )

        if 0 <= index < len(self._content_units):
            return self._content_units[index]
        return None

    def set_injection_mode(self, mode: str) -> None:
        """Set the injection mode for grouping.

        Args:
            mode: Injection mode - "line", "paragraph", or "character_scene".

        Raises:
            ValueError: If an invalid injection mode is specified.
        """
        if mode not in ("line", "paragraph", "character_scene"):
            raise ValueError(
                f"Invalid injection_mode: {mode}. "
                "Must be 'line', 'paragraph', or 'character_scene'."
            )
        self._injection_mode = mode

    @property
    def lines(self) -> List[str]:
        """Get the list of raw lines from the file."""
        return self._lines.copy()

    @property
    def injection_mode(self) -> str:
        """Get the current injection mode."""
        return self._injection_mode


def read_source_file(
    path: Path,
    skip_header: bool = True,
    skip_footer: bool = True,
    start_line: int = 1,
    end_line: Optional[int] = None,
    injection_mode: str = "line",
) -> List[str]:
    """Read and parse source text file with optional filtering and grouping.

    Args:
        path: Path object pointing to the UTF-8 encoded text file.
        skip_header: Skip Project Gutenberg header sections (license, title page).
        skip_footer: Skip Project Gutenberg footer markers.
        start_line: Start reading from this 1-based line number. Defaults to 1.
        end_line: Stop at this 1-based line number, or None to read to end.
        injection_mode: How content is grouped - "line", "paragraph", or "character_scene".

    Returns:
        List of content units ready for injection (lines/paragraphs/scenes).

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If start_line > end_line or invalid injection_mode.
    """
    reader = FileReader(path)
    lines = reader.read(skip_header, skip_footer, start_line, end_line)
    return reader.group_by_injection_mode(lines, injection_mode)


def get_content_count(
    path: Path,
    skip_header: bool = True,
    skip_footer: bool = True,
    start_line: int = 1,
    end_line: Optional[int] = None,
    injection_mode: str = "line",
) -> int:
    """Return total number of content units available after processing.

    Args:
        path: Path object pointing to the UTF-8 encoded text file.
        skip_header: Skip Project Gutenberg header sections.
        skip_footer: Skip Project Gutenberg footer markers.
        start_line: Start reading from this 1-based line number.
        end_line: Stop at this 1-based line number, or None to read to end.
        injection_mode: How content is grouped.

    Returns:
        Number of content units (lines/paragraphs/scenes) available for injection.
    """
    reader = FileReader(path)
    lines = reader.read(skip_header, skip_footer, start_line, end_line)
    return len(reader.group_by_injection_mode(lines, injection_mode))
