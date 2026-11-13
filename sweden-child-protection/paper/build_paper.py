"""Build the Korean policy manuscript from authored prose and verified result CSVs.

Use the Python runtime returned by load_workspace_dependencies (python-docx).
No statistical estimation, network access, or imputation occurs here.
"""
from pathlib import Path
import csv, json, re, hashlib
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

PAPER=Path(__file__).resolve().parent
ROOT=PAPER.parent; RESULTS=ROOT/'results'; OUTPUT=PAPER/'output'
OUTPUT.mkdir(exist_ok=True)

def read(name,folder=RESULTS):
    with (folder/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def num(x,places=2):
    if x in ['',None]:return '미관측'
    return f'{float(x):.{places}f}'

def pval(x):
    x=float(x)
    return '<.001' if x<.001 else f'{x:.3f}'.lstrip('0')

def ci(row):return f'[{float(row["ci95_low"]):.2f}, {float(row["ci95_high"]):.2f}]'

NAMES={
 'foreign_born_share':'전체 주민 해외 출생',
 'foreign_background':'전체 아동 해외배경',
 'any_foreign_parent_among_Sweden_born':'스웨덴 출생 아동 한 명 이상 해외 출생 부모',
 'two_foreign_parents_among_Sweden_born':'스웨덴 출생 아동 양부모 해외 출생',
}
tables={}
def tab(key,caption,headers,rows,widths,note):
    assert sum(widths)<=325.5
    assert all(len(row)==len(headers) for row in rows)
    tables[key]=dict(caption=caption,headers=headers,rows=rows,widths=widths,note=note)

tab('measurement','<표 1> 자료의 측정 대상과 해석 범위',
 ['자료와 지표','단위와 기간','관측 내용과 한계'],[
 ['VIND28 및 전국 공표값','절차 응답\n문제제기용','교육보장 서면 절차. 2024년 34%는 전국 공표값이며 이번 51개 지역의 충족률이나 지원률이 아님'],
 ['Kolada U33401','지방정부·연도\n2022–2025','상반기 0–20세 사회복지 조사 평균 일수. 개인의 보호·입소 대기기간 아님'],
 ['Kolada N02926','지방정부·연도\n2015, 2022–2025','연말 전체 주민 중 해외 출생 비중. 사건 표본의 구성 아님'],
 ['SCB TAB4824','지방정부·연령·성별\n2015, 2022–2024','0–17세 아동의 출생지와 부모 출생배경. 2025년 값 없음'],
 ['SCB 대도시권 분류','51개 지방정부','스톡홀름 26, 예테보리 13, 말뫼 12. 시 내부 구역과 구분']
 ],[75,82,168],'출처: Kolada 지표 메타데이터, SCB TAB4824 및 공식 대도시권 집계 분류[3–5], 교육보장 절차의 공식 설명과 전국 공표값[12, 13].')

cov=read('coverage_by_year.csv'); nat=read('outcome_national_coverage.csv')
rows=[]
for year in [2022,2023,2024,2025]:
    row=[str(year)]
    for metro in ['Stor-Stockholm','Stor-Göteborg','Stor-Malmö','All 51']:
        x=next(v for v in cov if v['metro']==metro and v['year']==str(year) and v['variable']=='U33401_days')
        row.append(f'{x["n_observed"]}/{x["n_expected"]}')
    n=next(v for v in nat if v['year']==str(year)); row.append(n['n_outcome_observed']+'/290')
    rows.append(row)
tab('coverage','<표 2> 연도별 평균 조사기간의 관측 범위',['연도','스톡홀름','예테보리','말뫼','51개 전체','전국'],rows,
    [34,62,60,49,65,55],'각 셀은 관측 지방정부 수/해당 집단 전체 수다. 미관측은 0일이나 조사 미실시를 뜻하지 않는다. 출처: 공식 Kolada 응답의 직접 집계.')

tab('background','<표 3> SCB의 아동 출생배경 네 범주', ['기호·코드','공식 스웨덴어 범주명','한국어 정의'],[
 ['A · 08','utrikes födda','해외 출생 아동'],
 ['B · 4','inrikes födda med två utrikes födda föräldrar','스웨덴 출생\n양부모 해외 출생'],
 ['C · 5','inrikes födda med en inrikes och en utrikes född förälder','스웨덴 출생\n한 부모만 해외 출생'],
 ['D · 6','inrikes födda med två inrikes födda föräldrar','스웨덴 출생\n양부모 스웨덴 출생'],
 ],[46,181,98],'출처: SCB TAB4824 실시간 메타데이터[4]. 모든 범주에서 만 0–17세와 두 성별을 합산한다. A의 분류에는 부모의 출생지를 별도로 적용하지 않는다.')

desc=read('descriptives.csv'); rows=[]
for metro,name in [('Stor-Stockholm','스톡홀름'),('Stor-Göteborg','예테보리'),('Stor-Malmö','말뫼'),('All 51','전체')]:
    r=next(v for v in desc if v['year']=='2024' and v['variable']=='U33401_days' and v['metro']==metro)
    rows.append([name,r['n_observed']+'/'+r['n_expected'],num(r['mean']),num(r['sd']),num(r['min'],0),num(r['max'],0)])
tab('descriptives','<표 4> 2024년 평균 조사기간의 지역별 분포',['대도시권','관측/전체','평균 일수','표준편차','최솟값','최댓값'],rows,
    [64,55,58,57,45,46],'관측 지방정부별 동일 가중치 통계다. 사건 수 가중 평균이 아니다. 예테보리시의 2024년 값은 미관측이다. 출처: 본고 계산.')

regs=read('regressions.csv')
cross=[v for v in regs if v['specification']=='OLS_metro_FE' and not v['predictor'].endswith('_2015')]
tab('cross','<표 5> 2024년 대도시권 고정효과 단면 회귀',['인구구성 지표','계수','95% 구간','p값'],
    [[NAMES[r['predictor']],num(r['coefficient'],3),ci(r),pval(r['p_value'])] for r in cross],
    [131,49,99,46],'각 지표를 별도 추정했다. 모든 모형 n=44, HC3 표준오차와 t(n−k) 구간. 단위는 비중 1%포인트당 일수. 2015년 네 지표를 포함한 기본 단면 8개 검정의 BH 보정값은 모두 약 .419였다.')

panel=[v for v in regs if v['specification']=='OLS_municipality_year_FE']
tab('panel','<표 6> 지방정부와 연도 고정효과의 기본 패널 추정',['인구구성 지표','n/G','계수','95% 구간','p값'],
    [[NAMES[r['predictor']],r['n']+'/'+r['n_municipalities'],num(r['coefficient']),ci(r),pval(r['p_value'])] for r in panel],
    [111,44,43,85,42],'G는 지방정부 수. 첫 행은 2022–2025년, 나머지는 2022–2024년이다. 지방정부 군집 표준오차, t(G−1) 구간. 단위는 1%포인트당 일수. 해외배경·양부모 해외 출생의 BH 보정 p값은 각각 .046, .019다.')

x='two_foreign_parents_among_Sweden_born'; rows=[]
for spec,label in [('OLS_municipality_year_FE','기본 불균형패널'),('OLS_municipality_year_FE_balanced','균형패널'),
                   ('OLS_municipality_metro_by_year_FE','대도시권별 연도 효과')]:
    r=next(v for v in regs if v['specification']==spec and v['predictor']==x)
    rows.append([label,r['n']+'/'+r['n_municipalities'],num(r['coefficient']),ci(r),pval(r['p_value'])])
f=next(v for v in read('panel_same_sample_comparison.csv') if v['predictor']==x)
rows.append(['균형표본과 대도시권별 연도 효과','120/40',num(f['balanced_metro_year_beta']),
             f'[{float(f["balanced_metro_year_ci95_low"]):.2f}, {float(f["balanced_metro_year_ci95_high"]):.2f}]',pval(f['balanced_metro_year_p'])])
tab('panel_sensitivity','<표 7> 양부모 해외 출생 비중의 패널 민감도',['모형','n/G','계수','95% 구간','p값'],rows,
    [111,44,43,85,42],'모든 행은 2022–2024년이다. 지방정부 군집 표준오차와 유한표본 보정을 적용했다. 민감도 p값은 탐색적이며 다중검정 보정 전 값이다.')

loo=read('two_parent_leave_one_municipality_out.csv'); rows=[['제외 없음','6.70','.0048']]
for code in ['1407','0192','0139','1230','1231']:
    r=next(v for v in loo if v['specification']=='TWFE_unbalanced' and v['omitted_code']==code)
    rows.append([r['omitted_municipality']+' '+code,num(r['coefficient']),pval(r['p_value'])])
rows.extend([['Öckerö·Nynäshamn·Upplands-Bro 동시 제외','3.21','.263'],['상위 5개 지지 지방정부 동시 제외','1.10','.690']])
tab('influence','<표 8> 양부모 해외 출생 비중의 지방정부 제외 진단',['제외한 지방정부','재추정 계수','p값'],rows,
    [204,67,54],'기본 지역·연도 고정효과 모형을 매번 재추정했다. 집단 제외 순위는 전체 표본의 단일 제외에서 계수를 가장 낮추는 순서로 정한 사후 스트레스 테스트다. 상위 5곳은 앞의 세 곳에 Staffanstorp와 Burlöv를 더한 집단이다.')

fd=read('two_parent_first_difference_models.csv'); rows=[]
for spec,label in [('FD_adjacent_unbalanced','인접 연도 차분'),('FD_adjacent_metro_interval_unbalanced','인접 연도와 대도시권별 구간 효과'),
                   ('FD_endpoint_2022_2024','2022–2024년 차분'),('FD_endpoint_2022_2024_metro_controls','2022–2024년 차분과 대도시권 조정')]:
    r=next(v for v in fd if v['specification']==spec)
    rows.append([label,r['n']+'/'+r['municipalities'],num(r['coefficient']),ci(r),pval(r['p_value'])])
tab('fd','<표 9> 양부모 해외 출생 비중의 일차차분 추정',['모형','변화/G','계수','95% 구간','p값'],rows,
    [111,44,43,85,42],'연간 차분에는 실제 연속 관측만 사용하며 구간 효과를 포함한다. 연간 차분은 지방정부 군집, 양 끝 시점 차분은 HC3 표준오차를 사용했다. 비중 1%포인트당 일수이며 두 시점 차분을 1년 변화로 간주하지 않았다.')

tab('policy','<표 10> 정책 제안과 평가를 위한 관측 항목',['관리 과제','운영 방향','후속 평가 항목'],[
 ['절차와 도달의 분리','조사와 실제 지원의 시점을 별도 기록','요청·위험평가·지원 개시·배치·교육 재개일'],
 ['사례 부담과 인력','인구비중 단독 기준 대신 현장 수요 점검','진행 사례/담당자, 위험도, 통역, 결원·이직'],
 ['보고 품질','미관측과 서비스 미제공을 구분','누락 사유, 시스템 변경, 정의 적용 이력'],
 ['개입 평가','시범 도입 전 평가설계와 비교 가능성 검토','시행일, 대상 기준, 미종결·이탈, 접근권한']
 ],[67,122,136],'본고의 정책 제안이다. 각 항목의 효과나 비용 절감은 이번 집계자료로 추정하지 않았다.')

annual=read('metro_51_2024.csv',ROOT/'data'); rows=[]
for r in annual:
    metro={'Stor-Stockholm':'스톡홀름','Stor-Göteborg':'예테보리','Stor-Malmö':'말뫼'}[r['metro']]
    rows.append([r['municipality_code'],r['municipality'],metro,num(r['U33401_days'],1),num(float(r[x])*100)])
tab('appendix51','<표 A1> 51개 지방정부의 2024년 관측값',['코드','지방정부','대도시권','조사일수','양부모 비중 %'],rows,
    [35,92,62,57,79],'양부모 비중은 스웨덴 출생 0–17세 아동 중 양부모 해외 출생 비중이다. 조사일수 미관측은 공식 응답의 전체값이 없는 경우다. 모든 인구배경 값은 관측되었다. 출처: SCB·Kolada, 본고 계산.')

tab('evidence','<표 B1> 자료와 분석 결과의 증거 상태',['수치 또는 주장','근거와 확인 범위'],[
 ['51개 대도시권 구성','SCB 실시간 공식 구성원 코드와 Kolada 명칭 대조'],
 ['29,376개 아동 배경계수','SCB API와 공식 벌크 CSV의 전 셀 일치'],
 ['평균 조사기간과 회귀 결과','공식 응답으로 새로 계산, CSV·코드 제공'],
 ['영향력과 일차차분','제외 후 고정효과·분산 재추정, 행렬식 독립 검산'],
 ['2024년 보호시설 개편','정부 발표와 사회보건청 당시 안내 확인'],
 ['연도별 현장 측정동등성','현재 정의와 보고 변경은 확인, 전체 설문 이력 미확보'],
 ['개인별 보호 도달과 인과효과','사건 날짜·배경 또는 정당화된 도구 부재로 미추정']
 ],[124,201],'사용자 제공 선행 통합 원고는 구성과 개념 구분의 참고자료이며, 그 안의 별도 추정치는 본고 결과에 합산하지 않았다.')

REFERENCES=[
 ('[1] Socialdepartementet (2024). Ny reglering ska stärka rättigheterna för barn och vuxna i skyddat boende. 22 February.','https://www.regeringen.se/pressmeddelanden/2024/02/ny-reglering-ska-starka-rattigheterna-for-barn-och-vuxna-i-skyddat-boende/'),
 ('[2] Socialstyrelsen (2024). Nya bestämmelser om skyddat boende. Meddelandeblad 2/2024, artikelnummer 2024-3-8989.','https://www.socialstyrelsen.se/contentassets/05d9681ae32f495481524a0b652e1301/2024-3-8989.pdf'),
 ('[3] RKA/Kolada (2026 접속). API v3 및 U33401·N02926 지표 메타데이터.','https://api.kolada.se/v3/kpi/U33401,N02926'),
 ('[4] Statistiska centralbyrån (2025). Antal personer med utländsk eller svensk bakgrund (fin indelning) efter region, ålder och kön. TAB4824 / UtlSvBakgFin, 2002–2024. 갱신 2025-03-21.','https://statistikdatabasen.scb.se/api/v2/tables/TAB4824/metadata?lang=sv'),
 ('[5] Statistiska centralbyrån (2026 접속). Storstadsområden 2005–, 공식 집계 분류와 구성 지방정부.','https://statistikdatabasen.scb.se/api/v2/codeLists/agg_RegionStoromr05-_1?lang=sv'),
 ('[6] RKA (2025). Förändringar i insamlingen av data till KKiK 2025. Enköping 공식 회의자료 보관본 및 RKA 보고 안내.','https://politik.enkoping.se/welcome-sv/namnder-styrelser/kommunfullmaktige/kommunfullmaktige-2025-11-04/agenda/forandringar-i-insamlingen-av-data-till-kkik-2025pdf?downloadMode=download'),
 ('[7] Åslund, O. and Fredriksson, P. (2005). Ethnic enclaves and welfare cultures – quasi-experimental evidence. IFAU Working Paper 2005:8.','https://www.ifau.se/globalassets/pdf/se/2005/wp05-08.pdf'),
 ('[8] Borusyak, K., Hull, P. and Jaravel, X. (2022). Quasi-Experimental Shift-Share Research Designs. Review of Economic Studies, 89(1), 181–213.','https://www.nber.org/papers/w24997'),
 ('[9] Adão, R., Kolesár, M. and Morales, E. (2019). Shift-Share Designs: Theory and Inference. Quarterly Journal of Economics, 134(4), 1949–2010.','https://www.nber.org/papers/w24944'),
 ('[10] Jaeger, D. A., Ruist, J. and Stuhler, J. (2018). Shift-Share Instruments and the Impact of Immigration. NBER Working Paper 24285.','https://www.nber.org/papers/w24285'),
 ('[11] 선행 통합 연구원고 (2026). 이주배경 인구가 집중된 지역에서 아동보호 행정 대응은 더 느린가. 스웨덴의 교육보장 절차와 사회복지 조사 장기화에 관한 이중 수준 분석. 11월 11일. 사용자 제공 미간행 원고.',''),
 ('[12] Socialstyrelsen (2019). Indikatorer – öppna jämförelser 2019. Socialtjänst och kommunal hälso- och sjukvård. 지표 80, 110–111쪽.','https://www.socialstyrelsen.se/globalassets/sharepoint-dokument/dokument-webb/oppna-jamforelser/oppna-jamforelser-socialtjanst-2019-indikatorer.pdf'),
 ('[13] Socialstyrelsen (2025). Individ- och familjeomsorg – Lägesrapport 2025. Artikelnummer 2025-3-9498. 39, 43쪽, 표 5.','https://www.socialstyrelsen.se/contentassets/24e1b0146b8a446a9096eb4cdf3e81b2/2025-3-9498.pdf'),
]

doc=Document(); section=doc.sections[0]
section.page_width=Pt(448); section.page_height=Pt(655)
section.left_margin=Pt(61.5); section.right_margin=Pt(61.5)
section.top_margin=Pt(51); section.bottom_margin=Pt(47)
section.header_distance=Pt(25); section.footer_distance=Pt(22)
section.different_first_page_header_footer=True
settings=doc.settings.element
settings.append(OxmlElement('w:evenAndOddHeaders'))
core=doc.core_properties; core.title='이주배경 인구가 많은 지역의 조사는 더 오래 걸리는가'; core.author=''; core.subject='스웨덴 51개 대도시권 지방정부 정책연구'; core.keywords='Sweden, child welfare, migrant background, municipal administration'; core.comments=''

def font(run,name='바탕',size=None,bold=None):
    run.font.name=name
    rf=run._element.get_or_add_rPr().get_or_add_rFonts()
    for a in ['ascii','hAnsi','eastAsia','cs']:rf.set(qn('w:'+a),name)
    if size is not None:run.font.size=Pt(size)
    if bold is not None:run.bold=bold

normal=doc.styles['Normal']; normal.font.name='바탕'; normal.font.size=Pt(10.5)
normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'바탕')
normal.paragraph_format.line_spacing=1.48
normal.paragraph_format.space_after=Pt(5)
normal.paragraph_format.first_line_indent=Pt(10.5)
normal.paragraph_format.widow_control=True
for name,size in [('Title',16),('Subtitle',11.3),('Heading 1',13),('Heading 2',11.1),('Heading 3',10.5)]:
    s=doc.styles[name]; s.font.name='바탕'; s.font.size=Pt(size); s.font.bold=name!='Subtitle'
    s.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'바탕')
    s.font.color.rgb=RGBColor(0,0,0)
    s.font.italic=False
    s.paragraph_format.first_line_indent=Pt(0)
    s.paragraph_format.keep_with_next=True
    s.paragraph_format.space_before=Pt(14 if name=='Heading 1' else 8)
    s.paragraph_format.space_after=Pt(7)
    if name in ['Title','Subtitle','Heading 1']:s.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
