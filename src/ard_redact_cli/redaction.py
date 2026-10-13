"""File-scoped placeholder assignment and reversible offset projection."""

import re
from collections import Counter
from dataclasses import dataclass

from ard_redact_cli.detection import PLACEHOLDER_PATTERN, Category, Detection


@dataclass
class TextUnit:
  source: str
  text: str
  offsets: list[int | None]

  @classmethod
  def project(
    cls, source: str, protected: set[int] | None = None, boundaries: set[int] | None = None
  ) -> "TextUnit":
    protected = protected or set()
    boundaries = boundaries or set()
    chars: list[str] = []
    offsets: list[int | None] = []
    for index, char in enumerate(source):
      if char == "\n" and index > 0 and source[index - 1] == "\r":
        continue
      if index in boundaries:
        chars.append(" ")
        offsets.append(None)
        continue
      if index in protected:
        continue
      chars.append(" " if char in "\r\n" else char)
      offsets.append(None if char in "\r\n" else index)
    return cls(source, "".join(chars), offsets)


class Redactor:
  def __init__(self) -> None:
    self._values: dict[tuple[Category, str], str] = {}
    self._serials: Counter[str] = Counter()
    self.counts: Counter[str] = Counter()

  def reserve(self, sources: list[str]) -> None:
    """Avoid colliding with placeholders already present in a document."""
    for source in sources:
      for match in PLACEHOLDER_PATTERN.finditer(source):
        category, serial = match[0][1:-1].rsplit("_", 1)
        self._serials[category] = max(self._serials[category], int(serial))

  def edits(self, unit: TextUnit, detections: list[Detection]) -> dict[int, str]:
    replacements: dict[int, str] = {}
    for item in detections:
      positions = [index for index in unit.offsets[item.start : item.end] if index is not None]
      if not positions:
        continue
      value = " ".join(item.value.split()).casefold()
      if item.category == "PHONE":
        value = re.sub(r"\D", "", value)
      key = (item.category, value)
      if key not in self._values:
        self._serials[item.category] += 1
        self._values[key] = f"[{item.category}_{self._serials[item.category]}]"
      replacements[positions[0]] = self._values[key]
      for index in positions[1:]:
        replacements[index] = ""
      self.counts[item.category] += 1
    return replacements

  def apply(self, unit: TextUnit, detections: list[Detection]) -> str:
    return apply_edits(unit.source, self.edits(unit, detections))


def apply_edits(source: str, edits: dict[int, str], start: int = 0) -> str:
  return "".join(edits.get(start + index, char) for index, char in enumerate(source))
