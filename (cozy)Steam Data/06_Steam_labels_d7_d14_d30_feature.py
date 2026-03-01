import pandas as pd

IN_CSV = r"(cozy)Steam Data\05_SteamDB_Review(accumulate)\05_SteamDB_Review(accumulate).csv"
OUT_CSV = r"(cozy)Steam Data\06_Steam_labels_d7_d14_d30_feature\06_Steam_labels_d7_d14_d30_feature.csv"

df = pd.read_csv(IN_CSV)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["appid", "date"])

rows = []

for appid, g in df.groupby("appid"):
    g = g.reset_index(drop=True)

    t0 = g.loc[0, "date"].date().isoformat()

    def pick(i):
        if i >= len(g):
            return "", "", "", ""
        tot = int(g.loc[i, "cum_total"])
        pos = int(g.loc[i, "cum_positive"])
        neg = int(g.loc[i, "cum_negative"])
        rat = (pos / tot) if tot > 0 else ""
        return tot, pos, neg, rat

    d7_tot, d7_pos, d7_neg, d7_rat   = pick(6)   # day_7
    d14_tot, d14_pos, d14_neg, d14_rat = pick(13) # day_14
    d30_tot, d30_pos, d30_neg, d30_rat = pick(29) # day_30

    rows.append([
        int(appid), t0,
        d7_tot, d7_pos, d7_neg, d7_rat,
        d14_tot, d14_pos, d14_neg, d14_rat,
        d30_tot, d30_pos, d30_neg, d30_rat
    ])

out = pd.DataFrame(rows, columns=[
    "appid", "t0_date",
    "d7_total", "d7_pos", "d7_neg", "d7_pos_ratio",
    "d14_total", "d14_pos", "d14_neg", "d14_pos_ratio",
    "d30_total", "d30_pos", "d30_neg", "d30_pos_ratio",
])

out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print("saved:", OUT_CSV)