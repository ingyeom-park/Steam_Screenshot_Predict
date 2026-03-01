import os, json, time, random
import requests

RAW_DIR = r"(cozy)Steam Data\02_Steam_Appdetails_snapshot\02_Steam_Appdetails_snapshot_raw"
IMG_DIR = r"(cozy)Steam Data\03_Steam_Screenshot(4 each)"

os.makedirs(IMG_DIR, exist_ok=True)

session    = requests.Session()
json_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json")]

for idx, fname in enumerate(sorted(json_files, key=lambda f: int(f.removesuffix(".json"))), 1):
    appid = fname.removesuffix(".json")

    with open(f"{RAW_DIR}/{fname}", encoding="utf-8") as f:
        payload = json.load(f)

    app = payload.get(appid, {})
    if not app.get("success"):
        print(f"[{idx}] {appid} skip (success=False)")
        continue

    screenshots = app["data"].get("screenshots") or []
    urls        = [s["path_full"] for s in screenshots[:4] if "path_full" in s]

    if not urls:
        print(f"[{idx}] {appid} skip (no screenshots)")
        continue

    game_dir = f"{IMG_DIR}/{appid}"
    os.makedirs(game_dir, exist_ok=True)

    for i, url in enumerate(urls):
        out_path = f"{game_dir}/ss_{i}.jpg"
        if os.path.exists(out_path):
            continue

        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"  [{appid}] ss_{i} failed: HTTP {resp.status_code}")
            continue

        with open(out_path, "wb") as f:
            f.write(resp.content)
        time.sleep(0.3 + random.random() * 0.3)

    print(f"[{idx}/{len(json_files)}] {appid} done ({len(urls)}장)")