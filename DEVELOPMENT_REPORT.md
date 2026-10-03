# Solution Writer Skill 可视化增强开发报告

最新视觉专项已改用A/B/C纯色主题，以下渐变章节为上一轮历史记录。当前实现、测试和限制见 [视觉专项报告](VISUAL_STYLE_REPORT.md)。

日期：2026年10月3日。工程：`D:/Project/skills/solution-writer-skill-main`。

本次在现有 Skill 内接入结构化可视化规划、四类本地绘图、Manifest、稳定锚点插图及普通表格1.2倍行距。保留现有CLI、研究与客户洞察、正文写作规范、封面及文档样式。没有增加独立软件、页面、MCP、数据库、常驻服务或新的Agent框架。

包含渐变专项增量在内，33项自动化测试通过；SVG模板和真实Mermaid两条主流水线样本都生成了5张图及DOCX，其中3张渐变展示图、1张轻渐变数据图。最终DOCX的分页视觉检查和真实LLM联调未完成，不能视为全部环境验收通过。渐变专项的改动、复现和最新样本见本报告末节。

## 原有实现审查

| 检查项 | 原有能力与问题 | 本次处理 |
| --- | --- | --- |
| SVG路径 | 有SVG→PNG工具，以及Markdown图片→DOCX入口；Skill描述为主链路已支持，但编排器没有生成、转换、插图调用，只能人工补图 | 复用转换和DOCX入口，增加真实的编排调用 |
| Mermaid路径 | 有结构化JSON→Mermaid、mmdc/Kroki及Manifest；独立CLI尚未接入编排器 | 统一模块复用已有模板及引擎，主流水线与独立CLI共用 |
| 数量 | 插图器按固定chapter1/2/3标题，每章只取第一张 | 按稳定章节/小节ID插入所有成功任务，同小节可多图 |
| 图形容量 | 无提示截断为14节点、20边；断开的边被静默丢弃 | 校验未知引用；不截断；默认18节点/30边，复杂图按边集合拆图 |
| 插图定位 | 固定匹配“一、需求理解／二、实施策略／三、运营方案”，和现在5–7章蓝图常不一致 | 合稿器生成稳定标识；可附唯一正文锚点；旧标题模式仅作兼容路径 |
| 幂等性 | 重复注入可重复图片 | 带ID的生成块完整替换，图题仍由导出器统一编号 |
| 失败处理 | 原渲染有有限重试；但找不到mmdc时整个CLI提前退出，无法记录逐任务状态；PNG成功但SVG失败可能仍记成功 | 保留有限重试，加入本地SVG降级及逐任务验证；图表失败保留正文和DOCX |
| Mermaid语法 | 初始化字符串的百分号被格式化吞掉；实际渲染发现classDef end使用保留字 | 修复初始化指令；改用finish类与安全节点前缀；实机验证通过 |
| 视觉风格 | 多套章节配色，与当前DOCX深海蓝/橙色不完全一致；新版Mermaid默认neo样式带阴影 | 新主流水线统一DOCX配色、CJK字体与classic扁平风格；缩小旧图例占用 |
| 数据图 | 未发现受控统计图渲染和来源校验 | 增加Matplotlib与可信数据集/逐点原文核验 |
| DOCX表格 | 普通表格段落原为1.3倍；编排导出复用独立渲染器 | 普通表格设置1.2倍，段落级设置防止样式覆盖 |

审查过的原有出口 [docx_exporter.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/export/docx_exporter.py) 无需修改，因为它已经复用独立DOCX生成器。原有CairoSVG→svglib/ReportLab回退亦直接复用。

## 修改与新增文件

