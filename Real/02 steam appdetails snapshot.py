import os, json, time, random
import pandas as pd
import requests
from datetime import datetime, timedelta

INPUT_CSV = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
OUT_DIR   = r"Real\02 steam appdetails snapshot"
CC        = "us"
LANG      = "english"

df     = pd.read_csv(INPUT_CSV)
appids = df["AppID"].dropna().astype(int).tolist()
total  = len(appids)

raw_dir = f"{OUT_DIR}\\02_Steam_Appdetails_snapshot_raw"
os.makedirs(raw_dir, exist_ok=True)

already_done = set(
    int(f.replace(".json", ""))
    for f in os.listdir(raw_dir)
    if f.endswith(".json")
)
remaining = [a for a in appids if a not in already_done]
skipped   = total - len(remaining)

print(f"전체 {total}개 | 이미 완료 {skipped}개 | 남은 {len(remaining)}개")

session    = requests.Session()
rows       = []
start_time = time.time()
done_count = 0

for i, appid in enumerate(remaining, 1):
    raw_path = f"{raw_dir}\\{appid}.json"

    payload = None
    for attempt in range(5):
        resp = session.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "cc": CC, "l": LANG},
            timeout=20
        )
        if resp.status_code == 429:
            wait = 120 * (attempt + 1)
            print(f"\n  [{appid}] 429 차단 -> {wait}초 대기 후 재시도 ({attempt+1}/5)")
            time.sleep(wait)
            continue
        if resp.status_code in (500, 502, 503, 504):
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
        done_count += 1
        print(f"{skipped+i}/{total} | 남은 {len(remaining)-i}개 | {appid} | FAILED (5회 모두 실패)")
        time.sleep(1)
        continue

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    app = payload.get(str(appid), {})
    if not app.get("success"):
        rows.append({"appid": appid, "success": False})
        done_count += 1
        print(f"{skipped+i}/{total} | 남은 {len(remaining)-i}개 | {appid} | NO DATA")
        time.sleep(1)
        continue

    data  = app["data"]
    price = data.get("price_overview") or {}
    plat  = data.get("platforms")      or {}
    rel   = data.get("release_date")   or {}
    pcreq = data.get("pc_requirements") or {}
    ach   = data.get("achievements")   or {}
    desc  = data.get("content_descriptors") or {}

    short_desc    = data.get("short_description") or ""
    detailed_desc = data.get("detailed_description") or ""
    developers    = data.get("developers") or []
    publishers    = data.get("publishers") or []

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

    done_count += 1
    elapsed  = time.time() - start_time
    avg_per  = elapsed / done_count
    left_n   = len(remaining) - i
    eta_sec  = avg_per * left_n
    eta_time = datetime.now() + timedelta(seconds=eta_sec)

    print(
        f"{skipped+i}/{total} | "
        f"남은 {left_n}개 | "
        f"경과 {str(timedelta(seconds=int(elapsed)))} | "
        f"완료예상 {eta_time.strftime('%H:%M:%S')} | "
        f"{appid} | {data.get('name')}"
    )

    time.sleep(1 + random.random() * 0.5)

out = f"{OUT_DIR}\\02_Steam_Appdetails_summary.csv"
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
print(f"\ndone -> {out}")
print(f"총 소요시간: {str(timedelta(seconds=int(time.time() - start_time)))}")