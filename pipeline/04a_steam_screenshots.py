"""
04a_steam_screenshots.py
================================================================================
[목적]
    02a 원본 JSON에서 스크린샷 URL을 추출해 최대 4장까지 다운로드한다.

[입력 파일]
    data/raw/02_steam_appdetails/json/{appid}.json

[출력 파일]
    data/raw/04_screenshots/{appid}/ss_0.jpg ~ ss_3.jpg
================================================================================
"""

import os, json, time, random
import requests
from datetime import datetime, timedelta

from project_paths import APPDETAILS_JSON_DIR, SCREENSHOTS_DIR

RAW_DIR = APPDETAILS_JSON_DIR
IMG_DIR = SCREENSHOTS_DIR

os.makedirs(IMG_DIR, exist_ok=True)

session = requests.Session()

# json_files: appid 숫자 기준 오름차순 정렬 (처리 순서 일관성 유지)
json_files = sorted(
    [f for f in os.listdir(RAW_DIR) if f.endswith(".json")],
    key=lambda f: int(f.removesuffix(".json"))
)
total = len(json_files)

# already_done: IMG_DIR 내 이미 존재하는 appid 폴더 집합 (resume용)
already_done = set(os.listdir(IMG_DIR))
remaining    = [f for f in json_files if f.removesuffix(".json") not in already_done]
skipped      = total - len(remaining)

print(f"전체 {total}개 | 이미 완료 {skipped}개 | 남은 {len(remaining)}개")

start_time = time.time()
done_count = 0

for i, fname in enumerate(remaining, 1):
    appid = fname.removesuffix(".json")

    f = open(RAW_DIR / fname, encoding="utf-8")
    payload = json.load(f)
    f.close()

    # Steam API 응답 구조: {str(appid): {"success": bool, "data": {...}}}
    # payload 키가 appid 문자열이므로 str 그대로 접근
    app = payload.get(appid, {})
    if not app.get("success"):
        print(f"[{skipped+i}/{total}] {appid} skip (success=False)")
        done_count += 1
        continue

    # path_full: 원본 해상도 URL (1920x1080 등)
    # [:4]: 최대 4장만 사용 (논문 기준, 06에서 ss_0~ss_3 으로 읽음)
    screenshots = app["data"].get("screenshots") or []
    urls        = [s["path_full"] for s in screenshots[:4] if "path_full" in s]

    if not urls:
        print(f"[{skipped+i}/{total}] {appid} skip (no screenshots)")
        done_count += 1
        continue

    game_dir = IMG_DIR / appid
    os.makedirs(game_dir, exist_ok=True)

    for j, url in enumerate(urls):
        out_path = game_dir / f"ss_{j}.jpg"
        # 개별 파일 단위 resume: 이미 있으면 스킵
        if os.path.exists(out_path):
            continue
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"  [{appid}] ss_{j} failed: HTTP {resp.status_code}")
            continue
        f = open(out_path, "wb")
        f.write(resp.content)
        f.close()

    done_count += 1
    elapsed  = time.time() - start_time
    avg_per  = elapsed / done_count
    left_n   = len(remaining) - i
    eta_time = datetime.now() + timedelta(seconds=avg_per * left_n)

    print(
        f"[{skipped+i}/{total}] "
        f"남은 {left_n}개 | "
        f"경과 {str(timedelta(seconds=int(elapsed)))} | "
        f"완료예상 {eta_time.strftime('%H:%M:%S')} | "
        f"{appid} ({len(urls)}장)"
    )

print(f"\ndone. 총 소요시간: {str(timedelta(seconds=int(time.time() - start_time)))}")
