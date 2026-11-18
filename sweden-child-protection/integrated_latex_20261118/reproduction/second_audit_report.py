import pandas as pd,numpy as np
from analysis import P
df=pd.read_csv(P/'results/second_audit_models.csv');su=pd.read_csv(P/'results/second_audit_summary.csv')
parts=[]
for pre,post in [(2023,2025),(2023,2026),(2025,2026)]:
 a=pd.read_csv(P/'results'/f'oof_{post}_{pre}.csv');d=a.high_foreign_2015;y=a.delta_y;g=a.g0_oof;w=a.control_weight
 raw=y[d==1].mean()-y[d==0].mean();out=-(g[d==1].mean()-g[d==0].mean());weight=-((w*(y-g)).sum()-(y-g)[d==0].mean())
 theta=df[(df.setting=='baseline')&(df.period==f'{post}-{pre}')].estimate_pp.iloc[0]
 assert abs((raw+out+weight)*100-theta)<1e-10
 parts.append(dict(period=f'{post}-{pre}',raw_pp=raw*100,outcome_adjustment_pp=out*100,weight_adjustment_pp=weight*100,total_pp=theta))
pd.DataFrame(parts).to_csv(P/'results/second_audit_decomposition.csv',index=False)
lines=['# VIND28 DML-DID 두 번째 점검','',
'원래 실행 코드를 찾았거나 원래 추정치를 정확 재현한 것은 아니다. 새 독립 구현 안에서 한 요소씩 변경하여 불안정성의 출처를 검사했다. 이전 주 추정과 원자료는 유지하였다. 기존 결과와의 차이를 하나의 원인으로 확정하지 않는다.','',
'## 주 추정의 산술 분해','',
'단순 DID + 예상 변화 보정 + 비교집단 가중치 보정 = 새 주 추정이다. 분해는 이 순서를 기준으로 한 회계 항등식이며 인과적 기여가 아니다. 다른 분해 순서는 항별 값을 달리할 수 있다.','',
'|기간|단순 DID|예상 변화 보정|가중치 보정|합계 (%p)|','|---|---:|---:|---:|---:|']
for r in parts:lines.append('|'+r['period']+'|'+'|'.join(f'{r[k]:+.2f}' for k in ['raw_pp','outcome_adjustment_pp','weight_adjustment_pp','total_pp'])+'|')
lines+=['','## 동일 폴드에서 보조모형만 교체','',
'linear는 표준화 로지스틱(C=1)과 Ridge(alpha=1), rf는 이전과 동일한 300개 나무·최소 잎 8개다. 상대 보조예측은 고정하였다. 기존 보고 수치에 가까운 설정을 고르는 기준으로 사용하지 않았다.','',
'|설정|기간|계수|95% 구간|p값|','|---|---|---:|---|---:|']
for r in df[df.family=='controlled'].to_dict('records'):lines.append(f"|{r['setting']}|{r['period']}|{r['estimate_pp']:+.2f}|[{r['lo_pp']:.2f}, {r['hi_pp']:.2f}]|{r['p_value']:.3f}|")
lines+=['','## 난수 요인의 분리','',
'fold_only는 학습기 난수를 고정하고 주의 폴드 배정만 10회 변경했다. learner_rng_only는 폴드를 고정하고 학습기 난수만 5회 변경했다. 서로 독립인 검정이나 신뢰구간이 아니며 다중검정 보정 전 빈도다. 이 작은 범위를 전체 가능한 분할의 분포로 해석하지 않는다.','',
'|요인|기간|계수 최소|계수 최대|p<.05 / 설정 수|','|---|---|---:|---:|---|']
for r in su.to_dict('records'):lines.append(f"|{r['family']}|{r['period']}|{r['minimum']:.2f}|{r['maximum']:.2f}|{r['significant']}/{r['n']}|")
lines+=['','## 가중치 정규화와 표준오차','',
'unnormalized_control_weights는 고정 예측에서 비교집단 가중치 분모를 전 표본 고비중 평균으로 바꾼 진단이다. 폴드별 고비중 평균까지 쓰는 공식 DoubleML의 전체 옵션을 그대로 복제한 것은 아니다. iid_normal_diagnostic_only는 시군 독립·정규 근사를 가정하는 부적절할 수 있는 비교용 구간이며 논문 주 추론으로 쓰지 않는다. finite_sample_ratio_IF는 고정 예측의 비율 추정량 선형화 진단이다. 보조학습 오차를 모두 반영한다고 주장하지 않는다.','',
'|설정|기간|계수|95% 구간|p값|','|---|---|---:|---|---:|']
for r in df[df.family.isin(['normalization','inference'])].to_dict('records'):lines.append(f"|{r['setting']}|{r['period']}|{r['estimate_pp']:+.2f}|[{r['lo_pp']:.2f}, {r['hi_pp']:.2f}]|{r['p_value']:.3f}|")
lines+=['','실행: `python second_audit.py` 다음 `python second_audit_report.py`. 전체 대안과 OOF 예측은 `results/second_audit_*.csv`에 보존하였다. 주 표본 191개, 고비중 51개, 주 21개를 유지했고 결측을 대체하지 않았다. 공식 점수 참고: https://docs.doubleml.org/stable/guide/scores.html .']
(P/'SECOND_AUDIT_KO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Report written')
