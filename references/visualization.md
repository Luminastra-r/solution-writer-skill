# 可视化任务与配置

原有 request.json 字段及 CLI 保持可用。新增字段均可省略；无需配置时由蓝图和章节输出绘图任务，不额外调用 LLM。

```json
{
  "raw_input": "用户需求与真实资料",
  "visualization": {
    "enabled": true,
    "max_diagrams": 8,
    "engine": "auto",
    "gradient_mode": "solid",
    "theme": "auto",
    "png_width": 1800,
    "retries": 1,
    "timeout": 60,
    "max_nodes": 18,
    "max_edges": 30,
    "allow_assumed_data": false
  },
  "visualization_data": [],
  "diagrams": []
}
```

`max_diagrams` 范围0–24，0表示不生成图；`retries` 范围0–2（默认失败后重试1次）；`png_width` 范围1200–3600；`timeout` 范围5–120秒。`max_nodes`范围4–24，`max_edges`范围4–48。超过可读范围的图会拆分；拆分图也占数量预算，若剩余预算不足以显示整组则整组跳过。一个图的失败不会导致整个文档失败。

`engine`: `auto`（本地 Mermaid 优先，简单结构用 SVG 降级）、`svg`（纯本地模板）、`mmdc`（严格要求本地 Mermaid CLI）、`kroki`（必须显式配置 `kroki_url`；会向所配置服务发送图内容）。`mmdc_bin` 可指定本地可执行路径。新增的 Matplotlib 为 Python 依赖；不要求 Graphviz，不部署服务。SVG转换继续复用 CairoSVG → svglib/ReportLab。

## 图表视觉主题（当前默认）

`visualization.theme` 支持 `auto`、`sage`、`tech`。auto 在整份文档只选一次：需求包含“数字/平台/AI/系统”优先tech，否则有业务模型时sage，其余tech；不依靠额外LLM调用。所有架构/流程/业务模型继承同一主主题。业务任务可显式设 `theme: sage/tech` 覆盖文档主题，统计图固定data配色。对自动选择不满意时应人工指定主题，不随机混搭。

主题token集中在 `scripts/solution_skill/visualization/theme.py`：

| 主题 | 背景与卡片 | 文字与强调 | 边框与连线 |
| --- | --- | --- | --- |
| sage（A） | 白底、米白#F2F0EB分组、#DFF3EC卡片 | #145748文字、#167D69强调 | #94BFB1边框、#929690连线 |
| tech（B） | 白底、#F5FBFD分组、白卡片、#E4F8FC辅助 | #252525文字、#185899强调 | #D5E8EF边框、#3488DA强调线 |
| data（C） | 白底、#E7F5F0面积填充 | #20A080主系列、#A4472A对比、#333333文字 | #E4E4E4网格、#C8C8C8轴线 |

业务模型采用侧边层级标题、浅色容器和最多两列的轻卡片；无依赖关系的SVG能力图采用两列卡片，不创造连接。取消宽幅深色标题条，仅保留细小强调线。图片优先使用微软雅黑或其他可用中文无衬线字体，Word封面/正文/表格样式不改变。统计图使用千分位、明确单位、轻轴线，柱状图保持零基线；折线忠实连接实际点，主系列浅色面积从零开始，不平滑、不改变原始差异。多系列采用不同线型/标记，条形图辅以纹理。

`gradient_mode` 默认为 `solid`。保留显式 `controlled` 作为SVG小面积强调线选项，A为#DFF3EC→#C8E9DD，B为#185899→#3488DA；普通卡片、Mermaid和统计图保持纯色。本机只验证了SVG→PNG与DOCX嵌入字节一致，最终Word页面渲染器缺失，所以默认使用纯色，不宣称渐变完整链路已验收。诊断图中的高饱和蓝紫只用于测试，不属于生产主题。

SVG线性渐变使用显式 `gradientUnits=objectBoundingBox`；CairoSVG转换失败时先将SVG填充改为同主题纯色，再交给现有转换器。降级不重新布局，坐标、字号、结构保持不变。`gradient_mode` 状态为 `controlled/solid/solid_fallback`，Manifest同时记录 `theme` 及错误原因。独立 `svg_to_png.py` 使用同一策略。图表PNG直接嵌入DOCX，不在Word重画。完整页面视觉检查仍须在具有页面渲染器的环境完成。

固定内容回归：`python scripts/verify_visual_style.py --output-dir artifacts/visual-style/after`。已保留的before目录为上一版真实渲染结果，不应使用新版命令覆盖。

## 任务契约

章节写作响应正文后附如下代码块；脚本提取为 `diagram_tasks.json` 并移除块，错误仅产生警告：

