#!/usr/bin/env python3
"""Fetch data from bitable for weekly report generation.

Usage:
  python3 fetch_data.py --config weekly-report-config.json \
    --period-start 2026-05-08 --period-end 2026-05-14 \
    --output-dir /tmp/weekly-report/fetched/
"""
import argparse, json, subprocess, sys, shutil, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))

def check_lark_cli():
    if not shutil.which("lark-cli"):
        print("ERROR: lark-cli not found. Install: npm install -g lark-cli", file=sys.stderr)
        sys.exit(1)

def call_api(method, path, data=None, params=None, identity="user"):
    cmd = ["lark-cli", "api", method, path]
    if data:
        cmd += ["--data", json.dumps(data, ensure_ascii=False)]
    if params:
        cmd += ["--params", json.dumps(params)]
    cmd += ["--as", identity]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"API error: {result.stderr[:300]}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Non-JSON: {result.stdout[:200]}", file=sys.stderr)
        return None

def search_records(app_token, table_id, field_names, filter_cond=None, identity="user"):
    body = {"field_names": field_names}
    if filter_cond:
        body["filter"] = filter_cond
    all_items = []
    page_token = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        resp = call_api("POST",
                        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                        data=body, params=params, identity=identity)
        if not resp or "data" not in resp:
            break
        items = resp["data"].get("items", [])
        all_items.extend(items)
        page_token = resp["data"].get("has_more") and resp["data"].get("page_token")
        if not page_token:
            break
    return all_items

def dt_to_ms(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=CST)
    return int(dt.timestamp() * 1000)

def ms_to_dt(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=CST)

def get_field_val(record, field_name):
    return record.get("fields", {}).get(field_name)

def get_text(record, field_name):
    v = get_field_val(record, field_name)
    if isinstance(v, list) and v:
        return v[0].get("text", "")
    return str(v) if v is not None else ""

def get_date_ms(record, field_name):
    v = get_field_val(record, field_name)
    if v is None:
        return None
    return int(v)

def get_person_ids(record, field_name):
    v = get_field_val(record, field_name)
    if not v or not isinstance(v, list):
        return []
    return [p.get("id", "") for p in v if isinstance(p, dict)]

def get_link_ids(record, field_name):
    v = get_field_val(record, field_name)
    if isinstance(v, dict):
        return v.get("link_record_ids") or []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []

def in_range(ms_val, start_ms, end_ms):
    if ms_val is None:
        return False
    return start_ms <= ms_val <= end_ms

def fetch_projects(config, identity):
    app = config["app_token"]
    tbl = config["tables"]["project"]
    fld = config["fields"]["project"]
    field_names = [fld[k] for k in ["name", "status", "region", "focus", "pm", "dl", "amount", "risk"]
                   if k in fld]
    items = search_records(app, tbl, field_names, identity=identity)
    projects = []
    for item in items:
        projects.append({
            "record_id": item["record_id"],
            "name": get_text(item, fld["name"]),
            "status": get_text(item, fld.get("status", "")),
            "region": get_text(item, fld.get("region", "")),
            "focus": get_text(item, fld.get("focus", "")),
            "pm": get_person_ids(item, fld.get("pm", "")),
            "dl": get_person_ids(item, fld.get("dl", "")),
            "amount": get_field_val(item, fld.get("amount", "")),
            "risk": get_text(item, fld.get("risk", "")),
        })
    return projects

def fetch_milestones(config, identity, ms_start, ms_end):
    app = config["app_token"]
    tbl = config["tables"]["milestone"]
    fld = config["fields"]["milestone"]
    field_names = [fld[k] for k in ["name", "status", "payment_type", "amount", "plan_date",
                                     "actual_date", "deviate", "project", "dl"]
                   if k in fld]
    items = search_records(app, tbl, field_names, identity=identity)
    milestones = []
    for item in items:
        plan_ms = get_date_ms(item, fld.get("plan_date", ""))
        actual_ms = get_date_ms(item, fld.get("actual_date", ""))
        status = get_text(item, fld.get("status", ""))
        is_in_window = (plan_ms is not None and ms_start <= plan_ms <= ms_end)
        is_achieved_in_period = (actual_ms is not None and in_range(actual_ms, ms_start, ms_end))
        if status == "进行中" and is_in_window:
            pass
        elif is_achieved_in_period:
            pass
        else:
            continue
        milestones.append({
            "record_id": item["record_id"],
            "name": get_text(item, fld["name"]),
            "status": status,
            "payment_type": get_text(item, fld.get("payment_type", "")),
            "amount": get_field_val(item, fld.get("amount", "")),
            "plan_date": plan_ms,
            "actual_date": actual_ms,
            "deviate": get_field_val(item, fld.get("deviate", "")),
            "project_ids": get_link_ids(item, fld.get("project", "")),
            "dl": get_person_ids(item, fld.get("dl", "")),
        })
    return milestones

def fetch_tasks(config, identity, period_start_ms, period_end_ms):
    app = config["app_token"]
    tbl = config["tables"]["task"]
    fld = config["fields"]["task"]
    field_names = [fld[k] for k in ["name", "type", "status", "progress", "owner",
                                     "start", "plan_end", "actual_end", "project"]
                   if k in fld]
    items = search_records(app, tbl, field_names, identity=identity)
    tasks = []
    for item in items:
        start_ms = get_date_ms(item, fld.get("start", ""))
        plan_end_ms = get_date_ms(item, fld.get("plan_end", ""))
        in_period = in_range(start_ms, period_start_ms, period_end_ms) or \
                    in_range(plan_end_ms, period_start_ms, period_end_ms)
        if not in_period:
            continue
        tasks.append({
            "record_id": item["record_id"],
            "name": get_text(item, fld["name"]),
            "type": get_text(item, fld.get("type", "")),
            "status": get_text(item, fld.get("status", "")),
            "progress": get_field_val(item, fld.get("progress", "")),
            "owner": get_person_ids(item, fld.get("owner", "")),
            "start": start_ms,
            "plan_end": plan_end_ms,
            "actual_end": get_date_ms(item, fld.get("actual_end", "")),
            "project_ids": get_link_ids(item, fld.get("project", "")),
        })
    return tasks

