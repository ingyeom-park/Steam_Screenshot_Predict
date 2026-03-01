import os, re
import pandas as pd
import numpy as np

app_csv = "02_Steam_Appdetails_summary.csv"
cv_img_csv = "cv_features_per_image.csv"

app = pd.read_csv(app_csv)
cvi = pd.read_csv(cv_img_csv)

app = app[app["type"].astype(str).str.lower() == "game"].copy()
app = app[app["is_free"] == False].copy()

# ═══ 1. PRICE ═══
app["price_usd"] = app["price_final"] / 100.0
app["has_discount"] = (app["price_discount_pct"] > 0).astype(int)

# ═══ 2. PLATFORM ═══
app["plat_mac"] = app["platform_mac"].astype(int)
app["plat_linux"] = app["platform_linux"].astype(int)

# ═══ 3. LANGUAGE ═══
tag_re = re.compile(r"<[^>]+>")

def parse_langs(s):
    s = "" if pd.isna(s) else str(s)
    s = s.split("<br")[0]
    s = tag_re.sub("", s).replace("*", "")
    return [p.strip() for p in s.split(",") if p.strip()]

app["_langs"] = app["supported_languages"].apply(parse_langs)
app["lang_n"] = app["_langs"].apply(len)

key_langs = ["Japanese", "Korean", "Simplified Chinese", "Traditional Chinese",
             "Russian", "French", "German", "Spanish - Spain",
             "Portuguese - Brazil", "Italian", "Turkish", "Polish"]
for lang in key_langs:
    col = "lang_" + lang.lower().replace(" - ", "_").replace(" ", "_")
    app[col] = app["_langs"].apply(lambda x, l=lang: int(l in x))

app["lang_cjk_n"] = (app["lang_japanese"] + app["lang_korean"] +
                      app["lang_simplified_chinese"] + app["lang_traditional_chinese"])

# ═══ 4. RELEASE DATE ═══
app["release_date"] = pd.to_datetime(app["release_date_text"], format="mixed", errors="coerce")
app["rel_month"] = app["release_date"].dt.month
app["rel_dow"] = app["release_date"].dt.dayofweek

app["rel_month_sin"] = np.sin(2 * np.pi * app["rel_month"] / 12)
app["rel_month_cos"] = np.cos(2 * np.pi * app["rel_month"] / 12)
app["rel_dow_sin"] = np.sin(2 * np.pi * app["rel_dow"] / 7)
app["rel_dow_cos"] = np.cos(2 * np.pi * app["rel_dow"] / 7)

# ═══ 5. HARDWARE SPECS ═══
def parse_ram(s):
    if pd.isna(s): return np.nan
    m = re.search(r"(\d+)\s*GB\s*RAM", str(s), re.IGNORECASE)
    return int(m.group(1)) if m else np.nan

def parse_storage(s):
    if pd.isna(s): return np.nan
    m = re.search(r"(\d+)\s*GB.*?(?:storage|space|available|hard)", str(s), re.IGNORECASE)
    return int(m.group(1)) if m else np.nan

app["hw_ram_gb"] = app["pc_minimum"].apply(parse_ram)
app["hw_storage_gb"] = app["pc_minimum"].apply(parse_storage)
app["hw_ram_gb"] = app["hw_ram_gb"].fillna(app["hw_ram_gb"].median())
app["hw_storage_gb"] = app["hw_storage_gb"].fillna(app["hw_storage_gb"].median())

# ═══ 6. GENRES (one-hot) ═══
genre_targets = ["Casual", "Simulation", "Adventure", "Strategy", "RPG",
                 "Early Access", "Action", "Sports"]

for g in genre_targets:
    col = "g_" + g.lower().replace(" ", "_")
    app[col] = app["genres"].fillna("").str.contains(g, regex=False).astype(int)

app["genre_n"] = app["genres"].fillna("").apply(lambda x: len([g for g in x.split("|") if g.strip()]))

# ═══ 7. CATEGORIES (one-hot) ═══
cat_targets = [
    "Steam Achievements", "Steam Cloud", "Full controller support",
    "Custom Volume Controls", "Playable without Timed Input", "Save Anytime",
    "Camera Comfort", "Mouse Only Option", "Stereo Sound",
    "Adjustable Difficulty", "Multi-player", "Co-op", "Online Co-op",
    "Steam Trading Cards", "Color Alternatives", "Steam Leaderboards",
    "Steam Workshop", "Stats", "Adjustable Text Size", "Touch Only Option",
]

for c in cat_targets:
    col = "c_" + re.sub(r"[^a-z0-9]", "_", c.lower()).strip("_")
    app[col] = app["categories"].fillna("").str.contains(c, regex=False).astype(int)

app["cat_n"] = app["categories"].fillna("").apply(lambda x: len([c for c in x.split("|") if c.strip()]))

# ═══ 8. VISUAL FEATURES (per-image → richer) ═══
vis_cols = ["bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"]

vis_mean = cvi.groupby("appid")[vis_cols].mean()
vis_mean.columns = ["v_" + c + "_mean" for c in vis_cols]

vis_std = cvi.groupby("appid")[vis_cols].std()
vis_std.columns = ["v_" + c + "_std" for c in vis_cols]

vis_range = cvi.groupby("appid")[vis_cols].max() - cvi.groupby("appid")[vis_cols].min()
vis_range.columns = ["v_" + c + "_range" for c in vis_cols]

vis_min = cvi.groupby("appid")[vis_cols].min()
vis_min.columns = ["v_" + c + "_min" for c in vis_cols]

vis_max = cvi.groupby("appid")[vis_cols].max()
vis_max.columns = ["v_" + c + "_max" for c in vis_cols]

vis_all = pd.concat([vis_mean, vis_std, vis_range, vis_min, vis_max], axis=1).reset_index()

# ═══ 9. 조립 ═══
meta_cols = [
    "appid",
    "price_usd", "has_discount",
    "plat_mac", "plat_linux",
    "screenshots_count", "movies_count",
    "lang_n", "lang_cjk_n",
    "lang_japanese", "lang_korean", "lang_simplified_chinese", "lang_traditional_chinese",
    "lang_russian", "lang_french", "lang_german", "lang_spanish_spain",
    "lang_portuguese_brazil", "lang_italian", "lang_turkish", "lang_polish",
    "rel_month_sin", "rel_month_cos", "rel_dow_sin", "rel_dow_cos",
    "hw_ram_gb", "hw_storage_gb",
    "genre_n",
] + ["g_" + g.lower().replace(" ", "_") for g in genre_targets] + [
    "cat_n",
] + ["c_" + re.sub(r"[^a-z0-9]", "_", c.lower()).strip("_") for c in cat_targets]

x_meta = app[meta_cols].copy()
x_vis = vis_all.copy()
x_full = x_meta.merge(x_vis, on="appid", how="left")

out_dir = "/home/claude/output"
os.makedirs(out_dir, exist_ok=True)

x_meta.to_csv(f"{out_dir}/08_X_meta_v2.csv", index=False, encoding="utf-8-sig")
x_vis.to_csv(f"{out_dir}/08_X_visual_v2.csv", index=False, encoding="utf-8-sig")
x_full.to_csv(f"{out_dir}/08_X_full_v2.csv", index=False, encoding="utf-8-sig")

print("meta:", x_meta.shape)
print("visual:", x_vis.shape)
print("full:", x_full.shape)

for c in x_full.columns:
    if c == "appid": continue
    if x_full[c].nunique() <= 1:
        print(f"  WARNING constant: {c}")

miss = x_full.isnull().sum()
print("missing:", miss[miss > 0].to_dict() if miss.sum() > 0 else "none")