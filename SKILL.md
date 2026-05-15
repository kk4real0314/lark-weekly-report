---
name: lark-weekly-report
version: 2.0.0
description: "飞书多维表格项目周报生成：从飞书多维表格拉取项目/里程碑/任务/问题/变更数据，按7章结构生成项目分析周报并写入飞书文档。当用户说'出周报'、'生成周报'、'帮我写周报'、'项目周报'、'weekly report'、'项目进展'、'这周项目怎么样'、'项目状态汇总'、'milestone report'、'项目分析报告'时触发——即使用户没有明确说'周报'，只要涉及项目整体进展、里程碑跟踪、问题汇总等跨维度分析，都应使用本 skill。也适用于首次配置周报环境时说'初始化周报配置'、'周报+init'。"
metadata:
  requires:
    bins: ["lark-cli"]
    skills: ["lark-shared", "lark-base", "lark-doc"]
---

# 飞书多维表格项目周报

**CRITICAL — 开始前 MUST 先用 Read 工具读取 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)，其中包含认证、权限处理**

## 前置检查

每次使用前必须确认环境就绪：

```bash
lark-cli --version  # 确认 lark-cli 已安装
lark-cli auth status --as user  # 确认已认证
python3 -c "import matplotlib; print(matplotlib.__version__)"  # 确认图表依赖
```

任一项失败则提示用户安装/认证后再继续。

## 适用场景

- "出周报" / "生成周报" / "帮我写周报" / "项目周报"
- "项目进展" / "这周项目怎么样" / "项目状态汇总"
- "初始化周报配置" / "周报 +init" / "配置周报"
- "weekly report" / "milestone report" / "project analysis report"

## 两个命令

| 命令 | 用途 | 前置 |
|---|---|---|
| `+init` | 首次配置：扫描 bitable → 匹配表/字段 → 生成 config | app_token |
| `+generate` | 生成周报：调脚本拉数据 → 聚合 → 画图 → 组装文档 | config 已存在 |

---

## `+init` — 初始化配置

### 流程

```
用户提供 app_token
        │
        ▼
  调 scan_bitable.py 扫描表+字段
        │
        ▼
  AI 语义匹配 5 张核心表 + 字段映射
        │
        ▼
  询问用户：是否需要周报台账？
        │
    不需要 → ledger = null
    需要 → 检查已有台账表 → 没有则创建表+字段
        │
        ▼
  生成 weekly-report-config.json → 用户确认/微调 → 保存
```

### Step 1: 扫描 bitable 结构

```bash
python3 scripts/scan_bitable.py --app-token TOKEN --output scan_result.json --as user
```

输出 JSON 包含所有表的 table_id/name + 每张表的字段列表（名+类型+枚举值采样）。

### Step 2: AI 语义匹配核心表

读取 `scan_result.json`，按用途关键词匹配：

| 核心表 | 匹配关键词（字段名包含） |
|---|---|
| 项目管理 | "项目名称" AND "项目状态" |
| 里程碑管理 | "付款类型" AND "当前计划时间" |
| 任务列表 | "任务名称" AND ("任务状态" OR "任务check状态") |
| 问题跟踪 | "问题描述" AND "问题级别" |
| 变更记录 | "变更内容" AND "变更状态" |

匹配失败时列出所有表让用户手动指定。

### Step 3: AI 匹配字段映射

对每张核心表，按字段名关键词 + 类型推断映射。参考 [`references/bitable-schema.md`](references/bitable-schema.md) 中的必需字段定义。

### Step 4: 台账表（可选）

询问用户是否需要周报台账：
- **不需要** → config 中 `tables.ledger = null`
- **需要 + 已有台账表** → 匹配字段，填入 config
- **需要 + 没有台账表** → 调 lark-cli 创建表 + 定义字段：

```bash
# 创建表
lark-cli api POST "/open-apis/bitable/v1/apps/$APP/tables" \
  --data '{"table":{"name":"项目分析周报"}}' --as user

# 批量添加字段
lark-cli api POST "/open-apis/bitable/v1/apps/$APP/tables/$TBL_ID/fields/batch_create" \
  --data '{"fields":[
    {"field_name":"周报标题","type":1},
    {"field_name":"报告状态","type":3,"property":{"options":[{"name":"草稿"},{"name":"已发布"}]}},
    {"field_name":"周报文档","type":15},
    {"field_name":"汇报日期","type":5},
    {"field_name":"周期开始","type":5},
    {"field_name":"周期结束","type":5}
  ]}' --as user
```

