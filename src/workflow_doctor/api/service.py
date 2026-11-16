"""Transport service calls the existing offline engine exactly once."""
import unicodedata
from pathlib import PurePosixPath

from ..scanner import scan_uploads
from .models import ApiProblem


def upload_label(filename: str | None, index: int) -> str:
    # Original names never enter a path, report, cache or error response.
    if (not filename or len(filename) > 255 or filename in (".", "..")
            or any(char in filename for char in ("/", "\\", ":"))
            or any(unicodedata.category(char).startswith("C") for char in filename)):
        raise ApiProblem(400, "UPLOAD_NAME_INVALID", "Upload name must be a plain filename without path or control characters")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in (".json", ".zip"):
        raise ApiProblem(415, "UPLOAD_TYPE_UNSUPPORTED", "Upload JSON files or exactly one ZIP")
    return f"upload[{index}]{suffix}"


def scan_and_store(files, config, store):
    try:
        report = scan_uploads(files, limits=config.scan_limits, analysis_limits=config.analysis_limits)
    except Exception:
        raise ApiProblem(500, "ENGINE_INTERNAL_ERROR", "The scan could not be completed") from None
    if report["error_count"]:
        error = report["errors"][0]
        code = error["code"]
        if code == "INPUT_UNSUPPORTED_TYPE":
            status = 415
        elif any(marker in code for marker in ("LIMIT", "TOO_LARGE", "COUNT", "SIZE_MISMATCH")):
            status = 413
        elif code.startswith("ZIP_") or code == "INPUT_MIXED_ARCHIVE":
            status = 400
        elif code == "INPUT_EMPTY":
            status = 422
        else:
            raise ApiProblem(500, "ENGINE_INTERNAL_ERROR", "The scan could not be completed")
        raise ApiProblem(status, code, error["message"])
    return store.put(report)
