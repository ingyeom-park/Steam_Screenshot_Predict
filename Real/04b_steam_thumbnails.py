"""
04b_steam_thumbnails.py
Steam CDN에서 게임별 헤더 이미지(썸네일) 다운로드
URL: https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg
크기: 460x215 px
저장: Real/04b steam thumbnails/{appid}/thumb.jpg
출력: 04b_thumbnails_summary.csv
"""

import os, time, random, csv, requests, pandas as pd
from pathlib import Path

APPID_CSV   = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUT_DIR     = r"Real\04b steam thumbnails"
SUMMARY_CSV = os.path.join(OUT_DIR, "04b_thumbnails_summary.csv")
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
DELAY_MIN, DELAY_MAX, MAX_RETRY = 0.3, 0.7, 3

df_ids = pd.read_csv(APPID_CSV, encoding='utf-8-sig')
appids = df_ids['AppID'].astype(str).tolist()
print(f"전체 AppID: {len(appids):,}개")

done = {}
if os.path.exists(SUMMARY_CSV):
    with open(SUMMARY_CSV, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            done[row['appid']] = row
    print(f"이미 완료: {len(done):,}개  →  재개 모드")

remaining = [a for a in appids if a not in done]
print(f"남은 작업: {len(remaining):,}개")

session = requests.Session()
session.headers.update(HEADERS)
results = list(done.values())

def download_thumb(appid):
    url = f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
    save_path = os.path.join(OUT_DIR, appid, "thumb.jpg")
    for attempt in range(1, MAX_RETRY + 1):
        resp = session.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 1000:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            f = open(save_path, 'wb')
            f.write(resp.content)
            f.close()
            return {'appid': appid, 'success': True, 'file_path': save_path, 'reason': ''}
        if resp.status_code == 404:
            return {'appid': appid, 'success': False, 'file_path': '', 'reason': '404_not_found'}
        if resp.status_code == 429:
            wait = 10 * attempt
            print(f"  429 → {wait}s 대기")
            time.sleep(wait)
            continue
        if attempt == MAX_RETRY:
            return {'appid': appid, 'success': False, 'file_path': '', 'reason': f'http_{resp.status_code}'}
        time.sleep(3 * attempt)
    return {'appid': appid, 'success': False, 'file_path': '', 'reason': 'max_retry_exceeded'}

success = sum(1 for r in results if str(r.get('success')) == 'True')
fail    = len(results) - success
total   = len(remaining)

csv_file = open(SUMMARY_CSV, 'a', encoding='utf-8-sig', newline='')
writer   = csv.DictWriter(csv_file, fieldnames=['appid','success','file_path','reason'])
if len(done) == 0:
    writer.writeheader()

start_time = time.time()

for i, appid in enumerate(remaining, 1):
    result = download_thumb(appid)
    results.append(result)
    writer.writerow(result)
    csv_file.flush()

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

    

csv_file.close()
print(f"\n완료: 성공 {success:,} / 실패 {fail:,} / 전체 {len(results):,}")
