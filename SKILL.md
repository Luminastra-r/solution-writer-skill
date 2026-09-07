---
name: solution-writer-skill
description: 面向 AI Agent 的长文解决方案写作技能。采用精简流水线，standard 模式下 7-9 次 LLM 调用生成万字方案初稿 + DOCX 交付，内置客户洞察、知识库检索与网络研究增强。
---

# Solution Writer Skill

## 触发方式
- 指令触发：`/写解决方案 <用户需求>`
- 非指令触发：当用户明确表达"写解决方案 / 写售前方案 / 写项目提案"时也可启用
- 编排器入口：
  `python scripts/orchestrate_solution.py --input-json ./artifacts/request.json --output-dir ./artifacts --model <model_name>`

## 能力边界
- 主能力：
  - 输入完整性评估与「一轮补充」引导（缺项列出主要缺失点，用户有多少补多少，不阻塞生成）
  - 客户背景独立深挖（1 次 LLM，提炼战略/年度重点/组织架构与汇报关系/隐性期许/措辞基调）
  - 基于自然语言需求生成方案蓝图（诊断 + 目的导向大纲 + 写作指导，1 次 LLM）
  - 按章撰写长文正文（每章 1 次 LLM，5-7 章，逐条兑现每节“内容概要”契约）
  - 合稿为 Markdown
  - 导出 DOCX
  - 轻量终审建议（standard/high_quality 模式）
- 研究增强：
  - hybrid 模式：web 检索客户背景 + knowledge 检索公司能力（并行，不互斥）
  - BM25-like 知识索引 + 类别加权
  - 客户洞察：把检索片段结构化为《客户洞察》，作为诊断与写作底座
- 可视化逻辑图：
  - agent 生成 SVG → 转 PNG → 嵌入 docx（见文末「可视化逻辑图」章节，主链路已支持）
  - Mermaid 路线（`render_diagrams.py` / `inject_diagrams.py`）保留为独立模块，可选

## 输入约束
- 推荐只传 `raw_input`
- 典型形式：
  `/写解决方案 <自然语言需求、背景、目标、限制、已有数据>`
- `request.json` 最小结构：

```json
{
  "raw_input": "/写解决方案 <自然语言需求>",
  "output_docx": "",
  "knowledge_root": "",
  "research_mode": "hybrid",
  "run_mode": "standard"
}
```

## 输出产物
- 主输出：
  - `artifacts/solution.md`
  - 最终 `docx`
- 中间产物：
  - `artifacts/normalized_request.json`
  - `artifacts/research_pack.json`
  - `artifacts/solution_blueprint.json`
  - `artifacts/chapters/chapter_XX.md`
  - `artifacts/quality_suggestions.json`
  - `artifacts/quality_suggestions.txt`
  - `artifacts/run_state.json`
- 补充产物（输入不足时）：
  - `artifacts/clarification_questions.json`
  - `artifacts/clarification_questions.md`

## 主流程
1. 读取 `raw_input`，解析结构化字段（客户名、区域、主题、需求等）
2. 输入完整性检查：缺项时列出主要缺失点，引导用户「一轮补充」（有多少补多少，不阻塞）
3. 构建 Research Pack（hybrid 模式下 web + knowledge 并行）
4. 客户背景深挖（0-1 次 LLM）：把检索片段 + 需求提炼为结构化《客户洞察》
5. 1 次 LLM 生成 Solution Blueprint（诊断 + 目的导向大纲 + 每节内容概要契约）
6. 按章写作（每章 1 次 LLM，逐条兑现 content_brief，显式对齐战略、措辞委婉）
7. 合稿 Markdown
8. 导出 DOCX
9. 轻量终审（standard/high_quality：1 次 LLM 基于摘要审查）

