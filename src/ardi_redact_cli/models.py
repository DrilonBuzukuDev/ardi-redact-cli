"""Explicit model installation into the currently running uv environment."""

import shutil
import subprocess
import sys

import spacy
from spacy.language import Language

MODELS: dict[str, str] = {
  "en": "en_core_web_md",
  "de": "de_core_news_md",
  "es": "es_core_news_md",
  "fr": "fr_core_news_md",
  "it": "it_core_news_md",
}
LANGUAGES: dict[str, str] = {
  "english": "en",
  "german": "de",
  "spanish": "es",
  "french": "fr",
  "italian": "it",
}


def model_name(name: str) -> str:
  alias = name.strip().lower()
  return MODELS.get(LANGUAGES.get(alias, alias), name)


def reject_small_model(name: str) -> None:
  if name.lower().endswith("_sm"):
    raise ValueError("Small (sm) models are not supported. Choose a medium (md) or larger model.")


def install_model(name: str) -> None:
  name = model_name(name)
  reject_small_model(name)
  if name not in MODELS.values():
    raise ValueError(
      "Choose a language: english, german, spanish, french, or italian (en/de/es/fr/it)."
    )
  uv = shutil.which("uv")
  if uv is None:
    raise ValueError("Model installation requires uv on PATH.")
  wheel = f"{name}-3.8.0-py3-none-any.whl"
  url = f"https://github.com/explosion/spacy-models/releases/download/{name}-3.8.0/{wheel}"
  subprocess.run([uv, "pip", "install", "--python", sys.executable, url], check=True)


def load_model(name: str) -> Language:
  name = model_name(name)
  reject_small_model(name)
  try:
    pipeline = spacy.load(name)
  except OSError:
    language = next((key for key, alias in LANGUAGES.items() if MODELS[alias] == name), None)
    command = (
      f"ardi-redact use {language}"
      if language
      else "install a compatible medium (md) or larger spaCy pipeline"
    )
    raise ValueError(f"spaCy model unavailable ({name}). To install it, {command}.") from None
  reject_small_model(str(pipeline.meta.get("name", "")))
  return pipeline
