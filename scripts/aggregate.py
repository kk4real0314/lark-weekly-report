#!/usr/bin/env python3
"""Aggregate fetched data by project dimension.

Usage:
  python3 aggregate.py --input-dir /tmp/weekly-report/fetched/ \
    --config weekly-report-config.json \
    --output /tmp/weekly-report/aggregated.json
"""
import argparse, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

CST = timezone(timedelta(hours=8))

def ms_to_date(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=CST).strftime("%Y/%m/%d")

def load_json(path):
    return json.loads(Path(path).read_text())

def main():
    parser = argparse.ArgumentParser(description="Aggregate fetched data by project")
    parser.add_argument("--input-dir", required=True, help="Directory with fetched JSON files")
    parser.add_argument("--config", required=True, help="Path to weekly-report-config.json")
    parser.add_argument("--output", default="/tmp/weekly-report/aggregated.json", help="Output path")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    in_dir = Path(args.input_dir)

    projects = load_json(in_dir / "projects.json")
    milestones = load_json(in_dir / "milestones.json")
    tasks = load_json(in_dir / "tasks.json")
    issues = load_json(in_dir / "issues.json")
    changes = load_json(in_dir / "changes.json")
    meta = load_json(in_dir / "meta.json")

    inactive_statuses = config.get("enums", {}).get("inactive_statuses", [])
    p0_val = config.get("enums", {}).get("issue_p0", "P0 关键路径问题")
    p1_val = config.get("enums", {}).get("issue_p1", "P1 ")

    proj_by_id = {p["record_id"]: p for p in projects}

    active_projects = [p for p in projects if p["status"] not in inactive_statuses]

    proj_milestones = defaultdict(list)
    for m in milestones:
        for pid in m.get("project_ids", []):
            proj_milestones[pid].append(m)

    proj_tasks = defaultdict(list)
    for t in tasks:
        for pid in t.get("project_ids", []):
            proj_tasks[pid].append(t)

    proj_issues = defaultdict(list)
    for i in issues:
        for pid in i.get("project_ids", []):
            proj_issues[pid].append(i)

    proj_changes = defaultdict(list)
    for c in changes:
        for pid in c.get("project_ids", []):
            proj_changes[pid].append(c)

    active_project_ids = {p["record_id"] for p in active_projects}
    active_with_activity = []
    for p in active_projects:
        pid = p["record_id"]
        has_activity = (len(proj_milestones.get(pid, [])) > 0 or
                       len(proj_tasks.get(pid, [])) > 0 or
                       len(proj_issues.get(pid, [])) > 0 or
                       len(proj_changes.get(pid, [])) > 0)
        if has_activity:
            active_with_activity.append(p)

    p0_issues = [i for i in issues if i["level"] == p0_val]
    p1_issues = [i for i in issues if i["level"] == p1_val]

    next_week_start_ms = meta["period_end_ms"] + 1
    next_week_end_ms = next_week_start_ms + 7 * 86400 * 1000
    next_week_tasks = [t for t in tasks
                       if (t.get("start") is not None and next_week_start_ms <= t["start"] <= next_week_end_ms)
                       or (t.get("plan_end") is not None and next_week_start_ms <= t["plan_end"] <= next_week_end_ms)]

    overdue_tasks = [t for t in tasks
                     if t.get("plan_end") is not None
                     and t["plan_end"] <= meta["period_end_ms"]
                     and t["status"] not in ("已完成", "延期完成")]

    result = {
        "meta": meta,
        "summary": {
            "total_projects": len(projects),
            "active_projects": len(active_projects),
            "active_with_activity": len(active_with_activity),
            "total_milestones": len(milestones),
            "total_tasks": len(tasks),
            "total_issues": len(issues),
            "p0_issues": len(p0_issues),
            "p1_issues": len(p1_issues),
            "total_changes": len(changes),
            "next_week_tasks": len(next_week_tasks),
            "overdue_tasks": len(overdue_tasks),
        },
        "active_with_activity": [
            {
                "record_id": p["record_id"],
                "name": p["name"],
                "status": p["status"],
                "region": p["region"],
                "focus": p["focus"],
                "risk": p["risk"],
            }
            for p in active_with_activity
        ],
        "by_project": {},
        "all_milestones": [
            {**m, "plan_date_str": ms_to_date(m.get("plan_date")),
             "actual_date_str": ms_to_date(m.get("actual_date")),
             "project_name": proj_by_id.get(m["project_ids"][0], {}).get("name", "") if m.get("project_ids") else ""}
            for m in milestones
        ],
        "all_tasks": [
            {**t, "start_str": ms_to_date(t.get("start")),
             "plan_end_str": ms_to_date(t.get("plan_end")),
             "project_name": proj_by_id.get(t["project_ids"][0], {}).get("name", "") if t.get("project_ids") else ""}
            for t in tasks
        ],
        "p0_issues": p0_issues,
        "p1_issues": p1_issues,
        "all_changes": [
            {**c, "start_str": ms_to_date(c.get("start")),
             "end_str": ms_to_date(c.get("end")),
             "project_name": proj_by_id.get(c["project_ids"][0], {}).get("name", "") if c.get("project_ids") else ""}
            for c in changes
        ],
        "next_week_tasks": [
            {**t, "start_str": ms_to_date(t.get("start")),
             "plan_end_str": ms_to_date(t.get("plan_end")),
             "project_name": proj_by_id.get(t["project_ids"][0], {}).get("name", "") if t.get("project_ids") else ""}
            for t in next_week_tasks
        ],
        "overdue_tasks": overdue_tasks,
    }

    for p in active_with_activity:
        pid = p["record_id"]
        result["by_project"][p["name"]] = {
            "project": {"name": p["name"], "status": p["status"], "region": p["region"],
                        "focus": p["focus"], "risk": p["risk"]},
            "milestones": proj_milestones.get(pid, []),
            "tasks": proj_tasks.get(pid, []),
            "issues": proj_issues.get(pid, []),
            "changes": proj_changes.get(pid, []),
        }

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"Aggregated: {result['summary']}")
    print(f"Output: {args.output}")

if __name__ == "__main__":
    main()
