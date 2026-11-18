"""Prepare the integrated manuscript for general journal submission."""
import re


ABSTRACT = r"""보호시설에 동반 입소한 아동의 학업보장 서면 절차에 관한 스웨덴의 공개 지표 VIND28에서 출발해, 이주배경 인구가 많은 지방정부에서 아동보호 행정 대응이 더 느린지를 검토한다. 세 대도시권 51개 시군 중 2024년 조사기간을 보고한 44개에서 인구구성과 조사기간의 횡단면 연관성은 작았다. 2022--2024년 시군·연도 고정효과 모형에서 스웨덴 출생 아동 중 양부모가 해외 출생인 비중이 같은 시군에서 1\%포인트 높아질 때 조사기간은 평균 6.70일 긴 것으로 추정됐다. 그러나, 영향력이 큰 시군을 함께 제외하거나 연간 변화량을 비교하면 신뢰구간이 0을 포함했다. VIND28의 191개 장기패널에서 2015년 해외 출생 주민 비중이 높은 집단의 충족률은 세 관측 시점인 2023·2025·2026년에 비교집단보다 높았다. 집단 간 격차는 각각 5.48, 20.78, 3.66\%포인트였다. 263개 연결표본에서도 2025년에서 2026년 사이 격차가 줄었으며, 고비중 집단의 충족 건수는 두 해 모두 35개였다. 이 기간의 독립 DML-DID 추정치는 $-18.43$\%포인트(95\% 신뢰구간 $[-40.09,\,3.22]$)였으며, 주별 학습 분할에 따라 추론이 달라졌다.

두 집단에 전국 개편이 동시에 적용돼 정책 효과를 분리할 미적용 비교집단이 없다. 조사기간 보고 시군과 미보고 시군의 인구구성이 달랐으며, 두 지표 모두 개별 아동의 보호·등교 시점을 기록하지 않는다. 따라서 결과는 시군 수준의 조사기간 연관성과 서면 절차 응답 격차의 변화를 보여 주는 데 한정된다."""

CONCLUSION = r"""\subsubsection{결론}
전국 개편이 2024년에 두 집단에 동시에 적용됐으므로, 이 연구에는 정책 효과를 식별할 미적용 비교집단이 없다. 개편 전에도 집단 간 VIND28 응답 격차는 해마다 달랐다. 사전 인구구성으로 나눈 두 집단의 공변량을 조정해도 개편이 없었을 때의 추세를 확인할 수는 없다. 아울러 조사기간은 일반 아동·청소년 사회복지 조사의 개시부터 종료까지의 시군 평균이고, VIND28은 서면 절차에 대한 시군 응답이다. 개별 이주배경 아동이 언제 보호나 교육 지원을 받았는지는 두 자료에서 관찰되지 않는다.

조사기간에서는 2024년 횡단면의 연관성이 작았고, 2022--2024년의 시군 내 비교에서는 스웨덴 출생 아동 중 양부모가 해외 출생인 비중과 양의 연관성이 나타났다. 그러나 영향력이 큰 시군을 함께 제외하거나 연간 변화량을 비교하면 신뢰구간이 0을 포함했다. 2024년에 조사기간을 보고하지 않은 7개 시군은 보고한 44개보다 해외 출생 주민 비중의 평균이 높았다. 짧은 패널에서 사건 구성이나 인력 등 시간에 따라 변하는 요인을 관찰하지 못한 점까지 고려하면, 양의 추정치를 대도시권 전체의 일관된 기간 증가나 인구구성의 효과로 해석하기 어렵다.

자료에서 가장 일관되게 확인되는 결과는 2025년에서 2026년 사이 VIND28 충족률 격차의 축소다. 이 변화는 191개 장기패널과 263개 연결표본에서 모두 나타났다. 이진 비교가 가능한 288개 시군에서 두 해의 결측에 가능한 모든 이진 응답을 적용해도 축소 방향이 유지됐다. 263개 표본에서는 고비중 집단의 충족 건수가 유지됐고 비교집단의 충족 건수가 늘었다. 독립 DML-DID에서도 같은 기간에 분할별 점추정치가 모두 음수였으나, 주 추정의 신뢰구간은 0을 포함했고 통계적 유의성은 분할에 따라 달라졌다. 조사기간이 지역 전반에서 더 길어진다는 명제를 뒷받침할 일관된 근거는 약하며, VIND28이 보여 주는 결과는 두 집단이 보고한 학업보장 서면 절차의 단기 격차 변화다.

"""

