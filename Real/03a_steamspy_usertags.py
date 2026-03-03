"""
03a_steamspy_usertags.py
================================================================================
[목적]
    SteamSpy API를 호출해 각 게임의 유저 태그와 태그별 투표 수를 수집한다.
    수집 결과는 appid별 JSON 파일로 저장한다.

[API]
    엔드포인트: https://steamspy.com/api.php
    파라미터:
        request : appdetails (게임 상세 정보 요청)
        appid   : 조회할 AppID
    응답 tags 딕셔너리: 키=태그명, 값=해당 태그에 투표한 유저 수

[입력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv

[출력 파일]
    Real/03 steamspy usertags/
        03_UserTags_raw/{appid}.json  <- 핵심 산출물
        03_UserTags_summary.csv       <- 임시 산출물 (이번 실행분만 포함)
    주의: 전체 통합 CSV는 03c_steamspy_usertags_summary_generate.py 로 생성.

[JSON 구조]
    성공 시: {appid: int, success: True,  tags: {태그명: 투표수, ...}}
    실패 시: {appid: int, success: False, tags: {}}

[resume 처리]
    RAW_DIR 에 이미 존재하는 {appid}.json 을 already_done 집합으로 로드.
    remaining 은 전체 appid 중 already_done 을 제외한 목록.
    -> 중단 후 재시작해도 중복 호출 없음.

[에러 처리]
    429 (Rate Limit) : 60*(시도횟수)초 대기 후 재시도 (최대 5회)
                       02a 의 120초보다 짧음 - SteamSpy rate limit이 덜 엄격함.
    5xx (서버 오류)  : 지수 백오프 (2^attempt + random) 후 재시도
    JSON 아닌 응답   : 지수 백오프 후 재시도
    5회 모두 실패    : success=False 로 JSON 저장 후 다음 게임으로 진행

[딜레이]
    요청 간 1.5~2.0초 랜덤 딜레이.
    SteamSpy는 비공식 API라 rate limit 기준이 불명확하므로 보수적으로 설정.

[실패 건 재수집 방법]
    1) 03b_steamspy_usertags_retry_cleanup.py 실행 -> success=False JSON 삭제
    2) 이 파일(03a) 재실행 -> 삭제된 appid 만 재수집

[태그 binary 변환]
    파일 하단에 binary 변환 코드가 주석으로 존재.
    논문(Trneny 2017) 52개 태그를 그대로 쓰지 않는 이유:
        - 2017년에 없던 태그(Souls-like, Cozy 등)가 현재는 주요 태그
        - Singleplayer/Multiplayer 등은 categories 피처와 중복
        - Great Soundtrack 등 품질 평가성 태그는 출시 전 예측 불가
    -> 수집 완료 후 05_analyze_tags.py 로 빈도 확인 후 태그 선정할 것.

[다음 단계]
    수집 완료 + 재수집(필요시 03b 활용)까지 마친 후
    03c_steamspy_usertags_summary_generate.py 실행 -> 최종 통합 CSV 생성.
================================================================================
"""

import os, json, time, random
import pandas as pd
import requests
from datetime import datetime, timedelta

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUT_DIR   = r"Real\03 steamspy usertags"
RAW_DIR   = f"{OUT_DIR}\\03_UserTags_raw"
OUT_CSV   = f"{OUT_DIR}\\03_UserTags_summary.csv"

os.makedirs(RAW_DIR, exist_ok=True)

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

already_done = set(
    int(f.replace(".json", ""))
    for f in os.listdir(RAW_DIR)
    if f.endswith(".json")
)
remaining = [a for a in appids if a not in already_done]
skipped   = total - len(remaining)

print(f"전체 {total}개 | 이미 완료 {skipped}개 | 남은 {len(remaining)}개")

session    = requests.Session()
rows       = []
start_time = time.time()
done_count = 0

