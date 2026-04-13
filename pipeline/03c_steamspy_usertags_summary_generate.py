"""
03c_steamspy_usertags_summary_generate.py
================================================================================
[목적]
    03a에서 저장한 원본 JSON만 읽어 전체 요약 CSV를 다시 생성한다.

[입력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv
    data/raw/03_steamspy_usertags/json/{appid}.json

[출력 파일]
    data/interim/03_steamspy_usertags_summary.csv
================================================================================
"""
import os, json
import pandas as pd
from project_paths import APP_LIST_CSV, USERTAGS_JSON_DIR, USERTAGS_SUMMARY_CSV

RAW_DIR = USERTAGS_JSON_DIR
OUT_CSV = USERTAGS_SUMMARY_CSV

df     = pd.read_csv(APP_LIST_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

rows = []

for i, appid in enumerate(appids, 1):
    raw_path = RAW_DIR / f"{appid}.json"

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
