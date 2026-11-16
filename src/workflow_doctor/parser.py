"""Strict, bounded JSON decoding; no evaluation, URL fetching or normalization."""
from __future__ import annotations

import json
import math
from typing import Any

from .models import Finding, ScanLimits


class _InvalidJSON(ValueError):
    """A fixed diagnostic reason without input values."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJSON("JSON contains duplicate object keys")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _InvalidJSON("JSON contains a non-finite number")
    return number


def _reject_constant(value: str):
    raise _InvalidJSON("JSON contains a nonstandard numeric constant")


def _bounded_int(value: str) -> int:
    if len(value.lstrip("-")) > 1000:
        raise _InvalidJSON("JSON integer exceeds the 1000-digit parser limit")
    return int(value)


def _check_depth(text: str, limit: int):
    # Check containers outside strings before Python's recursive decoder runs.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > limit:
                raise _InvalidJSON("JSON nesting exceeds the configured depth limit")
        elif char in "]}":
            depth -= 1


def parse_json(raw: bytes, limits: ScanLimits) -> tuple[Any, list[Finding]]:
    """Return the unchanged decoded object or safe WF001 evidence, never raw text."""
    try:
        text = raw.decode("utf-8-sig")
        _check_depth(text, limits.max_json_depth)
        return json.loads(text, object_pairs_hook=_unique_object,
                          parse_float=_finite_float, parse_int=_bounded_int,
                          parse_constant=_reject_constant), []
    except json.JSONDecodeError as exc:
        return None, [Finding("WF001", "error", "Invalid JSON syntax", "$",
                              "Correct the JSON syntax at the indicated line and column.",
                              {"line": exc.lineno, "column": exc.colno,
                               "character_offset": exc.pos})]
    except UnicodeError:
        return None, [Finding("WF001", "error", "Input is not valid UTF-8 JSON", "$",
                              "Export a UTF-8 JSON file; a UTF-8 BOM is supported.")]
    except _InvalidJSON as exc:
        return None, [Finding("WF001", "error", str(exc), "$",
                              "Use unique keys, finite JSON numbers and bounded nesting and integer lengths.")]
    except (ValueError, RecursionError):
        return None, [Finding("WF001", "error",
                              "JSON exceeds the decoder's runtime limits",
                              "$", "Reduce JSON nesting and numeric lengths.")]
