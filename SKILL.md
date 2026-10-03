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
  - 现有蓝图/章节调用规划结构化绘图任务，合稿后自动渲染与嵌入 DOCX
  - 流程/架构关系图（Mermaid，本地 SVG 降级）、数据图（Matplotlib）、业务模型（SVG 模板）

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
8. 按需校验、渲染并嵌入图表，再导出 DOCX（本地处理，不增加 LLM 调用）
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
- `matplotlib`（数据图；中文字体使用现有思源宋体，或系统 CJK 字体）
- Mermaid CLI 为可选本地依赖；缺失时用受控 SVG 模板，不自动发送业务数据到第三方

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
- 表格：表头 #204B8C 底白字加粗居中，数据行居中，顶/底深蓝线 + 行间浅灰横线，无竖线；普通单元格段落为 Word **1.2 倍**行距
- 强调：正文 `**加粗**` 会转为真正加粗（写作侧仅允许关键数值/结论词，单段≤2 处）
- 封面可选参数：`--subtitle`（元数据机构行，默认客户名）/ `--doctype`（类型标签）/ `--abstract`（摘要段）

## 自动可视化与文档嵌入

在原有蓝图 JSON 的章节中添加可选 `visualization_goals`，写作时按实际内容确认图表；正文后追加 `visualizations` JSON 代码块，脚本提取后不会进入正文。任务结构、数据来源约束和配置见 [visualization.md](references/visualization.md)。

图表必须有实质信息价值。多方协作、服务流程、系统连接、业务分层适合逻辑图；真实数值比较可用数据图。通常 3–6 张，默认上限 8 张，可配置；不按固定标题或每章凑图，同一小节可多图。正文解释原因与措施，图表表达结构或比较，避免重复表达相同信息。

数据图仅引用用户配置的数据集，或逐点提取用户输入/研究条目中的原文数值。区分 `verified`、`user_provided`、`assumed`；假设默认禁用，显式启用仍须标注，不能宣称实际经营成效。缺少可靠数值时改用逻辑图或跳过。

主链路在合稿后、导出前执行 `solution_skill.visualization`：验证结构与正文对应关系 → 本地渲染 SVG + 高清 PNG → 按稳定章节/小节 ID 或唯一内容锚点插入 → 导出 DOCX。图片采用克制的 A/B/C 主题，配置与色值见 [可视化规范](references/visualization.md)。文档级 `visualization.theme` 为 `auto/sage/tech`：运营体系优先鼠尾草绿与暖米白，科技平台优先科技蓝与浅青白；同一文档默认统一主主题，单图可显式覆盖。统计图统一采用青绿与陶土棕，使用线型、标记、图例区分系列。默认 `gradient_mode: solid`；显式 `controlled` 只对SVG展示图小面积强调线启用柔和同色系渐变，Mermaid与统计图保持纯色。完整Word页面未验证时，不宣称渐变全链路通过。图表使用可用中文无衬线字体，Word字体和配色保持原样。标准宽度不超过15.5cm，超高图自动适应正文页面；复杂内容应拆图以保证最终字号。Manifest记录主题、状态、位置、来源、错误及重试次数；绘图失败保留正文与DOCX导出，重复运行替换已有生成块。

较复杂关系先由 LLM 规划概览与子图；本地还可按完整边集合拆分，跨图同名节点表示同一对象，不静默丢节点/关系。预算不足以容纳全部分图时跳过该组并记录原因。Mermaid CLI 缺失时离线 SVG 路径可处理每图至多10节点/12边；复杂分组结构需安装本地 Mermaid CLI，否则跳过并保留正文。

保留原有 `render_diagrams.py`、`inject_diagrams.py`、`svg_to_png.py` 命令。`--engine auto` 默认优先本地 Mermaid，缺失或失败使用 SVG；`--engine kroki --kroki-url ...` 仅在显式指定时发送图内容。人工 SVG→PNG→Markdown 图片→DOCX 的原有路径仍可使用，但不要直接执行 LLM 生成的 Python 绘图代码。
