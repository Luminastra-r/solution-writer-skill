"""Current solid-theme contract, optional accents and faithful fallback."""
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import pytest
from PIL import Image
from sample_solution import fixture
from solution_skill.visualization.pipeline import render_tasks
from solution_skill.visualization.planning import options
from solution_skill.visualization.theme import NS, PALETTES, apply_theme


def test_document_theme_consistency_and_override(tmp_path):
    req, _, _, tasks = fixture()
    req['visualization']['theme'] = 'sage'
    tasks[2]['theme'] = 'tech'
    items = render_tasks(tasks, tmp_path, req)['items']
    assert all(i['status'] == 'ok' for i in items)
    assert [i['theme'] for i in items] == ['data','sage','tech','sage','sage']
    assert all(i['gradient_mode'] == 'solid' for i in items)
    assert options({})['gradient_mode'] == 'solid'
    for key, value in [('theme','random'),('gradient_mode','random')]:
        with pytest.raises(ValueError):
            options({'visualization':{key:value}})


def test_auto_theme_deterministic(tmp_path):
    req, _, _, tasks = fixture()
    first = render_tasks(tasks[1:2], tmp_path/'first', req)
    second = render_tasks(tasks[1:2], tmp_path/'second', req)
    assert first['options']['theme'] == second['options']['theme'] == 'tech'
    req['raw_input'] = '运营服务体系'
    assert render_tasks(tasks[1:2], tmp_path/'third', req)['options']['theme'] == 'sage'


def test_optional_accent_samples_and_fallback_same_geometry(tmp_path):
    import svg_to_png
    req, _, _, tasks = fixture()
    req['visualization'].update(theme='tech',gradient_mode='controlled')
    good = render_tasks(tasks[1:2], tmp_path/'good', req)['items'][0]
    assert good['gradient_mode'] == 'controlled'
    r = ET.parse(good['svg_path']).getroot()
    assert r.find(f'.//{{{NS}}}linearGradient').get('gradientUnits') == 'objectBoundingBox'
    with Image.open(good['image_path']) as im:
        samples=[im.convert('RGB').getpixel((round(x*im.width/680),round(13*im.width/680))) for x in (24,38,54)]
        assert len(set(samples)) == 3
    with patch.object(svg_to_png,'convert_with_cairosvg',side_effect=RuntimeError('forced Cairo failure')), patch.object(svg_to_png,'ENGINES',[('svglib',svg_to_png.convert_with_svglib)]):
        flat = render_tasks(tasks[1:2], tmp_path/'flat', req)['items'][0]
    assert flat['status'] == 'ok' and flat['gradient_mode'] == 'solid_fallback'
    f = ET.parse(flat['svg_path']).getroot()
    assert f.find(f'.//{{{NS}}}linearGradient') is None
    for attr in ('viewBox','height','width'):
        assert r.get(attr) == f.get(attr)
    for tag in ('path','text','rect','g'):
        geometry=lambda root:[{k:v for k,v in n.attrib.items() if k in ('d','x','y','height','width','font-size','transform')} for n in root.iter(f'{{{NS}}}{tag}')]
        assert geometry(r) == geometry(f)
    with Image.open(flat['image_path']) as im:
        assert im.width == 1800


def test_standalone_converter_safe_fallback(tmp_path):
    import svg_to_png
    req, _, _, tasks = fixture()
    req['visualization']['gradient_mode'] = 'controlled'
    item = render_tasks(tasks[1:2], tmp_path, req)['items'][0]
    with patch.object(svg_to_png,'convert_with_cairosvg',side_effect=RuntimeError('forced')):
        result = svg_to_png.convert_svg(Path(item['svg_path']), tmp_path/'flat.png', 1200)
    assert 'fallback to solid' in result


def test_data_stays_solid_and_series_identifiable(tmp_path):
    req, _, _, tasks = fixture()
    req['visualization']['gradient_mode'] = 'controlled'
    req['visualization_data'][0]['series'] = [{'name':'甲','values':[30,-20,0,40]}, {'name':'乙','values':[20,10,-5,30]}]
    from matplotlib.figure import Figure
    original = Figure.savefig
    observed=[]
    def capture(fig,*args,**kwargs):
        ax=fig.axes[0]
        observed.append(([(list(l.get_ydata()),l.get_linestyle(),l.get_marker()) for l in ax.lines],ax.get_ylim()))
        return original(fig,*args,**kwargs)
    with patch.object(Figure,'savefig',capture):
        item=render_tasks([dict(tasks[0],chart='line')],tmp_path,req)['items'][0]
    assert item['gradient_mode'] == 'solid' and item['theme'] == 'data'
    series, limits=observed[0]
    assert series[0] == ([30,-20,0,40],'-','o') and series[1] == ([20,10,-5,30],'--','s')
    assert limits[0] < -20 and limits[1] > 40


def test_mermaid_remains_flat(tmp_path):
    path=tmp_path/'graph.svg'
    path.write_text(f'<svg xmlns="{NS}" class="flowchart" viewBox="0 0 200 60"><rect width="200" height="60" fill="#EDF2F8"/></svg>')
    apply_theme(path,{'type':'flowchart','theme':'sage'},'Microsoft YaHei','controlled')
    root=ET.parse(path).getroot()
    assert root.get('data-sw-gradient-mode') == 'solid'
    assert root.find(f'{{{NS}}}rect').get('fill') == PALETTES['sage']['card']