REFERENCES = {
    "case1": r"제공 연구원고 A. (연도 미상). \textit{이주배경 인구구성과 아동보호 행정의 조사기간}. 미공개 연구원고.",
    "case2": r"제공 연구원고 B. (2026). \textit{집계된 개선의 이면: 스웨덴 보호시설 동반 아동의 학업보장 절차와 시군별 응답 전환}. 미공개 연구원고.",
    "reform": r"Socialstyrelsen. (2024). \textit{Nya bestämmelser om skyddat boende}. Meddelandeblad 2/2024, 2024-3-8989. \href{https://socialstyrelsen.se/publikationer/nya-bestammelser-om-skyddat-boende--meddelandeblad-2024-3-8989/}{공식 문서}.",
    "kkiK": r"SKR/RKA. (2025). \textit{Förändringar i insamlingen av data till KKiK 2025}. U33401 항목.",
    "kolada": r"Rådet för främjande av kommunala analyser. (연도 미상). \textit{Kolada 지표 메타데이터 U33401 및 N02926}. \href{https://api.kolada.se/v3/kpi/U33401,N02926}{공식 API}.",
    "scb": r"Statistiska centralbyrån. (연도 미상). \textit{Antal personer med utländsk eller svensk bakgrund (fin indelning) efter region, ålder och kön}, TAB4824 (UtlSvBakgFin). \href{https://statistikdatabasen.scb.se/api/v2/tables/TAB4824/metadata?lang=sv}{공식 API}.",
    "mapscb": r"Statistiska centralbyrån. (연도 미상). \textit{Digitala gränser}. 지방정부 경계 자료, SWEREF 99 TM, CC0. \href{https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/}{공식 자료}.",
    "vind": r"Socialstyrelsen. (2026a). \textit{Öppna jämförelser av våld i nära relationer}. 공개 안내 및 Analysstöd. \href{https://www.socialstyrelsen.se/statistik-och-data/oppna-jamforelser/socialtjanst/vald-i-nara-relationer/}{공식 자료}.",
    "newraw": r"Socialstyrelsen. (2026b). \textit{Öppna jämförelser 2026 -- Våld i nära relationer}. 2026-6-10349, DATA 시트. \href{https://www.socialstyrelsen.se/contentassets/11a181f7bb3f4fd3b827c842b7df21c9/2026-6-10349.xlsx}{원본 Excel}.",
    "scbcase2": r"Statistiska centralbyrån. (연도 미상). \textit{Statistikdatabasen}, TAB4823 및 TAB1121, 2015년 시군 관측. \href{https://statistikdatabasen.scb.se/api/v2/tables/TAB4823/metadata?lang=sv}{TAB4823}, \href{https://statistikdatabasen.scb.se/api/v2/tables/TAB1121/metadata?lang=sv}{TAB1121}.",
    "sz": r"Sant'Anna, P. H. C., \& Zhao, J. (2020). Doubly robust difference-in-differences estimators. \textit{Journal of Econometrics}, 219(1), 101--122. \href{https://doi.org/10.1016/j.jeconom.2020.06.003}{DOI 10.1016/j.jeconom.2020.06.003}.",
    "dml": r"Chernozhukov, V., Chetverikov, D., Demirer, M., Duflo, E., Hansen, C., Newey, W., \& Robins, J. (2018). Double/debiased machine learning for treatment and structural parameters. \textit{The Econometrics Journal}, 21(1), C1--C68. \href{https://doi.org/10.1111/ectj.12097}{DOI 10.1111/ectj.12097}.",
    "sdid": r"Arkhangelsky, D., Athey, S., Hirshberg, D. A., Imbens, G. W., \& Wager, S. (2021). Synthetic difference-in-differences. \textit{American Economic Review}, 111(12), 4088--4118. \href{https://doi.org/10.1257/aer.20190159}{DOI 10.1257/aer.20190159}.",
    "trygged": r"Trygged, S. (2017). Open comparisons of social services in Sweden---why, how, and for what? \textit{Cogent Social Sciences}, 3(1), 1404735. \href{https://doi.org/10.1080/23311886.2017.1404735}{DOI 10.1080/23311886.2017.1404735}.",
    "denvall": r"Denvall, V., Agevall Gross, L., Kjellgren, C., \& Skillmark, M. (2021). Lost in comparison: A program theory analysis of performance measurement in social work. \textit{Nordic Social Work Research}, 11(3), 249--263. \href{https://doi.org/10.1080/2156857X.2019.1690559}{DOI 10.1080/2156857X.2019.1690559}.",
    "dmlscore": r"DoubleML. (연도 미상). \textit{Score functions}. Observational panel difference-in-differences. 2026년 11월 18일 확인. \href{https://docs.doubleml.org/stable/guide/scores.html}{공식 문서}.",
}


