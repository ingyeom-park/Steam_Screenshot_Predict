import numpy as np
import pandas as pd

from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

csv = r"(cozy)Steam Data\09_Steam_Y\09_final_meta_plus_visual.csv"  # 본인 경로로만 맞추기
df = pd.read_csv(csv)

# d30_total 결측 1개 제외
df = df[df["d30_total"].notna()].copy()

# 학습에서 제외할 컬럼
drop = [
    "appid", "t0_date",
    "d7_total","d7_pos","d7_neg","d7_pos_ratio",
    "d14_total","d14_pos","d14_neg","d14_pos_ratio",
    "d30_total","d30_pos","d30_neg","d30_pos_ratio",
    "pc_min_len","pc_rec_len"
]

X = df.drop(columns=[c for c in drop if c in df.columns])
y = df["d30_total"].astype(float).values

print("rows:", len(df))
print("features:", X.shape[1])  # 여기서 53이 나와야 정상
print("y range:", float(np.min(y)), float(np.max(y)))

# 다중공선성(상관) 간단 체크: |corr|>=0.98만 출력
c = X.corr(numeric_only=True).abs()
pairs = []
cols = list(c.columns)
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        v = c.iat[i, j]
        if v >= 0.98:
            pairs.append((v, cols[i], cols[j]))

pairs = sorted(pairs, reverse=True)
print("high corr pairs (>=0.98):", len(pairs))
for v, a, b in pairs[:20]:
    print(round(v, 4), a, b)

# 모델
m_dummy = DummyRegressor(strategy="mean")
m_ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0, random_state=0))
m_rf = RandomForestRegressor(
    n_estimators=500,
    random_state=0,
    min_samples_leaf=2,
    n_jobs=-1
)

kf = KFold(n_splits=5, shuffle=True, random_state=0)

def cv_eval(model, name):
    maes = []
    r2s = []
    for tr, te in kf.split(X):
        Xtr, Xte = X.iloc[tr], X.iloc[te]
        ytr, yte = y[tr], y[te]
        model.fit(Xtr, ytr)
        pred = model.predict(Xte)
        maes.append(mean_absolute_error(yte, pred))
        r2s.append(r2_score(yte, pred))
    print(name, "MAE", round(float(np.mean(maes)), 3), "R2", round(float(np.mean(r2s)), 3))

cv_eval(m_dummy, "dummy")
cv_eval(m_ridge, "ridge")
cv_eval(m_rf, "rf")

# 로그 타깃 버전도 같이 보고 싶으면 (보통 더 안정적)
ylog = np.log1p(y)

def cv_eval_log(model, name):
    maes = []
    r2s = []
    for tr, te in kf.split(X):
        Xtr, Xte = X.iloc[tr], X.iloc[te]
        ytr, yte = ylog[tr], y[te]   # 학습은 log, 평가는 raw

        model.fit(Xtr, ytr)
        pred_log = model.predict(Xte)
        pred = np.expm1(pred_log)
        pred = np.clip(pred, 0, None)

        maes.append(mean_absolute_error(yte, pred))
        r2s.append(r2_score(yte, pred))
    print(name, "(log target) MAE", round(float(np.mean(maes)), 3), "R2", round(float(np.mean(r2s)), 3))

cv_eval_log(make_pipeline(StandardScaler(), Ridge(alpha=10.0, random_state=0)), "ridge")
cv_eval_log(RandomForestRegressor(n_estimators=500, random_state=0, min_samples_leaf=2, n_jobs=-1), "rf")