| 文件 | 作用 |
| --- | --- |
| [SKILL.md](D:/Project/skills/solution-writer-skill-main/SKILL.md) | 更新真实主链路能力、绘图选择及来源约束，移除“指定小节必出图”的要求 |
| [requirements.txt](D:/Project/skills/solution-writer-skill-main/requirements.txt) | 唯一新增Python依赖为Matplotlib |
| [render_diagrams.py](D:/Project/skills/solution-writer-skill-main/scripts/render_diagrams.py) | 原入口派发统一渲染；Mermaid语法、配色、布局、图例修复；默认同时SVG/PNG |
| [inject_diagrams.py](D:/Project/skills/solution-writer-skill-main/scripts/inject_diagrams.py) | 稳定锚点、多图、来源、幂等、插入状态；兼容旧标题 |
| [svg_to_png.py](D:/Project/skills/solution-writer-skill-main/scripts/svg_to_png.py) | 抽出可复用convert_svg接口，保留原转换引擎及CLI |
| [orchestrate_solution.py](D:/Project/skills/solution-writer-skill-main/scripts/orchestrate_solution.py) | 合稿后导出前执行可视化；持久化任务/Manifest；故障继续导出 |
| [generate_docx.py](D:/Project/skills/solution-writer-skill-main/scripts/generate_docx.py) | 普通表格1.2倍行距；识别内部锚点/来源；图像适应版心与页面高度 |
| [intake.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/intake.py) | 保留新增可选配置、可信数据集和显式任务 |
| [blueprint.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/writing/blueprint.py) | 现有调用附加visualization_goals；规范唯一稳定ID |
| [chapter_writer.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/writing/chapter_writer.py) | 同一写作调用附加任务JSON契约并提取，正文与元数据分离 |
| [markdown_builder.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/writing/markdown_builder.py) | 合稿时生成章节/小节标识，保证章标题存在 |
| [run_state.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/run_state.py) | 恢复绘图pending/completed/partial/failed状态 |
| [visualization/__init__.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/visualization/__init__.py) | 可复用模块入口 |
| [visualization/planning.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/visualization/planning.py) | 配置、规划契约、任务提取、结构/数据/正文校验、完整关系拆图 |
| [visualization/renderers.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/visualization/renderers.py) | 复用Mermaid/SVG转换，受控SVG模板及Matplotlib，中文字体检查 |
| [visualization/pipeline.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/visualization/pipeline.py) | 数量/重复控制、有限重试、产物校验、Manifest及文档嵌入 |
| [verify_visualization.py](D:/Project/skills/solution-writer-skill-main/scripts/verify_visualization.py) | 无API费用的真实编排器回归与持久化样本生成 |
| [visualization.md](D:/Project/skills/solution-writer-skill-main/references/visualization.md) | JSON任务、数据来源、配置、CLI使用与限制说明 |
| [conftest.py](D:/Project/skills/solution-writer-skill-main/tests/conftest.py) | 测试导入路径 |
| [sample_solution.py](D:/Project/skills/solution-writer-skill-main/tests/sample_solution.py) | 六章业务体系/流程/协作及公开数据的确定性样本 |
| [test_visualization.py](D:/Project/skills/solution-writer-skill-main/tests/test_visualization.py) | 类型、数据、布局产物、插图、失败、CLI、表格格式不变性测试 |
| [test_orchestration.py](D:/Project/skills/solution-writer-skill-main/tests/test_orchestration.py) | 真实主编排器与DOCX回归；只替换LLM边界 |
| [本报告](D:/Project/skills/solution-writer-skill-main/DEVELOPMENT_REPORT.md) | 审查、交付与验证记录 |

## 实际调用流程

1. 原有parse_input与Research Pack、客户洞察照常执行。
2. 原有蓝图调用生成章节/小节契约，附加可选visualization_goals，规划类型、位置、图文分工。
3. 原有每章一次写作调用输出正文及末尾visualizations JSON块。脚本提取任务并绑定chapter_id，畸形JSON只记录警告，不进入正文。
4. 合稿器根据蓝图生成solution-chapter/solution-section标识。正文标题匹配不明确时不生成小节锚点，相应图会跳过。
5. 可视化模块校验唯一插图位置、任务结构、数据来源及图文内容对应关系；去掉重复图，按预算处理复杂分图。正文先落盘，避免可视化阶段异常丢失正文。
6. 流程/关系图复用Mermaid模板，优先本地mmdc；auto模式缺失/失败时用SVG降级。业务模型用SVG模板。数据图用Matplotlib。SVG转换复用原工具。
7. 验证PNG可解码、SVG为有效XML，记录Manifest。失败默认再试一次，图结构重试可切换方向，最多重试两次，不额外调用LLM修图。
8. 图按稳定ID或唯一正文锚点插入，带规范图片引用、来源及幂等生成块。保存solution.md，再通过原export_docx→create_solution_docx生成Word；图题统一编号。
9. 原有轻量终审照常执行。本次没有修改其逻辑及研究/客户洞察模块。

