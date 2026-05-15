#!/usr/bin/env python3
"""Generate 3 charts for weekly report.

Usage:
  python3 generate_charts.py --input /tmp/weekly-report/aggregated.json \
    --output-dir /tmp/weekly-report/charts/
"""
import argparse, json, sys, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))

def check_matplotlib():
    try:
        import matplotlib
        return True
    except ImportError:
        print("ERROR: matplotlib not found.", file=sys.stderr)
        print("Install: python3 -m pip install matplotlib", file=sys.stderr)
        print("Or with venv: python3 -m venv /tmp/feishu-weekly/venv && /tmp/feishu-weekly/venv/bin/pip install matplotlib", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate weekly report charts")
    parser.add_argument("--input", required=True, help="Aggregated JSON path")
    parser.add_argument("--output-dir", default="/tmp/weekly-report/charts/", help="Output directory")
    args = parser.parse_args()

    if not check_matplotlib():
        sys.exit(1)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False

    data = json.loads(Path(args.input).read_text())
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    period_end_str = data["meta"]["period_end"]
    mmdd = period_end_str.replace("/", "").replace("-", "")[-4:]

    summary = data["summary"]
    active_projects = data["active_with_activity"]

    # Chart 1: Project status pie
    print("  Generating project status pie chart...")
    status_counts = {}
    for p in active_projects:
        s = p["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    if status_counts:
        fig, ax = plt.subplots(figsize=(10, 7))
        labels = list(status_counts.keys())
        sizes = list(status_counts.values())
        color_map = {"持续服务阶段": "#4CAF50", "终验": "#FF9800", "初验": "#2196F3",
                     "维保合同": "#9C27B0", "进行中": "#2196F3", "阶段验收": "#FF9800"}
        colors = [color_map.get(l, "#607D8B") for l in labels]
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.0f%%',
                                           startangle=90, textprops={'fontsize': 11})
        ax.set_title(f"活跃项目状态分布（{len(active_projects)}个）", fontsize=14, fontweight='bold')
        fig.tight_layout()
        fig.savefig(out_dir / f"chart_project_{mmdd}.png", dpi=200)
        plt.close(fig)

    # Chart 2: Milestone gantt
    print("  Generating milestone gantt chart...")
    milestones = data["all_milestones"]
    if milestones:
        today = datetime.now(CST).date()
        sorted_ms = sorted(milestones, key=lambda m: m.get("plan_date") or 0)
        fig, ax = plt.subplots(figsize=(16, max(6, len(sorted_ms) * 0.4)))
        y_labels = []
        for i, m in enumerate(sorted_ms):
            plan_ms = m.get("plan_date")
            if plan_ms is None:
                continue
            plan_date = datetime.fromtimestamp(plan_ms / 1000, tz=CST).date()
            amount = m.get("amount", 0) or 0
            label = f"{m.get('project_name', '')}-{m.get('payment_type', '')}"
            if amount:
                label += f" ({amount}万)"
            y_labels.append(label)
            days_to_due = (plan_date - today).days
            if days_to_due <= 14:
                color = "#FF5722"
            elif days_to_due <= 30:
                color = "#FF9800"
            else:
                color = "#4CAF50"
            bar_len = max(days_to_due, 1)
            ax.barh(i, bar_len, left=today, height=0.6, color=color, alpha=0.8)
            ax.text(plan_date, i, plan_date.strftime("%m/%d"), va='center', ha='left', fontsize=8)

        if y_labels:
            ax.set_yticks(range(len(y_labels)))
            ax.set_yticklabels(y_labels, fontsize=9)
        ax.axvline(x=today, color='red', linestyle='--', linewidth=1, label='今天')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
        fig.autofmt_xdate()
        ms_start_str = ms_to_date_str(data["meta"]["milestone_window_start_ms"])
        ms_end_str = ms_to_date_str(data["meta"]["milestone_window_end_ms"])
        ax.set_title(f"里程碑时间轴（{ms_start_str} ~ {ms_end_str}）", fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        fig.tight_layout()
        fig.savefig(out_dir / f"chart_gantt_{mmdd}.png", dpi=200)
        plt.close(fig)

    # Chart 3: Issue distribution bar
    print("  Generating issue distribution bar chart...")
    p0_issues = data["p0_issues"]
    p1_issues = data["p1_issues"]

    proj_p0 = {}
    for i in p0_issues:
        pname = i.get("project_name", "未知")
        proj_p0[pname] = proj_p0.get(pname, 0) + 1
    proj_p1 = {}
    for i in p1_issues:
        pname = i.get("project_name", "未知")
        proj_p1[pname] = proj_p1.get(pname, 0) + 1

    all_projs = sorted(set(list(proj_p0.keys()) + list(proj_p1.keys())))
    if all_projs:
        fig, ax = plt.subplots(figsize=(10, 6))
        x = range(len(all_projs))
        p0_vals = [proj_p0.get(p, 0) for p in all_projs]
        p1_vals = [proj_p1.get(p, 0) for p in all_projs]
        width = 0.35
        bars1 = ax.bar([i - width/2 for i in x], p0_vals, width, label='P0', color='#FF5722')
        bars2 = ax.bar([i + width/2 for i in x], p1_vals, width, label='P1', color='#FF9800')
        for bar in bars1:
            if bar.get_height() > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), str(int(bar.get_height())),
                        ha='center', va='bottom', fontsize=9)
        for bar in bars2:
            if bar.get_height() > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), str(int(bar.get_height())),
                        ha='center', va='bottom', fontsize=9)
        ax.set_xticks(list(x))
        ax.set_xticklabels(all_projs, fontsize=9, rotation=15, ha='right')
        ax.set_title("未关闭问题分布（按项目）", fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        fig.tight_layout()
        fig.savefig(out_dir / f"chart_issue_{mmdd}.png", dpi=200)
        plt.close(fig)

    print(f"Charts saved to {out_dir}")
    print(f"  chart_project_{mmdd}.png, chart_gantt_{mmdd}.png, chart_issue_{mmdd}.png")

def ms_to_date_str(ms):
    if ms is None:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=CST).strftime("%Y/%m/%d")

if __name__ == "__main__":
    main()
