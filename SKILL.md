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
- 不包含主链路能力：
  - 逻辑图渲染（独立模块）
  - 带图合稿

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