doc.styles['Title'].paragraph_format.line_spacing=1.3
doc.styles['Subtitle'].paragraph_format.line_spacing=1.35

def page_field(p):
    r=p.add_run(); fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); r._r.addnext(fld)
    font(r,size=8.3)
for header,even in [(section.header,False),(section.even_page_header,True)]:
    p=header.paragraphs[0]; p.paragraph_format.first_line_indent=Pt(0)
    p.alignment=WD_ALIGN_PARAGRAPH.LEFT if even else WD_ALIGN_PARAGRAPH.RIGHT
    if even:page_field(p)
    r=p.add_run(('  ' if even else '')+'스웨덴 대도시권 아동보호 행정'+('' if even else '  ')); font(r,size=8.3)
    if not even:page_field(p)

def para(text,style=None):
    p=doc.add_paragraph(style=style)
    r=p.add_run(text); font(r)
    if not style:p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    return p

def hyperlink(p,label,url):
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),p.part.relate_to(url,RT.HYPERLINK,is_external=True))
    r=OxmlElement('w:r'); pr=OxmlElement('w:rPr')
    f=OxmlElement('w:rFonts'); f.set(qn('w:eastAsia'),'바탕'); f.set(qn('w:ascii'),'바탕'); pr.append(f)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),'18');pr.append(sz); r.append(pr)
    t=OxmlElement('w:t');t.text=label;r.append(t);h.append(r);p._p.append(h)

