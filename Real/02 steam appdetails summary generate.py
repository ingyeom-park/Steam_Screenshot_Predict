import os, json
import pandas as pd

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
RAW_DIR   = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_snapshot_raw"
OUT_CSV   = r"Real\02 steam appdetails snapshot\02_Steam_Appdetails_summary.csv"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

rows = []

for i, appid in enumerate(appids, 1):
    raw_path = os.path.join(RAW_DIR, f"{appid}.json")

    if not os.path.exists(raw_path):
        print(f"{i}/{total} | {appid} | JSON 없음 (스킵)")
        continue

    with open(raw_path, encoding="utf-8") as f:
        payload = json.load(f)

    app = payload.get(str(appid), {})
    if not app.get("success"):
        rows.append({"appid": appid, "success": False})
        print(f"{i}/{total} | {appid} | NO DATA")
        continue

    data  = app["data"]
    price = data.get("price_overview")      or {}
    plat  = data.get("platforms")           or {}
    rel   = data.get("release_date")        or {}
    pcreq = data.get("pc_requirements")     or {}
    ach   = data.get("achievements")        or {}
    desc  = data.get("content_descriptors") or {}
    meta  = data.get("metacritic")          or {}
    rat   = data.get("ratings")             or {}
    esrb  = rat.get("esrb")                 or {}

    short_desc    = data.get("short_description")    or ""
    detailed_desc = data.get("detailed_description") or ""
    developers    = data.get("developers") or []
    publishers    = data.get("publishers") or []
    demos         = data.get("demos")      or []

    rows.append({
        "appid":                  appid,
        "success":                True,
        "type":                   data.get("type"),
        "name":                   data.get("name"),
        "required_age":           data.get("required_age"),
        "is_free":                data.get("is_free"),
        "release_coming_soon":    rel.get("coming_soon"),
        "release_date_text":      rel.get("date"),
        "price_currency":         price.get("currency"),
        "price_initial":          price.get("initial"),
        "price_final":            price.get("final"),
        "price_discount_pct":     price.get("discount_percent"),
        "platform_windows":       plat.get("windows"),
        "platform_mac":           plat.get("mac"),
        "platform_linux":         plat.get("linux"),
        "categories":             "|".join(c["description"] for c in (data.get("categories") or []) if "description" in c),
        "genres":                 "|".join(g["description"] for g in (data.get("genres")     or []) if "description" in g),
        "supported_languages":    data.get("supported_languages"),
        "developers":             "|".join(developers),
        "publishers":             "|".join(publishers),
        "achievements_total":     ach.get("total"),
        "recommendations_total":  (data.get("recommendations") or {}).get("total"),
        "has_website":            1 if data.get("website") else 0,
        "has_demo":               1 if demos else 0,
        "metacritic_score":       meta.get("score"),
        "esrb_rating":            esrb.get("rating"),
        "short_desc_len":         len(short_desc),
        "detailed_desc_len":      len(detailed_desc),
        "short_description":      short_desc,
        "detailed_description":   detailed_desc,
        "pc_minimum":             pcreq.get("minimum"),
        "pc_recommended":         pcreq.get("recommended"),
        "content_descriptor_ids": "|".join(str(x) for x in (desc.get("ids") or [])),
        "header_image":           data.get("header_image"),
        "screenshots_count":      len(data.get("screenshots") or []),
        "movies_count":           len(data.get("movies")      or []),
    })

    print(f"{i}/{total} | {appid} | {data.get('name')}")

pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\ndone -> {OUT_CSV}")
print(f"총 {len(rows)}개 저장")