#!/usr/bin/env python3
"""Scan bitable structure for +init.

Usage:
  python3 scan_bitable.py --app-token TOKEN [--output scan_result.json] [--as user]
"""
import argparse, json, subprocess, sys, shutil
from pathlib import Path

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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"API error: {result.stderr[:300]}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Non-JSON: {result.stdout[:200]}", file=sys.stderr)
        return None

def scan_tables(app_token, identity):
    resp = call_api("GET", f"/open-apis/bitable/v1/apps/{app_token}/tables", identity=identity)
    if not resp or "data" not in resp:
        print("Failed to list tables", file=sys.stderr)
        return []
    items = resp["data"].get("items", [])
    tables = []
    for t in items:
        tables.append({"table_id": t.get("table_id", ""), "name": t.get("name", "")})
    return tables

def scan_fields(app_token, table_id, identity):
    resp = call_api("GET", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields", identity=identity)
    if not resp or "data" not in resp:
        return []
    items = resp["data"].get("items", [])
    fields = []
    type_map = {1: "文本", 2: "数字", 3: "单选", 4: "多选", 5: "日期", 7: "数字",
                11: "人员", 13: "电话", 14: "URL", 15: "超链接", 17: "双向关联",
                18: "公式", 21: "单向关联", 22: "分组", 23: "创建时间", 24: "最后更新时间"}
    for f in items:
        finfo = {
            "field_id": f.get("field_id", ""),
            "field_name": f.get("field_name", ""),
            "type": f.get("type", 0),
            "type_name": type_map.get(f.get("type", 0), "unknown"),
        }
        prop = f.get("property") or {}
        if "options" in prop:
            finfo["options"] = [o.get("name", "") for o in prop["options"]]
        fields.append(finfo)
    return fields

def sample_enum_values(app_token, table_id, field_name, identity, limit=20):
    resp = call_api("POST", f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                    data={"field_names": [field_name]}, params={"page_size": limit}, identity=identity)
    if not resp or "data" not in resp:
        return []
    items = resp["data"].get("items", [])
    vals = set()
    for item in items:
        v = item.get("fields", {}).get(field_name)
        if v is None:
            continue
        if isinstance(v, list):
            for el in v:
                if isinstance(el, dict) and "text" in el:
                    vals.add(el["text"])
                elif isinstance(el, str):
                    vals.add(el)
        elif isinstance(v, str):
            vals.add(v)
    return sorted(vals)

def main():
    parser = argparse.ArgumentParser(description="Scan bitable tables and fields")
    parser.add_argument("--app-token", required=True, help="Bitable app_token")
    parser.add_argument("--output", default="scan_result.json", help="Output JSON path")
    parser.add_argument("--as", dest="identity", default="user", help="Identity (user/bot)")
    args = parser.parse_args()

    check_lark_cli()

    print(f"Scanning bitable {args.app_token}...")
    tables = scan_tables(args.app_token, args.identity)
    if not tables:
        print("No tables found", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(tables)} tables")

    result = {"app_token": args.app_token, "tables": []}

    for t in tables:
        print(f"  Scanning fields for: {t['name']} ({t['table_id']})")
        fields = scan_fields(args.app_token, t["table_id"], args.identity)

        for f in fields:
            if f.get("options"):
                f["sample_values"] = f["options"]
            elif f["type_name"] in ("单选", "多选"):
                f["sample_values"] = sample_enum_values(
                    args.app_token, t["table_id"], f["field_name"], args.identity)

        result["tables"].append({
            "table_id": t["table_id"],
            "name": t["name"],
            "fields": fields,
        })

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Scan result saved to {args.output}")
    print(f"  {len(tables)} tables, {sum(len(t['fields']) for t in result['tables'])} fields total")

if __name__ == "__main__":
    main()
