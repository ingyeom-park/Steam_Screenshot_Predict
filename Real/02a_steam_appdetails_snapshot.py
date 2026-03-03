"""
02_steam_appdetails_snapshot.py
================================================================================
[목적]
    01에서 수집한 AppID 목록을 기반으로 Steam 공식 API를 호출해
    각 게임의 상세 정보를 수집한다.

    수집 결과는 두 가지 형태로 저장:
        1) 원본 JSON 파일 (appid별 1개) : 나중에 추가 피처 추출 시 재사용 가능
        2) 요약 CSV : 피처 엔지니어링(08)에서 바로 쓸 수 있는 정제된 테이블

[API]
    엔드포인트: https://store.steampowered.com/api/appdetails
    파라미터:
        appids : 조회할 AppID (1회 1개)
        cc     : 국가 코드 (us) -> 가격을 USD 기준으로 받기 위함
        l      : 언어 (english) -> 텍스트 필드를 영어로 받기 위함

[입력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv
        컬럼: AppID, GameName

[출력 파일]
    Real/02 steam appdetails snapshot/
        02_Steam_Appdetails_snapshot_raw/{appid}.json   <- 게임별 원본 응답
        02_Steam_Appdetails_summary.csv                 <- 전체 요약 테이블

[요약 CSV 컬럼 설명]
    appid                  : Steam 게임 고유 ID
    success                : API 응답 성공 여부 (False면 나머지 컬럼 없음)
    type                   : 앱 타입 (game / dlc / demo 등)
    name                   : 게임명
    required_age           : 이용 연령 제한
    is_free                : 무료 게임 여부
    release_coming_soon    : 미출시 여부
    release_date_text      : 출시일 텍스트 (예: "15 Mar, 2022")
    price_currency         : 통화 (USD)
    price_initial          : 정가 (센트 단위, 예: 1999 = $19.99)
    price_final            : 현재가 (할인 적용 후)
    price_discount_pct     : 할인율 (%)
    platform_windows/mac/linux : 지원 플랫폼 여부
    categories             : 게임 카테고리 ("|" 구분, 예: "Single-player|Steam Achievements")
    genres                 : 장르 ("|" 구분, 예: "Action|RPG")
    supported_languages    : 지원 언어 목록 (HTML 태그 포함된 원본 문자열)
    developers             : 개발사 ("|" 구분)
    publishers             : 퍼블리셔 ("|" 구분)
    achievements_total     : 업적 총 개수
    recommendations_total  : 추천 수 (= 리뷰 수와 유사, Y변수 생성에 활용 가능)
    has_website            : 공식 웹사이트 존재 여부 (0/1)
    short_desc_len         : 짧은 설명 문자 수
    detailed_desc_len      : 상세 설명 문자 수 (긴 설명 = 정성 들인 스토어 페이지)
    short_description      : 짧은 설명 원문
    detailed_description   : 상세 설명 원문 (TF-IDF 피처 생성에 사용 예정)
    pc_minimum             : 최소 사양 원문 (HTML 포함) -> 08에서 파싱
    pc_recommended         : 권장 사양 원문 (HTML 포함) -> 08에서 파싱
    content_descriptor_ids : 성인 콘텐츠 분류 ID ("|" 구분)
    header_image           : 헤더 이미지 URL
    screenshots_count      : 스크린샷 수
    movies_count           : 트레일러 영상 수

[resume 처리]
    raw_dir 에 이미 존재하는 {appid}.json 파일을 already_done 집합으로 로드.
    remaining 은 전체 appid 중 already_done 을 제외한 목록.
    -> 중단 후 재시작해도 중복 호출 없음.
    단, 요약 CSV(rows)는 매 실행마다 remaining 처리분만 새로 쌓임.
    전체 통합 CSV가 필요하면 02_steam_appdetails_summary_generate.py 별도 실행.

[에러 처리]
    429 (Rate Limit) : 120 * (시도 횟수)초 대기 후 재시도 (최대 5회)
    5xx (서버 오류)  : 지수 백오프 (2^attempt + random) 후 재시도
    JSON 아닌 응답   : 동일하게 지수 백오프 후 재시도
    5회 모두 실패    : success=False 로 JSON 저장 후 다음 게임으로 진행

[다음 단계]
    이 파일 실행 완료 후 02b_steam_appdetails_summary.py 를 실행해
    JSON들에서 완전한 CSV를 생성한다.
    JSON 수집과 03(유저태그), 04(스크린샷) 수집은 순서 무관하게 진행 가능.
================================================================================
"""

import os, json, time, random
import pandas as pd
import requests
from datetime import datetime, timedelta

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUT_DIR   = r"Real\02 steam appdetails snapshot"
CC        = "us"
LANG      = "english"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

# raw_dir: 게임별 원본 JSON 저장 폴더
# JSON을 개별 저장하는 이유: 나중에 추가 피처가 필요할 때 API 재호출 없이 재사용 가능
raw_dir = f"{OUT_DIR}\\02_Steam_Appdetails_snapshot_raw"
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
    raw_path = f"{raw_dir}\\{appid}.json"

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
out = f"{OUT_DIR}\\02_Steam_Appdetails_summary.csv"
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
print(f"\ndone -> {out}")
print(f"총 소요시간: {str(timedelta(seconds=int(time.time() - start_time)))}")
print(f"※ 위 CSV는 불완전한 임시 파일입니다. 반드시 02b_steam_appdetails_summary.py 를 실행해 최종 CSV를 생성하세요.")