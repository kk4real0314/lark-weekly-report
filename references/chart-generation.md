# 图表生成规范

使用 matplotlib 生成 3 张图表，插入飞书文档。

## 环境准备

```bash
# 检测 matplotlib 是否可用
python3 -c "import matplotlib; print(matplotlib.__version__)"

# 不可用时安装（优先用 venv）
python3 -m venv /tmp/feishu-weekly/venv
/tmp/feishu-weekly/venv/bin/pip install matplotlib
```

## 通用配置

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
```

## 图表 1：项目状态分布饼图

- 尺寸：10×7 inch
- DPI：200
- 内容：按项目状态分组计数
- 颜色：持续服务=#4CAF50, 终验=#FF9800, 初验=#2196F3, 维保=#9C27B0
- 标题：`活跃项目状态分布（N个）`

## 图表 2：里程碑甘特图

- 尺寸：16×6 inch（宽≥16in，高≥6in）
- DPI：200
- 内容：仅画里程碑窗口内的进行中里程碑
- 每条：项目名-付款类型，标注计划日期和金额
- 颜色：≤14天到期=#FF5722, ≤30天=#FF9800, 其他=#4CAF50
- 红色虚线标注"今天"
- X 轴：日期格式 MM/dd，按周刻度
- 标题：`里程碑时间轴（窗口起始 ~ 窗口结束）`

## 图表 3：问题分布柱状图

- 尺寸：10×6 inch
- DPI：200
- 内容：按项目分组，P0/P1 分组柱状图
- P0 颜色：#FF5722，P1 颜色：#FF9800
- 柱顶标注数值
- 标题：`未关闭问题分布（按项目）`

## 插入飞书文档

1. `docs +media-insert` 插入（自动 append 到文档末尾）
2. `block_move_after` 移到正确章节位置
3. **从后往前移**避免偏移：先移图表 3，再移图表 2，最后移图表 1

## 文件命名

```
chart_project_{MMDD}.png
chart_gantt_{MMDD}.png
chart_issue_{MMDD}.png
```

MMDD 取周期结束日期。
