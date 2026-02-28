import os, json, time, random
import requests

RAW_DIR = "Steam_Appdetails_snapshot_100/raw_appdetails_20260228"
IMG_DIR = "Steam_Appdetails_snapshot_100/images"

os.makedirs(IMG_DIR, exist_ok=True)

session = requests.Session()
json_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".json")]

for idx, fname in enumerate(sorted(json_files, key=lambda x: int(x.replace(".json", ""))), 1):
    appid = fname.replace(".json", "")
    payload = json.load(open(f"{RAW_DIR}/{fname}", encoding="utf-8"))

    root = payload.get(appid, {})
    if not root.get("success"):
        print(f"[{idx}] {appid} skip (success=False)")
        continue

    screenshots = root["data"].get("screenshots") or []
    urls = [s["path_full"] for s in screenshots[:4] if "path_full" in s]

    if not urls:
        print(f"[{idx}] {appid} skip (no screenshots)")
        continue

    game_dir = f"{IMG_DIR}/{appid}"
    os.makedirs(game_dir, exist_ok=True)

    for i, url in enumerate(urls):
        out_path = f"{game_dir}/ss_{i}.jpg"
        if os.path.exists(out_path):
            continue

        r = session.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  [{appid}] ss_{i} failed: HTTP {r.status_code}")
            continue

        open(out_path, "wb").write(r.content)
        time.sleep(0.3 + random.random() * 0.3)

    print(f"[{idx}/{len(json_files)}] {appid} done ({len(urls)}장)")