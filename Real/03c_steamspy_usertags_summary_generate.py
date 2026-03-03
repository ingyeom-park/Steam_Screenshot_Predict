"""
03c_steamspy_usertags_summary_generate.py
================================================================================
[목적]
    03a 가 수집해둔 원본 JSON 파일들을 읽어 최종 통합 CSV를 생성한다.
    API를 다시 호출하지 않는다.

[02b 와의 관계]
    02b 와 동일한 패턴. 03a 의 임시 CSV는 해당 실행분만 포함하므로 불완전함.
    이 파일이 전체 appid 기준 완전한 CSV를 생성하는 최종 단계.

[입력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv
    Real/03 steamspy usertags/03_UserTags_raw/{appid}.json

[출력 파일]
    Real/03 steamspy usertags/03_UserTags_summary.csv
        컬럼:
            appid   : Steam 게임 고유 ID
            success : 수집 성공 여부
            tags    : {태그명: 투표수} 딕셔너리를 JSON 문자열로 직렬화한 값
                      예) {RPG: 1500, Fantasy: 1200}
                      08_feature_engineering.py 에서 json.loads() 로 파싱 후
                      선정된 태그 목록 기준으로 binary(0/1) 피처 생성.

[JSON 없는 경우]
    파일이 없으면 해당 appid 스킵 (rows 에 추가 안 함).

[다음 단계]
    이 파일 CSV + 05_analyze_tags.py 태그 선정 결과를 함께 사용해
    08_feature_engineering.py 에서 binary 태그 피처 생성.
================================================================================
"""
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