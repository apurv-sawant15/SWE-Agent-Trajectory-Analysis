"""
Utilities for inspecting SWE-Agent trajectories.

This module currently implements `locate_reproduction_code`, which searches a
trajectory for steps where the agent creates reproduction code or tests.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parent
CLAUDE_DIR = REPO_ROOT / "claude-sonnet-trajs"
QWEN_DIR = REPO_ROOT / "Qwen-2.5-Coder-Instruct-trajs"
LOG_FILE = REPO_ROOT / "locate_reproduction_code.log"
LOG_SEARCH_FILE = REPO_ROOT / "locate_search.log"
LOG_TOOL_FILE = REPO_ROOT / "locate_tool_use.log"

# Keywords that suggest a file is meant to reproduce or test a bug.
FILE_KEYWORDS = (
    "repro",
    "reproduce",
    "reproduction",
    "debug",
    "test",
    "tests",
    "pytest",
    "unit",
    "minimal",
)

# Keywords that can appear in thoughts describing reproduction steps.
THOUGHT_KEYWORDS = (
    "repro",
    "reproduce",
    "reproduction",
    "debug",
    "test case",
    "test to reproduce",
    "script to reproduce",
    "minimal example",
    "minimal repro",
    "unit test",
    "pytest",
)


def find_instance_dir(instance_id: str) -> Path:
    """
    Locate the trajectory directory for the given instance id.

    Preference order is claude-sonnet-trajs/, then Qwen-2.5-Coder-Instruct-trajs/.
    Raises FileNotFoundError if not found in either.
    """
    candidates = [
        CLAUDE_DIR / instance_id,
        QWEN_DIR / instance_id,
    ]
    for path in candidates:
        if path.is_dir():
            return path

    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"Could not find trajectory directory for '{instance_id}'. Looked in: {searched}"
    )


def load_trajectory(traj_path: Path) -> List[Dict[str, Any]]:
    """
    Load a trajectory file that may be JSON or JSONL.

    If JSON parsing fails, falls back to parsing each non-empty line as JSON.
    Returns a list of step dictionaries.
    """
    try:
        raw = json.loads(traj_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        steps: List[Dict[str, Any]] = []
        for lineno, line in enumerate(traj_path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(
                    f"Failed to parse JSONL line {lineno} in {traj_path}: {exc}"
                ) from exc
            steps.append(entry)
        if not steps:
            raise ValueError(f"No JSON objects found in {traj_path}")
        raw = steps

    if isinstance(raw, dict):
        if "trajectory" in raw and isinstance(raw["trajectory"], list):
            steps = raw["trajectory"]  # type: ignore[assignment]
        elif "steps" in raw and isinstance(raw["steps"], list):
            steps = raw["steps"]  # type: ignore[assignment]
        else:
            # Fall back to any list value that looks like a list of steps.
            list_value = next(
                (v for v in raw.values() if isinstance(v, list) and v), None
            )
            if list_value is None:
                raise ValueError(f"Unexpected trajectory format in {traj_path}")
            steps = list_value  # type: ignore[assignment]
    elif isinstance(raw, list):
        steps = raw  # type: ignore[assignment]
    else:
        raise ValueError(f"Unsupported trajectory data in {traj_path}")

    normalized: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Step {idx} in {traj_path} is not an object")
        normalized.append(step)
    return normalized


def _action_header(action_text: str) -> str:
    """Strip verbose payloads (like --file_text) to focus on the command header."""
    if not action_text:
        return ""
    if "--file_text" in action_text:
        return action_text.split("--file_text", 1)[0]
    return action_text.splitlines()[0]


def _is_creation_action(action_text: str) -> bool:
    """Heuristic for whether the action writes/creates a file."""
    lowered = action_text.lower()
    markers = (
        "str_replace_editor create",
        "apply_patch",
        "cat <<",
        "cat >",
        "tee ",
        "printf ",
        "echo ",
        "touch ",
    )
    return any(marker in lowered for marker in markers)


def _extract_filenames(text: str) -> List[str]:
    """Best-effort extraction of filenames/paths from an action string."""
    candidates: List[str] = []
    for token in re.findall(r"(/[^\\s'\"`]+)", text):
        candidates.append(token)
    for token in re.findall(r"([A-Za-z0-9_.\\/-]+\\.[A-Za-z0-9_.-]+)", text):
        candidates.append(token)

    seen = set()
    unique: List[str] = []
    for path in candidates:
        cleaned = path.strip('\'"')
        if cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return unique


def _has_keyword(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(key in lowered for key in keywords)


def _append_log_line(log_path: Path, instance_id: str, steps: List[int]) -> None:
    """Append a simple line to the provided log path."""
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{instance_id}: {steps}\n")
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning("Failed to write log: %s", exc)


def _append_log(instance_id: str, steps: List[int]) -> None:
    """Append a simple line to locate_reproduction_code.log."""
    _append_log_line(LOG_FILE, instance_id, steps)


def _get_tool_name(step: Dict[str, Any]) -> str:
    """Best-effort extraction of the tool name for a step."""
    for key in ("tool", "tool_name", "name"):
        if key in step and step[key]:
            return str(step[key])

    action_text = str(step.get("action") or step.get("command") or "")
    header = _action_header(action_text)
    return header.split()[0] if header else ""


def _get_command_text(step: Dict[str, Any]) -> str:
    """Best-effort extraction of the command/arguments issued in a step."""
    for key in ("command", "args", "input"):
        if key in step and step[key]:
            return str(step[key])
    return _action_header(str(step.get("action") or ""))


def _is_reproduction_step(step: Dict[str, Any]) -> bool:
    """Determine whether a step appears to create reproduction code."""
    raw_action = str(
        step.get("action")
        or step.get("tool")
        or step.get("command")
        or ""
    )
    header = _action_header(raw_action)
    if not _is_creation_action(header):
        return False

    filenames = _extract_filenames(header)
    if filenames and _has_keyword(" ".join(filenames), FILE_KEYWORDS):
        return True

    if _has_keyword(header, FILE_KEYWORDS):
        return True

    thought_text = str(step.get("thought") or "")
    if thought_text and _has_keyword(thought_text, THOUGHT_KEYWORDS):
        return True

    return False


def locate_reproduction_code(instance_id: str) -> List[int]:
    """
    Return 1-based step indices where reproduction code is created.

    Heuristic: look for steps whose action appears to create/write a file and
    whose filename (or, failing that, accompanying thought) references terms
    like repro/reproduce/debug/test/pytest/unit/minimal.
    """
    instance_dir = find_instance_dir(instance_id)
    traj_path = instance_dir / f"{instance_id}.traj"
    if not traj_path.is_file():
        raise FileNotFoundError(f"Trajectory file not found: {traj_path}")

    steps = load_trajectory(traj_path)
    matches = []
    for idx, step in enumerate(steps, start=1):
        if _is_reproduction_step(step):
            matches.append(idx)

    sorted_matches = sorted(set(matches))
    _append_log(instance_id, sorted_matches)
    return sorted_matches


def locate_search(instance_id: str) -> List[int]:
    """
    Return 1-based step indices where the agent searches/navigates the codebase.

    Heuristic:
    - Tool names like find_file/search_file/search_dir.
    - Shell commands containing search/navigation verbs: find, grep, rg, fd, ls,
      cd, cat, tree, ag, pwd.
    - str_replace_editor view commands (browsing files) count as navigation.
    """
    instance_dir = find_instance_dir(instance_id)
    traj_path = instance_dir / f"{instance_id}.traj"
    if not traj_path.is_file():
        raise FileNotFoundError(f"Trajectory file not found: {traj_path}")

    steps = load_trajectory(traj_path)
    search_tool_names = {"find_file", "search_file", "search_dir"}
    shell_markers = re.compile(r"\b(find|grep|rg|fd|ls|cd|cat|tree|ag|pwd)\b")
    matches: List[int] = []

    for idx, step in enumerate(steps, start=1):
        tool_name = _get_tool_name(step).lower()
        command_text = _get_command_text(step)
        command_lower = command_text.lower()

        # A: Explicit search tools.
        if tool_name in search_tool_names:
            matches.append(idx)
            continue

        # C: File viewing via editor.
        if tool_name == "str_replace_editor" and "view" in command_lower:
            matches.append(idx)
            continue

        # B: Shell commands with search/navigation verbs.
        if shell_markers.search(command_lower):
            matches.append(idx)
            continue

    unique_matches = sorted(set(matches))
    _append_log_line(LOG_SEARCH_FILE, instance_id, unique_matches)
    return unique_matches


def locate_tool_use(instance_id: str) -> Dict[str, int]:
    """
    Return a mapping of tool name -> number of invocations for this trajectory.

    Tool name is derived from the explicit tool fields (tool/tool_name/name) or,
    if absent, from the first token of the action/command text. Subcommands
    (e.g., str_replace_editor view/create) are collapsed to the base tool name.
    """
    instance_dir = find_instance_dir(instance_id)
    traj_path = instance_dir / f"{instance_id}.traj"
    if not traj_path.is_file():
        raise FileNotFoundError(f"Trajectory file not found: {traj_path}")

    steps = load_trajectory(traj_path)
    counts: Dict[str, int] = {}

    for step in steps:
        tool_name = _get_tool_name(step).strip()
        if not tool_name:
            continue
        counts[tool_name] = counts.get(tool_name, 0) + 1

    sorted_counts: Dict[str, int] = {k: counts[k] for k in sorted(counts)}
    _append_log_line(LOG_TOOL_FILE, instance_id, sorted_counts)
    return sorted_counts


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze SWE-Agent trajectories.")
    parser.add_argument(
        "command",
        choices=["locate_reproduction_code", "locate_search", "locate_tool_use"],
        help="Analysis function to run",
    )
    parser.add_argument("instance_id", help="Instance id, e.g., sympy__sympy-13877")
    return parser


def main(argv: List[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "locate_reproduction_code":
        result = locate_reproduction_code(args.instance_id)
    elif args.command == "locate_search":
        result = locate_search(args.instance_id)
    elif args.command == "locate_tool_use":
        result = locate_tool_use(args.instance_id)
    else:  # pragma: no cover - argparse guards choices
        raise ValueError(f"Unknown command {args.command}")

    print(result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
