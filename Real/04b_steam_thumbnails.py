"""
04b_steam_thumbnails.py
================================================================================
[목적]
    Steam CDN 에서 게임별 헤더 이미지(썸네일)를 다운로드한다.
    URL 구조: https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg
    크기: 460x215 px (Steam 스토어 페이지 상단 대표 이미지)
    저장: Real/04b steam thumbnails/{appid}/thumb.jpg

[04 와의 차이]
    04  : 02a JSON 에서 URL 추출 후 다운로드 (스크린샷 4장, JSON 필요)
    04b : appid 만으로 CDN URL 직접 구성 후 다운로드 (썸네일 1장, JSON 불필요)

[입력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv

[출력 파일]
    Real/04b steam thumbnails/
        {appid}/thumb.jpg
        04b_thumbnails_summary.csv
            컬럼: appid, success, file_path, reason
            reason 값:
                (빈 문자열)        : 성공
                404_not_found      : CDN 에 이미지 없음
                http_{상태코드}    : 기타 HTTP 오류
                max_retry_exceeded : 최대 재시도 초과

[resume 처리]
    SUMMARY_CSV 가 존재하면 done 딕셔너리로 로드.
    remaining 은 done 에 없는 appid 만 포함.
    CSV 를 append 모드로 열어 새 결과만 추가.

[에러 처리]
    404             : 즉시 실패 (재시도 불필요)
    429             : 10 * attempt 초 대기 후 재시도
    기타 HTTP 오류  : 3 * attempt 초 대기 후 재시도 (최대 MAX_RETRY=3회)
    len(content) <= 1000 : 빈 응답 200 대비 재시도

[딜레이]
    0.3~0.7초 랜덤. Steam CDN 은 정적 파일 서버라 rate limit 이 느슨함.

[다음 단계]
    06_opencv_features.py 에서 thumb.jpg + ss_0~ss_3.jpg 로
    게임당 최대 5장의 OpenCV 시각 피처 추출.
================================================================================
"""

import os, time, random, csv, requests, pandas as pd
from pathlib import Path

APPID_CSV   = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUT_DIR     = r"Real\04b steam thumbnails"
SUMMARY_CSV = os.path.join(OUT_DIR, "04b_thumbnails_summary.csv")
os.makedirs(OUT_DIR, exist_ok=True)

# User-Agent: 브라우저가 아닌 요청을 차단하는 CDN 대비
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DELAY_MIN, DELAY_MAX, MAX_RETRY = 0.3, 0.7, 3

df_ids = pd.read_csv(APPID_CSV, encoding='utf-8-sig')
appids = df_ids['AppID'].astype(str).tolist()
print(f"전체 AppID: {len(appids):,}개")

# done: {appid: row딕셔너리} - resume 용
done = {}
if os.path.exists(SUMMARY_CSV):
    with open(SUMMARY_CSV, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            done[row['appid']] = row
    print(f"이미 완료: {len(done):,}개  ->  재개 모드")

remaining = [a for a in appids if a not in done]
print(f"남은 작업: {len(remaining):,}개")

session = requests.Session()
session.headers.update(HEADERS)
results = list(done.values())


def download_thumb(appid):
    """
    appid 하나의 썸네일을 CDN 에서 다운로드.

    반환값:
        dict: appid, success(bool), file_path(str), reason(str)
    """
    url       = f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
    save_path = os.path.join(OUT_DIR, appid, "thumb.jpg")
    for attempt in range(1, MAX_RETRY + 1):
        resp = session.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 1000:
            # len > 1000: CDN 이 빈 응답을 200 으로 반환하는 경우 걸러냄
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            f = open(save_path, 'wb')
            f.write(resp.content)
            f.close()
            return {'appid': appid, 'success': True, 'file_path': save_path, 'reason': ''}
        if resp.status_code == 404:
            return {'appid': appid, 'success': False, 'file_path': '', 'reason': '404_not_found'}
        if resp.status_code == 429:
            wait = 10 * attempt
            print(f"  429 -> {wait}s 대기")
            time.sleep(wait)
            continue
        if attempt == MAX_RETRY:
            return {'appid': appid, 'success': False, 'file_path': '', 'reason': f'http_{resp.status_code}'}
        time.sleep(3 * attempt)
    return {'appid': appid, 'success': False, 'file_path': '', 'reason': 'max_retry_exceeded'}


# 초기 카운터: 기존 done 결과 기반
success = sum(1 for r in results if str(r.get('success')) == 'True')
fail    = len(results) - success
total   = len(remaining)

# append 모드: 기존 CSV 보존 + 새 결과만 추가
csv_file = open(SUMMARY_CSV, 'a', encoding='utf-8-sig', newline='')
writer   = csv.DictWriter(csv_file, fieldnames=['appid', 'success', 'file_path', 'reason'])
if len(done) == 0:
    writer.writeheader()

start_time = time.time()

for i, appid in enumerate(remaining, 1):
    result = download_thumb(appid)
    results.append(result)
    writer.writerow(result)
    csv_file.flush()  # 중단 시 버퍼 손실 방지

    if result['success']:
        success += 1
    else:
        fail += 1

    elapsed       = time.time() - start_time
    avg_sec       = elapsed / i
    remaining_sec = avg_sec * (total - i)
    eta_min       = int(remaining_sec // 60)
    eta_sec       = int(remaining_sec % 60)

    print(f"[{i:>5}/{total}] appid={appid:<8}  {'OK' if result['success'] else 'FAIL':4}  "
          f"성공:{success}  실패:{fail}  ETA {eta_min}m {eta_sec:02d}s")

    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

csv_file.close()
print(f"\n완료: 성공 {success:,} / 실패 {fail:,} / 전체 {len(results):,}")
