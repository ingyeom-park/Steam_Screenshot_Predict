import pandas as pd

in_csv = r"(cozy)Steam Data\labels_d7_d14_d30\labels_d7_d14_d30.csv"
out_csv = r"(cozy)Steam Data\07_Steam_AppID_List_Only\appid_list.csv"

df = pd.read_csv(in_csv)
a = df["appid"].dropna().astype(int).drop_duplicates().sort_values()

pd.DataFrame({"appid": a}).to_csv(out_csv, index=False, encoding="utf-8-sig")
print(len(a), "saved:", out_csv)