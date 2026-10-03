#!/usr/bin/env python3
"""
生成专业的解决方案 DOCX 文档

将 Markdown 格式的解决方案内容转换为排版精美的 DOCX 文档，
包含封面、目录、页眉页脚等专业排版元素，并自动去除 Markdown 格式符号。
"""

import os
import sys
import argparse
import re
import json
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---- 视觉规范常量（对标深度研报样例：墨黑 + 深海蓝主色 + 活力橙辅色，全篇衬线）----
COLOR_INK = RGBColor(0x1B, 0x1D, 0x1E)       # 章标题/封面主标题：墨黑
COLOR_PRIMARY = RGBColor(0x20, 0x4B, 0x8C)   # 深海蓝：节标题/装饰条/类型标签
COLOR_ACCENT = RGBColor(0xF4, 0x59, 0x38)    # 活力橙：次级强调/装饰强调点
COLOR_BODY = RGBColor(0x1B, 0x1D, 0x1E)      # 正文：墨黑（衬线小字高对比）
COLOR_GRAY = RGBColor(0x6F, 0x76, 0x79)       # 元数据：钢灰（对标样例）
COLOR_SUMMARY = RGBColor(0x4A, 0x4A, 0x4A)   # 封面摘要段：深灰（对标样例 16pt）
COLOR_CAPTION = RGBColor(0x9B, 0x9B, 0x9B)   # 图表注释浅灰
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TABLE_HEADER_BG = "204B8C"                   # 表头：深海蓝底
TABLE_HEADER_FG = "FFFFFF"                   # 表头文字：白
TABLE_LINE = "D9D9D9"                        # 表格内浅灰横线
FONT_CJK_BODY = "Noto Serif SC"   # 正文中文衬线（全篇对齐参考研报：Noto Serif SC Regular）
FONT_CJK_HEAD = "Noto Serif SC"   # 标题中文衬线（加粗=Noto Serif SC Bold，对标研报）
FONT_LATIN = "Noto Serif SC"      # 英文/数字衬线（参考研报拉丁字形亦出自 Noto Serif SC，全篇统一）


def style_run(run, size=10.5, color=COLOR_BODY, bold=False, italic=False,
              cjk_font=FONT_CJK_BODY, latin_font=FONT_LATIN, letter_spacing=None):
    """统一设置中英文字体、字号、颜色、字重。letter_spacing 单位 pt。"""
    run.font.name = latin_font
    run._element.rPr.rFonts.set(qn('w:eastAsia'), cjk_font)
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    if letter_spacing:
        rPr = run._element.get_or_add_rPr()
        spacing = OxmlElement('w:spacing')
        spacing.set(qn('w:val'), str(int(letter_spacing * 20)))
        rPr.append(spacing)


def set_paragraph_border(paragraph, edge="bottom", color="204B8C", size=12, space=4):
    """给段落加单边框（bottom=分隔线，left=竖线引导）。"""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    border = OxmlElement(f'w:{edge}')
    border.set(qn('w:val'), 'single')
    border.set(qn('w:sz'), str(size))
    border.set(qn('w:space'), str(space))
    border.set(qn('w:color'), color)
    pBdr.append(border)
    pPr.append(pBdr)


def add_dash(doc, width_cm=1.27, height_cm=0.06, fill="204B8C"):
    """封面短装饰条（对标样例：36pt × 1.5pt 细横条；可用 fill 参数换色）。"""
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    cell = table.rows[0].cells[0]
    cell.width = Cm(width_cm)
    table.rows[0].height = Cm(height_cm)
    table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    set_cell_shading(cell, fill)
    # 去掉表格边框与单元格边距
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for edge in ('top', 'bottom', 'left', 'right', 'insideH', 'insideV'):
        border = OxmlElement(f'w:{edge}')
        border.set(qn('w:val'), 'none')
        tblBorders.append(border)
    tblPr.append(tblBorders)
    cell.paragraphs[0].paragraph_format.space_before = Pt(0)
    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    run = cell.paragraphs[0].add_run(" ")
    run.font.size = Pt(2)
    return table


def set_run_shading(run, fill="F2F2F2"):
    """给 run 加底色（用于封面类型标签）。"""
    rPr = run._element.get_or_add_rPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), fill)
    rPr.append(shd)


