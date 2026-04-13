"""
02a_steam_appdetails_snapshot.py
================================================================================
[목적]
    Steam AppDetails API를 호출해 게임별 원본 JSON 스냅샷을 저장한다.

[입력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv

[출력 파일]
    data/raw/02_steam_appdetails/json/{appid}.json
    data/interim/02_steam_appdetails_summary.csv

[비고]
    여기서 생성하는 CSV는 중간 점검용이다.
    최종 요약은 02b_steam_appdetails_summary.py를 기준으로 다시 만든다.
================================================================================
"""

import os, json, time, random
import pandas as pd
import requests
from datetime import datetime, timedelta

from project_paths import APPDETAILS_JSON_DIR, APPDETAILS_SUMMARY_CSV, APP_LIST_CSV

CC        = "us"
LANG      = "english"

df     = pd.read_csv(APP_LIST_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

# raw_dir: 게임별 원본 JSON 저장 폴더
# JSON을 개별 저장하는 이유: 나중에 추가 피처가 필요할 때 API 재호출 없이 재사용 가능
raw_dir = APPDETAILS_JSON_DIR
os.makedirs(raw_dir, exist_ok=True)

# already_done: raw_dir에 이미 저장된 appid 집합 (resume용)
# remaining: 아직 처리되지 않은 appid 목록
already_done = set(
    int(f.replace(".json", ""))
    for f in os.listdir(raw_dir)
    if f.endswith(".json")
)
remaining = [a for a in appids if a not in already_done]
skipped   = total - len(remaining)

print(f"전체 {total}개 | 이미 완료 {skipped}개 | 남은 {len(remaining)}개")

session    = requests.Session()
rows       = []        # 이번 실행에서 처리한 게임들의 요약 데이터
start_time = time.time()
done_count = 0         # ETA 계산용 카운터

for i, appid in enumerate(remaining, 1):
    raw_path = raw_dir / f"{appid}.json"

    # ── API 호출 (최대 5회 재시도) ─────────────────────────────────────────
    payload = None
    for attempt in range(5):
        resp = session.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "cc": CC, "l": LANG},
            timeout=20
        )
        if resp.status_code == 429:
            # Steam API rate limit: 시도 횟수에 비례해 대기 시간 증가
            wait = 120 * (attempt + 1)
            print(f"\n  [{appid}] 429 차단 -> {wait}초 대기 후 재시도 ({attempt+1}/5)")
            time.sleep(wait)
            continue
        if resp.status_code in (500, 502, 503, 504):
            # 서버 오류: 지수 백오프 (1초, 2초, 4초, 8초...)
            time.sleep(2 ** attempt + random.random())
            continue
        if not resp.text.strip().startswith("{"):
            # JSON이 아닌 응답 (HTML 오류 페이지 등): 동일하게 재시도
            time.sleep(2 ** attempt + random.random())
            continue
        payload = resp.json()
        break

    # 5회 모두 실패 시 실패 기록 저장 후 다음 게임으로
    if payload is None:
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({"appid": appid, "success": False}, f, ensure_ascii=False)
        rows.append({"appid": appid, "success": False})
        done_count += 1
        print(f"{skipped+i}/{total} | 남은 {len(remaining)-i}개 | {appid} | FAILED (5회 모두 실패)")
        time.sleep(1)
        continue

    # 원본 JSON 저장 (indent=2: 사람이 읽기 쉽게)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # API는 {appid: {success: bool, data: {...}}} 구조로 반환
    app = payload.get(str(appid), {})
    if not app.get("success"):
        rows.append({"appid": appid, "success": False})
        done_count += 1
        print(f"{skipped+i}/{total} | 남은 {len(remaining)-i}개 | {appid} | NO DATA")
        time.sleep(1)
        continue

    # ── 필드 추출 ──────────────────────────────────────────────────────────
    data  = app["data"]
    # 각 서브딕셔너리는 없을 수 있으므로 or {} 로 빈 딕셔너리 대체
    price = data.get("price_overview") or {}
    plat  = data.get("platforms")      or {}
    rel   = data.get("release_date")   or {}
    pcreq = data.get("pc_requirements") or {}
    ach   = data.get("achievements")   or {}
    desc  = data.get("content_descriptors") or {}

    short_desc    = data.get("short_description") or ""
    detailed_desc = data.get("detailed_description") or ""
    developers    = data.get("developers") or []
    publishers    = data.get("publishers") or []

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
        "price_initial":          price.get("initial"),        # 센트 단위 (1999 = $19.99)
        "price_final":            price.get("final"),          # 할인 적용 후 현재가
        "price_discount_pct":     price.get("discount_percent"),
        "platform_windows":       plat.get("windows"),
        "platform_mac":           plat.get("mac"),
        "platform_linux":         plat.get("linux"),
        # "|" 구분자로 리스트를 문자열로 저장 (CSV 단일 셀에 다중값 저장)
        # 08_feature_engineering 에서 split("|") 후 one-hot encoding 처리
        "categories":             "|".join(c["description"] for c in (data.get("categories") or []) if "description" in c),
        "genres":                 "|".join(g["description"] for g in (data.get("genres")     or []) if "description" in g),
        "supported_languages":    data.get("supported_languages"),
        "developers":             "|".join(developers),
        "publishers":             "|".join(publishers),
        "achievements_total":     ach.get("total"),
        "recommendations_total":  (data.get("recommendations") or {}).get("total"),
        "has_website":            1 if data.get("website") else 0,
        "short_desc_len":         len(short_desc),
        "detailed_desc_len":      len(detailed_desc),          # 설명 성의 지표
        "short_description":      short_desc,
        "detailed_description":   detailed_desc,               # 08에서 TF-IDF 피처 생성
        "pc_minimum":             pcreq.get("minimum"),        # HTML 포함 원문, 08에서 파싱
        "pc_recommended":         pcreq.get("recommended"),    # HTML 포함 원문, 08에서 파싱
        "content_descriptor_ids": "|".join(str(x) for x in (desc.get("ids") or [])),
        "header_image":           data.get("header_image"),
        "screenshots_count":      len(data.get("screenshots") or []),
        "movies_count":           len(data.get("movies")      or []),
    })

    done_count += 1
    elapsed  = time.time() - start_time
    avg_per  = elapsed / done_count
    left_n   = len(remaining) - i
    eta_sec  = avg_per * left_n
    eta_time = datetime.now() + timedelta(seconds=eta_sec)

    print(
        f"{skipped+i}/{total} | "
        f"남은 {left_n}개 | "
        f"경과 {str(timedelta(seconds=int(elapsed)))} | "
        f"완료예상 {eta_time.strftime('%H:%M:%S')} | "
        f"{appid} | {data.get('name')}"
    )

    # Steam API 비공식 rate limit 회피: 요청 간 1~1.5초 랜덤 딜레이
    time.sleep(1 + random.random() * 0.5)

# ── 요약 CSV 저장 ─────────────────────────────────────────────────────────
# 이번 실행(remaining)에서 처리한 게임만 포함.
# 전체 통합 CSV가 필요하면 02_steam_appdetails_summary_generate.py 실행.
pd.DataFrame(rows).to_csv(APPDETAILS_SUMMARY_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {APPDETAILS_SUMMARY_CSV}")
print(f"총 소요시간: {str(timedelta(seconds=int(time.time() - start_time)))}")
print("※ 위 CSV는 중간 점검용입니다. 반드시 02b 를 실행해 최종 CSV를 생성하세요.")
