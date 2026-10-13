"""Detection with offsets into the input; never log detected values."""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal

import phonenumbers
from spacy.language import Language
from spacy.tokens import Doc

Category = Literal["PERSON", "LOCATION", "EMAIL", "PHONE", "GPS", "DATE", "ORG"]


@dataclass(frozen=True)
class Detection:
  start: int
  end: int
  category: Category
  value: str


# Decimal degrees, optionally in parentheses; decimal notation avoids ordinary
# integer pairs such as dates, dimensions, and list numbering.
GPS_PATTERN = re.compile(
  r"(?<![\w.+-])(?P<lat>[+-]?\d{1,3}\.\d+)\s*[,;]\s*"
  r"(?P<lon>[+-]?\d{1,3}\.\d+)(?![\w.])"
)
PLACEHOLDER_PATTERN = re.compile(r"\[(?:PERSON|LOCATION|EMAIL|PHONE|GPS|DATE|ORG)_\d+\]")
PRIORITY: dict[Category, int] = {
  "EMAIL": 0,
  "GPS": 1,
  "PHONE": 2,
  "PERSON": 3,
  "LOCATION": 4,
  "DATE": 5,
  "ORG": 6,
}


def resolve_overlaps(detections: Iterable[Detection]) -> list[Detection]:
  """Prefer structured matches, then longer spans, with deterministic ties."""
  accepted: list[Detection] = []
  for candidate in sorted(
    detections,
    key=lambda item: (PRIORITY[item.category], -(item.end - item.start), item.start),
  ):
    if not any(candidate.start < item.end and item.start < candidate.end for item in accepted):
      accepted.append(candidate)
  return sorted(accepted, key=lambda item: item.start)


class Detector:
  def __init__(self, nlp: Language, phone_region: str = "AT", organizations: bool = False) -> None:
    if phone_region not in phonenumbers.SUPPORTED_REGIONS:
      raise ValueError("Unsupported phone region; use an ISO country code such as AT or US.")
    self.nlp = nlp
    self.phone_region = phone_region
    self.organizations = organizations

  def batch(self, texts: Iterable[str]) -> Iterator[list[Detection]]:
    for doc in self.nlp.pipe(texts, batch_size=32):
      yield self._detect(doc)

  def _detect(self, doc: Doc) -> list[Detection]:
    text = doc.text
    matches: list[Detection] = []
    labels: dict[str, Category] = {
      "PERSON": "PERSON",
      "PER": "PERSON",
      "GPE": "LOCATION",
      "LOC": "LOCATION",
      "FAC": "LOCATION",
      "DATE": "DATE",
    }
    if self.organizations:
      labels["ORG"] = "ORG"
    for entity in doc.ents:
      if category := labels.get(entity.label_):
        matches.append(Detection(entity.start_char, entity.end_char, category, entity.text))
    for token in doc:
      if token.like_email:
        matches.append(Detection(token.idx, token.idx + len(token.text), "EMAIL", token.text))
    for match in phonenumbers.PhoneNumberMatcher(text, self.phone_region):
      matches.append(Detection(match.start, match.end, "PHONE", match.raw_string))
    for match in GPS_PATTERN.finditer(text):
      if abs(float(match["lat"])) <= 90 and abs(float(match["lon"])) <= 180:
        matches.append(Detection(match.start(), match.end(), "GPS", match[0]))
    protected = [(match.start(), match.end()) for match in PLACEHOLDER_PATTERN.finditer(text)]
    return resolve_overlaps(
      item
      for item in matches
      if not any(item.start < end and start < item.end for start, end in protected)
    )
