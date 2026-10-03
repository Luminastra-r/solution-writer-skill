# 图表配色与视觉质量专项报告

2026-10-03。本轮默认采用 A/B/C 纯色体系，取消宽幅蓝紫标题块，实际修改绘图代码；不新增模型调用或绘图架构，不修改 Word 封面、正文、标题、表格配色。**PNG视觉检查和自动化检查已完成；最终Word页面视觉验收因缺少LibreOffice尚未完成。**

## 渐变链路诊断

上一版并非没有实现渐变：SVG生成了linearGradient和stop，图形通过fill引用，CairoSVG输出的PNG也保留色差。原默认gradientUnits为SVG标准的objectBoundingBox；本轮显式写出该属性。单独的强蓝紫诊断图使用userSpaceOnUse，固定坐标20→660。

在诊断图内部横向五处采样，得到RGB：(93,107,255)、(100,105,255)、(107,102,255)、(114,100,255)、(121,98,255)。颜色连续变化，证明实际PNG保留渐变。嵌入DOCX后PNG的SHA-256与原文件相同，未发现Word打包阶段改写图片。但这不能证明Word页面显示与分页效果；已对诊断DOCX和四图样本分别调用打包的render_docx.py，两次均报`LibreOffice soffice.exe was not found on PATH`。所以**没有认定渐变完整链路验收通过**，默认切换为纯色。

实际视觉问题主要来自大面积高饱和标题、重复的横条层级、颜色权重过高，而不是SVG不支持渐变。Mermaid原生模板输出纯色，上一轮渐变依靠SVG后处理；本轮不再对Mermaid强加渐变。Cairo支持线性渐变；svglib存在丢失渐变、中文字体映射与透明效果差异，继续采用先改写同主题纯色SVG再转换的策略，避免静默丢色。降级前后坐标、字号、尺寸和结构由测试逐项对比。备用字体映射仍可能导致不同引擎的字形细节不同，不承诺逐像素相同。

诊断文件：[SVG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/gradient_probe.svg)、[PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/gradient_probe.png)、[DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/gradient_probe.docx)、[采样及检查JSON](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/checks.json)、[页面渲染失败日志](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/gradient-render.log)。蓝紫仅保留在诊断图，不用于生产主题。

## 采用的设计与配置

| 主题 | 设计 | 默认用途 |
| --- | --- | --- |
| A / sage | 白底，#F2F0EB米白分组，#DFF3EC卡片，#145748深绿文字，#167D69强调，#94BFB1边框 | 业务分层、运营体系、组织服务模型 |
| B / tech | 白底与#F5FBFD浅青分组，白卡片，#252525文字，#185899细强调线，#D5E8EF轻边框 | 科技平台、能力矩阵、展示卡片 |
| C / data | #20A080青绿主系列、#A4472A陶土棕对比、#E7F5F0浅面积，#E4E4E4网格和#C8C8C8坐标轴 | 数据统计和趋势分析 |

```json
{"visualization":{"theme":"auto","gradient_mode":"solid","max_diagrams":8}}
```

theme支持auto/sage/tech。auto按需求中“数字/平台/AI/系统”选择tech，否则存在业务模型时选择sage，其余tech；一次确定文档主主题，架构、流程、模型继承它。单图可显式`theme: sage/tech`覆盖。统计图始终使用C。规则是确定性的轻量本地判断，不新增模型调用；复杂领域应人工配置。四图对比样本刻意展示A业务模型和B能力卡片，属于显式覆盖；主流水线样本的非数据图统一B。

保留`gradient_mode: controlled`用于显式选择SVG小强调线：A为#DFF3EC→#C8E9DD，B为#185899→#3488DA；不填充大块背景，不加阴影或模糊，不对普通卡片渐变。Mermaid和数据图保持纯色。此选项的SVG/PNG及降级已测试，Word页面未认证，正式默认仍为solid。

三层模型从“标题横条＋矩形堆叠”改为侧边层级名称、米白分组、留白和最多两列卡片。层级与项目次序未改变。无连线能力图改为两列卡片，不增添业务关系；科技卡片采用细顶部强调线。图内优先使用微软雅黑等中文无衬线字体，Word原字体保持不变。

统计图使用千分位和明确单位、轻轴线、外置紧凑图例；柱状图保持零基线，不拉伸小值；折线不平滑，按原始数据点连线，主系列浅色面积从零开始。多系列结合实/虚线、圆/方等标记；条形图使用不同纹理，颜色不是唯一辨识方式。数据标签字号提高到11pt（源图），避免插入Word后过小。

## 四类固定内容对比

before由本轮修改前的真实代码生成，after由新代码生成；fixture.json结构化内容逐项相等。两套图片、SVG、DOCX及旧渲染代码快照均已保留，未覆盖上一轮样本。

| 类型 | 优化前 | 优化后 | 变化 |
| --- | --- | --- | --- |
| 三层业务架构 | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/before/diagrams/service_model.png) | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/diagrams/service_model.png) | 层标题移到侧边，浅色分组和卡片替代深色横条 |
| 四模块能力 | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/before/diagrams/capabilities.png) | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/diagrams/capabilities.png) | 四个横排节点改为2×2白卡，细蓝线和轻边框 |
| 横向柱状图 | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/before/diagrams/industry_bar.png) | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/diagrams/industry_bar.png) | 青绿纯色、轻坐标轴、千分位及更大标签 |
| 双系列折线 | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/before/diagrams/annual_line.png) | [PNG](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/diagrams/annual_line.png) | 青绿/陶土棕，实线圆点/虚线方点，浅面积和端点数值 |

