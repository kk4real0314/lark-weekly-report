# lark-weekly-report

飞书多维表格项目周报生成 skill。从 bitable 拉取项目/里程碑/任务/问题/变更数据，按 7 章结构生成周报并写入飞书文档。

## 依赖

- [lark-cli](https://github.com/nicepkg/lark-cli)（已安装且已认证）
- Python 3 + matplotlib
- lark-shared / lark-base / lark-doc skill（随 lark-cli 自动安装）

## 安装

```bash
npx skills add TheR2K/lark-weekly-report
```

## 使用

### 1. 初始化配置（首次使用）

对你的 AI Agent 说：

```
初始化周报配置，app_token 是 <你的 bitable app_token>
```

skill 会自动扫描 bitable 表结构，匹配 5 张核心表和字段映射，生成 `weekly-report-config.json` 供你确认。

### 2. 生成周报

```
出周报
```

或等价说法：`生成周报` / `帮我写周报` / `项目周报` / `weekly report` / `项目进展`

skill 会：
1. 拉取 bitable 数据（项目/里程碑/任务/问题/变更）
2. 按项目维度聚合
3. 生成 3 张图表（项目状态饼图/里程碑甘特图/问题分布图）
4. 组装 7 章内容写入飞书文档
5. 可选写入周报台账

### 3. 指定周期

```
帮我生成 4月30日到5月9日 的项目周报
```

默认周期为上周四到本周三。

## 周报结构（7 章）

1. 项目分析 — 活跃项目列表 + 状态 + 风险
2. 里程碑分析 — 甘特图 + 明细表 + 偏离分析
3. 本周任务 — 按项目展开的任务清单
4. 下周任务 — 到期任务 + 重点工作方向
5. 问题分析 — P0/P1 问题表格
6. 变更分析 — 变更明细 + 风险提示
7. 汇报总结 — 6~8 条要点

## 配置说明

初始化后生成的 `weekly-report-config.json` 包含：

- `app_token` — bitable 应用 token
- `tables` — 5 张核心表 + 可选台账表的 table_id
- `fields` — 各表字段映射（字段名 → 用途）
- `enums` — 枚举值定义（项目状态/问题级别等）
- `output.folder_token` — 周报文档输出文件夹
- `reporter` — 汇报人姓名

台账表（`tables.ledger`）为可选，设为 `null` 则跳过。

## 目录结构

```
lark-weekly-report/
├── SKILL.md              # skill 入口
├── scripts/              # 可执行脚本
│   ├── scan_bitable.py   # +init: 扫描 bitable 表结构
│   ├── fetch_data.py     # +generate: 拉数据 + 按时间窗口过滤
│   ├── aggregate.py      # +generate: 按项目维度聚合
│   ├── generate_charts.py# +generate: matplotlib 画 3 张图
│   └── generate_doc.py   # +generate: 输出结构化 JSON
├── references/           # 参考文档
│   ├── report-rules.md   # 7 章生成规则 + 约束
│   ├── bitable-schema.md # 表结构定义
│   ├── chart-generation.md# 图表规范
│   └── config.example.json# 配置模板
└── evals/                # 测试用例
    └── evals.json
```

## 版本

- **v2.0.0** — 重构为脚本驱动：5 个 Python 脚本固化核心逻辑，SKILL.md 从"说明书"升级为"可执行工具"。删除 IM 通知，台账降为可选，图表保留必选。
- **v1.0.0** — 初始版本，纯指令式（AI 现场写代码）