````markdown
```visualizations
{
  "diagrams": [{
    "id": "service_flow",
    "type": "flowchart",
    "title": "服务办理流程",
    "purpose": "展示办理顺序；正文解释职责与办理条件",
    "section_id": "ch04_s1",
    "anchor_text": "正文中唯一的完整原句",
    "layout": "auto",
    "nodes": [{"id":"receive","label":"需求受理"},{"id":"check","label":"业务核验"}],
    "edges": [{"from":"receive","to":"check"}],
    "source": {"kind":"proposal","reference":"本方案设计"}
  }]
}
```
````

`chapter_id` 由章节写作脚本绑定；手工配置 `request.diagrams` 时需显式提供。章节/小节锚点由合稿器根据蓝图ID生成，用户可改标题；小节标题需与契约一致才能生成该小节标识。`anchor_text` 可选，只在指定小节/章内唯一命中原文段落时插入，否则跳过；未指定时放在该小节/章结尾。未匹配的图不会移动到别章。图题由原有 DOCX 导出器自动编号，来源另起小字号段落。旧的 `chapter1/2/3` 固定标题模式保留为 CLI 兼容路径，同样支持多图和幂等。

支持类型：

| type | 内容 | 输出方式 |
| --- | --- | --- |
| flowchart | nodes/edges，节点 kind 可为 start/end/process/decision/data/quality | Mermaid；缺失时受控SVG |
| architecture | nodes/edges，可选 groups:[{id,title,node_ids}] | Mermaid；简单关系可降级SVG |
| data_chart | chart:bar/line/pie/scatter，dataset_id或逐点证据 | Matplotlib，矢量SVG与高清PNG |
| business_model | layers:[{title,items:[字符串]}]，2–6层，每层1–4项 | SVG分层模板 |

节点ID与图ID为安全ASCII标识，重复ID拒绝；标签/正文内容校验；未知引用、NaN/Infinity、数据长度不一致都会跳过。图内容去重；不执行任意代码，不接受自由 Python/HTML/JS 作为绘图任务。所有本地路径来自受控任务ID。

## 数值及来源

推荐用户提供已整理数据集，LLM只引用其ID，渲染器覆盖任务中自行填写的数值：

```json
{
  "visualization_data": [{
    "id": "confirmed_metrics",
    "labels": ["事项A", "事项B"],
    "series": [{"name": "实际办理量", "values": [120, 80]}],
    "unit": "件",
    "source": {"kind": "user_provided", "reference": "用户提供的2025年事项台账"}
  }]
}
```

以上数字只演示 JSON 格式，不能写成客户真实经营数据。`verified` 用于已经核实的公开/业务资料，`user_provided` 用于用户数据，`assumed` 为明确假设，默认拒绝。数据集的分类由提供者声明，程序不会自动联网核实，提交前应核对原始资料；LLM不能通过任务自行创建“verified”数据集。

没有数据集时，任务可提供 `points:[{label,value,evidence}]`。用户来源的每段 evidence 必须逐字存在于 raw_input；已核实来源必须逐字存在于同 reference 的 Research Pack 片段，且同时包含标签与数值。校验属于原文一致性检查，不能替代语义与业务口径核验。数据图的标签与全部数值还须出现在目标章节正文/表格中，否则不插图。逻辑图的节点或分层项也须出现在正文中。

条形图支持1–4数值系列；折线图横轴是输入标签顺序，应选择有时序/顺序意义的数据；饼图只支持一个非负系列、总和大于0、至多8项。散点图默认以类别序号为横轴；可信数据集可追加 `x_values` 和 `x_label` 使用数值横轴，LLM不能自行替换该横轴数值。每系列与标签数量一致，最多24项。过长标签换行，难以辨认的复杂图应拆解。不要把指标目标画成已经实现的效果。

## 独立运行与测试

```bash
python scripts/render_diagrams.py --spec-json artifacts/diagram_tasks.json --request-json artifacts/request.json --out-dir artifacts/diagrams --engine auto
python scripts/inject_diagrams.py --input-md artifacts/solution.md --manifest artifacts/diagrams/diagram_manifest.json --output-md artifacts/solution.md
python scripts/generate_docx.py --input artifacts/solution.md --output artifacts/solution.docx --project 项目 --customer 客户
python -m pytest tests -q
python scripts/verify_visualization.py --output-dir artifacts/visualization-regression
```

`render_diagrams.py` 的旧参数保留；现在默认同时提供SVG与PNG，`--export-svg`仍接受。独立CLI返回0表示全部渲染成功，2表示有失败/跳过任务（Manifest完整保留），1表示输入/配置错误；主编排器容忍图表失败并继续导出。Manifest包含`status`、`attempts`、`renderer`、`title`、`chapter_id`、`section_id`、`anchor_text`、`source`、`insertion_status`、`error`、`warnings`和输出文件路径。
