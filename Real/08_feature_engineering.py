"""
08_feature_engineering.py

입력 (모두 같은 폴더):
  - 02b_steam_appdetails_summary.csv
  - 03c_steamspy_usertags_summary.csv
  - 05_selected_tags_final.csv
  - 06_image_features.csv
  - 07a_pc_requirements.csv       ← 07a 출력

출력:
  - 08_features_X.csv             최종 피처 행렬 (appid 포함) + text_for_tfidf 컬럼
  - 08_feature_columns.txt        그룹별 피처 목록

피처 그룹:
  [A] 이미지        thumb 24개 + ss_0 24개 = 48개
  [B] 유저 태그     05 확정 목록 기준 binary (중복 3개 제외)
  [C] categories   "|" 분해 후 one-hot (노이즈 컬럼 제외)
  [D] genres       동일
  [E] 언어 지원     10개 binary
  [F] 하드웨어      07a_pc_requirements.csv 에서 로드
  [G] 개발사 경력   dev_prev_count (1개)
  [H] TF-IDF       → 09에서 train-only fit 처리
                     이 파일은 text_for_tfidf 컬럼만 전달
  [I] 수치 피처     price_usd 등 11개

제외 확정:
  - is_sequel                    (패턴 오탐 多, 예측 기여 불분명)
  - metacritic_score/has_metacritic  (82.8% 결측 + leakage 위험)
  - ESRB 5개                     (전부 0)
  - hw_directx                   (69.9% 중앙값 대체)
  - hw_has_cpu_req                (97% = 1, 분산 없음)
  - dev_prev_max/min/gini         (현재 시점 누적값 — 의미 왜곡)
  - tag_Sexual_Content/Gore/Violent  (genre와 완전 중복)
  - NOISY_CATS                   (Steam 시스템 기능 컬럼)
  - 07b_tfidf_features.csv       (전체 fit → leakage, 09에서 재처리)
"""

import pandas as pd
import numpy as np
import json
import re

BASE = r"C:\Users\Administrator\Desktop\Steam_Screenshot_Predict\Real"

APPDETAILS  = BASE + r"\02 steam appdetails snapshot\02_Steam_Appdetails_summary.csv"
USERTAGS    = BASE + r"\03 SteamSpy UserTags\03_UserTags_summary.csv"
TAGS_FINAL  = BASE + r"\05 analyze tags\05_selected_tags_final.csv"
IMG_FEATS   = BASE + r"\06 opencv features\06_image_features.csv"
HW_FEATS    = BASE + r"\07 preprocess\07a_pc_requirements.csv"

OUT_X    = BASE + r"\08 features\08_features_X.csv"
OUT_COLS = BASE + r"\08 features\08_feature_columns.txt"

NOISY_CATS = {
    "Steam Timeline", "SteamVR Collectibles", "Steam Turn Notifications",
    "Stereo Sound", "Surround Sound", "HDR available",
    "Includes Source SDK", "Chat - Speech to text", "Chat - Text to speech",
    "Commentary available", "Narrated Game Menus",
    "Playable without Timed Input", "Subtitle Options",
    "Touch Only Option", "Keyboard Only Option", "Mouse Only Option",
    "Adjustable Difficulty", "Adjustable Text Size",
    "Color Alternatives", "Camera Comfort", "Custom Volume Controls",
}

DUPLICATE_TAGS = {"Sexual Content", "Gore", "Violent"}

LANGUAGES = [
    "English", "French", "German", "Spanish", "Japanese",
    "Simplified Chinese", "Traditional Chinese", "Korean",
    "Portuguese", "Russian",
]

IMG_FEATURE_COLS = [
    "hue_bin_0","hue_bin_1","hue_bin_2","hue_bin_3",
    "hue_bin_4","hue_bin_5","hue_bin_6","hue_bin_7",
    "hue_bin_8","hue_bin_9","hue_bin_10","hue_bin_11",
    "hue_bin_12","hue_bin_13","hue_bin_14","hue_bin_15",
    "avg_saturation","avg_value","distinct_colors","reduced_palette_colors",
    "edge_density","brightness_std","warm_color_ratio","texture_complexity",
]


