from pathlib import Path

import pytest
import spacy

from ardi_redact_cli import models
from ardi_redact_cli.detection import Detector
from ardi_redact_cli.models import LANGUAGES, MODELS, load_model, model_name
from ardi_redact_cli.processing import process_file


def test_model_aliases() -> None:
  for alias, name in MODELS.items():
    assert model_name(alias) == name
  assert model_name("custom_model") == "custom_model"


def test_missing_model_actionable() -> None:
  with pytest.raises(ValueError, match=r"medium \(md\) or larger"):
    load_model("definitely_missing_model")


@pytest.mark.skipif(
  not spacy.util.is_package("en_core_web_md"), reason="English model not installed"
)
def test_real_model_end_to_end(tmp_path: Path) -> None:
  path = tmp_path / "sample.txt"
  path.write_text("John Smith lives in Vienna. Email: john@example.com")
  result = process_file(path, Detector(load_model("en_core_web_md")))
  assert result.output.read_text() == ("[PERSON_1] lives in [LOCATION_1]. Email: [EMAIL_1]")


@pytest.mark.parametrize("language", LANGUAGES)
def test_full_language_names(language: str) -> None:
  expected = MODELS[LANGUAGES[language]]
  assert model_name(language) == expected
  assert model_name(f" {language.upper()} ") == expected
  assert expected.endswith("_md")


@pytest.mark.parametrize("language", LANGUAGES)
def test_installer_targets_current_environment(
  language: str, monkeypatch: pytest.MonkeyPatch
) -> None:
  calls: list[list[str]] = []

  def run(command: list[str], *, check: bool) -> None:
    assert check
    calls.append(command)

  def which(_name: str) -> str:
    return "/bin/uv"

  monkeypatch.setattr(models.shutil, "which", which)
  monkeypatch.setattr(models.subprocess, "run", run)
  models.install_model(language)
  name = MODELS[LANGUAGES[language]]
  assert calls == [
    [
      "/bin/uv",
      "pip",
      "install",
      "--python",
      models.sys.executable,
      f"https://github.com/explosion/spacy-models/releases/download/{name}-3.8.0/"
      f"{name}-3.8.0-py3-none-any.whl",
    ]
  ]


def test_install_requires_uv(monkeypatch: pytest.MonkeyPatch) -> None:
  def which(_name: str) -> None:
    return None

  monkeypatch.setattr(models.shutil, "which", which)
  with pytest.raises(ValueError, match="uv on PATH"):
    models.install_model("german")


def test_install_rejects_unknown_language() -> None:
  with pytest.raises(ValueError, match="Choose a language"):
    models.install_model("portuguese")


@pytest.mark.parametrize("name", ["en_core_web_sm", "de_core_news_sm"])
def test_small_models_rejected(name: str) -> None:
  with pytest.raises(ValueError, match="Small"):
    models.load_model(name)
  with pytest.raises(ValueError, match="Small"):
    models.install_model(name)


def test_small_model_directory_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  pipeline = spacy.blank("en")
  pipeline.meta["name"] = "core_web_sm"

  def load(_name: str) -> spacy.language.Language:
    return pipeline

  monkeypatch.setattr(models.spacy, "load", load)
  with pytest.raises(ValueError, match="Small"):
    models.load_model(str(tmp_path))


def test_missing_language_suggests_use(monkeypatch: pytest.MonkeyPatch) -> None:
  def missing(_name: str) -> None:
    raise OSError("missing")

  monkeypatch.setattr(models.spacy, "load", missing)
  with pytest.raises(ValueError, match="ardi-redact use german"):
    models.load_model("german")
