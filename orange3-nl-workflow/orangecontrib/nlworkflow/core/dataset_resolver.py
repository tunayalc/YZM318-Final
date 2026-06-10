"""Resolve dataset file paths mentioned in natural-language prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_EXTENSIONS = (".csv", ".tsv", ".tab", ".xlsx")


@dataclass
class DatasetResolution:
    path: str | None = None
    warnings: list[str] = field(default_factory=list)
    source: str = "none"


def _candidate_dirs(prompt: str, search_dirs: list[Path] | None) -> list[Path]:
    if search_dirs is not None:
        return [Path(item).expanduser() for item in search_dirs]

    home = Path.home()
    cwd = Path.cwd()
    lowered = prompt.casefold()
    dirs = []

    if any(word in lowered for word in ("indirilen", "downloads", "download")):
        dirs.extend([home / "Downloads", home / "İndirilenler"])
    if any(word in lowered for word in ("masaüstü", "desktop")):
        dirs.append(home / "Desktop")
    if any(word in lowered for word in ("belgeler", "documents")):
        dirs.append(home / "Documents")

    dirs.extend(
        [
            cwd,
            cwd / "data",
            cwd / "datasets",
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
        ]
    )

    unique = []
    seen = set()
    for path in dirs:
        resolved = path.expanduser()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def _strip_candidate(value: str) -> str:
    return value.strip().strip(" \t\r\n\"'`“”‘’()[]{}<>.,;:")


def _prompt_path_matches(prompt: str) -> list[tuple[int, str]]:
    matches = []
    extensions = "|".join(re.escape(ext[1:]) for ext in DATA_EXTENSIONS)
    quoted = re.compile(
        rf"['\"`“”‘’](?P<path>[^'\"`“”‘’]+?\.({extensions}))['\"`“”‘’]",
        re.IGNORECASE,
    )
    absolute = re.compile(
        rf"(?P<path>(?:~|/)[^\n\r\t,;]+?\.({extensions}))",
        re.IGNORECASE,
    )
    filename = re.compile(
        rf"(?P<path>[A-Za-z0-9_ğüşöçıİĞÜŞÖÇ][A-Za-z0-9_ğüşöçıİĞÜŞÖÇ .()@+-]*?\.({extensions}))",
        re.IGNORECASE,
    )

    for pattern in (quoted, absolute, filename):
        for match in pattern.finditer(prompt):
            candidate = _strip_candidate(match.group("path"))
            if candidate:
                matches.append((match.start("path"), match.end("path"), candidate))

    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    filtered = []
    for start, end, candidate in matches:
        if any(prev_start <= start and end <= prev_end for prev_start, prev_end, _ in filtered):
            continue
        filtered.append((start, end, candidate))

    result = []
    seen = set()
    for start, _, candidate in filtered:
        key = (start, candidate)
        if key not in seen:
            seen.add(key)
            result.append((start, candidate))
    return result


def _prompt_path_candidates(prompt: str) -> list[str]:
    return [candidate for _, candidate in _prompt_path_matches(prompt)]


def _latest_file_request_position(prompt: str) -> int:
    lowered = prompt.casefold()
    positions = [
        lowered.rfind(phrase)
        for phrase in ("son indirdiğim", "en son", "latest")
    ]
    return max(positions)


def _fuzzy_dataset_request_position(prompt: str) -> int:
    lowered = prompt.casefold()
    positions = [
        lowered.rfind(phrase)
        for phrase in ("dataset", "veri seti", "csv seç", "csv sec", "csv'yi seç")
    ]
    return max(positions)


def _resolve_existing(candidate: str, dirs: list[Path]) -> Path | None:
    variants = [candidate]
    if not Path(candidate).expanduser().is_absolute() and " " in candidate:
        parts = candidate.split()
        variants.extend(" ".join(parts[index:]) for index in range(1, len(parts)))

    for variant in variants:
        raw = Path(variant).expanduser()
        if raw.is_absolute() and raw.exists():
            return raw.resolve()
        if raw.exists():
            return raw.resolve()

    for variant in variants:
        for directory in dirs:
            path = directory / variant
            if path.exists():
                return path.resolve()
    return None


def _latest_file_in_dirs(dirs: list[Path]) -> Path | None:
    files = []
    for directory in dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for ext in DATA_EXTENSIONS:
            files.extend(directory.glob(f"*{ext}"))
    if not files:
        return None
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0].resolve()


def _data_files_in_dirs(dirs: list[Path]) -> list[Path]:
    files = []
    for directory in dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for ext in DATA_EXTENSIONS:
            files.extend(directory.glob(f"*{ext}"))
    return files


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_ğüşöçıİĞÜŞÖÇ-]{3,}", text)
    }


def _resolve_fuzzy_dataset(prompt: str, dirs: list[Path]) -> Path | None:
    lowered = prompt.casefold()
    if not any(word in lowered for word in ("csv", "dataset", "veri seti", "dosya")):
        return None

    prompt_tokens = _tokens(prompt)
    ignored = {
        "csv",
        "dataset",
        "veri",
        "seti",
        "dosya",
        "dosyasını",
        "seç",
        "sec",
        "aç",
        "ac",
    }
    prompt_tokens -= ignored
    if not prompt_tokens:
        return None

    ranked = []
    for path in _data_files_in_dirs(dirs):
        name_tokens = _tokens(path.stem.replace("_", " ").replace("-", " "))
        score = len(prompt_tokens & name_tokens)
        if score:
            ranked.append((score, path.stat().st_mtime, path))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][2].resolve()


def _prompt_asks_for_latest_file(prompt: str) -> bool:
    return _latest_file_request_position(prompt) >= 0


def resolve_dataset_path(
    prompt: str,
    *,
    explicit_path: str | None = None,
    search_dirs: list[Path] | None = None,
) -> DatasetResolution:
    """Resolve the dataset path that should be used for generation.

    Prompt-mentioned paths intentionally take precedence over the UI field so
    stale widget settings do not override what the user just requested.
    """
    dirs = _candidate_dirs(prompt, search_dirs)
    warnings = []
    path_matches = _prompt_path_matches(prompt)
    latest_request_pos = _latest_file_request_position(prompt)
    fuzzy_request_pos = _fuzzy_dataset_request_position(prompt)

    if latest_request_pos >= 0 and (
        not path_matches or latest_request_pos > path_matches[-1][0]
    ):
        latest = _latest_file_in_dirs(dirs)
        if latest is not None:
            return DatasetResolution(str(latest), warnings, "latest")
        warnings.append("Prompt asked for the latest dataset file, but no data file was found.")
        return DatasetResolution(None, warnings, "none")

    if path_matches:
        if fuzzy_request_pos > path_matches[-1][0]:
            fuzzy = _resolve_fuzzy_dataset(prompt[fuzzy_request_pos:], dirs)
            if fuzzy is not None:
                return DatasetResolution(str(fuzzy), warnings, "fuzzy")
        candidate = path_matches[-1][1]
        resolved = _resolve_existing(candidate, dirs)
        if resolved is not None:
            return DatasetResolution(str(resolved), warnings, "prompt")
        warnings.append(f"Prompt mentioned a dataset file but it was not found: {candidate}")
        return DatasetResolution(None, warnings, "none")

    fuzzy = _resolve_fuzzy_dataset(prompt, dirs)
    if fuzzy is not None:
        return DatasetResolution(str(fuzzy), warnings, "fuzzy")

    if explicit_path:
        expanded = Path(explicit_path).expanduser()
        if expanded.exists():
            return DatasetResolution(str(expanded.resolve()), warnings, "field")
        warnings.append(f"Selected dataset path does not exist: {explicit_path}")

    return DatasetResolution(None, warnings, "none")
