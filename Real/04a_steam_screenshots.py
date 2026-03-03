"""
04a_steam_screenshots.py
================================================================================
[목적]
    02a 가 수집한 원본 JSON 에서 스크린샷 URL을 추출해
    각 게임의 스크린샷을 최대 4장 다운로드한다.

[입력 파일]
    Real/02 steam appdetails snapshot/02_Steam_Appdetails_snapshot_raw/{appid}.json
        - data.screenshots 필드에 URL 목록 포함.
        - 각 항목 구조: {"id": ..., "path_thumbnail": ..., "path_full": ...}

[출력 파일]
    Real/04 steam screenshots/{appid}/ss_0.jpg ~ ss_3.jpg
        - 게임당 최대 4장 (스크린샷이 4장 미만이면 있는 만큼만 저장)
        - 파일명 ss_0~ss_3: 06_opencv_features.py 에서 이 이름으로 읽음

[스크린샷 4장 제한 이유]
    논문(Trneny 2017) 기준으로 앞 4장을 사용.
    그 이상은 06에서 쓰지 않으므로 저장 공간 낭비.

[resume 처리]
    IMG_DIR 내 이미 존재하는 appid 폴더를 already_done 집합으로 로드.
    remaining 은 폴더가 없는 appid 만 포함.
    개별 스크린샷 단위로도 os.path.exists() 체크해
    같은 게임 폴더 내 부분 완료된 경우도 처리.

[스킵 조건]
    1) JSON success=False : 게임 정보 자체가 없는 경우
    2) screenshots 필드 비어있음 : 스크린샷 없는 게임

[에러 처리]
    HTTP 200 이외 응답: 해당 스크린샷만 스킵, 다음 장 진행.
    CDN 에서 제공되므로 별도 재시도 로직 없음.

[다음 단계]
    다운로드 완료 후 06_opencv_features.py 에서
    ss_0~ss_3.jpg 를 읽어 OpenCV 시각 피처 추출.
================================================================================
"""

import os, json, time, random
import requests
from datetime import datetime, timedelta

RAW_DIR = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_snapshot_raw"
IMG_DIR = r"Real\04 steam screenshots"

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

    f = open(f"{RAW_DIR}/{fname}", encoding="utf-8")
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

    game_dir = f"{IMG_DIR}/{appid}"
    os.makedirs(game_dir, exist_ok=True)

    for j, url in enumerate(urls):
        out_path = f"{game_dir}/ss_{j}.jpg"
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
