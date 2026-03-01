import os, re
import pandas as pd

# 경로는 본인 폴더 구조에 맞게만 맞추면 됨
app_csv = r"(cozy)Steam Data\02_Steam_Appdetails_snapshot\02_Steam_Appdetails_summary.csv"
cv_csv  = r"(cozy)Steam Data\04_Steam_Screenshots_openCV\cv_features_per_game.csv"

out_dir = r"(cozy)Steam Data\08_Steam_X"
os.makedirs(out_dir, exist_ok=True)

app = pd.read_csv(app_csv)
cv  = pd.read_csv(cv_csv)

# 안전장치(이미 필터링 해둔 상태여도 괜찮음)
app = app[app["type"].astype(str).str.lower() == "game"].copy()
app = app[app["is_free"] == False].copy()

def cnt_pipe(s):

    s = "" if pd.isna(s) else str(s)
    return len([x for x in s.split("|") if x.strip()])

tag_re = re.compile(r"<[^>]+>")

def cnt_lang(s):
    s = "" if pd.isna(s) else str(s)
    s = s.split("<br")[0]          # 뒤에 주석 제거
    s = tag_re.sub("", s)          # HTML 제거
    s = s.replace("*", "")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return len(dict.fromkeys(parts))

# 파생 피처(가볍게)
app["cat_n"] = app["categories"].apply(cnt_pipe)
app["gen_n"] = app["genres"].apply(cnt_pipe)
app["lang_n"] = app["supported_languages"].apply(cnt_lang)

# 사양 텍스트는 지금은 길이만(원문 파싱은 나중에)
app["pc_min_len"] = app["pc_minimum"].fillna("").astype(str).str.len()
app["pc_rec_len"] = app["pc_recommended"].fillna("").astype(str).str.len()

# 1차 X_meta (텍스트 원문 제외)
x_meta = app[[
    "appid",
    "release_coming_soon",
    "price_initial", "price_final", "price_discount_pct",
    "platform_windows", "platform_mac", "platform_linux",
    "screenshots_count", "movies_count",
    "cat_n", "gen_n", "lang_n",
    "pc_min_len", "pc_rec_len",
]].copy()

# X_visual (OpenCV 요약 전부)
x_vis = cv.copy()

# 합친 X
x = x_meta.merge(x_vis, on="appid", how="left")

x_meta.to_csv(f"{out_dir}/08_X_meta.csv", index=False, encoding="utf-8-sig")
x_vis.to_csv(f"{out_dir}/08_X_visual.csv", index=False, encoding="utf-8-sig")
x.to_csv(f"{out_dir}/08_X_meta_plus_visual.csv", index=False, encoding="utf-8-sig")

print("meta:", x_meta.shape)
print("vis :", x_vis.shape)
print("X   :", x.shape)
print("cv missing:", x["num_ok"].isna().sum())
print("saved to:", out_dir)
