from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import pytest
from spacy.language import Language
from typer.testing import CliRunner

from ard_redact_cli import cli, processing
from ard_redact_cli.detection import Detection, Detector
from ard_redact_cli.formats import PreparedFile
from ard_redact_cli.processing import process_file
from ard_redact_cli.redaction import TextUnit


def test_dry_run_and_exclusive_output(tmp_path: Path, detector: Detector) -> None:
  path = tmp_path / "notes.txt"
  path.write_text("Alice")
  result = process_file(path, detector, dry_run=True)
  assert result.counts == {"PERSON": 1}
  assert not result.output.exists()
  result.output.write_text("existing")
  with pytest.raises(FileExistsError):
    process_file(path, detector)
  assert result.output.read_text() == "existing"
  process_file(path, detector, overwrite=True)
  assert result.output.read_text() == "[PERSON_1]"
  assert path.read_text() == "Alice"


def test_output_link_to_original_rejected(tmp_path: Path, detector: Detector) -> None:
  path = tmp_path / "notes.txt"
  path.write_text("Alice")
  output = tmp_path / "notes_pii.txt"
  output.symlink_to(path)
  with pytest.raises(ValueError):
    process_file(path, detector, overwrite=True)
  assert path.read_text() == "Alice"


def test_directory_skip_outputs_and_recursive(tmp_path: Path) -> None:
  (tmp_path / "a.txt").write_text("Alice")
  (tmp_path / "a_pii.txt").write_text("Alice")
  (tmp_path / "ignore.pdf").write_text("Alice")
  sub = tmp_path / "sub"
  sub.mkdir()
  (sub / "b.md").write_text("Alice")
  assert [path.name for path in cli.discover(tmp_path, False)] == ["a.txt"]
  assert [path.name for path in cli.discover(tmp_path, True)] == ["a.txt", "b.md"]


def test_cli_recursive_counts_and_privacy(
  tmp_path: Path, nlp: Language, monkeypatch: pytest.MonkeyPatch
) -> None:
  def load(_name: str) -> Language:
    return nlp

  monkeypatch.setattr(cli, "load_model", load)
  path = tmp_path / "notes.txt"
  path.write_text("Alice in Vienna john@example.com Acme")
  runner = CliRunner()
  result = runner.invoke(cli.app, [str(tmp_path), "--recursive", "--dry-run", "--organizations"])
  assert result.exit_code == 0, result.output
  assert "PERSON=1" in result.output and "ORG=1" in result.output
  assert "john@example.com" not in result.output and "Alice" not in result.output
  assert not (tmp_path / "notes_pii.txt").exists()
  assert runner.invoke(cli.app, ["--help"]).exit_code == 0


def test_cli_keeps_going_and_hides_exception_text(
  tmp_path: Path, nlp: Language, monkeypatch: pytest.MonkeyPatch
) -> None:
  def load(_name: str) -> Language:
    return nlp

  monkeypatch.setattr(cli, "load_model", load)
  (tmp_path / "bad.docx").write_text("sensitive original PII")
  (tmp_path / "good.txt").write_text("Alice")
  result = CliRunner().invoke(cli.app, [str(tmp_path)])
  assert result.exit_code == 1
  assert "sensitive original PII" not in result.output
  assert (tmp_path / "good_pii.txt").read_text() == "[PERSON_1]"


def test_failure_leaves_no_output(
  tmp_path: Path, detector: Detector, monkeypatch: pytest.MonkeyPatch
) -> None:
  path = tmp_path / "notes.txt"
  path.write_text("Alice")

  def fail(_texts: Iterator[str]) -> Iterator[list[Detection]]:
    raise RuntimeError("private value")
    yield []

  monkeypatch.setattr(detector, "batch", fail)
  with pytest.raises(RuntimeError):
    process_file(path, detector)
  assert sorted(item.name for item in tmp_path.iterdir()) == ["notes.txt"]


def test_write_failure_cleans_temporary_and_preserves_existing(
  tmp_path: Path, detector: Detector, monkeypatch: pytest.MonkeyPatch
) -> None:
  path = tmp_path / "notes.txt"
  path.write_text("Alice")
  output = tmp_path / "notes_pii.txt"
  output.write_text("existing")

  class BrokenFile:
    units: list[TextUnit] = [TextUnit.project("Alice")]
    warnings: list[str] = []

    def write(self, edits: list[dict[int, str]], stream: BinaryIO) -> None:
      stream.write(b"partial output")
      raise OSError("disk full")

  def prepare(_path: Path) -> PreparedFile:
    return BrokenFile()

  monkeypatch.setattr(processing, "prepare", prepare)
  with pytest.raises(OSError):
    process_file(path, detector, overwrite=True)
  assert path.read_text() == "Alice" and output.read_text() == "existing"
  assert sorted(item.name for item in tmp_path.iterdir()) == ["notes.txt", "notes_pii.txt"]
