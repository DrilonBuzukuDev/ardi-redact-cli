"""Typer entry point. Reports category counts, never source text."""

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from ardi_redact_cli.detection import Detector
from ardi_redact_cli.formats import SUPPORTED
from ardi_redact_cli.models import LANGUAGES, MODELS, install_model, load_model, model_name
from ardi_redact_cli.processing import process_file

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def setup_languages() -> None:
  typer.echo("Choose language support. Each selected language downloads a medium (md) model.")
  selected = [
    language
    for language in LANGUAGES
    if typer.confirm(f"Install {language.title()} support?", default=language == "english")
  ]
  for language in selected:
    typer.echo(f"Installing {language.title()} support...")
    install_model(language)
    typer.echo(
      f"{language.title()} support installed. Redact with ardi-redact <path> in {language}."
    )
  if not selected:
    typer.echo("No languages selected. Add one later with ardi-redact use <language>.")


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
  path: Annotated[
    Path | None,
    typer.Argument(help="File/directory to redact [in <language>], `setup`, or `use <language>`."),
  ] = None,
  qualifier: Annotated[
    str | None,
    typer.Argument(help="`in` before the redaction language, or language after `use`."),
  ] = None,
  language: Annotated[
    str | None,
    typer.Argument(
      help="Language after `in`: english (default), german, spanish, french, italian (or codes)."
    ),
  ] = None,
  recursive: Annotated[bool, typer.Option(help="Include subdirectories.")] = False,
  dry_run: Annotated[bool, typer.Option(help="Report counts without writing files.")] = False,
  model: Annotated[
    str | None, typer.Option(help="Advanced: select an installed medium/larger spaCy pipeline.")
  ] = None,
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
    if path == Path("use"):
      if language is not None:
        raise ValueError("Use ardi-redact use <language>.")
      if qualifier is None:
        raise ValueError("Choose a language: english, german, spanish, french, or italian.")
      install_model(qualifier)
      typer.echo(f"Model for {qualifier} installed ({model_name(qualifier)}).")
      typer.echo(f"Redact with ardi-redact <path> in {qualifier}.")
      return
    if qualifier is not None:
      if qualifier != "in" or language is None or path is None or path == Path("setup") or install:
        raise ValueError("Use ardi-redact <path> in <language>.")
      if model is not None:
        raise ValueError("Choose either `in <language>` or --model.")
      if model_name(language) not in MODELS.values():
        raise ValueError("Choose a language: english, german, spanish, french, or italian.")
      model = language
    model = model or "english"
    if install:
      install_model(model)
      typer.echo("Model installed.")
      return
    if path is None or path == Path("setup"):
      setup_languages()
      return
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