### Step 5: 生成配置

参考 [`references/config.example.json`](references/config.example.json) 格式，填入匹配结果。输出到工作区 `weekly-report-config.json`，提示用户确认。

---

## `+generate` — 生成周报

### 前置条件

1. 读取 `../lark-shared/SKILL.md`（认证）
2. 读取工作区 `weekly-report-config.json`（配置）
3. 执行前置检查（lark-cli + matplotlib）

### 时间窗口计算

```python
from datetime import datetime, timedelta

today = datetime.now()
weekday = today.weekday()  # 0=Mon, 2=Wed
this_wed = today - timedelta(days=(weekday - 2) % 7)
last_thu = this_wed - timedelta(days=6)
# 周期 = last_thu ~ this_wed
# 里程碑窗口 = 本月1日 ~ today + 50天
```

用户指定特殊周期时按用户要求覆盖，但里程碑窗口不变。

### 执行流程

**Step 1: 拉取数据**

```bash
python3 scripts/fetch_data.py \
  --config weekly-report-config.json \
  --period-start $LAST_THU --period-end $THIS_WED \
  --output-dir /tmp/weekly-report/fetched/ --as user
```

输出：projects.json, milestones.json, tasks.json, issues.json, changes.json, meta.json

**Step 2: 聚合数据**

```bash
python3 scripts/aggregate.py \
  --input-dir /tmp/weekly-report/fetched/ \
  --config weekly-report-config.json \
  --output /tmp/weekly-report/aggregated.json
```

**Step 3: 生成图表**

```bash
python3 scripts/generate_charts.py \
  --input /tmp/weekly-report/aggregated.json \
  --output-dir /tmp/weekly-report/charts/
```

输出：chart_project_MMDD.png, chart_gantt_MMDD.png, chart_issue_MMDD.png

**Step 4: 生成文档内容**

```bash
python3 scripts/generate_doc.py \
  --input /tmp/weekly-report/aggregated.json \
  --config weekly-report-config.json \
  --charts-dir /tmp/weekly-report/charts/ \
  --output /tmp/weekly-report/doc_content.json
```

输出：结构化 JSON，包含 7 章数据 + 图表路径 + config 信息。

**Step 5: AI 组装并写入飞书文档**

AI 读取 `doc_content.json` + [`references/report-rules.md`](references/report-rules.md)，执行：

1. 按 7 章模板组装 DocxXML 内容
2. `docs +create --api-version v2 --folder-token $FOLDER_TOKEN` 创建文档
3. `docs +media-insert` 插入 3 张图表（append 到末尾）
4. `block_move_after` 从后往前移图到正确章节位置
5. 若 config 中 ledger 已配置，写台账（新增一行记录）
6. 返回文档链接给用户

---

## 约束速查

| 约束 | 说明 |
|---|---|
| 时间窗口 = 周期本身 | 不用"过去N天"，锚点绑定到上周四~本周三 |
| 任务筛选只用开始/计划完成 | 不用实际完成时间，避免拉入历史任务 |
| 问题按产生时间筛选 | 不查全量存量，避免拉入历史问题 |
| 搁置问题不展示 | P0/P1 表格中也不出现搁置项 |
| 项目列表只展示有动态的 | 避免歧义 |
| 里程碑窗口固定 | 本月1日~未来50天，不受特殊周期影响 |
| 台账可选 | ledger = null 时跳过写台账 |
| 写操作默认 dry-run | 确认后再执行 |

## 参考

- [lark-shared](../lark-shared/SKILL.md) — 认证、权限（必读）
- [lark-base](../lark-base/SKILL.md) — bitable 操作
- [lark-doc](../lark-doc/SKILL.md) — 文档创建/更新
- [report-rules.md](references/report-rules.md) — 周报生成规则
- [bitable-schema.md](references/bitable-schema.md) — 表结构定义
- [chart-generation.md](references/chart-generation.md) — 图表规范
- [config.example.json](references/config.example.json) — 配置模板