def set_cell_shading(cell, fill):
    """设置表格单元格底色。"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def set_cell_border(cell, edge, size=6, color="1A1A1A"):
    """设置单元格单边框（三线表用）。"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn('w:tcBorders'))
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    border = OxmlElement(f'w:{edge}')
    border.set(qn('w:val'), 'single')
    border.set(qn('w:sz'), str(size))
    border.set(qn('w:color'), color)
    tcBorders.append(border)


def set_table_three_line_borders(table):
    """研报表格：顶/底深青灰线，行间浅灰横线，无竖线。"""
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    edges = (('top', 'single', '12', TABLE_HEADER_BG),
             ('bottom', 'single', '12', TABLE_HEADER_BG),
             ('insideH', 'single', '4', TABLE_LINE),
             ('left', 'none', None, None),
             ('right', 'none', None, None),
             ('insideV', 'none', None, None))
    for edge, val, sz, color in edges:
        border = OxmlElement(f'w:{edge}')
        border.set(qn('w:val'), val)
        if sz:
            border.set(qn('w:sz'), sz)
            border.set(qn('w:color'), color)
        tblBorders.append(border)
    tblPr.append(tblBorders)


def add_rich_text(paragraph, text, size=10.5, color=COLOR_BODY):
    """添加正文 run，**加粗** 片段转为 bold run（其余 Markdown 符号照常清理）。"""
    parts = re.split(r'\*\*(.+?)\*\*', text)
    for i, part in enumerate(parts):
        if not part:
            continue
        run = paragraph.add_run(clean_markdown_format(part))
        style_run(run, size=size, color=color, bold=(i % 2 == 1))


def clean_markdown_format(text):
    """
    去除 Markdown 格式符号
    
    Args:
        text: 包含 Markdown 格式的文本
    
    Returns:
        清理后的纯文本
    """
    if not text:
        return text
    
    # 去除加粗 **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    # 去除斜体 *text*
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    # 去除删除线 ~~text~~
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    
    # 去除行内代码 `text`
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # 去除链接 [text](url)，保留 text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    
    # 去除无序列表标记（行首的 - 或 * 或 +）
    text = re.sub(r'^[\s]*[-*+][\s]+', '', text, flags=re.MULTILINE)
    
    # 去除有序列表标记（行首的 1. 或 2. 等）
    text = re.sub(r'^[\s]*\d+\.[\s]+', '', text, flags=re.MULTILINE)
    
    # 去除标题标记（行首的 #）
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    # 去除分隔线（--- 或 *** 等）
    text = re.sub(r'^[\s]*[-*_]{3,}[\s]*$', '', text, flags=re.MULTILINE)
    
    # 去除引用标记（行首的 >）
    text = re.sub(r'^[\s]*>[\s]*', '', text, flags=re.MULTILINE)
    
    # 去除多余的空行（连续3个及以上换行符改为2个）
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def set_chinese_font(run, font_name="宋体", size=11):
    """设置中文字体"""
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = Pt(size)


def set_body_paragraph_format(paragraph):
    """正文段落：首行缩进2字符、1.75倍行距、段前后各0.5行。"""
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(22)  # 约等于 11pt 字体下首行缩进2字符
    fmt.line_spacing = 1.75
    fmt.space_before = Pt(6)
    fmt.space_after = Pt(6)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def setup_page_layout(doc):
    """A4 版式（对标样例 595.3×841.9pt）：四边距 2.54cm，营造留白感。"""
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.header_distance = Cm(1.5)
    section.footer_distance = Cm(1.75)


def setup_styles(doc):
    """全局样式：正文墨黑衬线、章标题墨黑、节标题深海蓝。"""
    normal_style = doc.styles['Normal']
    normal_style.font.name = FONT_LATIN
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = COLOR_BODY
    normal_style._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_CJK_BODY)

    heading1 = doc.styles['Heading 1']
    heading1.font.name = FONT_LATIN
    heading1.font.size = Pt(20)
    heading1.font.bold = True
    heading1.font.color.rgb = COLOR_INK
    heading1._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_CJK_HEAD)
    heading1.paragraph_format.space_before = Pt(18)
    heading1.paragraph_format.space_after = Pt(14)
    heading1.paragraph_format.line_spacing = 1.3

    heading2 = doc.styles['Heading 2']
    heading2.font.name = FONT_LATIN
    heading2.font.size = Pt(18)
    heading2.font.bold = True
    heading2.font.color.rgb = COLOR_INK
    heading2._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_CJK_HEAD)
    heading2.paragraph_format.space_before = Pt(18)
    heading2.paragraph_format.space_after = Pt(15)
    heading2.paragraph_format.line_spacing = 1.3

    heading3 = doc.styles['Heading 3']
    heading3.font.name = FONT_LATIN
    heading3.font.size = Pt(14)
    heading3.font.bold = True
    heading3.font.color.rgb = COLOR_PRIMARY
    heading3._element.rPr.rFonts.set(qn('w:eastAsia'), FONT_CJK_HEAD)
    heading3.paragraph_format.space_before = Pt(14)
    heading3.paragraph_format.space_after = Pt(8)
    heading3.paragraph_format.line_spacing = 1.25