def fetch_issues(config, identity, period_start_ms, period_end_ms):
    app = config["app_token"]
    tbl = config["tables"]["issue"]
    fld = config["fields"]["issue"]
    field_names = [fld[k] for k in ["description", "status", "level", "type", "product",
                                     "created", "dev", "project"]
                   if k in fld]
    items = search_records(app, tbl, field_names, identity=identity)
    shelved = config.get("enums", {}).get("shelved_status", "搁置")
    issues = []
    for item in items:
        created_ms = get_date_ms(item, fld.get("created", ""))
        if not in_range(created_ms, period_start_ms, period_end_ms):
            continue
        status = get_text(item, fld.get("status", ""))
        if status == shelved:
            continue
        issues.append({
            "record_id": item["record_id"],
            "description": get_text(item, fld["description"]),
            "status": status,
            "level": get_text(item, fld.get("level", "")),
            "type": get_text(item, fld.get("type", "")),
            "product": get_field_val(item, fld.get("product", "")),
            "created": created_ms,
            "dev": get_person_ids(item, fld.get("dev", "")),
            "project_ids": get_link_ids(item, fld.get("project", "")),
        })
    return issues

def fetch_changes(config, identity, period_start_ms, period_end_ms):
    app = config["app_token"]
    tbl = config["tables"]["change"]
    fld = config["fields"]["change"]
    field_names = [fld[k] for k in ["content", "status", "level", "type", "modules",
                                     "start", "end", "dev", "project"]
                   if k in fld]
    items = search_records(app, tbl, field_names, identity=identity)
    changes = []
    for item in items:
        start_ms = get_date_ms(item, fld.get("start", ""))
        if not in_range(start_ms, period_start_ms, period_end_ms):
            continue
        changes.append({
            "record_id": item["record_id"],
            "content": get_text(item, fld["content"]),
            "status": get_text(item, fld.get("status", "")),
            "level": get_text(item, fld.get("level", "")),
            "type": get_text(item, fld.get("type", "")),
            "modules": get_field_val(item, fld.get("modules", "")),
            "start": start_ms,
            "end": get_date_ms(item, fld.get("end", "")),
            "dev": get_person_ids(item, fld.get("dev", "")),
            "project_ids": get_link_ids(item, fld.get("project", "")),
        })
    return changes

def main():
    parser = argparse.ArgumentParser(description="Fetch bitable data for weekly report")
    parser.add_argument("--config", required=True, help="Path to weekly-report-config.json")
    parser.add_argument("--period-start", required=True, help="Period start date (YYYY-MM-DD)")
    parser.add_argument("--period-end", required=True, help="Period end date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="/tmp/weekly-report/fetched/", help="Output directory")
    parser.add_argument("--as", dest="identity", default="user", help="Identity (user/bot)")
    args = parser.parse_args()

    check_lark_cli()

    config = json.loads(Path(args.config).read_text())
    period_start_ms = dt_to_ms(args.period_start)
    period_end_ms = dt_to_ms(args.period_end)

    today = datetime.now(CST)
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ms_window_end = int((today + timedelta(days=50)).timestamp() * 1000)
    ms_window_start = int(month_start.timestamp() * 1000)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching data for period {args.period_start} ~ {args.period_end}")
    print(f"Milestone window: {month_start.strftime('%Y-%m-%d')} ~ {(today + timedelta(days=50)).strftime('%Y-%m-%d')}")

    print("  Fetching projects...")
    projects = fetch_projects(config, args.identity)
    Path(out_dir / "projects.json").write_text(json.dumps(projects, ensure_ascii=False, indent=2))
    print(f"    {len(projects)} projects")

    print("  Fetching milestones...")
    milestones = fetch_milestones(config, args.identity, ms_window_start, ms_window_end)
    Path(out_dir / "milestones.json").write_text(json.dumps(milestones, ensure_ascii=False, indent=2))
    print(f"    {len(milestones)} milestones")

    print("  Fetching tasks...")
    tasks = fetch_tasks(config, args.identity, period_start_ms, period_end_ms)
    Path(out_dir / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
    print(f"    {len(tasks)} tasks")

    print("  Fetching issues...")
    issues = fetch_issues(config, args.identity, period_start_ms, period_end_ms)
    Path(out_dir / "issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=2))
    print(f"    {len(issues)} issues")

    print("  Fetching changes...")
    changes = fetch_changes(config, args.identity, period_start_ms, period_end_ms)
    Path(out_dir / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2))
    print(f"    {len(changes)} changes")

    meta = {
        "period_start": args.period_start,
        "period_end": args.period_end,
        "period_start_ms": period_start_ms,
        "period_end_ms": period_end_ms,
        "milestone_window_start_ms": ms_window_start,
        "milestone_window_end_ms": ms_window_end,
        "fetched_at": datetime.now(CST).isoformat(),
        "counts": {
            "projects": len(projects),
            "milestones": len(milestones),
            "tasks": len(tasks),
            "issues": len(issues),
            "changes": len(changes),
        }
    }
    Path(out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"Done. Output: {out_dir}")

if __name__ == "__main__":
    main()