def revise_for_submission(source):
    start = source.index(r"\begin{abstract}") + len(r"\begin{abstract}")
    end = source.index(r"\end{abstract}", start)
    source = source[:start] + "\n" + ABSTRACT + "\n" + source[end:]
    start = source.index(r"\subsubsection{표본과 측정에 따른 안정성}")
    end = source.index(r"\subsubsection{중심 연구 질문에 대한 관측자료 수준의 답변}", start)
    sensitivity = (
        "\\subsubsection{표본과 측정에 따른 안정성}\n"
        "두 사례에서 민감도 점검이 드러낸 문제는 다르다. 사례 1에서는 몇몇 시군의 관측이 양의 패널 기울기에 큰 영향을 준다. "
        "사례 2에서는 두 표본에서 응답 격차가 줄었지만 그 과정은 표본에 따라 달랐다. 또한 조정 추정치의 크기와 유의성은 학습 분할에 따라 달라졌다. "
        "이 차이는 관측의 범위와 추정 방식이 해석에 중요하다는 가설 H3에 부합한다.\n\n"
    )
    source = source[:start] + sensitivity + source[end:]
    start = source.index(r"\subsubsection{중심 연구 질문에 대한 관측자료 수준의 답변}")
    end = source.index(r"\FloatBarrier", start)
    source = source[:start] + CONCLUSION + source[end:]
    source = source.replace("{\\small 통합 연구원고\\quad 2026년 11월 18일}\n", "")
    source = source.replace(r"\usepackage{setspace,placeins,fancyhdr,xurl,hyperref}",
                            r"\usepackage{setspace,placeins,fancyhdr,xurl,hyperref}"
                            "\n" r"\usepackage[font=small,labelfont=bf,labelsep=period,justification=raggedright,singlelinecheck=false]{caption}")
    source = source.replace("이 글의 기여는 여러 방법의 유의한 계수를 모으는 데 있지 않다. ", "")
    source = source.replace("이 통합은 제공된 두 PDF의 결과와 기존 CASE 1 계산 파일을 대조하여 작성하였다.",
                            "조사기간 분석은 제공된 연구원고의 보고치와 해당 계산 파일을 대조했다.")
    source = source.replace("SCB TAB4824는 0--17세", r"SCB TAB4824\cite{scb}는 0--17세")
    source = source.replace("SCB 도식용 경계를 양 연도에 사용했다.", r"SCB 도식용 경계\cite{mapscb}를 양 연도에 사용했다.")
    source = source.replace(r"정제·추정 코드를 재현 패키지에 보존했다\cite{newraw}.",
                            r"정제·추정 코드를 재현 패키지에 보존했다\cite{newraw,scbcase2}.")
    source = source.replace("원고에서는 21개 주를 5개 폴드로 나누고 평가 주를 학습에서 제외하였다.",
                            "독립 추정에서는 21개 주를 5개 교차적합 분할(폴드)로 나누고 평가 주를 학습에서 제외했다.")
    source = source.replace("\\FloatBarrier\n\\subsection{CASE 1 자료와 모형}", "\\subsection{CASE 1 자료와 모형}")
    source = source.replace(r"\setmainhangulfont{Batang}",
                            r"\setmainhangulfont[BoldFont={Malgun Gothic Bold},ItalicFont={Batang}]{Batang}")
    source = re.sub(r"(?<![\dA-Za-z])\.(?=\d+(?![\d\\]))", "0.", source)
    source = source.replace("CASE 1", "사례 1").replace("CASE 2", "사례 2")
    source = source.replace("일차차분", "1차 차분")
    source = source.replace("\\end{table}\n동일 40개 지방정부로",
                            "\\end{table}\n\n동일한 40개 지방정부로")
    source = source.replace(r"\textbf{주제어:}", r"\textbf{주제어}\enspace").replace(r"\textbf{JEL:}", r"\textbf{JEL 분류}\enspace")
    source = source.replace(r"\%p", r"\%포인트")
    source = source.replace("제공 사례 1 원고의 보고값을 유지하였다. 이번 통합에서 재추정하지 않았다.",
                            r"\textbf{자료.} 기존 계산 결과.")
    source = source.replace("제공 사례 2 원고 보고치의 전사이며 이번 통합에서 재추정하지 않았다.",
                            r"\textbf{자료.} 기존 연구원고의 보고치.")
    source = re.sub(r"(?m)(\\begin\{minipage\}\{\.98\\linewidth\}\\footnotesize)([ \n])",
                    r"\1\2\\raggedright\\textbf{주.} ", source)
    source = source.replace("자료 · ", r"\textbf{자료.} ").replace("경계 · ", r"\textbf{경계.} ")
    source = source.replace("출처: 공식 Kolada 응답의 직접 집계. "+r"\textbf{자료.} 기존 계산 결과.",
                            r"\textbf{자료.} 기존 Kolada 응답의 집계.")
    source = source.replace("출처: 본고 계산. "+r"\textbf{자료.} 기존 계산 결과.", r"\textbf{자료.} 기존 계산 결과.")
    source = source.replace("2024년 단면과 2022--2025년 패널", "2024년 횡단면과 2022--2025년 패널")
    source = source.replace("사례 2 기존 원고의 보고치: 변화 차이와 조정 추정", "VIND28 변화 차이의 기존 추정 결과")
    source = source.replace("사례 2 추가 점검: 폴드 배정과 학습기 난수의 분리", "VIND28 추정의 폴드 배정과 학습기 난수 민감도")

    start = source.index(r"\begingroup\small\begin{thebibliography}")
    body = source[:start]
    citation_keys = dict.fromkeys(
        key for group in re.findall(r"\\cite\{([^}]+)\}", body) for key in group.split(",")
    )
    assert set(citation_keys) == REFERENCES.keys()
    references = "\n".join(rf"\bibitem{{{key}}} {REFERENCES[key]}" for key in citation_keys)
    return (body + "\\clearpage\n\\begingroup\\setstretch{1.15}\n"
            + "\\begin{thebibliography}{99}\n" + references
            + "\n\\end{thebibliography}\n\\endgroup\n\\end{document}\n")

