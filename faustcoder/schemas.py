"""Load and validate the JSON Schemas copied into ``schemas/``.

Schemas are read from disk only. The validator does not resolve remote
``$schema`` or ``$ref`` URLs. The directory is the checkout's
``schemas/`` folder, or ``FAUSTCODER_SCHEMA_DIR`` when that variable is
set.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import rfc3339_validator  # noqa: F401  -- date-time checks fail closed without it
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError as JsonSchemaError

from faustcoder.errors import SchemaError, SchemaValidationError

_ENVELOPE_NAME = "artifact-envelope.schema.json"


def schema_directory() -> Path:
    """Return the directory that holds the copied JSON Schemas."""
    override = os.environ.get("FAUSTCODER_SCHEMA_DIR")
    if override:
        directory = Path(override)
    else:
        directory = Path(__file__).resolve().parent.parent / "schemas"
    if not (directory / _ENVELOPE_NAME).is_file():
        raise SchemaError(f"artifact envelope schema not found in {directory}")
    return directory


def schema_names() -> tuple[str, ...]:
    """Return the ``*.schema.json`` filenames in the schema directory."""
    names = sorted(path.name for path in schema_directory().glob("*.schema.json"))
    if not names:
        raise SchemaError(f"no schemas in {schema_directory()}")
    return tuple(names)


def validate(instance: object, schema_name: str) -> None:
    """Validate ``instance`` against one schema file. Raise on failure."""
    if schema_name not in schema_names():
        raise SchemaError(f"unknown schema: {schema_name}")
    validator = _validator(schema_name, str(schema_directory()))
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if not errors:
        return
    detail = "; ".join(_format_error(error) for error in errors)
    raise SchemaValidationError(schema_name, detail)


@lru_cache(maxsize=32)
def _validator(schema_name: str, schema_dir: str) -> Draft202012Validator:
    path = Path(schema_dir) / schema_name
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{schema_name} is not JSON: {exc}") from exc
    try:
        Draft202012Validator.check_schema(schema)
    except JsonSchemaError as exc:
        raise SchemaError(f"{schema_name} is not a valid JSON Schema: {exc}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _format_error(error: object) -> str:
    path = getattr(error, "absolute_path", ())
    location = "/".join(str(part) for part in path) or "(root)"
    message = getattr(error, "message", str(error))
    return f"{location}: {message}"
