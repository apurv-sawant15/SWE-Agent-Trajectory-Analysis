"""
Spot-check script for detailed inspection of locate_* outputs on a single instance.

How to run:
    python3 test_code_spotcheck.py sympy__sympy-13877

What you get:
- Basic counts: total steps, reproduction/search indices, tool usage map.
- Detailed listings for each reproduction and search step (thought, tool, command, files).
- First N steps (default 20) with tool/command headers to eyeball the tool-use heuristic.

What to look for:
- Are repro/search indices pointing at the right actions?
- Are any obvious repro steps missing?
- Are non-search actions being flagged as search?
- Do tool counts match the per-step tool headers?
"""

from __future__ import annotations

import argparse
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


def load_instance_steps(instance_id: str) -> List[Dict[str, Any]]:
    traj_path = find_instance_dir(instance_id) / f"{instance_id}.traj"
    return load_trajectory(traj_path)


def _clean_text(text: str, limit: int = 200) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "..."


def print_step_details(steps: Sequence[Dict[str, Any]], idx: int) -> None:
    if idx < 1 or idx > len(steps):
        print(f"  Step {idx} is out of range for {len(steps)} steps\n")
        return
    step = steps[idx - 1]
    thought = _clean_text(str(step.get("thought") or ""))
    tool = _get_tool_name(step) or "(unknown)"
    command = _get_command_text(step)
    files = _extract_filenames(str(step.get("action") or command))

    print(f"  Step {idx}:")
    if thought:
        print(f"    Thought: {thought}")
    print(f"    Tool: {tool}")
    if command:
        print(f"    Command: {command}")
    if files:
        print(f"    Files: {', '.join(files)}")
    print()


def spotcheck_instance(instance_id: str, max_tool_steps: int = 20) -> None:
    steps = load_instance_steps(instance_id)
    repro_steps = locate_reproduction_code(instance_id)
    search_steps = locate_search(instance_id)
    tool_counts = locate_tool_use(instance_id)

    print(f"Instance: {instance_id}")
    print(f"Total steps: {len(steps)}")
    print(f"Reproduction steps: {repro_steps}")
    print(f"Search steps: {search_steps}")
    print(f"Tool usage counts: {tool_counts}\n")

    if repro_steps:
        print("Reproduction step details:")
        for idx in repro_steps:
            print_step_details(steps, idx)
    else:
        print("Reproduction step details: (none)\n")

    if search_steps:
        print("Search step details:")
        for idx in search_steps:
            print_step_details(steps, idx)
    else:
        print("Search step details: (none)\n")

    print(f"First {min(max_tool_steps, len(steps))} steps (tool headers):")
    print_all_tools_by_step(instance_id, max_steps=max_tool_steps, steps=steps)


def print_all_tools_by_step(
    instance_id: str, max_steps: int | None = 20, steps: Sequence[Dict[str, Any]] | None = None
) -> None:
    steps = steps or load_instance_steps(instance_id)
    limit = len(steps) if max_steps is None else min(max_steps, len(steps))
    for idx in range(1, limit + 1):
        step = steps[idx - 1]
        tool = _get_tool_name(step) or "(unknown)"
        command = _get_command_text(step)
        print(f"  {idx}: tool={tool} | command={command}")
    print()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spot-check a single SWE-Agent trajectory.")
    parser.add_argument("instance_id", help="Instance id, e.g., sympy__sympy-13877")
    parser.add_argument(
        "--max-tool-steps",
        type=int,
        default=20,
        help="Number of initial steps to list with tool headers (default: 20)",
    )
    return parser


def main(argv: List[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    spotcheck_instance(args.instance_id, max_tool_steps=args.max_tool_steps)


if __name__ == "__main__":
    main()

# Heuristic notes / TODOs (do not change code.py yet):
# - Search detection counts any command with navigation verbs; consider ignoring plain "cd && python" runs.
# - Reproduction detection could optionally look for python invocations of newly created files to boost confidence.