for i, appid in enumerate(remaining, 1):
    raw_path = f"{RAW_DIR}\\{appid}.json"

    payload = None
    for attempt in range(5):
        resp = session.get(
            "https://steamspy.com/api.php",
            params={"request": "appdetails", "appid": appid},
            timeout=20
        )
        if resp.status_code == 429:
            wait = 60 * (attempt + 1)
            print(f"\n  [{appid}] 429 차단 -> {wait}초 대기 후 재시도 ({attempt+1}/5)")
            time.sleep(wait)
            continue
        if resp.status_code in (500, 502, 503, 504):
            time.sleep(2 ** attempt + random.random())
            continue
        if not resp.text.strip().startswith("{"):
            time.sleep(2 ** attempt + random.random())
            continue
        payload = resp.json()
        break

    if payload is None:
        result = {"appid": appid, "success": False, "tags": {}}
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        rows.append({"appid": appid, "success": False, "tags": ""})
        done_count += 1
        print(f"{skipped+i}/{total} | 남은 {len(remaining)-i}개 | {appid} | FAILED (5회 모두 실패)")
        time.sleep(1)
        continue

    tags = payload.get("tags") or {}
    result = {"appid": appid, "success": True, "tags": tags}

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    rows.append({"appid": appid, "success": True, "tags": json.dumps(tags, ensure_ascii=False)})

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
        f"{appid} | 태그 {len(tags)}개"
    )

    time.sleep(1.5 + random.random() * 0.5)

pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {OUT_CSV}")
print(f"총 소요시간: {str(timedelta(seconds=int(time.time() - start_time)))}")


# -----------------------------------------------------------------------
# [주석처리된 binary CSV 변환 코드]
#
# 원래 논문(Trněný 2017)에서는 전체 300개+ 태그 중
# 개발자가 직접 붙일 법한 장르/게임플레이 태그 52개를 선정해서
# 각각 binary(0/1) 피처로 변환했음.
#
# 여기서도 동일하게 선정된 태그 기준으로 binary CSV를 만들려 했으나,
# 논문이 2017년 기준이라 당시 없었던 태그(Souls-like, Cozy, Auto Battler 등)가
# 지금은 주요 태그가 됐을 수 있음.
#
# 또한 Singleplayer/Multiplayer/Co-op 등 플레이 방식 태그는
# categories 피처와 중복되므로 제외 대상.
# Great Soundtrack, Atmospheric 등 품질 평가성 태그도 출시 전 예측 불가 → 제외.
#
# 따라서 raw 수집 완료 후 전체 태그 빈도를 먼저 확인하고,
# 실제 데이터 기반으로 어떤 태그를 피처로 쓸지 직접 판단한 뒤
# 아래 코드를 활성화할 것.
#
# 다음 단계:
#   → 04_Analyze_Tags.py 로 전체 태그 빈도 집계 및 시각화
#   → 카테고리 중복 / 품질 평가성 태그 필터링 후 목록 확정
#   → 아래 코드 주석 해제하고 binary CSV 생성
# -----------------------------------------------------------------------

# SELECTED_TAGS = [
#     "2D", "4X", "Board Game", "Card Game", "City Builder", "Crafting",
#     "Cyberpunk", "Dating Sim", "Episodic", "Family Friendly", "Fantasy",
#     "Female Protagonist", "Fighting", "First-Person", "Flight", "FPS",
#     "Hidden Object", "Horror", "JRPG", "Medieval", "Noir", "Nudity",
#     "Open World", "Parkour", "Pixel Graphics", "Platformer", "Point & Click",
#     "Puzzle", "Remake", "Retro", "Rhythm", "Roguelike", "Rogue-lite",
#     "RTS", "Sandbox", "Sci-fi", "Space", "Stealth", "Steampunk",
#     "Story Rich", "Superhero", "Survival", "Survival Horror", "Third Person",
#     "Third-Person Shooter", "Tower Defense", "Turn-Based", "Turn-Based Strategy",
#     "Visual Novel", "Walking Simulator", "World War II", "Zombies"
# ]

# print("\nbinary CSV 생성 중...")
# bin_rows = []
# for appid in appids:
#     raw_path = os.path.join(RAW_DIR, f"{appid}.json")
#     if not os.path.exists(raw_path):
#         continue
#     with open(raw_path, encoding="utf-8") as f:
#         d = json.load(f)
#     tags = d.get("tags") or {}
#     tags_lower = {k.lower() for k in tags.keys()}
#     row = {"appid": appid}
#     for tag in SELECTED_TAGS:
#         row[f"tag_{tag.replace(' ', '_')}"] = 1 if tag.lower() in tags_lower else 0
#     bin_rows.append(row)

# out_binary = f"{OUT_DIR}\\03_UserTags_binary.csv"
# pd.DataFrame(bin_rows).to_csv(out_binary, index=False, encoding="utf-8-sig")
# print(f"done -> {out_binary}")