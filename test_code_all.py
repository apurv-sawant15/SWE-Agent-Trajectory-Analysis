"""
Sweep all trajectories and run locate_* sanity checks.

How to run:
    python3 test_code_all.py

How to interpret:
- Each line shows: instance id, model label, counts for reproduction/search steps, and tool usage mapping.
- Warnings flag anomalies worth checking: zero tool calls, search steps dominating the trajectory, or out-of-range reproduction indices.
- ERROR lines mean the analysis failed for that trajectory; inspect the message or the underlying .traj file.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from code import (
    CLAUDE_DIR,
    QWEN_DIR,
    REPO_ROOT,
    load_trajectory,
    locate_reproduction_code,
    locate_search,
    locate_tool_use,
)


def iter_instances() -> Iterable[Tuple[str, str, Path]]:
    """Yield (label, instance_id, traj_path) for all available instances."""
    roots = [("claude", CLAUDE_DIR), ("qwen", QWEN_DIR)]
    for label, root in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            instance_id = child.name
            traj_path = child / f"{instance_id}.traj"
            if traj_path.is_file():
                yield label, instance_id, traj_path


def format_summary_line(
    instance_id: str,
    label: str,
    reproduction_steps: Sequence[int],
    search_steps: Sequence[int],
    tool_counts: Dict[str, int],
) -> str:
    return (
        f"{instance_id} ({label}) -> "
        f"repro_steps={len(reproduction_steps)}, "
        f"search_steps={len(search_steps)}, "
        f"tools={tool_counts}"
    )


def collect_warnings(
    reproduction_steps: Sequence[int],
    search_steps: Sequence[int],
    tool_counts: Dict[str, int],
    total_steps: int,
) -> List[str]:
    warnings: List[str] = []
    if not tool_counts:
        warnings.append("WARNING: zero tool calls reported")

    if total_steps:
        ratio = len(search_steps) / total_steps
        if ratio > 0.8:
            warnings.append(
                f"WARNING: search steps high ({len(search_steps)}/{total_steps})"
            )

    if total_steps:
        out_of_range = [idx for idx in reproduction_steps if idx < 1 or idx > total_steps]
        if out_of_range:
            warnings.append(
                f"WARNING: reproduction indices out of range for {total_steps} steps ({out_of_range})"
            )

    return warnings


def analyze_instance(label: str, instance_id: str, traj_path: Path) -> Tuple[str, List[str]]:
    """Run locate_* functions with basic safety and warning checks."""
    try:
        steps = load_trajectory(traj_path)
        reproduction_steps = locate_reproduction_code(instance_id)
        search_steps = locate_search(instance_id)
        tool_counts = locate_tool_use(instance_id)
    except Exception as exc:
        short_error = f"{exc}"
        return f"{instance_id} ({label}) -> ERROR: {short_error}", []

    summary = format_summary_line(instance_id, label, reproduction_steps, search_steps, tool_counts)
    warnings = collect_warnings(reproduction_steps, search_steps, tool_counts, len(steps))
    return summary, warnings


def main() -> None:
    report_lines: List[str] = []
    for label, instance_id, traj_path in iter_instances():
        summary, warnings = analyze_instance(label, instance_id, traj_path)
        print(summary)
        report_lines.append(summary)
        for warning in warnings:
            warning_line = f"  {warning}"
            print(warning_line)
            report_lines.append(warning_line)

    if report_lines:
        report_path = REPO_ROOT / "test_code_all_report.txt"
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
