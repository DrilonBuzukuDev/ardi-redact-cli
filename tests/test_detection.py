from collections.abc import Iterator

import pytest
from spacy.language import Language
from spacy.tokens import Doc

from ardi_redact_cli.detection import Detection, Detector, resolve_overlaps
from ardi_redact_cli.redaction import Redactor, TextUnit


def test_categories_and_repetition(detector: Detector) -> None:
  unit = TextUnit.project(
    "John Smith lives in Vienna. john@example.com John Smith January 2, 2026 Acme "
    "+43 664 1234567; 48.2082, 16.3738"
  )
  redactor = Redactor()
  result = redactor.apply(unit, next(detector.batch([unit.text])))
  assert result == (
    "[PERSON_1] lives in [LOCATION_1]. [EMAIL_1] [PERSON_1] [DATE_1] Acme [PHONE_1]; [GPS_1]"
  )
  assert redactor.counts["PERSON"] == 2


def test_organizations_opt_in(nlp: Language) -> None:
  assert next(Detector(nlp).batch(["Acme"])) == []
  assert next(Detector(nlp, organizations=True).batch(["Acme"]))[0].category == "ORG"


@pytest.mark.parametrize(
  "source", ["91.0000, 16.3738", "48.2082, 181.0000", "12, 14", "x48.2, 16.3"]
)
def test_invalid_gps(source: str, detector: Detector) -> None:
  assert not any(item.category == "GPS" for item in next(detector.batch([source])))


@pytest.mark.parametrize("source", ["-90.0, +180.0", "48.2082;16.3738", "(48.2, 16.3)"])
def test_valid_gps(source: str, detector: Detector) -> None:
  assert any(item.category == "GPS" for item in next(detector.batch([source])))


def test_overlap_priority() -> None:
  email = Detection(0, 16, "EMAIL", "john@example.com")
  assert resolve_overlaps([Detection(0, 4, "PERSON", "john"), email]) == [email]
  assert (
    resolve_overlaps([Detection(0, 4, "PERSON", "John"), Detection(0, 10, "PERSON", "John Smith")])[
      0
    ].end
    == 10
  )


def test_placeholder_collision_and_casefold(detector: Detector) -> None:
  unit = TextUnit.project("[PERSON_1] John Smith john smith")
  redactor = Redactor()
  redactor.reserve([unit.source])
  assert redactor.apply(unit, next(detector.batch([unit.text]))) == (
    "[PERSON_1] [PERSON_2] [PERSON_2]"
  )


def test_invalid_region(nlp: Language) -> None:
  with pytest.raises(ValueError):
    Detector(nlp, "XX")


def test_batch_uses_pipe(nlp: Language, monkeypatch: pytest.MonkeyPatch) -> None:
  calls: list[int] = []
  original = nlp.pipe

  def pipe(texts: list[str], *, batch_size: int) -> Iterator[Doc]:
    calls.append(batch_size)
    return original(texts, batch_size=batch_size)

  monkeypatch.setattr(nlp, "pipe", pipe)
  assert len(list(Detector(nlp).batch(["Alice", "Vienna"]))) == 2
  assert calls == [32]