def safe_col(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", s).strip("_")


def clean_text(raw):
    if pd.isna(raw):
        return ""
    s = str(raw)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&[a-zA-Z]+;", " ", s)
    s = re.sub(r"&#\d+;", " ", s)
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("[1] 데이터 로드")
print("=" * 60)

df         = pd.read_csv(APPDETAILS,  encoding="utf-8-sig")
tags_raw   = pd.read_csv(USERTAGS,    encoding="utf-8-sig")
tags_final = pd.read_csv(TAGS_FINAL,  encoding="utf-8-sig")
img_df     = pd.read_csv(IMG_FEATS,   encoding="utf-8-sig")
hw_df      = pd.read_csv(HW_FEATS,    encoding="utf-8-sig")

for d in [df, tags_raw, img_df, hw_df]:
    d["appid"] = d["appid"].astype(str)

df = df[df["success"] == True].copy()
df = df.drop_duplicates(subset="appid").copy()
print(f"appdetails 유효 (중복 제거 후): {len(df):,}개")


# ══════════════════════════════════════════════════════════════
print("\n[A] 이미지 피처 (thumb 24 + ss_0 24 = 48개)")

thumb_ok = img_df[(img_df["image_type"] == "thumb") & (img_df["success"] == True)].copy()
ss0_ok   = img_df[(img_df["image_type"] == "ss_0")  & (img_df["success"] == True)].copy()

thumb_feats = thumb_ok[["appid"] + IMG_FEATURE_COLS].copy()
ss0_feats   = ss0_ok[["appid"]   + IMG_FEATURE_COLS].copy()
thumb_feats.columns = ["appid"] + ["thumb_" + c for c in IMG_FEATURE_COLS]
ss0_feats.columns   = ["appid"] + ["ss0_"   + c for c in IMG_FEATURE_COLS]

img_merged   = thumb_feats.merge(ss0_feats, on="appid", how="inner")
valid_appids = set(img_merged["appid"])

df = df[df["appid"].isin(valid_appids)].copy()
print(f"ss_0 실패 게임 제거 후: {len(df):,}개")
print(f"이미지 피처: {len([c for c in img_merged.columns if c != 'appid'])}개")


# ══════════════════════════════════════════════════════════════
print(f"\n[B] 유저 태그 binary")

selected_tags = [t for t in tags_final["tag"].tolist() if t not in DUPLICATE_TAGS]
print(f"선택 태그: {len(selected_tags)}개  (중복 {len(DUPLICATE_TAGS)}개 제외)")

tags_raw["tags_dict"] = tags_raw["tags"].apply(
    lambda s: json.loads(s) if pd.notna(s) and s != "" else {}
)

tag_rows = []
for _, row in tags_raw[tags_raw["appid"].isin(valid_appids)].iterrows():
    d = {"appid": row["appid"]}
    for tag in selected_tags:
        d["tag_" + safe_col(tag)] = 1 if tag in row["tags_dict"] else 0
    tag_rows.append(d)

tag_features = pd.DataFrame(tag_rows)
print(f"태그 피처: {len([c for c in tag_features.columns if c != 'appid'])}개")


# ══════════════════════════════════════════════════════════════
print(f"\n[C] categories one-hot")

all_cats = set()
for val in df["categories"].dropna():
    for c in str(val).split("|"):
        c = c.strip()
        if c and c not in NOISY_CATS:
            all_cats.add(c)
all_cats = sorted(all_cats)

cat_rows = []
for _, row in df[["appid","categories"]].iterrows():
    d = {"appid": row["appid"]}
    cats_in_game = set()
    if pd.notna(row["categories"]):
        for c in str(row["categories"]).split("|"):
            cats_in_game.add(c.strip())
    for c in all_cats:
        d["cat_" + safe_col(c)] = 1 if c in cats_in_game else 0
    cat_rows.append(d)

cat_features = pd.DataFrame(cat_rows)
print(f"categories 피처: {len([c for c in cat_features.columns if c != 'appid'])}개  (노이즈 {len(NOISY_CATS)}개 제외)")


# ══════════════════════════════════════════════════════════════
print(f"\n[D] genres one-hot")

all_genres = set()
for val in df["genres"].dropna():
    for g in str(val).split("|"):
        g = g.strip()
        if g:
            all_genres.add(g)
all_genres = sorted(all_genres)

genre_rows = []
for _, row in df[["appid","genres"]].iterrows():
    d = {"appid": row["appid"]}
    genres_in_game = set()
    if pd.notna(row["genres"]):
        for g in str(row["genres"]).split("|"):
            genres_in_game.add(g.strip())
    for g in all_genres:
        d["genre_" + safe_col(g)] = 1 if g in genres_in_game else 0
    genre_rows.append(d)

genre_features = pd.DataFrame(genre_rows)
print(f"genres 피처: {len([c for c in genre_features.columns if c != 'appid'])}개")


# ══════════════════════════════════════════════════════════════
print(f"\n[E] 언어 지원 binary ({len(LANGUAGES)}개)")

lang_rows = []
for _, row in df[["appid","supported_languages"]].iterrows():
    d = {"appid": row["appid"]}
    text = str(row["supported_languages"]) if pd.notna(row["supported_languages"]) else ""
    for lang in LANGUAGES:
        d["lang_" + safe_col(lang)] = 1 if lang.lower() in text.lower() else 0
    lang_rows.append(d)

lang_features = pd.DataFrame(lang_rows)
print(f"언어 피처: {len([c for c in lang_features.columns if c != 'appid'])}개")


# ══════════════════════════════════════════════════════════════
print(f"\n[F] 하드웨어 피처 — 07a_pc_requirements.csv 로드")

hw_use = hw_df[["appid","hw_ram_gb","hw_storage_gb","hw_has_gpu_req"]].copy()
hw_use = hw_use[hw_use["appid"].isin(valid_appids)]
print(f"하드웨어 피처: 3개  (hw_ram_gb, hw_storage_gb, hw_has_gpu_req)")


# ══════════════════════════════════════════════════════════════
print(f"\n[G] 개발사 경력 (dev_prev_count)")

df["release_dt"] = df["release_date_text"].apply(
    lambda s: pd.to_datetime(str(s).strip(), errors="coerce") if pd.notna(s) else pd.NaT
)
df["primary_developer"] = df["developers"].apply(
    lambda x: str(x).split("|")[0].strip() if pd.notna(x) else ""
)

df_sorted = df.sort_values("release_dt").reset_index(drop=True)
dev_rows = []
for _, row in df_sorted.iterrows():
    dev    = row["primary_developer"]
    cur_dt = row["release_dt"]
    if dev == "" or pd.isna(cur_dt):
        dev_rows.append({"appid": row["appid"], "dev_prev_count": 0})
        continue
    past_count = int(((df_sorted["primary_developer"] == dev) & (df_sorted["release_dt"] < cur_dt)).sum())
    dev_rows.append({"appid": row["appid"], "dev_prev_count": past_count})

dev_features = pd.DataFrame(dev_rows)
dev_features["appid"] = dev_features["appid"].astype(str)
print(f"개발사 경력 피처: 1개")
print(f"  prev_count=0 (신규): {(dev_features['dev_prev_count']==0).sum():,}개 ({(dev_features['dev_prev_count']==0).mean()*100:.1f}%)")


# ══════════════════════════════════════════════════════════════
print(f"\n[H] TF-IDF 텍스트 원문 전달 (09에서 train-only fit)")
# 07b_tfidf_features.csv 는 전체 fit → leakage
# 대신 detailed_description clean text를 text_for_tfidf 컬럼으로 넘김
# 09에서: train에만 fit → train/test 각각 transform → 50개 컬럼 생성

text_df = df[["appid"]].copy()
text_df["text_for_tfidf"] = df["detailed_description"].apply(clean_text)

empty_text = (text_df["text_for_tfidf"].str.strip() == "").sum()
print(f"텍스트 있음: {len(text_df) - empty_text:,}개  없음: {empty_text:,}개")
print(f"  → 09에서 TfidfVectorizer.fit(X_train['text_for_tfidf']) 후 transform 적용")


# ══════════════════════════════════════════════════════════════
print(f"\n[I] 수치 피처")

num_df = df[["appid"]].copy()
num_df["price_usd"]          = pd.to_numeric(df["price_initial"],      errors="coerce").fillna(0) / 100
num_df["achievements_total"] = pd.to_numeric(df["achievements_total"], errors="coerce").fillna(0)
num_df["screenshots_count"]  = pd.to_numeric(df["screenshots_count"],  errors="coerce").fillna(0)
num_df["movies_count"]       = pd.to_numeric(df["movies_count"],       errors="coerce").fillna(0)
num_df["short_desc_len"]     = pd.to_numeric(df["short_desc_len"],     errors="coerce").fillna(0)
num_df["detailed_desc_len"]  = pd.to_numeric(df["detailed_desc_len"],  errors="coerce").fillna(0)
num_df["required_age"]       = pd.to_numeric(df["required_age"],       errors="coerce").fillna(0)
num_df["platform_mac"]       = df["platform_mac"].apply(lambda x: 1 if str(x) == "True" else 0)
num_df["platform_linux"]     = df["platform_linux"].apply(lambda x: 1 if str(x) == "True" else 0)
num_df["has_demo"]           = pd.to_numeric(df["has_demo"],    errors="coerce").fillna(0).astype(int)
num_df["has_website"]        = pd.to_numeric(df["has_website"], errors="coerce").fillna(0).astype(int)

print(f"수치 피처: {len([c for c in num_df.columns if c != 'appid'])}개")


# ══════════════════════════════════════════════════════════════
print(f"\n[merge] 전체 병합")

merged = df[["appid"]].copy()
for feat_df in [img_merged, tag_features, cat_features, genre_features,
                lang_features, hw_use, dev_features, num_df]:
    merged = merged.merge(feat_df, on="appid", how="left")

# text_for_tfidf는 fillna(0) 대상에서 제외하고 별도 병합
merged = merged.merge(text_df, on="appid", how="left")

merged = merged.drop_duplicates(subset="appid").copy()

feature_cols = [c for c in merged.columns if c not in ("appid", "text_for_tfidf")]
merged[feature_cols] = merged[feature_cols].fillna(0)
merged["text_for_tfidf"] = merged["text_for_tfidf"].fillna("")

print(f"최종 게임 수: {len(merged):,}개")
print(f"최종 수치 피처 수: {len(feature_cols)}개  (text_for_tfidf 별도)")


# ══════════════════════════════════════════════════════════════
print(f"\n[저장]")

merged.to_csv(OUT_X, index=False, encoding="utf-8-sig")
print(f"피처 행렬 -> {OUT_X}")

groups = [
    ("이미지 thumb",   [c for c in feature_cols if c.startswith("thumb_")]),
    ("이미지 ss_0",    [c for c in feature_cols if c.startswith("ss0_")]),
    ("유저 태그",      [c for c in feature_cols if c.startswith("tag_")]),
    ("categories",   [c for c in feature_cols if c.startswith("cat_")]),
    ("genres",       [c for c in feature_cols if c.startswith("genre_")]),
    ("언어 지원",      [c for c in feature_cols if c.startswith("lang_")]),
    ("하드웨어",       [c for c in feature_cols if c.startswith("hw_")]),
    ("개발사 경력",    [c for c in feature_cols if c.startswith("dev_")]),
    ("수치/기타",      [c for c in feature_cols if not any(
        c.startswith(p) for p in ["thumb_","ss0_","tag_","cat_","genre_","lang_","hw_","dev_"])]),
]

f = open(OUT_COLS, "w", encoding="utf-8")
f.write(f"총 수치 피처 수: {len(feature_cols)}\n")
f.write("text_for_tfidf: 별도 컬럼 (09에서 train-only TF-IDF fit 후 50개 생성)\n\n")
for gname, cols in groups:
    f.write(f"[{gname}] {len(cols)}개\n")
    for c in cols:
        f.write(f"  {c}\n")
    f.write("\n")
f.close()
print(f"피처 목록 -> {OUT_COLS}")

print("\n" + "=" * 60)
print("08 완료")
print("=" * 60)
print("\n피처 그룹 요약:")
for gname, cols in groups:
    print(f"  {gname:<25} {len(cols):>4}개")
print(f"  {'text_for_tfidf':<25}    1개  (→ 09에서 TF-IDF 50개로 변환)")
print(f"  {'수치 피처 합계':<25} {len(feature_cols):>4}개")