### 关键调优点（对齐资深售前实操）
- 客户洞察前置：战略/年度重点/组织与汇报关系/隐性期许结构化，作为“往战略靠、往痛点打”的依据
- 目的导向大纲：每个末级小节带 `section_goal`（要回答什么）+ `content_brief`（要落地的抓手/机制/角色/指标）
- 阶段递进结构：外包/运营类场景自动采用「合作初稿 → 调研诊断正式方案 → 数字化展望」递进骨架
- 写作契约化：正文逐条兑现内容概要，显式说明如何支撑客户战略，涉及内部管理痛点时措辞委婉

## 运行模式（run_mode）

| 模式 | LLM 调用 | 适用场景 |
|------|---------|---------|
| fast | 6-8 次 | 内部初稿，无终审、无客户深挖 |
| standard（默认） | 8-10 次 | 正式方案初稿，含客户深挖 + 终审 |
| high_quality | 11-15 次 | 投标/正式提交，含蓝图审查 + 批量审查 |

> 说明：客户背景深挖仅在可识别客户且有可用上下文时触发（standard/high_quality），否则自动跳过、不额外消耗调用。

## 研究模式（research_mode）

| 模式 | 行为 |
|------|------|
| hybrid（默认） | web 取客户背景/政策 + knowledge 取产品/案例/运营（并行） |
| knowledge | 只使用本地知识库 |
| web | 只进行网络检索 |
| off | 不做外部研究 |
| auto（兼容旧值） | 等同于 hybrid |

## 环境要求
- Python 3.8+
- `openai`
- `requests`
- `python-docx`
- `cairosvg`（逻辑图 SVG→PNG；不可用时回退 `svglib`+`reportlab`）

## 运行建议
```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model <model_name> \
  --research-mode hybrid \
  --run-mode standard
```

## 交付约束
- 主交付目标是"高质量长文 + DOCX"
- 方案深度优先于花哨增强
- hybrid 模式下 web 和 knowledge 并行，不再互斥
- 以章为写作单位，不再逐节审查
- 终审基于摘要而非全文截断

## 视觉规范（深度研报风，对标样例 PDF · 全篇衬线）

DOCX 导出（`generate_docx.py`，orchestrator 亦复用）统一遵循以下规范，无需额外配置：
- 主色板：墨黑 #1B1D1E（章标题/封面主标题/正文）；**深海蓝 #204B8C**（节标题 / 封面装饰条 / 类型标签 / 表头底）；**活力橙 #F45938**（次级强调点，如封面摘要前的短橙条）；摘要/元数据灰 #6F7679；图表注释浅灰 #9B9B9B；表头深海蓝底 #204B8C、白字
- 字体：**全篇 Noto Serif SC（思源宋体）衬线** —— 中文与西文/数字统一使用 `Noto Serif SC`（参考研报即以此字体生成；本机已装 `NotoSerifSC-VF.ttf`）。标题加粗即 Noto Serif SC Bold，达厚重观感。另在 `word/settings.xml` 写入 `embedTrueTypeFonts`+`saveSubsetFonts`，在 Word 另存为时自动嵌入字形子集，跨机器保真。字号：章 18pt、节 14pt、正文 10.5pt、图注 9pt 浅灰、封面大标题 40pt
- 封面：左对齐垂直流 + **双大圆水印背景**（`scripts/assets/cover_bg_a4.png`：右上深海蓝 ~5% + 左下活力橙 ~4%，A4 透明 PNG，以浮动图 `behindDoc=1` 锚定页面铺满整页）。文字节奏：短深海蓝细条(1.27cm×1.5pt) → 字距拉开的深海蓝 13pt 类型标签 → **40pt** 墨黑衬线大标题(行距1.2) → 短深海蓝细条 → **16pt 深灰 #4A4A4A** 摘要段(行距1.7) → **11pt 钢灰 #6F7679** 元数据（年月 + 机构各一行）
- 目录页：居中墨黑"目 录"，**无分隔线**；页脚居中浅灰页码
- 版式：**A4**（21.0×29.7cm）；四边距 2.54cm；正文 1.75 倍行距、段前后各 0.5 行、两端对齐、首行缩进 2字符
- 表格：表头 #204B8C 底白字加粗居中，数据行居中，顶/底深蓝线 + 行间浅灰横线，无竖线
- 强调：正文 `**加粗**` 会转为真正加粗（写作侧仅允许关键数值/结论词，单段≤2 处）
- 封面可选参数：`--subtitle`（元数据机构行，默认客户名）/ `--doctype`（类型标签）/ `--abstract`（摘要段）