def table_block(t):
    p=para(t['caption']); p.paragraph_format.first_line_indent=Pt(0); p.paragraph_format.keep_with_next=True
    p.paragraph_format.space_before=Pt(7); p.paragraph_format.space_after=Pt(5)
    for r in p.runs:font(r,size=9.7,bold=True)
    tbl=doc.add_table(rows=1,cols=len(t['headers'])); tbl.alignment=WD_TABLE_ALIGNMENT.CENTER; tbl.autofit=False
    for col,w in zip(tbl.columns,t['widths']):col.width=Pt(w)
    pr=tbl._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for edge in ['top','bottom','insideH','left','right','insideV']:
        e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single' if edge in ['top','bottom'] else 'nil')
        e.set(qn('w:sz'),'5'); e.set(qn('w:color'),'444444'); borders.append(e)
    pr.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for side,val in [('top',65),('bottom',65),('left',50),('right',50)]:
        e=OxmlElement('w:'+side);e.set(qn('w:w'),str(val));e.set(qn('w:type'),'dxa');margins.append(e)
    pr.append(margins)
    header=tbl.rows[0]; trpr=header._tr.get_or_add_trPr(); repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
    allrows=[t['headers']]+t['rows']
    for i,values in enumerate(allrows):
        row=header if i==0 else tbl.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for j,(cell,text,w) in enumerate(zip(row.cells,values,t['widths'])):
            cell.width=Pt(w); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Pt(0)
            p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0);p.paragraph_format.line_spacing=1.22
            # Keep compact tables with their source notes; long appendix tables may split.
            p.paragraph_format.keep_with_next=(len(t['rows'])<=4 or i>=len(allrows)-3)
            # Identifiers and short numerical cells are centered; prose remains left-aligned.
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if (j==0 and w>=60) or w>=90 else WD_ALIGN_PARAGRAPH.CENTER
            run=p.add_run(str(text));font(run,size=8.8 if len(values)>=5 else 9.1,bold=i==0)
            if i==0:
                cb=OxmlElement('w:tcBorders');e=OxmlElement('w:bottom');e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'666666');cb.append(e);cell._tc.get_or_add_tcPr().append(cb)
    p=para('주: '+t['note']);p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.line_spacing=1.25;p.paragraph_format.space_after=Pt(7)
    for r in p.runs:font(r,size=8.5)