无新增LLM调用。回归中六章仍为蓝图1次＋章节6次，共7次。附加规划和任务JSON会增加少量输入/输出token；本次未测量真实模型的token增幅，不能宣称完全零token增量。

## 类型与配置

流程图、架构/合作关系图、数据图（柱状/折线/饼/散点）、分层业务模型图均可输出SVG和PNG。数据图SVG字形转路径，中文跨机器保真；图形模板使用现有思源宋体/可用CJK字体。无法找到覆盖文字的字体时任务失败并保留正文。

默认按信息价值建议3–6张，上限8张，不保证或强制最低数量。同章节和同小节支持多张不同用途的图片。新增request字段为visualization、visualization_data、diagrams，均可省略。详细契约见 [配置说明](D:/Project/skills/solution-writer-skill-main/references/visualization.md)。

```json
{
  "visualization": {
    "enabled": true,
    "max_diagrams": 8,
    "engine": "auto",
    "png_width": 1800,
    "retries": 1,
    "timeout": 60,
    "max_nodes": 18,
    "max_edges": 30,
    "allow_assumed_data": false
  }
}
```

max_diagrams允许0–24；0不出图。本地SVG降级每图最多10节点/12边；超过时按完整边集合拆分，重复边界节点维持同一身份，所有原关系均保留。分图占预算，预算不足时整组跳过。复杂分组图需本地Mermaid；没有相应引擎时不画一个丢失分组含义的替代图。

数值优先来自用户提供的结构化数据集，LLM只引用dataset_id，不能替换其数值。另一种路径为从用户输入或同来源Research Pack片段提取逐点原文证据；校验标签与其后首个数值配对。假设默认禁用，显式启用时在来源中显示“假设数据（非实际成效）”。目标章节必须出现图中文字及数值；不一致则跳过。原文校验不能替代统计口径和业务语义审阅，尤其是用户声明“verified”的数据集，程序不会自动联网核实。

本地绘图不上传客户业务数据。旧Kroki方式仍可用，但只有显式设置engine=kroki和kroki_url才会发送图内容；该远程路径本次未做在线测试。

## DOCX表格修改范围

普通表格内每个单元格段落设置line_spacing=1.2及WD_LINE_SPACING.MULTIPLE。结果OOXML为w:line="288"、w:lineRule="auto"，表示1.2倍，非固定磅值。多段落、段内换行及嵌套表格由同一个辅助函数处理。

字体、字号、颜色、边框、单元格边距、对齐、列宽、行高和分页规则未改变。封面装饰条所用的单格布局表格不属于普通内容表格，不修改。正文仍1.75倍；标题、封面、目录、页脚、既有图题样式保持原值。新增图来源用已有9pt图注灰色；图片按原15.5cm宽度插入，只有超出版心或过高时才缩小并保持比例。

表格辅助函数测试将前后完整表格XML剔除行距新增属性后比较，确认其它结构相同；非表格段落XML保持一致。独立DOCX CLI和主编排器都实际运行并检查了输出。

## 样本与复现

