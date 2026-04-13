"""
03a_steamspy_usertags.py
================================================================================
[목적]
    SteamSpy API를 호출해 게임별 유저 태그와 태그별 투표 수를 수집한다.

[입력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv

[출력 파일]
    data/raw/03_steamspy_usertags/json/{appid}.json
    data/interim/03_steamspy_usertags_summary.csv

[비고]
    이 CSV는 실행 점검용이다.
    최종 통합 CSV는 03c에서 다시 생성한다.
================================================================================
"""

import os, json, time, random
import pandas as pd
import requests
from datetime import datetime, timedelta

from project_paths import APP_LIST_CSV, USERTAGS_JSON_DIR, USERTAGS_SUMMARY_CSV

RAW_DIR = USERTAGS_JSON_DIR
OUT_CSV = USERTAGS_SUMMARY_CSV

os.makedirs(RAW_DIR, exist_ok=True)

df     = pd.read_csv(APP_LIST_CSV)
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
    raw_path = RAW_DIR / f"{appid}.json"

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
