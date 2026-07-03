# 使用示例与联调说明

## 快速开始
### 1) 准备请求文件
将输入保存为：

```text
./artifacts/request.json
```

可直接参考：

```text
references/request-example.json
```

### 2) 执行编排器
```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model gpt-4.1
```

如需接入兼容 OpenAI 的网关：

```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model your-model \
  --base-url https://your-gateway.example.com/v1
```

### 3) 调整研究与重写策略
```bash
python scripts/orchestrate_solution.py \
  --input-json ./artifacts/request.json \
  --output-dir ./artifacts \
  --model your-model \
  --research-mode auto \
  --review-rewrite-limit 1
```

## 典型请求示例

### 银行厅堂服务外包方案
```json
{
  "raw_input": "/写解决方案 客户是建设银行某分行，项目是厅堂服务外包优化。当前存在服务质量波动、客户投诉偏多、网点忙闲不均、现场管理动作不统一等问题。希望在合规前提下，围绕客户满意度提升、投诉率下降、人员配置优化、服务标准统一、弹性用工机制、投入产出提升，形成一套可落地的年度运营优化方案。请结合当地网点布局、客群特点、监管要求、同业实践、经营压力和现有团队基础，输出一份正式解决方案。",
  "output_docx": "",
  "knowledge_root": "./knowledge",
  "research_mode": "auto",
  "cooldown_seconds": 10,
  "review_rewrite_limit": 1
}
```

## 运行产物
执行后会生成：
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
- 最终 DOCX
- `artifacts/quality_suggestions.json`
- `artifacts/quality_suggestions.txt`

## 节点内同步质检

### 大纲节点
- 先生成大纲
- 再立即检查大纲是否覆盖关键章节、层级是否均衡、是否过于提纲化
- 未通过时自动重写一次

### 正文节点
- 每个 section 生成后立即检查
- 检查维度包括：
  - 内容颗粒度是否足够
  - 逻辑是否自洽
  - 篇幅是否达到建议区间
  - 是否有明确动作、机制、指标、角色分工
  - 是否与用户输入和研究上下文一致
- 未通过时按建议重写，直到达到重写上限

## 知识库与检索

### 本地知识库优先
若 `knowledge_root` 下存在内容，系统会优先读取并筛选相关片段，纳入研究上下文。

### 外部检索补充
若知识库为空或信息不足，且 `research_mode` 为 `auto` 或 `web`，系统会补充网络检索结果，用于完善：
- 客户年度战略或重点工作方向
- 所在地域与客群特点
- 近期监管与合规要求
- 同业模式与市场压力

## 常见问题

### Q1：为什么正文不是一次性输出？
因为主链路采用分段串写。这样更稳，也更适合在每个节点同步质检和定点重写。

### Q2：质检现在会不会只是在最后卡输出？
不会。大纲和各正文节点都已经同步质检。最终 `quality_suggestions` 只是总体验收建议，不负责卡住主交付。

### Q3：知识库为空会怎么样？
不会中断。`auto` 模式下会自动尝试外部检索；`off` 模式下则只依赖用户输入。

### Q4：最终 DOCX 来自哪里？
DOCX 直接基于 `solution_temp.md` 导出，不再依赖图渲染或带图合稿步骤。