def add_page_number_footer(doc):
    """页脚居中页码（浅灰小字）。"""
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    run_el = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), FONT_LATIN)
    rFonts.set(qn('w:hAnsi'), FONT_LATIN)
    rPr.append(rFonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '18')  # 9pt
    rPr.append(sz)
    color = OxmlElement('w:color')
    color.set(qn('w:val'), '9B9B9B')
    rPr.append(color)
    run_el.append(rPr)
    t = OxmlElement('w:t')
    t.text = '1'
    run_el.append(t)
    fld.append(run_el)
    p._p.append(fld)


def enable_font_embedding(doc):
    """在 word/settings.xml 写入嵌入字体标志：在 Word 中另存为时自动嵌入"用到的字形子集"，
    使 Noto Serif SC 等自定义字体可跨机器保真（文件体积小，仅含文档实际用到的字形）。
    WPS/其他查看器忽略该标志亦不影响正常打开。"""
    try:
        settings = doc.settings.element
    except AttributeError:
        settings = doc.settings._element
    for tag in ("w:embedTrueTypeFonts", "w:saveSubsetFonts"):
        el = OxmlElement(tag)
        settings.insert(0, el)


def create_solution_docx(content, output_path, project_name, customer_name, input_base_dir,
                         subtitle="", doc_type="深度研究 / 解决方案", abstract=""):
    """
    创建解决方案 DOCX 文档

    Args:
        content: 文档内容（Markdown格式）
        output_path: 输出文件路径
        project_name: 项目名称
        customer_name: 客户名称
        input_base_dir: 输入Markdown所在目录（用于解析图片相对路径）
        subtitle: 封面副标题（可选，默认用 customer_name）
        doc_type: 封面类型标签文字（如 "深度研究"、"风险分析"）
        abstract: 封面摘要（可选，竖线引导的斜体灰字区）
    """
    doc = Document()

    # 设置文档版式与样式
    setup_page_layout(doc)
    setup_styles(doc)
    add_page_number_footer(doc)

    # 1. 添加封面
    add_cover_page(doc, project_name, customer_name, subtitle=subtitle,
                   doc_type=doc_type, abstract=abstract)

    # 2. 添加分页符
    doc.add_page_break()

    # 3. 添加目录占位符
    add_toc_placeholder(doc)

    # 4. 添加分页符
    doc.add_page_break()

    # 5. 解析并添加正文内容
    add_body_content(doc, content, input_base_dir)

    # 6. 嵌入字体标志（Word 另存为时子集化，保证自定义字体跨机器一致）
    enable_font_embedding(doc)

    # 7. 保存文档
    doc.save(output_path)
    print(f"文档已生成: {output_path}")
    return output_path


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
COVER_BG_IMAGE = ASSETS_DIR / "cover_bg_a4.png"


