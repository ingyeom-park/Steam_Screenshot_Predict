import os, json, time, random, datetime
import pandas as pd
import requests

INPUT_CSV = "SteamDB_AppID,GameName_100.csv"
OUT_DIR = "data"
CC = "us"
LANG = "english"

df = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()

today = datetime.datetime.now().strftime("%Y%m%d")
raw_dir = f"{OUT_DIR}/raw_appdetails_{today}"
os.makedirs(raw_dir, exist_ok=True)
os.makedirs(f"{OUT_DIR}/derived", exist_ok=True)

session = requests.Session()
rows = []

for i, appid in enumerate(appids, 1):
    raw_path = f"{raw_dir}/{appid}.json"

    if os.path.exists(raw_path):
        payload = json.load(open(raw_path, encoding="utf-8"))
    else:
        payload = None
        for attempt in range(5):
            r = session.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": appid, "cc": CC, "l": LANG},
                timeout=20
            )
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt + random.random())
                continue
            if not r.text.strip().startswith("{"):
                time.sleep(2 ** attempt + random.random())
                continue
            payload = r.json()
            break

        if payload is None:
            json.dump({"appid": appid, "success": False}, open(raw_path, "w", encoding="utf-8"), ensure_ascii=False)
            rows.append({"snapshot_date": today, "appid": appid, "success": False})
            time.sleep(0.9 + random.random() * 0.6)
            continue

        json.dump(payload, open(raw_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    root = payload.get(str(appid), {})
    if not root.get("success"):
        rows.append({"snapshot_date": today, "appid": appid, "success": False})
        time.sleep(0.9 + random.random() * 0.6)
        continue

    d = root["data"]
    price = d.get("price_overview") or {}
    plat  = d.get("platforms") or {}
    rel   = d.get("release_date") or {}
    pcreq = d.get("pc_requirements") or {}

    rows.append({
        "appid":                appid,
        "type":                 d.get("type"),
        "name":                 d.get("name"),
        "is_free":              d.get("is_free"),
        "release_coming_soon":  rel.get("coming_soon"),
        "release_date_text":    rel.get("date"),
        "price_currency":       price.get("currency"),
        "price_initial":        price.get("initial"),
        "price_final":          price.get("final"),
        "price_discount_pct":   price.get("discount_percent"),
        "platform_windows":     plat.get("windows"),
        "platform_mac":         plat.get("mac"),
        "platform_linux":       plat.get("linux"),
        "categories":           "|".join(c["description"] for c in (d.get("categories") or []) if "description" in c),
        "genres":               "|".join(g["description"] for g in (d.get("genres") or []) if "description" in g),
        "supported_languages":  d.get("supported_languages"),
        "pc_minimum":           pcreq.get("minimum"),
        "pc_recommended":       pcreq.get("recommended"),
        "header_image":         d.get("header_image"),
        "screenshots_count":    len(d.get("screenshots") or []),
        "movies_count":         len(d.get("movies") or []),
    })

    time.sleep(0.9 + random.random() * 0.6)
    if i % 10 == 0:
        print(f"{i}/{len(appids)}")

out = f"{OUT_DIR}/derived/appdetails_flat_{today}.csv"
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
print("done ->", out)