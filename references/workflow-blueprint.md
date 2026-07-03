# Solution Writer Workflow Blueprint

## 目标
- 稳定交付高质量长文解决方案与 DOCX
- 主链路优先保证正文深度、完整性、可落地性
- 质检建议在大纲节点和各正文节点同步执行，不再只在末端卡输出
- 知识增强采用“本地知识库优先，网络检索补充”

## 主流程
1. `Input`
   - 输入：`/写解决方案 <自然语言需求>`
   - 输出：`artifacts/request.json`
2. `ResearchContext`
   - 输入：`raw_input` + `knowledge_root`
   - 输出：`artifacts/research_context.json`
   - 说明：优先读取本地知识库；本地无内容或信息不足时按 `research_mode` 触发网络检索
3. `AnalysisBrief`
   - 输入：`raw_input` + `research_context`
   - 输出：`artifacts/analysis_brief.json`
   - 说明：提炼战略目标、地域和客群特征、监管边界、核心痛点、市场压力、根因诊断
4. `OutlineGen`
   - 输入：`raw_input` + `analysis_brief` + `research_context`
   - 输出：`artifacts/outline.json`
5. `OutlineReview`
   - 输入：`raw_input` + `analysis_brief` + `outline`
   - 输出：`artifacts/outline_review.json`
   - 说明：若质检判定不通过，自动重写一次大纲
6. `SectionWriterLoop`
   - 输入：`raw_input` + `analysis_brief` + `research_context` + `outline` + 已完成摘要
   - 输出：`artifacts/sections/*.md`
   - 说明：以二级目录为最小写作单元；无二级目录时退化到一级目录
7. `SectionReviewLoop`
   - 输入：当前 section 正文 + 同步上下文
   - 输出：`artifacts/reviews/<section_id>.json`
   - 说明：节点内检查颗粒度、逻辑、篇幅、可落地性，不通过则按建议重写
8. `MergeMarkdown`
   - 输入：各 section 正文
   - 输出：`solution_temp.md`
9. `DocxExport`
   - 输入：`solution_temp.md`
   - 输出：最终 `docx`
10. `QualityReview`
   - 输入：用户输入、研究上下文、大纲、全文
   - 输出：`artifacts/quality_suggestions.json`、`artifacts/quality_suggestions.txt`
   - 说明：这是终态建议，不回写正文

## 研究上下文策略
- `research_mode=auto`
  - 优先本地知识库
  - 本地为空或片段不足时补充网络检索
- `research_mode=knowledge`
  - 只使用本地知识库
- `research_mode=web`
  - 可直接执行网络检索补充
- `research_mode=off`
  - 不做外部研究，仅依赖用户输入

## 节点级质检策略
- 大纲节点重点检查：
  - 是否覆盖需求理解、诊断、策略、实施、保障、成效
  - 是否存在空泛标题或层级不均衡
- 正文节点重点检查：
  - 是否回答了该目录应回答的问题
  - 是否给出动作、机制、路径、角色、指标
  - 是否与用户输入和研究上下文一致
  - 是否存在明显空话、套话、提纲化表达

## 降级策略
- 大纲 JSON 不合法：
  - 优先自动抽取 JSON
  - 再用 LLM 修复 JSON
  - 仍失败则退回本地兜底大纲
- LLM 流式中断：
  - 自动重试
  - 重跑时复用已完成 section
- 知识库为空：
  - `auto` / `web` 模式下走外部检索
  - `knowledge` / `off` 模式下仅使用已有输入

## 产物清单
- `artifacts/request.json`
- `artifacts/research_context.json`
- `artifacts/analysis_brief.json`
- `artifacts/outline.json`
- `artifacts/outline_review.json`
- `artifacts/sections/<section_id>.md`
- `artifacts/reviews/<section_id>.json`
- `artifacts/section_index.json`
- `artifacts/run_state.json`
- `solution_temp.md`
- 最终 `docx`
- `artifacts/quality_suggestions.json`
- `artifacts/quality_suggestions.txt`
