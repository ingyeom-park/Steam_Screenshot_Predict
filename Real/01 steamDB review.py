"""
01 steamDB review accumulate.py

SteamDB API로 게임별 일자별 누적 리뷰 데이터 수집
resume 기능 포함 — 중단 후 재실행하면 이미 수집된 AppID는 건너뜀

입력:
  - INPUT_CSV : AppID 목록이 있는 CSV (01 steamDB appid, gamename.csv)

출력:
  - OUTPUT_CSV : 일자별 누적 리뷰 데이터
  - DONE_CSV   : 수집 완료된 AppID 목록 (resume용)
"""

import csv
import time
import random
import datetime
import requests
import os
from pathlib import Path
from tqdm import tqdm

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
BASE = r"\Real"

INPUT_CSV  = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUTPUT_CSV = BASE + r"\01 steamDB review\01 SteamDB review accumulate.csv"
DONE_CSV   = BASE + r"\01 steamDB review\01 done appids.csv"

COOKIE = (
    "__Host-cc=us; __Host-steamdb=9202041-26f77e871cbf96a54c7715ea7140f4ea890805ff; cf_clearance=LYff3Qt_C.DyK6Pt1iYs5EKaN.JjtwGBU6QOiiql9QI-1772814615-1.2.1.1-Xhgg55HSLjReQqSclPmuguY76UmP0KQ_qKBiXrkdMREXYLoOZEqNxIVld_xamAf8q6PM85.e73FfKEk.4eskudmSGFC9Qo4AtkF80lSrhL5GKSyN5rOPXDu68N.keMEJ7dTYY.035NELI6Q99r4xBeNGYbGo1jCbxqTyPuauZHeVx5aCyFOO3GPsR4FJ44Rf_gFtsH6fbXERXHjb_kD1YbHlpeOC8VPU1szCPvzetizPKNohqI1hJsvArzqOeZM6"
)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
)

API_URL       = "https://steamdb.info/api/GetGraphReviewsLoggedIn/"
REQUEST_DELAY = 5.0   # 초 (SteamDB는 매우 민감하므로 기본 딜레이 상향)
RETRY_WAIT    = 60    # 429 발생 시 대기 초

FIELDNAMES = [
    "AppID", "GameName", "date",
    "cum_positive", "cum_negative", "cum_total",
    "daily_positive", "daily_negative", "daily_total",
    "positive_ratio",
]


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def load_apps(csv_path):
    rows = []
    f = open(csv_path, "r", encoding="utf-8-sig")
    reader = csv.DictReader(f)
    for r in reader:
        rows.append({"AppID": r["AppID"].strip(), "GameName": r["GameName"].strip()})
    f.close()
    return rows


def load_done_appids(done_path):
    if not Path(done_path).exists():
        return set()
    done = set()
    f = open(done_path, "r", encoding="utf-8-sig")
    reader = csv.DictReader(f)
    for r in reader:
        done.add(r["AppID"].strip())
    f.close()
    return done


def fetch_reviews(AppID, session):
    headers = {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate",
        "accept-language": "ko-KR,ko;q=0.8",
        "cookie": COOKIE,
        "referer": f"https://steamdb.info/app/{AppID}/charts/",
        "sec-ch-ua": '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"',
        "sec-ch-ua-arch": '"x86"',
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-full-version-list": '"Not:A-Brand";v="99.0.0.0", "Brave";v="145.0.0.0", "Chromium";v="145.0.0.0"',
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

    resp = session.get(API_URL, params={"appid": AppID}, headers=headers, timeout=30)

    if resp.status_code == 429:
        tqdm.write(f"  [429] Rate-limited. {RETRY_WAIT}초 대기 후 재시도...")
        time.sleep(RETRY_WAIT)
        resp = session.get(API_URL, params={"appid": AppID}, headers=headers, timeout=30)

    if resp.status_code == 429:
        return "RATE_LIMIT"

    if resp.status_code == 304:
        return None

    if resp.status_code != 200:
        tqdm.write(f"  [HTTP {resp.status_code}] AppID={AppID} — 건너뜀")
        return None

    if not resp.content or not resp.text.strip():
        tqdm.write(f"  [EMPTY] AppID={AppID} — 응답 바디 없음, 건너뜀")
        return None

    parsed = None
    try:
        parsed = resp.json()
    except Exception:
        tqdm.write(f"  [JSON ERR] AppID={AppID} — 파싱 실패. 응답 앞부분: {resp.text[:200]}")
        return None

    if not parsed.get("success"):
        tqdm.write(f"  [API fail] AppID={AppID}: {parsed}")
        return None

    return parsed


def parse_review_data(AppID, GameName, data):
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
            "AppID":          AppID,
            "GameName":       GameName,
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
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

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

    out_file_exists  = Path(OUTPUT_CSV).exists()
    out_f            = open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig")
    out_writer       = csv.DictWriter(out_f, fieldnames=FIELDNAMES)
    if not out_file_exists:
        out_writer.writeheader()

    done_file_exists = Path(DONE_CSV).exists()
    done_f           = open(DONE_CSV, "a", newline="", encoding="utf-8-sig")
    done_writer      = csv.DictWriter(done_f, fieldnames=["AppID"])
    if not done_file_exists:
        done_writer.writeheader()

    session = requests.Session()
    success = 0
    fail    = 0
    consecutive_429 = 0

    pbar = tqdm(remaining, total=left, unit="game",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")

    for app in pbar:
        AppID    = app["AppID"]
        GameName = app["GameName"]

        pbar.set_description(f"{GameName[:30]:<30}")

        data = fetch_reviews(AppID, session)

        if data == "RATE_LIMIT":
            consecutive_429 += 1
            fail += 1
            if consecutive_429 >= 3:
                tqdm.write(f"\n[CRITICAL] 3회 연속 429 에러 발생. IP 차단을 방지하기 위해 프로그램을 종료합니다.")
                break
            tqdm.write(f"  [429] 연속 발생 ({consecutive_429}/3). 5분간 강제 휴식 후 다음 게임 시도...")
            time.sleep(300)
            continue

        elif data is None:
            consecutive_429 = 0
            fail += 1
            tqdm.write(f"  [FAIL] {AppID} | {GameName}")
            continue
        else:
            consecutive_429 = 0
            rows = parse_review_data(AppID, GameName, data)
            out_writer.writerows(rows)
            out_f.flush()
            success += 1
            tqdm.write(f"  [OK]   {AppID} | {GameName} | {len(rows)}일치")

        done_writer.writerow({"AppID": AppID})
        done_f.flush()

        # 고정된 요청 패턴을 피하기 위해 랜덤 딜레이 추가
        time.sleep(REQUEST_DELAY + random.uniform(0, 3))

    out_f.close()
    done_f.close()

    print(f"\n완료 — 성공: {success}개  실패: {fail}개")
    print(f"결과 저장 → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