## 可视化逻辑图（内置 Visualizer + 文档嵌入）

当方案内容出现以下任一情形时，生成逻辑图：
- 多方/多角色关系（如签约结构、职责划分、系统对接）
- 流程/步骤链（如办理流程、审批流、数据流向）
- 对比或架构呈现（如方案选型、模块划分）

生成与嵌入流程（每张图执行一次）：
1. 调 read_me(modules=["diagram"]) 加载设计系统，严格遵守其返回的规则。
2. 生成 SVG 字符串，写入本地文件 assets/diagram_<序号>.svg（viewBox 固定 "0 0 680 H"，扁平纯色填充，单图≤2 个色系，字号 13–15px，禁用渐变/阴影/emoji，节点文字 dominant-baseline="central"，并含 <title>/<desc>）。
3. 调 show_widget(title=..., widget_code=<该SVG>, loading_messages=[...]) 做内联预览。
4. 用 cairosvg 把 SVG 转成 assets/diagram_<序号>.png（output_width=1200 保证清晰）。
5. 在方案文档的"## 逻辑图"小节（若该小节不存在则在对应结构段落后新建）用 python-docx 的 add_picture 嵌入 PNG，宽度约 6 英寸；随后保存 docx。
6. 图只承载结构，所有说明文字写在正文（图外）。

确定性约定：若方案模板含"## 架构与关系 / ## 逻辑图"小节，默认在该节必出一张结构图；其余情形按上面触发规则判断。

### 本 skill 的落地约定（与主链路对齐）

- 图文件统一放 `artifacts/diagrams/`（即上文的 `assets/`）：`diagram_01.svg` / `diagram_01.png`。
- 转 PNG 优先用工具脚本，自动处理回退：
  `python scripts/svg_to_png.py artifacts/diagrams/diagram_01.svg`（cairosvg 优先，失败自动回退 svglib，输出同名 .png，宽 1200px）。
  脚本内置中文字体处理：自动注册系统可用的 CJK 字体（SimHei/雅黑/Noto 等）并注入 SVG 文本，无需在 SVG 中指定 font-family。
- 嵌入方式：在 `artifacts/solution.md` 对应小节后直接插入一行 Markdown 图片引用，例如
  `![总体架构逻辑图](diagrams/diagram_01.png)`，
  随后走既有导出管线（`export_docx` / `generate_docx.py`）即自动嵌入 docx（图宽 15.5cm ≈ 6 英寸，自动编号图题"图N"），无需手写 add_picture。
- 时序：所有图在"合稿 Markdown 之后、导出 DOCX 之前"完成生成与插入。

### 跨平台兼容（非 WorkBuddy 环境）

- `read_me` / `show_widget` 是 WorkBuddy 平台工具，仅用于加载设计规范与聊天内预览，**不影响产出物**。
- 在其他 agent 平台使用时：跳过第 1、3 步，直接按第 2 步的 SVG 规范手写 SVG 落盘，再执行第 4、5 步即可，最终 docx 效果一致。
- SVG 设计规范（无 read_me 可用时按此执行）：浅色背景（white/transparent）、深色文字；viewBox "0 0 680 H"；扁平纯色填充，单图 ≤2 个色系；字号 13–15px；禁用渐变/阴影/滤镜/emoji；节点文字 `dominant-baseline="central"`；根元素含 `<title>` 与 `<desc>`；箭头用 `<marker>` 定义。
