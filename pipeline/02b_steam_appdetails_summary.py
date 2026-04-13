"""
02b_steam_appdetails_summary.py
================================================================================
[목적]
    02a에서 저장한 원본 JSON만 읽어 최종 요약 CSV를 다시 생성한다.

[입력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv
    data/raw/02_steam_appdetails/json/{appid}.json

[출력 파일]
    data/interim/02_steam_appdetails_summary.csv
================================================================================
"""

import os, json
import pandas as pd

from project_paths import APPDETAILS_JSON_DIR, APPDETAILS_SUMMARY_CSV, APP_LIST_CSV

df     = pd.read_csv(APP_LIST_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

rows = []

for i, appid in enumerate(appids, 1):
    raw_path = APPDETAILS_JSON_DIR / f"{appid}.json"

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

pd.DataFrame(rows).to_csv(APPDETAILS_SUMMARY_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {APPDETAILS_SUMMARY_CSV}")
print(f"총 {len(rows)}개 저장")