def mr(text):
    r=OxmlElement('m:r');t=OxmlElement('m:t');t.text=text;r.append(t);return r

def sub(base,index):
    s=OxmlElement('m:sSub');e=OxmlElement('m:e');e.append(mr(base));v=OxmlElement('m:sub');v.append(mr(index));s.append(e);s.append(v);return s

def equation(key):
    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Pt(0)
    p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(6)
    if key in ['background','anyparent']:p.paragraph_format.keep_with_next=True
    op=OxmlElement('m:oMathPara');m=OxmlElement('m:oMath');op.append(m)
    mapping={'background':('F','A+B','A+B+C+D',1),'anyparent':('P','B+C','B+C+D',2),'twoparent':('Q','B','B+C+D',3)}
    if key in mapping:
        letter,a,b,no=mapping[key]; m.append(sub(letter,'it'));m.append(mr(' = 100 × '))
        frac=OxmlElement('m:f');n=OxmlElement('m:num');n.append(mr(a));d=OxmlElement('m:den');d.append(mr(b));frac.append(n);frac.append(d);m.append(frac)
    else:
        specs={
        'cross':([('Y','i,2024'),' = α + β ',('X','i,2024'),' + ',('γ','m(i)'),' + ',('ε','i')],4),
        'panel':([('Y','it'),' = ',('α','i'),' + ',('λ','t'),' + β ',('X','it'),' + ',('ε','it')],5),
        'fd':(['Δ',('Y','it'),' = ',('δ','t'),' + β Δ',('X','it'),' + Δ',('ε','it')],6)}
        tokens,no=specs[key]
        for tok in tokens:m.append(sub(*tok) if isinstance(tok,tuple) else mr(tok))
    p._p.append(op);r=p.add_run(f'   ({no})');font(r,size=9)

