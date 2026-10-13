"""Explicit model installation into the currently running uv environment."""

import shutil
import subprocess
import sys

import spacy
from spacy.language import Language

MODELS: dict[str, str] = {
  "en": "en_core_web_sm",
  "de": "de_core_news_sm",
  "es": "es_core_news_sm",
  "fr": "fr_core_news_sm",
  "it": "it_core_news_sm",
}


def model_name(name: str) -> str:
  return MODELS.get(name, name)


def install_model(name: str) -> None:
  name = model_name(name)
  if name not in MODELS.values():
    raise ValueError("Installer supports the five bundled language choices: en, de, es, fr, it.")
  uv = shutil.which("uv")
  if uv is None:
    raise ValueError("Model installation requires uv on PATH.")
  wheel = f"{name}-3.8.0-py3-none-any.whl"
  url = f"https://github.com/explosion/spacy-models/releases/download/{name}-3.8.0/{wheel}"
  subprocess.run([uv, "pip", "install", "--python", sys.executable, url], check=True)


def load_model(name: str) -> Language:
  name = model_name(name)
  try:
    return spacy.load(name)
  except OSError:
    raise ValueError(
      "spaCy model unavailable. Install it with ard-redact --install-model --model " + name
    ) from None
