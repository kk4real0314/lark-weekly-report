#!/usr/bin/env python3
"""Generate weekly report document content as structured JSON.

This script outputs structured JSON for each chapter. The AI then uses this
JSON + report-rules.md to assemble DocxXML and write to Feishu.

Usage:
  python3 generate_doc.py --input /tmp/weekly-report/aggregated.json \
    --config weekly-report-config.json \
    --charts-dir /tmp/weekly-report/charts/ \
    --output /tmp/weekly-report/doc_content.json
"""
import argparse, json, sys, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))

def check_lark_cli():
    if not shutil.which("lark-cli"):
        print("ERROR: lark-cli not found. Install: npm install -g lark-cli", file=sys.stderr)
        sys.exit(1)

def ms_to_date(ms):
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=CST).strftime("%Y/%m/%d")

def ms_to_datetime(ms):
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=CST).strftime("%Y/%m/%d %H:%M")

def format_person(oid_list, person_map=None):
    if not oid_list:
        return ""
    if person_map:
        names = [person_map.get(oid, oid) for oid in oid_list]
    else:
        names = oid_list
    return ", ".join(names)

def main():
    parser = argparse.ArgumentParser(description="Generate weekly report document content")
    parser.add_argument("--input", required=True, help="Aggregated JSON path")
    parser.add_argument("--config", required=True, help="Config JSON path")
    parser.add_argument("--charts-dir", default="/tmp/weekly-report/charts/", help="Charts directory")
    parser.add_argument("--output", default="/tmp/weekly-report/doc_content.json", help="Output JSON path")
    args = parser.parse_args()

    check_lark_cli()

    data = json.loads(Path(args.input).read_text())
    config = json.loads(Path(args.config).read_text())
    charts_dir = Path(args.charts_dir)

    period_start = data["meta"]["period_start"]
    period_end = data["meta"]["period_end"]
    reporter = config.get("reporter", "")
    summary = data["summary"]

    period_start_fmt = ms_to_date(data["meta"]["period_start_ms"])
    period_end_fmt = ms_to_date(data["meta"]["period_end_ms"])

    # Chapter 1: Project Analysis
    ch1_projects = []
    for p in data["active_with_activity"]:
        ch1_projects.append({
            "name": p["name"],
            "status": p["status"],
            "region": p["region"],
            "focus": p["focus"],
            "risk": p["risk"],
        })

    # Chapter 2: Milestone Analysis
    ch2_milestones = []
    for m in data["all_milestones"]:
        ch2_milestones.append({
            "project": m.get("project_name", ""),
            "payment_type": m.get("payment_type", ""),
            "status": m.get("status", ""),
            "plan_date": ms_to_date(m.get("plan_date")),
            "actual_date": ms_to_date(m.get("actual_date")),
            "amount": m.get("amount", 0),
            "deviate": m.get("deviate"),
        })

    # Chapter 3: This Week Tasks
    ch3_tasks = []
    for t in data["all_tasks"]:
        ch3_tasks.append({
            "project": t.get("project_name", ""),
            "name": t["name"],
            "type": t.get("type", ""),
            "status": t.get("status", ""),
            "progress": t.get("progress", 0),
            "start": ms_to_date(t.get("start")),
            "plan_end": ms_to_date(t.get("plan_end")),
        })

    # Chapter 4: Next Week Tasks
    ch4_tasks = []
    for t in data["next_week_tasks"]:
        ch4_tasks.append({
            "project": t.get("project_name", ""),
            "name": t["name"],
            "type": t.get("type", ""),
            "status": t.get("status", ""),
            "start": ms_to_date(t.get("start")),
            "plan_end": ms_to_date(t.get("plan_end")),
        })

    # Chapter 5: Issue Analysis
    ch5_p0 = []
    for i in data["p0_issues"]:
        ch5_p0.append({
            "status": i.get("status", ""),
            "type": i.get("type", ""),
            "description": i.get("description", ""),
            "product": i.get("product", ""),
            "created": ms_to_date(i.get("created")),
            "dev": format_person(i.get("dev", [])),
        })
    ch5_p1 = []
    for i in data["p1_issues"]:
        ch5_p1.append({
            "status": i.get("status", ""),
            "type": i.get("type", ""),
            "description": i.get("description", ""),
            "product": i.get("product", ""),
            "created": ms_to_date(i.get("created")),
            "dev": format_person(i.get("dev", [])),
        })

    # Chapter 6: Change Analysis
    ch6_changes = []
    for c in data["all_changes"]:
        ch6_changes.append({
            "project": c.get("project_name", ""),
            "content": c.get("content", ""),
            "status": c.get("status", ""),
            "level": c.get("level", ""),
            "type": c.get("type", ""),
            "modules": c.get("modules", ""),
            "start": ms_to_datetime(c.get("start")),
            "end": ms_to_datetime(c.get("end")),
        })

    # Charts
    mmdd = period_end_fmt.replace("/", "").replace("-", "")[-4:]
    chart_files = {
        "project": str(charts_dir / f"chart_project_{mmdd}.png"),
        "gantt": str(charts_dir / f"chart_gantt_{mmdd}.png"),
        "issue": str(charts_dir / f"chart_issue_{mmdd}.png"),
    }

    result = {
        "title": f"华北区项目周报｜{period_start_fmt} ~ {period_end_fmt}｜{reporter}",
        "period": {"start": period_start_fmt, "end": period_end_fmt},
        "summary": summary,
        "ch1_projects": ch1_projects,
        "ch2_milestones": ch2_milestones,
        "ch3_tasks": ch3_tasks,
        "ch4_tasks": ch4_tasks,
        "ch5_p0": ch5_p0,
        "ch5_p1": ch5_p1,
        "ch6_changes": ch6_changes,
        "chart_files": chart_files,
        "config": {
            "app_token": config["app_token"],
            "folder_token": config.get("output", {}).get("folder_token", ""),
            "ledger_table": config.get("tables", {}).get("ledger"),
            "ledger_fields": config.get("fields", {}).get("ledger", {}),
        },
    }

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"Document content generated: {args.output}")
    print(f"  Title: {result['title']}")
    print(f"  Ch1: {len(ch1_projects)} projects, Ch2: {len(ch2_milestones)} milestones")
    print(f"  Ch3: {len(ch3_tasks)} tasks, Ch4: {len(ch4_tasks)} next-week tasks")
    print(f"  Ch5: {len(ch5_p0)} P0 + {len(ch5_p1)} P1 issues, Ch6: {len(ch6_changes)} changes")
    print(f"\nNext step: AI reads this JSON + report-rules.md, assembles DocxXML and writes to Feishu.")

if __name__ == "__main__":
    main()
