"""
01_steamdb_review_history.py
================================================================================
[목적]
    SteamDB 로그인 전용 API에서 게임별 일자별 누적 리뷰 히스토리를 수집한다.

[입력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv

[출력 파일]
    data/raw/01_steamdb_review_history/01_steamdb_review_history.csv
    data/raw/01_steamdb_review_history/01_steamdb_review_done_appids.csv
    data/raw/01_steamdb_review_history/01_steamdb_review_failed_appids.csv

[주의]
    SteamDB 로그인 쿠키는 pipeline/local_config.py 에서 관리한다.
================================================================================
"""

import csv
import datetime
import os
import random
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

from local_config import DEFAULT_USER_AGENT, STEAMDB_COOKIE
from project_paths import (
    APP_LIST_CSV,
    STEAMDB_REVIEW_CSV,
    STEAMDB_REVIEW_DIR,
    STEAMDB_REVIEW_DONE_CSV,
    STEAMDB_REVIEW_FAILED_CSV,
)

INPUT_CSV  = APP_LIST_CSV
OUTPUT_CSV = STEAMDB_REVIEW_CSV
DONE_CSV   = STEAMDB_REVIEW_DONE_CSV
FAILED_CSV = STEAMDB_REVIEW_FAILED_CSV
COOKIE     = STEAMDB_COOKIE
USER_AGENT = DEFAULT_USER_AGENT

API_URL             = "https://steamdb.info/api/GetGraphReviewsLoggedIn/"
REQUEST_DELAY       = 5.0   # 초 (SteamDB는 매우 민감하므로 기본 딜레이 상향)
RETRY_WAIT_BASE     = 60    # 429 발생 시 기본 대기 초 (지수 백오프 기준값)
MAX_RETRY_WAIT      = 600   # 지수 백오프 상한 (초)
SESSION_RESET_EVERY = 50    # N건마다 세션 재생성 (세션 기반 핑거프린팅 회피)

FIELDNAMES = [
    "AppID", "GameName", "date",
    "cum_positive", "cum_negative", "cum_total",
    "daily_positive", "daily_negative", "daily_total",
    "positive_ratio",
]


