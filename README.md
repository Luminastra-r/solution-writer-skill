# Solution Writer Skill

> 面向 AI Agent 的长文解决方案写作技能——通过精简流水线在 7-15 次 LLM 调用内生成万字级商务方案初稿并导出 DOCX，内置客户洞察、知识库检索与网络研究增强。

[English](./README_EN.md) | **中文**

---

## 简介

Solution Writer Skill 是一个可独立运行的 AI Agent 技能模块，专注于生成高质量的长文商务解决方案文档。它将资深售前顾问的写作经验沉淀为标准化流水线，从自然语言需求输入到万字方案初稿 + DOCX 交付，全程仅需 7-15 次 LLM 调用。

### 核心能力

- **输入完整性评估**：自动检测需求缺项，引导用户一轮补充（不阻塞生成）
- **客户背景深挖**：1 次 LLM 调用提炼客户战略定位、年度重点、组织架构与隐性期许
- **方案蓝图生成**：诊断分析 + 目的导向大纲 + 每节内容契约（1 次 LLM）
- **逐章长文撰写**：每章 1 次 LLM，逐条兑现内容概要契约，显式对齐客户战略
- **合稿与导出**：Markdown 合稿 + DOCX 一键导出
- **轻量终审建议**：基于摘要的方案质量审查（standard / high_quality 模式）
- **研究增强**：hybrid 模式下 web 检索客户背景 + knowledge 检索公司能力（并行）

## 快速开始

### 环境要求

- Python 3.8+
- 兼容 OpenAI API 的 LLM 服务（支持自定义 base_url）

### 安装

```bash
git clone https://github.com/your-username/solution-writer-skill.git
cd solution-writer-skill
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
```

### 运行

1. 准备请求文件：

```json
// artifacts/request.json
{
  "raw_input": "/写解决方案 客户是某零售连锁企业，拟对门店运营体系进行年度升级。当前存在门店服务质量波动、客户投诉偏多、门店忙闲不均等问题。希望围绕客户满意度提升、投诉率下降、人员配置优化、服务标准统一，形成一套可落地的年度运营优化方案。",
  "output_docx": "",
  "knowledge_root": "./knowledge",
  "research_mode": "hybrid",
  "run_mode": "standard"
}
```

> 完整示例参见 [`references/request-example.json`](./references/request-example.json)

2. 执行编排器：

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

### 产物

执行后生成以下文件：

| 产物 | 说明 |
|------|------|
| `artifacts/solution.md` | 合稿后的完整方案 Markdown |
| 最终 `.docx` | 导出的 Word 文档 |
| `artifacts/normalized_request.json` | 结构化后的请求 |
| `artifacts/research_pack.json` | 研究上下文（web + knowledge） |
| `artifacts/solution_blueprint.json` | 方案蓝图（大纲 + 契约） |
| `artifacts/chapters/chapter_XX.md` | 各章节正文 |
| `artifacts/quality_suggestions.txt` | 终审建议 |
| `artifacts/run_state.json` | 运行状态与 LLM 调用计数 |

## 运行模式

| 模式 | LLM 调用 | 适用场景 |
|------|---------|---------|
| `fast` | 6-8 次 | 内部初稿，无终审、无客户深挖 |
| `standard`（默认） | 8-10 次 | 正式方案初稿，含客户深挖 + 终审 |
| `high_quality` | 11-15 次 | 投标/正式提交，含蓝图审查 + 批量审查 |

> 客户背景深挖仅在可识别客户且有可用上下文时触发（standard / high_quality），否则自动跳过。

## 研究模式

| 模式 | 行为 |
|------|------|
| `hybrid`（默认） | web 取客户背景/政策 + knowledge 取产品/案例/运营（并行） |
| `knowledge` | 只使用本地知识库 |
| `web` | 只进行网络检索 |
| `off` | 不做外部研究 |
| `auto` | 兼容旧值，等同于 `hybrid` |

## 项目结构

