import os, json, time, random
import requests
from datetime import datetime, timedelta

RAW_DIR = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_snapshot_raw"
IMG_DIR = r"Real\04 steam screenshots"

os.makedirs(IMG_DIR, exist_ok=True)

session    = requests.Session()
json_files = sorted(
    [f for f in os.listdir(RAW_DIR) if f.endswith(".json")],
    key=lambda f: int(f.removesuffix(".json"))
)
total = len(json_files)

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

    app = payload.get(appid, {})
    if not app.get("success"):
        print(f"[{skipped+i}/{total}] {appid} skip (success=False)")
        done_count += 1
        continue

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
