"""
02_steam_appdetails_summary_generate.py
================================================================================
[목적]
    02_steam_appdetails_snapshot.py 가 수집해둔 원본 JSON 파일들을 읽어 요약 CSV를 (재)생성한다. API를 다시 호출하지 않는다.

[이 파일이 필요한 이유]
    02_steam_appdetails_snapshot.py 는 API를 호출하면서 동시에 CSV를 생성하는데,
    중간에 중단하거나 나중에 컬럼을 추가하고 싶을 때마다 API를 재호출하면
    rate limit에 걸리고 시간도 오래 걸림.
    이 파일은 이미 저장된 JSON에서만 읽으므로 빠르게 재생성 가능.

[snapshot.py 와의 차이 - 추가된 컬럼 3개]
    has_demo        : 데모 버전 존재 여부 (0/1)
                      data["demos"] 리스트가 비어있지 않으면 1
                      런치 전 데모 공개가 성공에 영향을 주는지 측정 가능
    metacritic_score: 메타크리틱 점수 (없으면 None)
                      data["metacritic"]["score"] 에서 추출
                      점수 자체가 Y변수와 상관관계가 있을 수 있으나
                      런치 시점에는 없는 경우가 많아 결측값 처리 필요
    esrb_rating     : ESRB 등급 (예: "Everyone", "Teen", "Mature 17+")
                      data["ratings"]["esrb"]["rating"] 에서 추출
                      논문 피처 목록에 포함된 항목

    -> 이 파일이 snapshot.py 보다 컬럼이 더 많은 완성본.
       08_feature_engineering.py 에서는 이 파일을 기준으로 사용.

[입력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv
        - 처리할 appid 목록 (전체 순회)
    Real/02 steam appdetails snapshot/02_Steam_Appdetails_snapshot_raw/{appid}.json
        - 02_steam_appdetails_snapshot.py 가 수집한 원본 JSON 파일들

[출력 파일]
    Real/02 steam appdetails snapshot/02_Steam_Appdetails_summary.csv
        - 전체 appid 기준 요약 테이블 (snapshot.py 의 CSV를 덮어씀)

[JSON 없는 경우 처리]
    raw_path 에 파일이 없으면 해당 appid 는 스킵 (rows 에 추가 안 함).
    -> 02_snapshot.py 가 아직 수집 못 한 게임이거나 수집 실패한 게임.
    -> 스킵된 appid 는 출력 CSV 에 아예 포함되지 않음 (success=False 행도 없음).
    단, API success=False 인 JSON 은 rows 에 success=False 로 추가됨.

[다음 단계]
    이 파일로 생성된 CSV 가 08_feature_engineering.py 의 주요 입력.
    categories/genres one-hot, 언어 지원 binary, pc_requirements 파싱,
    TF-IDF (detailed_description), 개발사 경력, metacritic_score, esrb_rating 등
    대부분의 메타데이터 피처가 이 CSV에서 만들어짐.
================================================================================
"""

import os, json
import pandas as pd

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
RAW_DIR   = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_snapshot_raw"
OUT_CSV   = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_summary.csv"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

rows = []

for i, appid in enumerate(appids, 1):
    raw_path = os.path.join(RAW_DIR, f"{appid}.json")

    # JSON 파일 자체가 없으면 스킵 (아직 수집 안 됐거나 수집 실패)
    # success=False 행도 추가하지 않음 -> 출력 CSV에서 완전히 누락
    if not os.path.exists(raw_path):
        print(f"{i}/{total} | {appid} | JSON 없음 (스킵)")
        continue

    with open(raw_path, encoding="utf-8") as f:
        payload = json.load(f)

    # API 응답 구조: {str(appid): {"success": bool, "data": {...}}}
    app = payload.get(str(appid), {})
    if not app.get("success"):
        # success=False JSON (수집 당시 API가 데이터 없다고 응답한 경우)
        rows.append({"appid": appid, "success": False})
        print(f"{i}/{total} | {appid} | NO DATA")
        continue

    # ── 서브딕셔너리 추출 (없으면 빈 딕셔너리로 대체) ────────────────────
    data  = app["data"]
    price = data.get("price_overview")      or {}
    plat  = data.get("platforms")           or {}
    rel   = data.get("release_date")        or {}
    pcreq = data.get("pc_requirements")     or {}
    ach   = data.get("achievements")        or {}
    desc  = data.get("content_descriptors") or {}
    meta  = data.get("metacritic")          or {}  # 메타크리틱 점수 (없는 게임 많음)
    rat   = data.get("ratings")             or {}
    esrb  = rat.get("esrb")                 or {}  # ESRB 등급 (없는 게임 많음)

    short_desc    = data.get("short_description")    or ""
    detailed_desc = data.get("detailed_description") or ""
    developers    = data.get("developers") or []
    publishers    = data.get("publishers") or []
    demos         = data.get("demos")      or []  # 데모 버전 리스트

    rows.append({
        "appid":                  appid,
        "success":                True,
        "type":                   data.get("type"),
        "name":                   data.get("name"),
        "required_age":           data.get("required_age"),
        "is_free":                data.get("is_free"),
        "release_coming_soon":    rel.get("coming_soon"),
        "release_date_text":      rel.get("date"),
        "price_currency":         price.get("currency"),
        "price_initial":          price.get("initial"),       # 센트 단위 (1999 = $19.99)
        "price_final":            price.get("final"),
        "price_discount_pct":     price.get("discount_percent"),
        "platform_windows":       plat.get("windows"),
        "platform_mac":           plat.get("mac"),
        "platform_linux":         plat.get("linux"),
        # "|" 구분자: CSV 단일 셀에 다중값 저장, 08에서 split 후 one-hot 처리
        "categories":             "|".join(c["description"] for c in (data.get("categories") or []) if "description" in c),
        "genres":                 "|".join(g["description"] for g in (data.get("genres")     or []) if "description" in g),
        "supported_languages":    data.get("supported_languages"),  # HTML 태그 포함 원문
        "developers":             "|".join(developers),
        "publishers":             "|".join(publishers),
        "achievements_total":     ach.get("total"),
        "recommendations_total":  (data.get("recommendations") or {}).get("total"),
        "has_website":            1 if data.get("website") else 0,
        "has_demo":               1 if demos else 0,          # 논문 외 추가 피처
        "metacritic_score":       meta.get("score"),          # 없으면 None, 결측 처리 필요
        "esrb_rating":            esrb.get("rating"),         # 없으면 None (한국/일본 게임 등)
        "short_desc_len":         len(short_desc),
        "detailed_desc_len":      len(detailed_desc),         # 스토어 페이지 성의 지표
        "short_description":      short_desc,
        "detailed_description":   detailed_desc,              # 08에서 TF-IDF 피처 생성
        "pc_minimum":             pcreq.get("minimum"),       # HTML 포함 원문, 08에서 파싱
        "pc_recommended":         pcreq.get("recommended"),   # HTML 포함 원문, 08에서 파싱
        "content_descriptor_ids": "|".join(str(x) for x in (desc.get("ids") or [])),
        "header_image":           data.get("header_image"),
        "screenshots_count":      len(data.get("screenshots") or []),
        "movies_count":           len(data.get("movies")      or []),
    })

    print(f"{i}/{total} | {appid} | {data.get('name')}")

pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {OUT_CSV}")
print(f"총 {len(rows)}개 저장")