```
solution-writer-skill/
├── SKILL.md                          # 技能定义文件
├── scripts/
│   ├── orchestrate_solution.py       # 主编排器入口
│   ├── generate_docx.py              # DOCX 独立导出
│   ├── inject_diagrams.py            # 图表注入（独立模块）
│   ├── render_diagrams.py            # 图表渲染（独立模块）
│   └── solution_skill/               # 核心 Python 包
│       ├── config.py                 # 常量、枚举、数据类
│       ├── intake.py                 # 输入解析与完整性评估
│       ├── llm_client.py             # OpenAI 兼容流式客户端
│       ├── run_state.py              # 运行状态管理
│       ├── text_utils.py             # 文本处理工具
│       ├── json_utils.py             # JSON 修复工具
│       ├── research/                 # 研究增强模块
│       │   ├── research_pack_builder.py
│       │   ├── customer_insight.py
│       │   ├── knowledge_index.py    # BM25 知识索引
│       │   └── web_search.py         # DuckDuckGo 检索
│       ├── writing/                  # 写作模块
│       │   ├── blueprint.py          # 方案蓝图生成
│       │   ├── chapter_writer.py     # 逐章撰写
│       │   ├── markdown_builder.py   # Markdown 合稿
│       │   └── quality_review.py     # 质量审查
│       └── export/
│           └── docx_exporter.py      # DOCX 导出
├── references/                       # 参考文档与模板
│   ├── workflow-blueprint.md
│   ├── writing-guidelines.md
│   ├── solution-template.md
│   ├── usage-examples.md
│   ├── request-example.json
│   └── diagram-spec-example.json
├── requirements.txt
├── .env.example
└── LICENSE
```

## 流水线概览

```
输入解析 → 完整性检查 → 研究上下构建 → 客户洞察深挖 → 方案蓝图生成
    → 逐章撰写 → Markdown 合稿 → DOCX 导出 → 质量终审
```

- **客户洞察前置**：战略/年度重点/组织与汇报关系/隐性期许结构化，作为"往战略靠、往痛点打"的依据
- **目的导向大纲**：每个末级小节带 `section_goal`（要回答什么）+ `content_brief`（要落地的抓手/机制/角色/指标）
- **写作契约化**：正文逐条兑现内容概要，显式说明如何支撑客户战略，涉及内部管理痛点时措辞委婉
- **降级策略**：大纲 JSON 不合法时自动抽取/修复/兜底；LLM 流式中断时自动重试并复用已完成章节

## 知识库

将你的知识库文件（Markdown / TXT）放入 `knowledge/` 目录，系统会自动索引并按 BM25-like 算法 + 类别加权检索相关片段，融入方案写作。

> 知识库为空时不中断流程，`hybrid` / `web` 模式下会自动补充网络检索。

## 命令行参数

```bash
python scripts/orchestrate_solution.py --help
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input-json` | （必填） | 输入请求 JSON 路径 |
| `--output-dir` | `./artifacts` | 产物输出目录 |
| `--model` | 环境变量 `MODEL_NAME` | LLM 模型名称 |
| `--base-url` | 环境变量 `OPENAI_BASE_URL` | LLM 网关地址 |
| `--api-key` | 环境变量 `OPENAI_API_KEY` | LLM API 密钥 |
| `--knowledge-root` | `./knowledge` | 本地知识库目录 |
| `--research-mode` | `hybrid` | 研究模式 |
| `--run-mode` | `standard` | 运行模式 |
| `--max-web-results` | `12` | 最大网络检索结果数 |
| `--review-rewrite-limit` | 模式默认 | 审查后重写次数上限 |

## 技术栈

- **Python 3.8+** — 纯 Python 实现，无框架依赖
- **openai** — 兼容 OpenAI API 的流式 LLM 客户端
- **requests** — DuckDuckGo 网络检索
- **python-docx** — DOCX 文档导出

## 贡献

欢迎提交 Issue 和 Pull Request。请确保：

1. 代码通过 `python -m py_compile` 编译检查
2. 新增功能附带简要说明
3. 不引入硬编码的密钥或敏感信息

## 许可证

[MIT License](./LICENSE)