def add_page_background(doc, anchor_paragraph):
    """整页背景装饰（对标研报封面双大圆水印）。

    将 A4 透明 PNG（右上深海蓝大圆 + 左下活力橙大圆，低透明度）作为浮动图片
    插入：衬于文字下方（behindDoc=1）、锚定到页面 (0,0)、尺寸铺满整页。
    """
    if not COVER_BG_IMAGE.exists():
        return
    section = doc.sections[0]
    run = anchor_paragraph.add_run()
    run.add_picture(str(COVER_BG_IMAGE),
                    width=section.page_width, height=section.page_height)

    # 把 wp:inline 改写为 wp:anchor（页面锚定 + 衬于文字下方）
    drawing = run._element.find(qn('w:drawing'))
    if drawing is None:
        return
    inline = drawing.find(qn('wp:inline'))
    if inline is None:
        return
    anchor = OxmlElement('wp:anchor')
    for key, val in (('distT', '0'), ('distB', '0'), ('distL', '0'), ('distR', '0'),
                     ('simplePos', '0'), ('relativeHeight', '0'), ('behindDoc', '1'),
                     ('locked', '1'), ('layoutInCell', '1'), ('allowOverlap', '1')):
        anchor.set(key, val)

    simple_pos = OxmlElement('wp:simplePos')
    simple_pos.set('x', '0')
    simple_pos.set('y', '0')

    pos_h = OxmlElement('wp:positionH')
    pos_h.set('relativeFrom', 'page')
    off_h = OxmlElement('wp:posOffset')
    off_h.text = '0'
    pos_h.append(off_h)

    pos_v = OxmlElement('wp:positionV')
    pos_v.set('relativeFrom', 'page')
    off_v = OxmlElement('wp:posOffset')
    off_v.text = '0'
    pos_v.append(off_v)

    extent = inline.find(qn('wp:extent'))
    doc_pr = inline.find(qn('wp:docPr'))
    graphic = inline.find(qn('a:graphic'))
    wrap_none = OxmlElement('wp:wrapNone')

    for el in (simple_pos, pos_h, pos_v, extent, wrap_none, doc_pr, graphic):
        if el is not None:
            anchor.append(el)

    drawing.remove(inline)
    drawing.append(anchor)


def add_cover_page(doc, project_name, customer_name, subtitle="", doc_type="深度研究 / 解决方案", abstract=""):
    """封面（对标研报样例）：左对齐垂直流 + 双大圆水印背景。
    短蓝条 → 13pt 类型标签 → 40pt 墨黑衬线大标题 → 短蓝条 → 16pt 灰色摘要 → 11pt 元数据。
    垂直节奏对标样例：条①(页顶~44pt) → 标签(+100pt) → 标题(+29pt) → 条②(+50pt) → 摘要(+39pt) → 元数据(+44pt)。
    """
    # 顶部留白（约 44pt，对标样例装饰条距页顶位置）
    bg_anchor = None
    for _ in range(3):
        p = doc.add_paragraph()
        if bg_anchor is None:
            bg_anchor = p

    # 整页背景装饰：右上深海蓝大圆 + 左下活力橙大圆（水印级透明度，衬于文字下方）
    add_page_background(doc, bg_anchor)

    # 短装饰条①（深海蓝细条）
    add_dash(doc)

    # 类型标签：13pt、字距拉开、深海蓝（与装饰条间距约 100pt）
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(doc_type)
    style_run(run, size=13, color=COLOR_PRIMARY, cjk_font=FONT_CJK_HEAD, letter_spacing=3)
    p.paragraph_format.space_before = Pt(100)
    p.paragraph_format.space_after = Pt(0)

    # 主标题：40pt 墨黑衬线加粗（对标样例），行距 1.2
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(project_name)
    style_run(run, size=40, color=COLOR_INK, bold=True, cjk_font=FONT_CJK_HEAD)
    p.paragraph_format.space_before = Pt(28)
    p.paragraph_format.line_spacing = 1.2
    p.paragraph_format.space_after = Pt(48)

    # 短装饰条②（深海蓝细条）
    add_dash(doc)

    # 摘要段：16pt 深灰常规体，行距 1.7（对标样例）
    if abstract:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(abstract)
        style_run(run, size=16, color=COLOR_SUMMARY)
        p.paragraph_format.space_before = Pt(38)
        p.paragraph_format.line_spacing = 1.7
        p.paragraph_format.space_after = Pt(0)

    # 元数据：11pt 钢灰两行（年月 + 机构），行距对标样例
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(datetime.now().strftime('%Y年%m月'))
    style_run(run, size=11, color=COLOR_GRAY)
    p.paragraph_format.space_before = Pt(42)
    p.paragraph_format.space_after = Pt(0)

    org = subtitle or customer_name
    if org:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(org)
        style_run(run, size=11, color=COLOR_GRAY)
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after = Pt(0)


