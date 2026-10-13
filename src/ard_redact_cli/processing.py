"""File processing and atomic output publication."""

import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ard_redact_cli.detection import Detector
from ard_redact_cli.formats import prepare
from ard_redact_cli.redaction import Redactor


@dataclass(frozen=True)
class Result:
  output: Path
  counts: Counter[str]
  warnings: list[str]


def output_path(path: Path) -> Path:
  return path.with_name(f"{path.stem}_pii{path.suffix}")


def process_file(
  path: Path, detector: Detector, *, dry_run: bool = False, overwrite: bool = False
) -> Result:
  output = output_path(path)
  if not dry_run and output.exists() and not overwrite:
    raise FileExistsError("Output already exists; use --overwrite to replace it.")
  if output.is_symlink() or (output.exists() and output.samefile(path)):
    raise ValueError("Output points to an original or a symlink; refusing to replace it.")
  prepared = prepare(path)
  redactor = Redactor()
  redactor.reserve([unit.source for unit in prepared.units])
  edits = [
    redactor.edits(unit, detections)
    for unit, detections in zip(
      prepared.units, detector.batch(unit.text for unit in prepared.units), strict=True
    )
  ]
  if not dry_run:
    descriptor, temporary = tempfile.mkstemp(prefix=".ard-redact-", dir=path.parent)
    try:
      with os.fdopen(descriptor, "wb") as stream:
        prepared.write(edits, stream)
        stream.flush()
        os.fsync(stream.fileno())
      if overwrite:
        os.replace(temporary, output)
      else:
        # Atomic exclusive publication also protects against concurrent runs.
        os.link(temporary, output)
    finally:
      Path(temporary).unlink(missing_ok=True)
  return Result(output, redactor.counts, prepared.warnings)
