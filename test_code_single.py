"""
Quick harness for manually checking the locate_* functions on one trajectory.

How to run:
    python3 test_code_single.py

What to look for:
- Reproduction steps: creation commands that write repro/test scripts and match the PR scenario.
- Search steps: navigation/search commands (view/grep/ls/cd) that make sense for code exploration.
- Tool usage counts: tool prefixes in actions (e.g., str_replace_editor, cd) align with the per-step summaries.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from code import (
    _extract_filenames,
    _get_command_text,
    _get_tool_name,
    find_instance_dir,
    load_trajectory,
    locate_reproduction_code,
    locate_search,
    locate_tool_use,
)

INSTANCE_ID = "sympy__sympy-13877"


def load_instance_steps(instance_id: str) -> List[Dict[str, Any]]:
    """Load trajectory steps for a single instance using code.py helpers."""
    traj_path = find_instance_dir(instance_id) / f"{instance_id}.traj"
    return load_trajectory(traj_path)


def _clean_text(text: str, limit: int = 160) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + "..."


def print_step_summary(steps: Sequence[Dict[str, Any]], idx: int) -> None:
    """Print a concise summary for a 1-based step index."""
    if idx < 1 or idx > len(steps):
        print(f"Step {idx} is out of range for {len(steps)} steps\n")
        return

    step = steps[idx - 1]
    thought = _clean_text(str(step.get("thought") or ""))
    tool = _get_tool_name(step) or "(unknown)"
    command = _get_command_text(step)
    files = _extract_filenames(str(step.get("action") or command))

    print(f"Step {idx}:")
    if thought:
        print(f"  Thought: {thought}")
    print(f"  Tool: {tool}")
    if command:
        print(f"  Command: {command}")
    if files:
        print(f"  Files: {', '.join(files)}")
    print()


def inspect_reproduction_steps(
    instance_id: str, steps: Sequence[Dict[str, Any]] | None = None, matches: Iterable[int] | None = None
) -> None:
    """Locate reproduction steps and print per-step summaries."""
    steps = steps or load_instance_steps(instance_id)
    match_list = list(matches) if matches is not None else locate_reproduction_code(instance_id)

    print(f"\nReproduction steps for {instance_id}: {match_list}\n")
    for idx in match_list:
        print_step_summary(steps, idx)


def inspect_search_steps(
    instance_id: str, steps: Sequence[Dict[str, Any]] | None = None, matches: Iterable[int] | None = None
) -> None:
    """Locate search/navigation steps and print per-step summaries."""
    steps = steps or load_instance_steps(instance_id)
    match_list = list(matches) if matches is not None else locate_search(instance_id)

    print(f"\nSearch/navigation steps for {instance_id}: {match_list}\n")
    for idx in match_list:
        print_step_summary(steps, idx)


def print_raw_outputs(
    instance_id: str, reproduction: List[int], search: List[int], tool_counts: Dict[str, int]
) -> None:
    print(f"Instance: {instance_id}")
    print(f"Reproduction steps: {reproduction}")
    print(f"Search steps: {search}")
    print(f"Tool usage counts: {tool_counts}\n")


def main(instance_id: str = INSTANCE_ID) -> None:
    steps = load_instance_steps(instance_id)
    reproduction_steps = locate_reproduction_code(instance_id)
    search_steps = locate_search(instance_id)
    tool_counts = locate_tool_use(instance_id)

    print(f"Loaded {len(steps)} steps for {instance_id}\n")
    print_raw_outputs(instance_id, reproduction_steps, search_steps, tool_counts)

    inspect_reproduction_steps(instance_id, steps=steps, matches=reproduction_steps)
    inspect_search_steps(instance_id, steps=steps, matches=search_steps)


if __name__ == "__main__":
    main()

# Running this script prints the raw locate_* outputs followed by per-step summaries.
# Use the summaries to sanity-check that reproduction steps truly build repro/tests,
# search steps reflect navigation/grep/listing commands, and tool usage counts look reasonable.