def add_toc_placeholder(doc):
    """目录页：居中墨黑标题，无分隔线（对标样例）。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("目  录")
    style_run(run, size=20, color=COLOR_INK, bold=True, cjk_font=FONT_CJK_HEAD)
    p.paragraph_format.space_after = Pt(18)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("[ 目录将在打开文档时自动生成 ]")
    style_run(run, size=10.5, color=COLOR_CAPTION)


def parse_markdown_table(lines, start_index):
    """
    解析 Markdown 表格
    
    Args:
        lines: 所有行
        start_index: 表格开始的行索引
    
    Returns:
        (table_data, end_index): 表格数据和结束行索引
    """
    table_data = []
    i = start_index
    
    # 读取表头
    if i < len(lines) and lines[i].startswith('|'):
        header_row = [cell.strip() for cell in lines[i].split('|')[1:-1]]
        # 清理表头中的 Markdown 格式
        header_row = [clean_markdown_format(cell) for cell in header_row]
        table_data.append(header_row)
        i += 1
    
    # 跳过分隔行（|---|---|）
    if i < len(lines) and lines[i].startswith('|') and '---' in lines[i]:
        i += 1
    
    # 读取数据行
    while i < len(lines) and lines[i].startswith('|'):
        data_row = [cell.strip() for cell in lines[i].split('|')[1:-1]]
        # 清理单元格中的 Markdown 格式
        data_row = [clean_markdown_format(cell) for cell in data_row]
        table_data.append(data_row)
        i += 1
    
    return table_data, i


def parse_markdown_image(line):
    """解析 Markdown 图片语法：![alt](path)"""
    match = re.match(r'^\s*!\[(.*?)\]\((.*?)\)\s*$', line)
    if not match:
        return None, None
    alt = match.group(1).strip()
    path = match.group(2).strip()
    return alt, path


def resolve_image_path(image_path, base_dir):
    """解析图片路径，支持相对路径。"""
    p = Path(image_path)
    if p.is_absolute():
        return p
    return Path(base_dir) / p


def add_image_to_doc(doc, image_abs_path, caption, figure_index):
    """插入图片与图题（9pt 斜体灰注释）。"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run()
    section = doc.sections[-1]
    available = section.page_width - section.left_margin - section.right_margin
    # Keep the original width unless margins or a tall image require a smaller size.
    from PIL import Image
    with Image.open(image_abs_path) as image:
        ratio = image.height / image.width
    height_limit = section.page_height - section.top_margin - section.bottom_margin - Cm(2.5)
    width = min(Cm(15.5), available, int(height_limit / ratio))
    run.add_picture(str(image_abs_path), width=width)
    p.paragraph_format.keep_with_next = True

    caption_text = caption if caption else f"逻辑图{figure_index}"
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.first_line_indent = Pt(0)
    cp.paragraph_format.space_before = Pt(0)
    cp.paragraph_format.space_after = Pt(10)
    cp.paragraph_format.line_spacing = 1.2
    c_run = cp.add_run(f"图{figure_index} {caption_text}")
    style_run(c_run, size=9, color=COLOR_CAPTION)


def add_table_to_doc(doc, table_data):
    """研报表格：表头深青灰底白字加粗居中；数据行居中、行间浅灰横线。"""
    if not table_data or len(table_data) < 2:
        return

    rows = len(table_data)
    cols = len(table_data[0])

    table = doc.add_table(rows=rows, cols=cols)
    table.autofit = True
    set_table_three_line_borders(table)

    for i, row_data in enumerate(table_data):
        row = table.rows[i]
        is_header = (i == 0)
        for j, cell_text in enumerate(row_data):
            cell = row.cells[j]
            if is_header:
                set_cell_shading(cell, TABLE_HEADER_BG)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.2
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            p.paragraph_format.first_line_indent = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            run = p.add_run(cell_text)
            if is_header:
                style_run(run, size=10.5, color=COLOR_WHITE, bold=True, cjk_font=FONT_CJK_HEAD)
            else:
                style_run(run, size=10.5, color=COLOR_BODY)
    set_table_line_spacing(table)


def set_table_line_spacing(table):
    """Only paragraph line spacing, including nested cells/multiple paragraphs."""
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.line_spacing = 1.2
                paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            for nested in cell.tables:
                set_table_line_spacing(nested)


