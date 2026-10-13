"""Typer entry point. Reports category counts, never source text."""

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from ard_redact_cli.detection import Detector
from ard_redact_cli.formats import SUPPORTED
from ard_redact_cli.models import install_model, load_model
from ard_redact_cli.processing import process_file

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def discover(path: Path, recursive: bool) -> list[Path]:
  if path.is_file():
    if path.suffix.lower() not in SUPPORTED:
      raise ValueError("Unsupported format; choose DOCX, MD, TXT, VTT, or SRT.")
    if path.is_symlink():
      raise ValueError("Symlink inputs are not supported.")
    return [path]
  if not path.is_dir():
    raise ValueError("Input path does not exist or is not a file/directory.")
  candidates = path.rglob("*") if recursive else path.iterdir()
  return sorted(
    item
    for item in candidates
    if item.is_file()
    and not item.is_symlink()
    and not any(parent.is_symlink() for parent in item.parents)
    and item.suffix.lower() in SUPPORTED
    and not item.stem.endswith("_pii")
  )


@app.command()
def main(
  path: Annotated[Path | None, typer.Argument(help="File or directory to redact.")] = None,
  recursive: Annotated[bool, typer.Option(help="Include subdirectories.")] = False,
  dry_run: Annotated[bool, typer.Option(help="Report counts without writing files.")] = False,
  model: Annotated[
    str, typer.Option(help="spaCy model or language: en, de, es, fr, it.")
  ] = "en_core_web_sm",
  phone_region: Annotated[
    str, typer.Option(help="ISO country code for national phone numbers.")
  ] = "AT",
  organizations: Annotated[
    bool,
    typer.Option(
      "--organizations", "--redact-organizations", help="Also redact organizations (ORG)."
    ),
  ] = False,
  overwrite: Annotated[bool, typer.Option(help="Replace existing _pii outputs.")] = False,
  install: Annotated[
    bool,
    typer.Option("--install-model", help="Install the selected model and exit (network required)."),
  ] = False,
) -> None:
  """Redact PII locally, keeping originals and document structure intact."""
  try:
    if install:
      install_model(model)
      typer.echo("Model installed.")
      return
    if path is None:
      raise ValueError("Provide a file/directory, or use --install-model.")
    paths = discover(path, recursive)
    if not paths:
      raise ValueError("No supported input files found.")
    detector = Detector(load_model(model), phone_region.upper(), organizations)
  except (ValueError, subprocess.CalledProcessError) as error:
    typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(1) from None
  failed = False
  for source in paths:
    try:
      result = process_file(source, detector, dry_run=dry_run, overwrite=overwrite)
      counts = ", ".join(f"{category}={count}" for category, count in sorted(result.counts.items()))
      prefix = "[dry-run] " if dry_run else ""
      typer.echo(f"{prefix}{source} → {result.output}: {counts or 'no PII detected'}")
      for warning in result.warnings:
        typer.echo(f"Warning: {warning}", err=True)
    except Exception:
      # Parser/NER exceptions may embed source text. Deliberately suppress it.
      typer.echo(
        f"Error processing {source}: check input, model, permissions, and existing outputs."
        " Use --overwrite only to replace an existing output.",
        err=True,
      )
      failed = True
  if failed:
    raise typer.Exit(1)
