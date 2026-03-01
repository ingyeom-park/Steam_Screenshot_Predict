import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, accuracy_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

meta_csv = r"(cozy)Steam Data\09_Steam_Y\09_final_meta_only.csv"
vis_csv  = r"(cozy)Steam Data\09_Steam_Y\09_final_visual_only.csv"
full_csv = r"(cozy)Steam Data\09_Steam_Y\09_final_meta_plus_visual.csv"

def run_one(name, df, q=0.70):
    df = df[df["d30_total"].notna()].copy()

    y = df["d30_total"].astype(float).values
    thr = np.quantile(y, q)          # q=0.70이면 상위 30%가 1
    yb = (y >= thr).astype(int)

    drop = [
        "appid","t0_date",
        "d7_total","d7_pos","d7_neg","d7_pos_ratio",
        "d14_total","d14_pos","d14_neg","d14_pos_ratio",
        "d30_total","d30_pos","d30_neg","d30_pos_ratio",
        "pc_min_len","pc_rec_len"
    ]
    X = df.drop(columns=[c for c in drop if c in df.columns])

    print(name, "rows", len(df), "features", X.shape[1], "thr", float(thr), "pos", int(yb.sum()))

    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)

    m_dummy = DummyClassifier(strategy="most_frequent")
    m_logit = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=5000, class_weight="balanced", random_state=0)
    )
    m_rf = RandomForestClassifier(
        n_estimators=800,
        random_state=0,
        n_jobs=-1,
        min_samples_leaf=2,
        class_weight="balanced_subsample"
    )

    def cv(model, tag):
        aucs, aps, f1s, accs = [], [], [], []
        for tr, te in kf.split(X, yb):
            Xtr, Xte = X.iloc[tr], X.iloc[te]
            ytr, yte = yb[tr], yb[te]
            model.fit(Xtr, ytr)
            p = model.predict_proba(Xte)[:, 1]
            pred = (p >= 0.5).astype(int)
            aucs.append(roc_auc_score(yte, p))
            aps.append(average_precision_score(yte, p))
            f1s.append(f1_score(yte, pred))
            accs.append(accuracy_score(yte, pred))
        print(tag,
              "ROC-AUC", round(float(np.mean(aucs)), 3),
              "PR-AUC", round(float(np.mean(aps)), 3),
              "F1", round(float(np.mean(f1s)), 3),
              "ACC", round(float(np.mean(accs)), 3))

    cv(m_dummy, "dummy")
    cv(m_logit, "logit")
    cv(m_rf, "rf")
    print()

run_one("meta_only", pd.read_csv(meta_csv), q=0.70)
run_one("visual_only", pd.read_csv(vis_csv), q=0.70)
run_one("meta+visual", pd.read_csv(full_csv), q=0.70)