import os, json, time, random
import pandas as pd
import requests

INPUT_CSV = r"(cozy)Steam Data\01_SteamDB_AppID,GameName\01_SteamDB_AppID,GameName.csv"
OUT_DIR   = r"(cozy)Steam Data\02_Steam_Appdetails_snapshot"
CC        = "us"
LANG      = "english"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()

raw_dir = f"{OUT_DIR}\\02_Steam_Appdetails_snapshot_raw"
os.makedirs(raw_dir, exist_ok=True)

session = requests.Session()
rows    = []

for i, appid in enumerate(appids, 1):
    raw_path = f"{raw_dir}\\{appid}.json"

    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = None
        for attempt in range(5):
            resp = session.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": appid, "cc": CC, "l": LANG},
                timeout=20
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt + random.random())
                continue
            if not resp.text.strip().startswith("{"):
                time.sleep(2 ** attempt + random.random())
                continue
            payload = resp.json()
            break

        if payload is None:
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump({"appid": appid, "success": False}, f, ensure_ascii=False)
            rows.append({"appid": appid, "success": False})
            time.sleep(0.9 + random.random() * 0.6)
            continue

        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    app = payload.get(str(appid), {})
    if not app.get("success"):
        rows.append({"appid": appid, "success": False})
        time.sleep(0.9 + random.random() * 0.6)
        continue

    data  = app["data"]
    price = data.get("price_overview") or {}
    plat  = data.get("platforms")      or {}
    rel   = data.get("release_date")   or {}
    pcreq = data.get("pc_requirements") or {}

    rows.append({
        "appid":                appid,
        "type":                 data.get("type"),
        "name":                 data.get("name"),
        "is_free":              data.get("is_free"),
        "release_coming_soon":  rel.get("coming_soon"),
        "release_date_text":    rel.get("date"),
        "price_currency":       price.get("currency"),
        "price_initial":        price.get("initial"),
        "price_final":          price.get("final"),
        "price_discount_pct":   price.get("discount_percent"),
        "platform_windows":     plat.get("windows"),
        "platform_mac":         plat.get("mac"),
        "platform_linux":       plat.get("linux"),
        "categories":           "|".join(c["description"] for c in (data.get("categories") or []) if "description" in c),
        "genres":               "|".join(g["description"] for g in (data.get("genres")     or []) if "description" in g),
        "supported_languages":  data.get("supported_languages"),
        "pc_minimum":           pcreq.get("minimum"),
        "pc_recommended":       pcreq.get("recommended"),
        "header_image":         data.get("header_image"),
        "screenshots_count":    len(data.get("screenshots") or []),
        "movies_count":         len(data.get("movies")      or []),
    })

    time.sleep(0.9 + random.random() * 0.6)
    if i % 10 == 0:
        print(f"{i}/{len(appids)}")

out = f"{OUT_DIR}\\02_Steam_Appdetails_summary.csv"
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
print("done ->", out)