真实数值采用工信部2025年1月26日发布的2024年行业历史数据：软件产品30417亿元、信息技术服务92190亿元、信息安全2290亿元、嵌入式系统软件12379亿元。它们是全国行业收入，明确不代表演示园区的实际经营或实施成效。[工信部原始资料](https://www.miit.gov.cn/jgsj/yxj/xxfb/art/2025/art_82c3dba8d5f442beb4c49b04fbfd0e33.html)

六章样本是用于流水线验收的精简确定性方案，包含三层业务体系、系统架构、办理流程与组织协作；不冒充真实模型生成的万字方案。两章没有可靠数值或独立绘图价值，未强制插图。

| 样本 | 位置 |
| --- | --- |
| 默认SVG离线样本DOCX | [sample_solution.docx](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/sample_solution.docx) |
| 同一小节双图的Markdown | [solution.md](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/solution.md) |
| 5图状态/锚点/来源 | [diagram_manifest.json](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/diagram_manifest.json) |
| 数据柱状图 | [industry_bar.png](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/industry_bar.png) |
| 业务模型图 | [service_model.png](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/service_model.png) |
| 架构图 | [system_arch.png](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/system_arch.png) |
| 流程图 | [service_flow.png](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/service_flow.png) |
| 协作关系图 | [collaboration.png](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/diagrams/collaboration.png) |
| 每张图的矢量版本 | 同目录对应同名.svg文件 |
| Word结构检查 | [checks.json](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/checks.json) |
| pytest结果 | [pytest-results.xml](D:/Project/skills/solution-writer-skill-main/artifacts/visualization-regression/pytest-results.xml) |
| 实际Mermaid主链路DOCX | [sample_solution.docx](D:/Project/skills/solution-writer-skill-main/artifacts/mermaid-regression/sample_solution.docx) |
| 实际Mermaid状态与矢量图 | [diagram_manifest.json](D:/Project/skills/solution-writer-skill-main/artifacts/mermaid-regression/diagrams/diagram_manifest.json) |
| 原有3份Mermaid规格回归 | [diagram_manifest.json](D:/Project/skills/solution-writer-skill-main/artifacts/legacy-mermaid-regression/diagram_manifest.json) |

```powershell
python scripts/verify_visualization.py --output-dir artifacts/visualization-regression
python -m pytest tests -q --junitxml artifacts/visualization-regression/pytest-results.xml
python -X utf8 C:/Users/rau12/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

正式运行仍使用原命令及用户配置模型：

```powershell
python scripts/orchestrate_solution.py --input-json artifacts/request.json --output-dir artifacts --model <原有模型名称>
```

Mermaid实机测试使用临时目录内的CLI 12.0.0及Mermaid 12.1.0，并使用本机Chrome作本地无头渲染；未下载浏览器，也未设置全局Mermaid依赖。复现时可用已安装的本地mmdc或指定mmdc_bin。统计图仅新增Matplotlib依赖，未引入Graphviz。

## 验收结果与限制

| 验收项 | 实际结果 |
| --- | --- |
| 四类图表 | SVG离线及Mermaid主流水线样本均成功生成4种类型、5张图，SVG/PNG均有效 |
| 同章/同小节两张不同图 | ch03_s1内业务模型和系统架构各一张，图片与图题数量一致 |
| 完整流水线多图 | 六章精简方案从parse_input到DOCX实际运行，LLM边界采用离线响应，7次调用 |
| 不虚构统计图 | 未知数据集、假设默认禁用、无可信原文、错误标签/数值配对、NaN、长度错误均拒绝 |
| 无绘图价值章节 | 样本ch02与ch06未插图，没有凑满8张 |
| 图文一致 | 目标章缺少图中文字或数值时跳过，错误/歧义锚点不插入其它章节 |
| 中文与代表图视觉 | 实际打开5张SVG降级PNG及Mermaid代表图，中文完整，无明显文字/节点重叠；PNG高清、SVG可解析 |
| 数量与复杂结构 | 上限/关闭/重复控制通过；拆图测试检查全部节点及每条边完整保留；预算不足整组跳过 |
| 图片失败不阻断 | 强制渲染错误2次后记录failed，正文保留且DOCX生成；整个可视化阶段异常也继续导出 |
| 幂等 | 多次渲染/注入仍为5张图与5条来源；旧CLI同章2图重复注入数量不变 |
| 表格1.2倍 | 两条导出路径输出已检查；样本18个普通表格段落均为288/auto，正文1.75倍 |
| 单元格其它格式 | 多段/换行/嵌套表格的XML不变性测试通过，只新增/修改段落行距 |
| 原有Mermaid规格 | 3/3本地实机渲染成功，兼容分组、决策、图例、反馈虚线 |
| Skill校验 | quick_validate通过；Windows默认GBK读取曾失败，使用Python UTF-8模式后通过 |
| 最终DOCX页面渲染 | **未通过环境检查**：已尝试文档技能render_docx.py，报LibreOffice soffice.exe was not found on PATH，未生成页面PNG/PDF |
| 真实LLM联调/万字写作 | **未运行**：没有指定可调用模型配置；本次仅测试实际编排器的确定性LLM边界，不证明各模型都遵守附加JSON契约 |
| Kroki在线回归 | **未运行**：本次验证本地离线路径，不发送业务资料到第三方 |

首轮自动化测试结果为26 passed；加入渐变专项后为33 passed。Mermaid实机发现并修复的保留字与初始化问题已真实回归；临时npm依赖不完整的问题已修复并核对官方包完整性。可变字体在Matplotlib中出现正常字重回退到200的非致命日志，最终样本检查未发现缺字。

仍需在具备文档页面渲染器的环境检查真实Word分页、图片与来源的跨页效果；这些不能用OOXML检查替代。真实LLM遵约率、长篇方案的图表选择和真实token增幅也需要随后联调。本次不宣称所有任意复杂图都不会重叠；复杂分组应走Mermaid，无法可靠绘制时保留正文并记录错误。

本目录没有.git，无法提供基于Git历史的完整差异报告。已按修改文件范围审查：没有修改research目录、客户洞察、质量审查、LLM客户端、核心写作规则或封面/正文/标题样式。请求范围内的正文增量仅为附加可视化契约、稳定锚点及必要章标题；排版增量仅为普通表格行距、新图来源及图像自适应。

## 渐变专项增量与最新验收

渐变直接接入现有统一渲染层，主编排器和独立命令均可用，没有新增模型调用或运行时依赖。六章离线样本仍为7次既有LLM边界调用。用户配置可省略，默认 `visualization.gradient_mode = "controlled"`，设置 `"solid"` 可关闭渐变。数量控制仍默认上限8张、通常按需3–6张，不为展示渐变增加图片数量。

本轮新增 [theme.py](D:/Project/skills/solution-writer-skill-main/scripts/solution_skill/visualization/theme.py) 和 [test_gradients.py](D:/Project/skills/solution-writer-skill-main/tests/test_gradients.py)。修改 `visualization/renderers.py`、`planning.py`、`pipeline.py`、`render_diagrams.py`、`svg_to_png.py`、`verify_visualization.py`、`SKILL.md`、`references/visualization.md` 及本报告。DOCX生成器、研究、客户洞察和正文写作模块本轮没有修改。

所有渐变定义集中为主题token：主渐变 `#5B6CFF → #7B61FF`、辅助渐变 `#4E7BFF → #63D6F5`、浅卡片 `#F7FAFF → #E8EAFE`、柔光 `#DCE6FF → #EFD7F8`。辅助和柔光token预留，本期默认模板不使用模糊滤镜或透明装饰，避免备用转换器差异。条形图主系列采用主色起点混合18%白色的轻渐变，其余系列、坐标轴和网格保持纯色；折线、饼图、散点图维持纯色。架构及业务模型增加渐变一级标题条；业务模型仅首层卡片使用浅渐变，保留其余深海蓝分层标题和浅色内容。流程仅明确标为start的关键节点加渐变，普通流程无需渐变。

实际调用为：既有规划/数据校验 → Mermaid或受控SVG/Matplotlib输出几何 → 共用主题处理（矢量线性渐变、标题自适应换行）→ 同一SVG经CairoSVG转PNG → 原有锚点插图 → 原有DOCX导出。新增中文标题转为矢量字形，并保留可访问文字标签，避免备用转换器的中文粗体映射缺字。没有把图表转换成嵌入SVG的位图。

渐变转换失败时，先把SVG的受控填充统一改为同色系纯色并移除渐变定义，再使用既有转换器输出PNG。Manifest记录 `gradient_mode: solid_fallback` 和具体原因；SVG与PNG保持同一降级状态。独立 `svg_to_png.py` 同样遵守该策略。两条转换器都失败才交给既有有限重试，最终仍保留正文并导出DOCX。

实测修复了三项问题：Windows相对mmdc路径含正斜杠时命令解析失败（改为存在文件的绝对路径）；svglib对嵌套SVG的尺寸处理不一致（改为统一分组变换）；ReportLab重复按96 DPI放大图像（已经按目标像素缩放后改用72 DPI）。检查降级PNG还发现标题缺字及透明装饰失真，已用矢量标题并取消透明装饰修复。流程关键节点也适配了Mermaid的新嵌套形状结构。上述修复均未改写图表业务数据或关系。

| 渐变验收项 | 结果与证据 |
| --- | --- |
| 至少2张明显渐变展示图 | 实际3张：三层服务体系、服务系统架构、组织协作关系；两条引擎流水线均成功 |
| 至少1张轻渐变数据图 | 2024年全国软件业分领域收入条形图；程序检查实际PNG像素包含两端颜色 |
| 渐变范围受控 | 测试仅主数据系列渐变、明确start节点渐变；普通文字/节点/轴线不受影响 |
| 比较与数据准确性 | 双系列、正值/负值/零值的纯色与渐变SVG路径坐标完全相同，来源校验原样保留 |
| PNG与DOCX一致 | 两份DOCX的5张内嵌PNG与输出文件SHA-256逐张一致；未在Word中重新绘制渐变 |
| 失败降级 | 模拟Cairo不可用，实际svglib渲染2张纯色图成功，标题中文与布局已打开检查，Manifest记录降级原因 |
| 表格与其它排版 | 18个普通表格段落仍为1.2倍；与首轮DOCX比较，样式、表格、非图片段落、节属性、页眉页脚XML全部一致 |
| 自动化与Skill校验 | 33 passed；quick_validate通过 |
| 最终Word页面渐变一致性 | **未完成**：已再次运行打包的render_docx.py，缺少LibreOffice soffice.exe；不能将嵌入字节检查当作分页或Word显示验收 |

最新样本及证据：

- [渐变SVG模板路径DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/sample_solution.docx)
- [渐变Mermaid路径DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-mermaid-regression/sample_solution.docx)
- [三层服务体系PNG](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/diagrams/service_model.png)、[架构PNG](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-mermaid-regression/diagrams/system_arch.png)、[轻渐变数据PNG](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/diagrams/industry_bar.png)；同目录提供同名SVG
- [Manifest](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/diagrams/diagram_manifest.json)、[检查结果及图片哈希](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/checks.json)、[排版不变性检查](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/layout-invariance.json)
- [降级样本Manifest](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-fallback-regression/diagram_manifest.json)、[关键流程节点样本](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-flow-regression/service_flow.png)
- [33项测试结果](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/pytest-results.xml)、[Word渲染失败日志](D:/Project/skills/solution-writer-skill-main/artifacts/gradient-regression/docx-render.log)

```powershell
python -X utf8 scripts/verify_visualization.py --output-dir artifacts/gradient-regression
python -X utf8 scripts/verify_visualization.py --output-dir artifacts/gradient-solid-regression --gradient-mode solid
python -m pytest tests -q --junitxml artifacts/gradient-regression/pytest-results.xml

# 本机Mermaid回归，生产环境替换为自己的本地mmdc路径
$env:PUPPETEER_EXECUTABLE_PATH='C:/Program Files/Google/Chrome/Application/chrome.exe'
python -X utf8 scripts/verify_visualization.py --output-dir artifacts/gradient-mermaid-regression --engine mmdc --mmdc-bin artifacts/test-tools/node_modules/.bin/mmdc.cmd
```

当前剩余环境验收仍为Word最终分页渲染与真实LLM联调。渐变专项没有增加这两项验证能力，也没有把它们标记为通过。