timing=read('upgrade_timing_models.csv')
timing=[v for v in timing if v['specification'].startswith('common_sample_')]
tab('timing','<표 C1> 동일 표본에서 인구 측정시점 비교',
    ['인구비중 시점','계수','95% 신뢰구간','p값'],
    [['전년도 말' if v['predictor']=='lag_x_pp' else '당해 연도 말',num(v['coefficient']),ci(v),pval(v['p_value'])] for v in timing],
    [100,45,130,50],
    '2023–2024년 41개 지방정부·82개 관측치. 지방정부·연도 고정효과 및 지방정부 군집 표준오차, t(40). 단위는 비중 1%포인트당 일수다. 출처: 공식 자료를 이용한 추가 계산.')

source=(PAPER/'manuscript_source_ko.md').read_text(encoding='utf-8')
rendered=[]; firsttitle=True; firstsubtitle=True; english=False; abstract=False; pending_break=False
for block in re.split(r'\n\s*\n',source.strip()):
    block=block.strip()
    if block=='{{PAGEBREAK}}':pending_break=True;rendered.append('\n---\n');continue
    figure=re.fullmatch(r'\{\{FIG:([^}]+)\}\}',block)
    if figure:
        p=para('<그림 C1> 양부모 해외 출생 비중의 모형별 추정');p.paragraph_format.keep_with_next=True;p.paragraph_format.first_line_indent=Pt(0)
        for r in p.runs:font(r,size=9,bold=True)
        p=doc.add_paragraph();p.paragraph_format.first_line_indent=Pt(0);p.add_run().add_picture(str(RESULTS/figure.group(1)),width=Pt(325))
        rendered.append('![그림 C1](../../results/'+figure.group(1)+')');continue
    match=re.fullmatch(r'\{\{TABLE:(\w+)\}\}',block)
    if match:
        t=tables[match.group(1)];table_block(t)
        rendered.append(t['caption']+'\n\n| '+' | '.join(t['headers'])+' |\n| '+' | '.join(['---']*len(t['headers']))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('\n',' ') for v in row)+' |' for row in t['rows'])+'\n\n주: '+t['note']);continue
    match=re.fullmatch(r'\{\{EQ:(\w+)\}\}',block)
    if match:
        equation(match.group(1));rendered.append({'background':'F_it = 100 × (A+B)/(A+B+C+D)','anyparent':'P_it = 100 × (B+C)/(B+C+D)','twoparent':'Q_it = 100 × B/(B+C+D)',
            'cross':'Y_i,2024 = α + β X_i,2024 + γ_m(i) + ε_i','panel':'Y_it = α_i + λ_t + β X_it + ε_it','fd':'ΔY_it = δ_t + β ΔX_it + Δε_it'}[match.group(1)]);continue
    if block=='{{REFERENCES}}':
        for text,url in REFERENCES:
            p=para(text);p.paragraph_format.first_line_indent=Pt(-10);p.paragraph_format.left_indent=Pt(10);p.paragraph_format.line_spacing=1.22;p.paragraph_format.space_after=Pt(3)
            for r in p.runs:font(r,size=9)
            if url:hyperlink(p,'  원문',url)
        rendered.append('\n\n'.join(text+(' [원문]('+url+')' if url else '') for text,url in REFERENCES));continue
    if block.startswith('# '):
        text=block[2:]
        if text=='English Abstract':english=True
        elif text.startswith('1 '):abstract=False
        if firsttitle:
            p=para('정책연구논문 초안');p.paragraph_format.first_line_indent=Pt(0)
            p.paragraph_format.space_after=Pt(18)
            for r in p.runs:font(r,size=9)
            p=para(text.replace(' 지역의 조사는',' 지역의\n조사는'),'Title');p.paragraph_format.space_after=Pt(12)
            firsttitle=False
        else:p=para(text,'Heading 1')
        if pending_break:p.paragraph_format.page_break_before=True;pending_break=False
    elif block.startswith('## '):
        if firstsubtitle:
            p=para(block[3:],'Subtitle');p.paragraph_format.space_after=Pt(13);firstsubtitle=False
        else:
            p=para(block[3:],'Heading 2')
            if english:
                for r in p.runs:font(r,name='Times New Roman',size=11,bold=True)
    elif block.startswith('### '):
        p=para(block[4:],'Heading 3');p.paragraph_format.space_before=Pt(8)
        if block[4:]=='국문초록':abstract=True
    else:
        p=para(block.replace('\n',' '))
        if abstract:
            p.paragraph_format.line_spacing=1.32
            for r in p.runs:font(r,size=10)
        if english:
            p.paragraph_format.line_spacing=1.3
            for r in p.runs:font(r,name='Times New Roman',size=10)
        if block.startswith('연구논문 초안'):
            p.alignment=WD_ALIGN_PARAGRAPH.RIGHT;p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(16)
            for r in p.runs:font(r,size=8.8)
        elif block.startswith(('주제어:','JEL 분류:','Keywords:')):
            p.paragraph_format.first_line_indent=Pt(0)
            for r in p.runs:font(r,size=9.2)
    rendered.append(block)

# Word's built-in Title style can carry a theme-colored paragraph border.
# Remove it from both style definitions and document paragraphs, and disable
# East Asian document-grid snapping so the selected line spacing is respected.
for el in list(doc.styles.element.xpath('//w:pBdr'))+list(doc.element.xpath('//w:pBdr')):
    el.getparent().remove(el)
for p in doc.paragraphs:
    pr=p._p.get_or_add_pPr();snap=OxmlElement('w:snapToGrid');snap.set(qn('w:val'),'0');pr.append(snap)

path=OUTPUT/'Sweden_ChildProtection_Policy_Draft_KO.docx';doc.save(path)
(OUTPUT/'Sweden_ChildProtection_Policy_Draft_KO.md').write_text('\n\n'.join(rendered)+'\n',encoding='utf-8')
(PAPER/'table_manifest.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)
print('tables',len(tables),'native equations',len(doc.element.xpath('//m:oMath')),'paragraphs',len(doc.paragraphs))
print('manuscript characters',len(source))