# ──────────────────────────────────────────────
# 세션 생성
# ──────────────────────────────────────────────
def make_session():
    """500/502/503/504 에 대한 자동 재시도 어댑터가 달린 세션을 반환한다."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def load_apps(csv_path):
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({"AppID": r["AppID"].strip(), "GameName": r["GameName"].strip()})
    return rows


def load_done_appids(done_path):
    if not Path(done_path).exists():
        return set()
    done = set()
    with open(done_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            done.add(r["AppID"].strip())
    return done


def fetch_reviews(appid, session, retry_wait):
    headers = {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate",
        "accept-language": "ko-KR,ko;q=0.8",
        "cookie": COOKIE,
        "priority": "u=1, i",
        "referer": f"https://steamdb.info/app/{appid}/charts/",
        "sec-ch-ua": '"Brave";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-arch": '"x86"',
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-full-version-list": '"Brave";v="147.0.0.0", "Not.A/Brand";v="8.0.0.0", "Chromium";v="147.0.0.0"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-model": '""',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"19.0.0"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sec-gpc": "1",
        "user-agent": USER_AGENT,
        "x-requested-with": "XMLHttpRequest",
    }

    # 네트워크 예외 처리 (타임아웃, 연결 끊김 등)
    try:
        resp = session.get(API_URL, params={"appid": appid}, headers=headers, timeout=30)
    except requests.exceptions.Timeout:
        tqdm.write(f"  [TIMEOUT] AppID={appid} - 타임아웃")
        return "NETWORK_ERROR"
    except requests.exceptions.ConnectionError as e:
        tqdm.write(f"  [CONN ERR] AppID={appid} - 연결 오류: {e}")
        return "NETWORK_ERROR"
    except requests.exceptions.RequestException as e:
        tqdm.write(f"  [REQ ERR] AppID={appid} - 요청 오류: {e}")
        return "NETWORK_ERROR"

    # 429: 지수 백오프 적용 후 1회 재시도
    if resp.status_code == 429:
        tqdm.write(f"  [429] Rate-limited. {retry_wait}초 대기 후 재시도...")
        time.sleep(retry_wait)
        try:
            resp = session.get(API_URL, params={"appid": appid}, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            tqdm.write(f"  [REQ ERR] 재시도 중 오류: {e}")
            return "NETWORK_ERROR"

    if resp.status_code == 429:
        return "RATE_LIMIT"

    if resp.status_code == 304:
        return None

    if resp.status_code != 200:
        tqdm.write(f"  [HTTP {resp.status_code}] AppID={appid} - 건너뜀")
        return None

    if not resp.content or not resp.text.strip():
        tqdm.write(f"  [EMPTY] AppID={appid} - 응답 바디 없음, 건너뜀")
        return None

    try:
        parsed = resp.json()
    except Exception:
        tqdm.write(f"  [JSON ERR] AppID={appid} - 파싱 실패. 응답 앞부분: {resp.text[:200]}")
        return None

    if not parsed.get("success"):
        tqdm.write(f"  [API fail] AppID={appid}: {parsed}")
        return None

    return parsed


def parse_review_data(appid, game_name, data):
    inner    = data["data"]
    start    = inner["start"]
    step     = inner["step"]
    values_p = inner["values_p"]
    values_n = inner["values_n"]

    rows   = []
    length = min(len(values_p), len(values_n))

    for i in range(length):
        ts        = start + step * i
        dt        = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        cum_p     = values_p[i]
        cum_n     = values_n[i]

        cum_total = cum_p + cum_n

        if i == 0:
            delta_p = cum_p
            delta_n = cum_n
        else:
            delta_p = cum_p - values_p[i - 1]
            delta_n = cum_n - values_n[i - 1]
        delta_total = delta_p + delta_n

        ratio_p = round(cum_p / cum_total, 6) if cum_total > 0 else None

        rows.append({
            "AppID":          appid,
            "GameName":       game_name,
            "date":           dt,
            "cum_positive":   cum_p,
            "cum_negative":   cum_n,
            "cum_total":      cum_total,
            "daily_positive": delta_p,
            "daily_negative": delta_n,
            "daily_total":    delta_total,
            "positive_ratio": ratio_p,
        })

    return rows


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    if not COOKIE.strip():
        print("pipeline/local_config.py 에 STEAMDB_COOKIE 값을 먼저 입력해야 합니다.")
        return

    os.makedirs(STEAMDB_REVIEW_DIR, exist_ok=True)

    apps      = load_apps(INPUT_CSV)
    done_ids  = load_done_appids(DONE_CSV)
    remaining = [a for a in apps if a["AppID"] not in done_ids]

    total   = len(apps)
    already = len(done_ids)
    left    = len(remaining)

    print(f"전체: {total}개  |  완료: {already}개  |  남은 것: {left}개")
    if left == 0:
        print("모두 수집 완료.")
        return

    eta_sec = left * REQUEST_DELAY
    eta_str = str(datetime.timedelta(seconds=int(eta_sec)))
    print(f"예상 소요 시간: 약 {eta_str}  (딜레이 {REQUEST_DELAY}초 기준, 실제는 더 걸릴 수 있음)\n")

    out_file_exists    = Path(OUTPUT_CSV).exists()
    done_file_exists   = Path(DONE_CSV).exists()
    failed_file_exists = Path(FAILED_CSV).exists()

    out_f    = open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig")
    done_f   = open(DONE_CSV,   "a", newline="", encoding="utf-8-sig")
    failed_f = open(FAILED_CSV, "a", newline="", encoding="utf-8-sig")

    try:
        out_writer    = csv.DictWriter(out_f,    fieldnames=FIELDNAMES)
        done_writer   = csv.DictWriter(done_f,   fieldnames=["AppID"])
        failed_writer = csv.DictWriter(failed_f, fieldnames=["AppID", "reason"])

        if not out_file_exists:
            out_writer.writeheader()
        if not done_file_exists:
            done_writer.writeheader()
        if not failed_file_exists:
            failed_writer.writeheader()

        session         = make_session()
        success         = 0
        fail            = 0
        consecutive_429 = 0
        retry_wait      = RETRY_WAIT_BASE
        request_count   = 0

        pbar = tqdm(remaining, total=left, unit="game",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

        for app in pbar:
            AppID    = app["AppID"]
            GameName = app["GameName"]

            pbar.set_description(f"{GameName[:30]:<30}")

            # 주기적으로 세션 재생성 (세션 기반 핑거프린팅 차단 회피)
            request_count += 1
            if request_count % SESSION_RESET_EVERY == 0:
                session.close()
                session = make_session()
                tqdm.write(f"  [SESSION] 세션 재생성 ({request_count}번째 요청)")

            data = fetch_reviews(AppID, session, retry_wait=retry_wait)

            if data == "RATE_LIMIT":
                consecutive_429 += 1
                fail += 1
                retry_wait = min(retry_wait * 2, MAX_RETRY_WAIT)  # 지수 백오프
                failed_writer.writerow({"AppID": AppID, "reason": "RATE_LIMIT"})
                failed_f.flush()
                if consecutive_429 >= 3:
                    tqdm.write("\n[CRITICAL] 3회 연속 429 에러 발생. 프로그램을 종료합니다.")
                    break
                tqdm.write(f"  [429] 연속 발생 ({consecutive_429}/3). 5분간 강제 휴식 후 다음 게임 시도...")
                time.sleep(300)
                continue

            elif data == "NETWORK_ERROR":
                consecutive_429 = 0
                fail += 1
                failed_writer.writerow({"AppID": AppID, "reason": "NETWORK_ERROR"})
                failed_f.flush()
                tqdm.write(f"  [FAIL/NET] {AppID} | {GameName}")
                time.sleep(REQUEST_DELAY)
                continue

            elif data is None:
                consecutive_429 = 0
                fail += 1
                failed_writer.writerow({"AppID": AppID, "reason": "API_FAIL"})
                failed_f.flush()
                tqdm.write(f"  [FAIL] {AppID} | {GameName}")
                continue

            else:
                consecutive_429 = 0
                retry_wait = RETRY_WAIT_BASE  # 성공 시 백오프 초기화
                rows = parse_review_data(AppID, GameName, data)
                if not rows:
                    tqdm.write(f"  [EMPTY DATA] {AppID} | {GameName} - 파싱 결과 없음")
                    failed_writer.writerow({"AppID": AppID, "reason": "EMPTY_DATA"})
                    failed_f.flush()
                    fail += 1
                    continue
                out_writer.writerows(rows)
                out_f.flush()
                success += 1
                tqdm.write(f"  [OK]   {AppID} | {GameName} | {len(rows)}일치")

            done_writer.writerow({"AppID": AppID})
            done_f.flush()

            # 고정된 요청 패턴을 피하기 위해 랜덤 딜레이 추가
            time.sleep(REQUEST_DELAY + random.uniform(0, 5))

    finally:
        out_f.close()
        done_f.close()
        failed_f.close()
        session.close()

    print(f"\n완료 - 성공: {success}개  실패: {fail}개")
    print(f"결과 저장 -> {OUTPUT_CSV}")
    print(f"실패 목록 -> {FAILED_CSV}")


if __name__ == "__main__":
    main()
