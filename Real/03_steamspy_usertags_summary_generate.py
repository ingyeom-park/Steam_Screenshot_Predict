import os, json
import pandas as pd

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
RAW_DIR   = r"Real\03 steamspy usertags\03_UserTags_raw"
OUT_CSV   = r"Real\03 steamspy usertags\03_UserTags_summary.csv"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

rows = []

for i, appid in enumerate(appids, 1):
    raw_path = os.path.join(RAW_DIR, f"{appid}.json")

    if not os.path.exists(raw_path):
        print(f"{i}/{total} | {appid} | JSON 없음 (스킵)")
        continue

    f = open(raw_path, encoding="utf-8")
    d = json.load(f)
    f.close()

    if not d.get("success"):
        rows.append({"appid": appid, "success": False, "tags": ""})
        print(f"{i}/{total} | {appid} | FAILED")
        continue

    tags = d.get("tags") or {}
    rows.append({
        "appid":   appid,
        "success": True,
        "tags":    json.dumps(tags, ensure_ascii=False)
    })
    print(f"{i}/{total} | {appid} | 태그 {len(tags)}개")

pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {OUT_CSV}")
print(f"총 {len(rows)}개 저장")