def add_body_content(doc, content, input_base_dir):
    """添加正文内容"""
    lines = content.split('\n')
    i = 0
    figure_index = 1
    
    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("<!-- solution-source:") and line.endswith(" -->"):
            try:
                source = json.loads(line[len("<!-- solution-source:"):-4])
                p = doc.add_paragraph()
                p.paragraph_format.first_line_indent = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(6)
                style_run(p.add_run("来源：" + source), size=9, color=COLOR_CAPTION)
            except (ValueError, TypeError):
                pass
            i += 1
            continue
        if line.startswith("<!-- solution-") or line == "<!-- /solution-figure -->":
            i += 1
            continue

        # 检查是否是图片
        alt_text, image_path = parse_markdown_image(line)
        if image_path:
            image_abs_path = resolve_image_path(image_path, input_base_dir)
            if image_abs_path.exists():
                add_image_to_doc(doc, image_abs_path, alt_text, figure_index)
                figure_index += 1
            else:
                p = doc.add_paragraph()
                p.paragraph_format.first_line_indent = Pt(0)
                run = p.add_run(f"[图片未找到] {image_path}")
                set_chinese_font(run, "宋体", 10)
                run.font.color.rgb = RGBColor(160, 0, 0)
            i += 1
            continue
        
        # 检查是否是表格开始
        if line.startswith('|'):
            table_data, i = parse_markdown_table(lines, i)
            add_table_to_doc(doc, table_data)
            continue
        
        # 跳过空行，避免在 Word 中产生“段落间空一行”
        if not line:
            i += 1
            continue
        
        # 清理当前行的 Markdown 格式
        cleaned_line = clean_markdown_format(line)
        
        # 处理标题（对标研报：# 文档题-墨黑 / ## 章-墨黑 / ### 节-深海蓝 / #### 段引导）
        if line.startswith('# '):
            p = doc.add_paragraph()
            p.style = 'Heading 1'
            run = p.add_run(cleaned_line)
            style_run(run, size=20, color=COLOR_INK, bold=True, cjk_font=FONT_CJK_HEAD)

        elif line.startswith('#### '):
            p = doc.add_paragraph()
            run = p.add_run(cleaned_line)
            style_run(run, size=12, color=COLOR_BODY, bold=True, cjk_font=FONT_CJK_HEAD)
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(4)

        elif line.startswith('### '):
            p = doc.add_paragraph()
            p.style = 'Heading 3'
            run = p.add_run(cleaned_line)
            style_run(run, size=14, color=COLOR_PRIMARY, bold=True, cjk_font=FONT_CJK_HEAD)

        elif line.startswith('## '):
            p = doc.add_paragraph()
            p.style = 'Heading 2'
            run = p.add_run(cleaned_line)
            style_run(run, size=18, color=COLOR_INK, bold=True, cjk_font=FONT_CJK_HEAD)

        else:
            # 普通段落：保留 **加粗** 为重点强调（关键数据/结论）
            p = doc.add_paragraph()
            add_rich_text(p, line, size=11)
            set_body_paragraph_format(p)
        
        i += 1


def main():
    parser = argparse.ArgumentParser(description='生成解决方案 DOCX 文档')
    parser.add_argument('--input', '-i', required=True, help='输入 Markdown 文件路径')
    parser.add_argument('--output', '-o', help='输出 DOCX 文件路径（可选）')
    parser.add_argument('--project', '-p', required=True, help='项目名称')
    parser.add_argument('--customer', '-c', required=True, help='客户名称')
    parser.add_argument('--subtitle', default='', help='封面副标题（可选，默认用客户名称）')
    parser.add_argument('--doctype', default='深度研究 / 解决方案', help='封面类型标签，如 "深度研究 / 风险分析"')
    parser.add_argument('--abstract', default='', help='封面摘要（可选，竖线引导斜体区）')
    
    args = parser.parse_args()
    
    # 读取输入文件
    if not os.path.exists(args.input):
        print(f"错误：输入文件不存在: {args.input}")
        return 1
    
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取输入文件时出错: {str(e)}")
        return 1
    
    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        # 生成默认文件名：YYYYMMDD_客户简称_项目名_方案.docx
        date_str = datetime.now().strftime('%Y%m%d')
        customer_short = args.customer[:4] if len(args.customer) > 4 else args.customer
        project_short = args.project[:6] if len(args.project) > 6 else args.project
        # 清理文件名中的非法字符
        customer_short = re.sub(r'[<>:"/\\|?*]', '', customer_short)
        project_short = re.sub(r'[<>:"/\\|?*]', '', project_short)
        output_path = f"{date_str}_{customer_short}_{project_short}_方案.docx"
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            print(f"创建输出目录时出错: {str(e)}")
            return 1
    
    # 生成文档
    try:
        input_base_dir = str(Path(args.input).resolve().parent)
        create_solution_docx(content, output_path, args.project, args.customer, input_base_dir,
                             subtitle=args.subtitle, doc_type=args.doctype,
                             abstract=args.abstract)
        return 0
    except Exception as e:
        print(f"生成文档时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
