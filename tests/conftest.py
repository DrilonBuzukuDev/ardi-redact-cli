from typing import cast

import pytest
import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler

from ard_redact_cli.detection import Detector


@pytest.fixture
def nlp() -> Language:
  pipeline = spacy.blank("en")
  ruler = cast(EntityRuler, pipeline.add_pipe("entity_ruler"))
  ruler.add_patterns(
    [
      {"label": "PERSON", "pattern": [{"LOWER": "john"}, {"LOWER": "smith"}]},
      {"label": "PERSON", "pattern": [{"LOWER": "alice"}]},
      {"label": "GPE", "pattern": "Vienna"},
      {"label": "DATE", "pattern": "January 2, 2026"},
      {"label": "ORG", "pattern": "Acme"},
    ]
  )
  return pipeline


@pytest.fixture
def detector(nlp: Language) -> Detector:
  return Detector(nlp)