每张PNG旁有同名SVG。[优化前DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/before/sample.docx)、[优化后DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/after/sample.docx)、[主流水线Mermaid样本DOCX](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/mermaid/sample_solution.docx)。这些是待最终页面验收的样本，不称为已完成Word视觉验收的交付稿。

并排预览：[三层架构](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/comparison-service_model.png)、[四模块卡片](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/comparison-capabilities.png)、[柱状图](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/comparison-industry_bar.png)、[双系列折线](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/comparison-annual_line.png)。两主题的可选强调线与实际svglib降级样本分别保存在`artifacts/visual-style/optional-accent/{sage,tech}`及`fallback/{sage,tech}`，均含SVG、PNG、Manifest。

双系列使用工信部公开的2023/2024年软件产品与信息技术服务收入，分别为29030/30417和81226/92190亿元。按当年公开口径展示，不据此推导可比增速，也不表示客户实施成效。[2023年原始资料](https://www.miit.gov.cn/jgsj/yxj/xxfb/art/2024/art_3cb679c2662d4127af3cc857d7dbff8e.html)、[2024年原始资料](https://www.miit.gov.cn/jgsj/yxj/xxfb/art/2025/art_82c3dba8d5f442beb4c49b04fbfd0e33.html)。业务结构沿用原测试方案，无新增经营数据。

## 修改清单及验证

| 文件 | 修改 |
| --- | --- |
| scripts/solution_skill/visualization/theme.py | A/B/C统一token，文档选题规则、低权重标题、轻边框、可选小渐变 |
| scripts/solution_skill/visualization/renderers.py | 分层容器、两列卡片、中文无衬线字体、数据轴线/标签/线型/标记/填充 |
| scripts/solution_skill/visualization/planning.py | 可选theme校验、默认solid |
| scripts/solution_skill/visualization/pipeline.py | 文档主题一次解析，单图显式覆盖，Manifest记录实际主题 |
| scripts/verify_visual_style.py | 新增固定内容前后对比、独立渐变诊断、嵌入哈希和实际插图尺寸检查 |
| scripts/verify_visualization.py | 回归入口默认solid |
| tests/test_gradients.py | 更新旧默认高饱和渐变契约，验证当前主题、局部渐变及降级几何一致性 |
| SKILL.md、references/visualization.md | 当前规范、配置、适用范围及验收限制 |
| DEVELOPMENT_REPORT.md、VISUAL_STYLE_REPORT.md | 保留历史报告并指向本轮结果 |

32项自动化测试通过：保留原26项数量、来源真实性、同章多图、幂等、失败继续导出、两条DOCX入口和表格格式测试；当前6项主题专项测试覆盖主题一致性及人工覆盖、确定性自动选择、实际渐变像素、真实svglib降级且几何不变、独立转换器降级、数据线型/标记/负值范围、Mermaid纯色。旧7项渐变测试要求默认蓝紫，与新需求冲突，已更新；旧源码保存在baseline-source，不把33降为32隐瞒为旧测试全数未变。[测试结果](D:/Project/skills/solution-writer-skill-main/artifacts/visual-style/pytest-results.xml)。

已实际打开四张新PNG、Word插入尺寸的144dpi检查图及Mermaid架构图。未见明显缺字、卡片重叠或大面积深色块。Word中四张图宽均为15.5cm，高约9.24/6.32/7.97/7.97cm，最小文字估算9.73/10.34/9.59/9.59pt。缩放图用于检查阅读大小，**不是Word页面截图**。四张内嵌PNG与源PNG逐张哈希一致，普通表格为1.2倍。Mermaid真实主编排生成5图/5图题，18个普通表格段落仍1.2倍，正文1.75倍，仍为7次确定性LLM边界调用。

未修改generate_docx.py、原业务编排器、研究/客户洞察/写作核心逻辑，不新增依赖。原数量上限、插入与数据校验继续复用。图片自身高度变化可能影响分页，不能用格式代码未变代替分页验收。

## 未解决项与复现

附件仅包含本轮文字要求，没有四张原始参考图片；本次按文字给出的色值及设计原则实施，未宣称逐图对照参考截图。最终Word页面仍因缺少打包LibreOffice而未渲染，无法确认跨页配图协调、图题跨页或最终字形显示。长篇真实LLM联调未运行。自动主题选择是轻量规则，不等于完整语义分类；本轮固定样本的字号通过估算，不代表任意复杂长图均可读，仍需沿用拆图策略并做实际页面检查。

```powershell
python -X utf8 scripts/verify_visual_style.py --output-dir artifacts/visual-style/after
python -m pytest tests -q --junitxml artifacts/visual-style/pytest-results.xml
$env:PUPPETEER_EXECUTABLE_PATH='C:/Program Files/Google/Chrome/Application/chrome.exe'
python -X utf8 scripts/verify_visualization.py --output-dir artifacts/visual-style/mermaid --engine mmdc --mmdc-bin artifacts/test-tools/node_modules/.bin/mmdc.cmd
```

所有固定样本保存在`artifacts/visual-style/`：before、after、mermaid及baseline-source。不要用新版命令覆盖before。复现主流水线可替换本地mmdc路径；不需要上传业务资料。
