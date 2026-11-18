"""Insert actual independent re-estimates, retaining clearly labelled legacy tables."""
from pathlib import Path
import csv
P=Path(__file__).resolve().parent
def read(name):
 with (P/'reproduction/results'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def apply_reproduction(s,table,records):
 old='CASE 2의 원시 패널과 실행 코드는 이번에 제공되지 않았으므로 해당 결과는 원고 보고치를 전사한 것이며 재현 또는 재추정의 성과로 보고하지 않는다.'
 new='CASE 2는 Socialstyrelsen의 공식 2026년 Excel과 SCB의 2015년 원자료를 새로 내려받아 패널을 재구축하고 DML-DID를 독립 재추정하였다. 원래 실행 코드는 발견하지 못했으므로 기존 구현을 그대로 복원한 정확 재현과는 구분한다. 기존 DR-DID·SDID와 추가 원고 보고치는 새 추정치와 별도로 표시한다.'
 assert old in s;s=s.replace(old,new)
 s=s.replace('DML-DID를 포함한 조정 추정은 기간·집단 경계·측정 기준에 민감했다.','공식 원자료를 재구축한 독립 DML-DID 주 추정은 2025--2023년 $+9.24$, 2026--2023년 $-11.21$, 2026--2025년 $-18.43$\\%포인트였으며 세 구간은 모두 0을 포함했다. 기존 보고치의 유의성은 이번 구현에서 확인되지 않았다.')
 methods=r'''
\subsubsection{공식 원자료 재구축과 독립 DML-DID 구현}
2026년 11월 18일 Socialstyrelsen의 공식 2026년 Excel DATA 시트와 SCB TAB4823·TAB1121의 2015년 응답을 내려받았다. 다운로드 URL, UTC 시각, 요청 본문, 원본 해시와 정제·추정 코드를 재현 패키지에 보존했다. 전국 경계값은 15.662790386208915\%로 일치했고, 장기표본 191개와 연결표본 263개, 여섯 개 집단·연도별 충족 건수와 최근 전환표가 기존 원고와 같았다. 포함·제외 시군의 중위소득 평균도 308.203과 299.400천 SEK로 기존 보고치와 일치했다. 2026년 파일의 역사적 관측을 사용했으며, 당시의 개별 파일 대조와 측정동등성 감사를 새로 완료한 것은 아니다.

Malmö에는 같은 연도의 이진 응답이 반복되고 일부 연도에는 숫자 집계도 함께 있었다. 서로 일치하는 Ja/Nej를 한 건만 채택하고 중복 원행을 남겼다. 상충하는 이진 응답이 나오면 정제를 중단하도록 했다. 다른 도시의 수치 집계를 이진값으로 바꾸거나 결측을 0으로 대체하지 않았다. 원래 코드를 찾지 못했으므로 아래 설정은 이번에 새로 고정한 구현이며, 기존 계수를 맞추기 위해 선택하지 않았다.

공변량은 2015년 인구 로그, 65세 이상 비율, 여성 비율, 소비단위당 중위 가처분소득(자본이득 포함), 저경제수준 비율이다. 소득은 SCB의 2024년 고정가격 천 SEK다. 21개 주를 난수 시드 20261106으로 섞어 5개 평가 폴드로 나누었다. 각 폴드의 주는 두 보조모형의 학습에서 모두 제외했다. 성향점수와 비교집단 변화 회귀에 각각 무작위숲 분류기·회귀기를 사용했으며, 나무 300개, 최소 잎 관측 8개, 전체 공변량 후보를 고정했다. 성향점수는 $[.05,.95]$로 제한했다. 원고의 부트스트랩 시드를 원래 교차적합 시드로 확인한 것은 아니다.

$r_i=\Delta Y_i-\widehat g_{0,-k(i)}(X_i)$, $\widehat q_i=(1-H_i)\widehat e_i/(1-\widehat e_i)$, $\widehat p=\overline H$, $\overline q=n^{-1}\sum_i\widehat q_i$로 쓰면 새 점수는 다음과 같다\cite{dmlscore}.
\begin{align}
\widehat\theta&=\frac1n\sum_i\left(\frac{H_i}{\widehat p}-\frac{\widehat q_i}{\overline q}\right)r_i,\\
\widehat\psi_i&=-\frac{H_i}{\widehat p}\widehat\theta+\left(\frac{H_i}{\widehat p}-\frac{\widehat q_i}{\overline q}\right)r_i.
\end{align}
표준오차는 $\widehat{\mathrm{se}}^2=\{G/(G-1)\}n^{-2}\sum_{c=1}^{G}(\sum_{i\in c}\widehat\psi_i)^2$로 계산하고 $t_{20}$ 구간을 사용했다. 평균 점수 0, 폴드 사이의 주 중복 없음, 공변량 결측 없음, 상수 보조모형에서 단순 DID 점추정·표준오차 일치를 코드로 확인했다. 이는 보조학습 수렴률이나 인과 가정을 검증한 것은 아니다. 패키지의 공개 점수를 Python으로 구현했으며 DoubleML 패키지 자체를 실행한 결과는 아니다.

주 추정 이외에 로지스틱·Ridge와 ExtraTrees, 네 추가 시드, 성향점수 제한 .01·.10, 자본이득 제외 소득을 각각 확인했다. 주 추정과 대안을 합해 기간별 10개 설정이며, 원래 표의 집단 경계 민감도와는 다른 점검이다. 시드 대안은 폴드와 학습기의 난수를 함께 바꾸므로 순수한 폴드 효과로 해석하지 않는다. 세 기간의 변화 보조모형은 각각 학습하므로 독립 추정치에 정확한 가산성을 강제하지 않는다.

'''
 anchor='\\subsection{식별 대상과 통계적 추론의 범위}'
 assert anchor in s;s=s.replace(anchor,methods+anchor)
 oldpara='DML-DID의 2025--2023년 대비는 $+18.10$\\%포인트, 2026--2025년 대비는 $-26.46$\\%포인트다. 두 구간은 0을 제외하지만, 동일 대비에서 DR-DID 또는 SDID의 구간은 0을 포함하는 경우가 있다. 2026--2023년의 세 조정 결과는 모두 0을 포함한다. 2025년 격차 확대와 다음 관측의 축소를 한 번의 사후 평균으로 압축하면 시간 경로를 놓칠 수 있다. 특정 방법의 유의한 구간만 선택하지 않는다.'
 newpara='기존 원고의 DML-DID는 2025--2023년 $+18.10$, 2026--2025년 $-26.46$\\%포인트이고 두 보고 구간은 0을 제외했다. 그러나 이 수치를 공식 원자료의 새 구현으로 그대로 얻지는 못했다. 표~\\ref{tab:c2new}는 원래 코드의 정확 재현을 주장하지 않고, 같은 표본과 기초 공변량을 사용한 독립 재추정과 나란히 비교한다.'
 assert oldpara in s;s=s.replace(oldpara,newpara)
 rows=[]
 for r in read('reported_vs_reestimated.csv'):
  m=next(x for x in read('dml_main.csv') if x['period']==r['period'])
  rows.append([r['period'],f"{float(r['reported_pp']):+.2f}",f"{float(r['new_pp']):+.2f}",f"[{float(r['new_lo']):.2f}, {float(r['new_hi']):.2f}]",f"{float(m['p_value']):.3f}"])
 newtable=table('c2new','CASE 2 기존 DML 보고치와 공식 원자료의 독립 재추정',['대비','기존 보고','독립 추정','새 95% 구간','p값'],rows,'단위 %p; n=191, 고비중 51, 주 G=21. 새 구간은 주 영향함수 표준오차와 t(20). 기존 코드를 발견하지 못했으므로 정확 일치 재현이 아니다. 기존 구간은 앞 표의 보고치와 구분한다.',[.21,.14,.15,.29,.10])
 ss=[]
 for r in read('sensitivity_summary.csv'):ss.append([r['period'],f"[{float(r['minimum_pp']):.2f}, {float(r['maximum_pp']):.2f}]",r['positive']+'/'+r['negative'],r['p_below_05']+'/'+r['specifications']])
 newtable+=table('c2newrobust','CASE 2 독립 DML 구현의 민감도',['대비','계수 범위 (%p)','양수/음수','p<.05 / 설정 수'],ss,'기간별 주 추정과 대안 9개. 대안은 학습기 2개, 시드 4개, 절단 2개, 소득 개념 1개다. 서로 독립인 검정이 아니며 다중검정 보정 전 값이다. 기존 원고의 민감도 표를 재현한 결과가 아니다.',[.21,.29,.18,.23])
 text=r'''
공식 자료의 독립 재추정에서는 2025--2023년 $+9.24$\%포인트, 95\% 구간 $[-16.18,34.67]$이었고, 2026--2023년은 $-11.21$ $[-35.83,13.41]$, 2026--2025년은 $-18.43$ $[-40.09,3.22]$였다. 세 주 구간이 모두 0을 포함하므로, 원래의 두 유의한 DML 대비가 새로운 구현에서도 확인됐다고 기술할 수 없다. 원래 학습기와 폴드가 불명확하여 차이의 원인을 특정 설정 하나로 귀속하거나 기존 수치가 오류라고 판정할 수도 없다.

가중치 집중과 분할 변동을 살펴볼 이유도 있다. 새 비교집단 유효표본크기는 54.79였으며 성향점수 21개가 .05 아래에서 제한되었다. 기간별 10개 설정 모두에서 2025--2023년은 양수, 2026--2025년은 음수였지만 전자는 유의한 설정이 없고 후자는 한 설정만 $p<.05$였다. 2026--2023년은 학습기에 따라 부호도 바뀌었다. 따라서 살아남는 것은 격차의 확대 후 축소라는 방향과 연결 전환의 산술이며, 일정한 유의성은 아니다.

'''
 anchor='원고의 비교집단 유효표본크기는'
 assert anchor in s;s=s.replace(anchor,newtable+'\n'+text+'\n'+anchor)
 s=s.replace('\\caption{CASE 2 변화 차이와 조정 추정의 95\\% 구간}','\\caption{CASE 2 기존 원고의 보고치: 변화 차이와 조정 추정}')
 # Newly verified descriptive tables are distinct from unrerun legacy models.
 for label in ['c2flow','c2levels','c2transitions','c2expand','c2missing']:
  record=next(r for r in records if r['label']==label)
  verified = ' 2026년 공식 파일에서 결측 범위를 다시 계산해 보고값과 일치함을 확인했다.' if label=='c2missing' else ' 공식 원자료에서 표본 수, 충족 건수와 전환 셀을 다시 계산해 일치를 확인했다.'
  # Table notes were escaped by the builder; substitution is ASCII/Korean only.
  ending=' 제공 CASE 2 원고 보고치의 전사이며 이번 통합에서 재추정하지 않았다.'
  start=s.index('\\label{tab:'+label+'}')
  end=s.index('\\end{table}',start)
  s=s[:start]+s[start:end].replace(ending,verified)+s[end:]
  record['note']=record['note'].replace(ending,verified)
 s=s.replace('H2의 집단 차이는 연도별 수준과 전환, 조정 방법에 따라 달라진다.','H2의 집단 차이는 연도별 수준과 전환, 조정 방법에 따라 달라진다. 독립 DML 재추정의 세 주 구간은 모두 0을 포함하며, 방향의 재현과 유의성의 재현은 구분해야 한다.')
 s=s.replace('제공 CASE 2 원고가 인용한 원자료이며 이번 통합에서 원파일 재검증은 수행하지 않음.','제공 CASE 2 원고의 출처. 이번에 공식 Excel DATA를 새로 확보했으나 당시 조사표 전체의 동등성을 재인증한 것은 아님.')
 s=s.replace('개별적인 개인의 불리함을 확인할 근거가 아니다.','개별적인 개인의 불리함을 확인할 근거가 아니다.')
 # Add primary sources for the actual new retrieval and explicit score.
 anchor='\\end{thebibliography}'
 refs=r'''
\bibitem{dmlscore} DoubleML. Score functions: observational panel difference-in-differences. \url{https://docs.doubleml.org/stable/guide/scores.html}. 2026년 11월 18일 확인. 본고는 공개 점수를 직접 구현하였다.
\bibitem{newraw} Socialstyrelsen. \textit{Öppna jämförelser 2026 -- Våld i nära relationer}, DATA 시트. \url{https://www.socialstyrelsen.se/contentassets/11a181f7bb3f4fd3b827c842b7df21c9/2026-6-10349.xlsx}. SCB TAB4823 및 TAB1121, 2015년. 2026년 11월 18일 공식 원자료 다운로드; 요청·해시는 동봉 재현자료 참조.
'''
 s=s.replace(anchor,refs+anchor)
 s=s.replace('2026년 11월 18일 Socialstyrelsen의 공식 2026년 Excel DATA 시트와','2026년 11월 18일 Socialstyrelsen의 공식 2026년 Excel DATA 시트와')
 s=s.replace('원본 해시와 정제·추정 코드를 재현 패키지에 보존했다.','원본 해시와 정제·추정 코드를 재현 패키지에 보존했다\\cite{newraw}.')
 more=[]
 for r in read('second_audit_summary.csv'):
  more.append(['폴드만 변경' if r['family']=='fold_only' else '학습 난수만 변경',r['period'],f"[{float(r['minimum']):.2f}, {float(r['maximum']):.2f}]",r['significant']+'/'+r['n']])
 tab=table('c2second','CASE 2 추가 점검: 폴드 배정과 학습기 난수의 분리',['변경 요인','대비','계수 범위 (%p)','p<.05 / 횟수'],more,'표본 191개·주 21개와 학습기 설정을 유지. 폴드만 변경은 학습 난수를 고정한 10개 배정, 학습 난수만 변경은 폴드를 고정한 5개 난수다. 구간은 주 군집 t(20). 빈도는 보정 전이며 서로 독립인 검정이나 통합 유의확률이 아니다. 원래 폴드를 복원한 결과도 아니다.',[.24,.19,.29,.19])
 extra=r'''
추가로 폴드 배정과 학습기 자체의 난수를 분리하여 검사했다. 동일 폴드에서 성향점수 모형만 로지스틱으로 바꾸면 2025--2023년 대비는 9.24에서 13.85\%포인트, 결과 변화 모형만 Ridge로 바꾸면 13.01\%포인트가 되었다. 두 모형을 함께 바꾸면 15.07\%포인트였다. 반면 고정 예측에서 비교 가중치의 정규화만 바꾼 진단은 9.59\%포인트로 변화가 작았다. 두 표준오차 진단에서도 기본 추정의 유의성 판정은 달라지지 않았다. 이 비교는 새 구현 내부의 민감도를 분리하며, 불명확한 원래 구현과의 차이를 특정 원인으로 확정하지 않는다.

특히 주별 폴드 배정만 바꾼 10개 설정에서 2026--2025년 계수는 모두 음수였으며 8개 구간이 0을 제외했다. 2025--2023년은 모두 양수였지만 유의한 설정은 2개였고, 2026--2023년은 어느 설정에서도 유의하지 않았다. 고정 폴드에서 학습기 난수만 바꿀 때보다 계수 변동이 컸다. 따라서 한 분할에서의 비유의를 신호의 부재로 일반화해서도 안 되고, 유의한 분할만 골라 결과를 확정해서도 안 된다. 단기 격차 축소의 방향은 반복되며 그 크기와 유의성은 분할에 의존한다. 이 빈도를 투표식 검정이나 통합 p값으로 사용하지 않았다.

'''
 s=s.replace('원고의 비교집단 유효표본크기는',tab+'\n'+extra+'\n원고의 비교집단 유효표본크기는')
 s=s.replace('기존 보고치의 유의성은 이번 구현에서 확인되지 않았다.','기존 보고치의 유의성은 이번 주 모형에서 확인되지 않았다. 추가로 폴드만 바꾼 10개 설정에서 2026--2025년 계수는 모두 음수였고 8개가 유의하여, 단기 격차 축소의 방향과 분할에 따른 추론 변동을 함께 보여 주었다.')
 return s
