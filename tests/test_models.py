from pathlib import Path

import pytest
import spacy

from ard_redact_cli.detection import Detector
from ard_redact_cli.models import MODELS, load_model, model_name
from ard_redact_cli.processing import process_file


def test_model_aliases() -> None:
  for alias, name in MODELS.items():
    assert model_name(alias) == name
  assert model_name("custom_model") == "custom_model"


def test_missing_model_actionable() -> None:
  with pytest.raises(ValueError, match="--install-model"):
    load_model("definitely_missing_model")


@pytest.mark.skipif(
  not spacy.util.is_package("en_core_web_sm"), reason="English model not installed"
)
def test_real_model_end_to_end(tmp_path: Path) -> None:
  path = tmp_path / "sample.txt"
  path.write_text("John Smith lives in Vienna. Email: john@example.com")
  result = process_file(path, Detector(load_model("en_core_web_sm")))
  assert result.output.read_text() == ("[PERSON_1] lives in [LOCATION_1]. Email: [EMAIL_1]")
