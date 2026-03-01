import os
import pandas as pd

# 경로는 본인 폴더 구조에 맞게만 맞추면 됨
x_meta_csv = r"(cozy)Steam Data\08_Steam_X\08_X_meta.csv"
x_vis_csv  = r"(cozy)Steam Data\08_Steam_X\08_X_visual.csv"
x_csv      = r"(cozy)Steam Data\08_Steam_X\08_X_meta_plus_visual.csv"


y_csv = r"(cozy)Steam Data\06_Steam_labels_d7_d14_d30_feature\06_Steam_labels_d7_d14_d30_feature.csv"

out_dir = r"(cozy)Steam Data\09_Steam_Y"
os.makedirs(out_dir, exist_ok=True)

x_meta = pd.read_csv(x_meta_csv)
x_vis  = pd.read_csv(x_vis_csv)
x      = pd.read_csv(x_csv)
y      = pd.read_csv(y_csv)

# 조인
m = x_meta.merge(y, on="appid", how="inner")
v = x_vis.merge(y, on="appid", how="inner")
f = x.merge(y, on="appid", how="inner")

# 저장
m.to_csv(f"{out_dir}/09_final_meta_only.csv", index=False, encoding="utf-8-sig")
v.to_csv(f"{out_dir}/09_final_visual_only.csv", index=False, encoding="utf-8-sig")
f.to_csv(f"{out_dir}/09_final_meta_plus_visual.csv", index=False, encoding="utf-8-sig")

# 간단 점검 출력
print("meta_only:", m.shape)
print("visual_only:", v.shape)
print("meta+visual:", f.shape)

for col in ["d7_total", "d14_total", "d30_total"]:
    if col in f.columns:
        miss = f[col].isna().sum()
        print(col, "missing:", miss)

print("saved to:", out_dir)