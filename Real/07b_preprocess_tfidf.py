"""
07b_preprocess_tfidf.py

입력:
  - 02b_steam_appdetails_summary.csv   (detailed_description 컬럼)

출력:
  - 07b_tfidf_features.csv
      appid + tfidf_* 50개 컬럼
  - 07b_tfidf_vocabulary.txt
      선택된 50개 단어 목록 (09에서 train-only refit 시 참조용)

leakage 경고:
  이 스크립트는 전체 데이터(train+test)에 fit합니다.
  따라서 이 출력 파일은 EDA 및 피처 확인 전용입니다.

  09_modeling.py에서 반드시 아래 순서로 재처리하십시오:
    1) train/test split
    2) TfidfVectorizer.fit(train 텍스트)
    3) train: .transform(train 텍스트)
    4) test:  .transform(test 텍스트)   ← fit 금지

텍스트 전처리 순서:
  1) HTML 태그 제거
  2) &amp; &quot; 등 HTML entity 제거
  3) 숫자 제거
  4) 2글자 미만 토큰 제거 (token_pattern으로 처리)
  5) 소문자 변환 (TfidfVectorizer 내부 처리)
  6) 영문 stopwords 제거

TfidfVectorizer 파라미터:
  max_features = 50
  stop_words   = "english"
  min_df       = 5      (5개 미만 문서에 등장하는 단어 제외)
  max_df       = 0.95   (95% 이상 문서에 등장하는 단어 제외 — 너무 흔한 단어)
  sublinear_tf = True   (tf 값에 log 적용 — 단어 빈도 스케일 완화)
  token_pattern= r"\\b[a-zA-Z][a-zA-Z]+\\b"  (순수 영문자 2글자 이상만)
"""

import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer


IN_CSV   = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_summary.csv"
OUT_CSV  = r"Real\07 preprocess\07b_tfidf_features.csv"
OUT_VOC  = r"Real\07 preprocess\07b_tfidf_vocabulary.txt"

def clean_text(raw):
    """HTML 제거 + entity 제거 + 숫자 제거"""
    if pd.isna(raw):
        return ""
    s = str(raw)
    # HTML 태그 제거
    s = re.sub(r"<[^>]+>", " ", s)
    # HTML entity 제거 (&amp; &quot; &lt; 등)
    s = re.sub(r"&[a-zA-Z]+;", " ", s)
    s = re.sub(r"&#\d+;", " ", s)
    # 숫자 제거
    s = re.sub(r"\d+", " ", s)
    # 연속 공백 정리
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ──────────────────────────────────────────────────────────────
print("=" * 60)
print("[1] 데이터 로드")
print("=" * 60)

df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
df = df[df["success"] == True].copy()
df["appid"] = df["appid"].astype(str)
print(f"유효 게임: {len(df):,}개")


# ──────────────────────────────────────────────────────────────
print("\n[2] 텍스트 전처리")

df["text_clean"] = df["detailed_description"].apply(clean_text)

empty_count = (df["text_clean"].str.strip() == "").sum()
print(f"전처리 완료: {len(df):,}개")
print(f"설명 없음(빈 텍스트): {empty_count:,}개 ({empty_count/len(df)*100:.1f}%)")

# 텍스트 길이 분포 확인
lengths = df["text_clean"].str.split().str.len()
print(f"단어 수 — min: {lengths.min():.0f}  median: {lengths.median():.0f}  max: {lengths.max():.0f}")


# ──────────────────────────────────────────────────────────────
print("\n[3] TF-IDF 벡터화 (전체 fit — EDA 전용)")
print("    ※ 09_modeling.py에서 train-only fit으로 교체 필수")

tfidf = TfidfVectorizer(
    max_features  = 50,
    stop_words    = "english",
    min_df        = 5,
    max_df        = 0.95,
    sublinear_tf  = True,
    token_pattern = r"\b[a-zA-Z]{3,}\b",  # 영문자 3글자 이상 (ll, am 등 노이즈 차단)
)

matrix   = tfidf.fit_transform(df["text_clean"])
vocab    = tfidf.get_feature_names_out()
tfidf_cols = ["tfidf_" + w for w in vocab]

print(f"선택된 단어 수: {len(vocab)}개")
print(f"단어 목록: {list(vocab)}")


# ──────────────────────────────────────────────────────────────
print("\n[4] 저장")

tfidf_df = pd.DataFrame(matrix.toarray(), columns=tfidf_cols)
tfidf_df.insert(0, "appid", df["appid"].values)
tfidf_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"TF-IDF 피처 행렬 -> {OUT_CSV}  shape: {tfidf_df.shape}")

# 어휘 목록 저장
f = open(OUT_VOC, "w", encoding="utf-8")
f.write("※ 이 어휘 목록은 전체 데이터 fit 결과입니다.\n")
f.write("  09_modeling.py에서 train-only fit 후 어휘가 달라질 수 있습니다.\n\n")
for i, w in enumerate(vocab, 1):
    f.write(f"{i:>3}. {w}\n")
f.close()
print(f"어휘 목록 -> {OUT_VOC}")

print("\n완료")
