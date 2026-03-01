"""
SteamDB 리뷰 추이 데이터 수집 스크립트
======================================
appdetails CSV에서 appid 목록을 읽고,
SteamDB API로 누적 긍정/부정 리뷰 그래프 데이터를 가져와
일자별 CSV로 저장합니다.

사용법:
  1. 아래 COOKIE, USER_AGENT 값을 본인 것으로 교체
  2. INPUT_CSV 경로를 appdetails CSV 경로로 지정
  3. python fetch_steamdb_reviews.py

출력:
  - steamdb_reviews_daily.csv  (일자별 누적 + 파생지표)
"""

import csv
import json
import time
import datetime
import requests
from pathlib import Path

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
INPUT_CSV = r"(cozy)Steam Data\01_SteamDB_AppID,GameName\01_SteamDB_AppID,GameName.csv" # appid 열이 있는 CSV
OUTPUT_CSV = r"(cozy)Steam Data\05_SteamDB_Review(accumulate)\05_SteamDB_Review(accumulate).csv"

COOKIE = (
	"__Host-cc=us; "
	"__Host-steamdb=9213941-5c75f9bf2cdb2c5d3b5f5f151140b27c5ba8936b; "
	"cf_clearance=9CwIeSZcym.5cPmQqgcyolrJmGhQnfk0IKNh2.OoUX4-1772299523-1.2.1.1-"
	"tofsRApoZVojqRGIMAUpwr93ZVMniEieqOZbeb3s8QMa.AUbQTPkIX2OHEYFkVAORWiqNjcGDgxsH"
	".falB.0RZS8ukL4SX5fgXPpjZFtwExcSq.pK3_J_ot5uDLH3zxlmmNvKKCvLzryHjq6zOmQmUcMso"
	"RrAyIKn8jo6_QeuqqsRbnZvMT2EMhjxZaku1.litJnkRkkDnAExMqB6ABD4REgElKBXY0rzPU.HzFP"
	"_OWcGrK7EO5VCSQXwzntBk2R"
)

USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
	"AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/145.0.0.0 Safari/537.36"
)

API_URL = "https://steamdb.info/api/GetGraphReviewsLoggedIn/"
REQUEST_DELAY = 1.5  # 초 — 429 방지용, 필요시 조절

# ──────────────────────────────────────────────
# 1) appid 목록 로드
# ──────────────────────────────────────────────
def load_appids(csv_path: str) -> list[dict]:
	"""appid와 name을 읽어온다."""
	rows = []
	with open(csv_path, "r", encoding="utf-8-sig") as f:
		reader = csv.DictReader(f)
		for r in reader:
			rows.append({"appid": r["appid"].strip(), "name": r["name"].strip()})
	return rows


# ──────────────────────────────────────────────
# 2) API 호출
# ──────────────────────────────────────────────
def fetch_reviews(appid: str, session: requests.Session) -> dict | None:
	"""
	SteamDB 리뷰 그래프 API를 호출해 JSON을 반환.
	실패 시 None.
	"""
	headers = {
		"accept": "application/json",
		"accept-encoding": "gzip, deflate",
		"accept-language": "ko-KR,ko;q=0.8",
		"cookie": COOKIE,
		"referer": f"https://steamdb.info/app/{appid}/charts/",
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
	try:
		resp = session.get(API_URL, params={"appid": appid}, headers=headers, timeout=30)
		if resp.status_code == 429:
			print(f"  [429] Rate-limited on appid {appid}. 30초 대기 후 재시도...")
			time.sleep(30)
			resp = session.get(API_URL, params={"appid": appid}, headers=headers, timeout=30)
		if resp.status_code != 200:
			print(f"  [HTTP {resp.status_code}] appid={appid}")
			return None
		data = resp.json()
		if not data.get("success"):
			print(f"  [API fail] appid={appid}: {data}")
			return None
		return data
	except Exception as e:
		print(f"  [ERROR] appid={appid}: {e}")
		return None


# ──────────────────────────────────────────────
# 3) JSON → 행 리스트 변환
# ──────────────────────────────────────────────
def parse_review_data(appid: str, name: str, data: dict) -> list[dict]:
	"""
	API 응답을 일자별 행으로 변환.

	API 응답 구조:
	  data.start    : UNIX timestamp (첫 데이터 시점)
	  data.step     : 초 단위 간격 (보통 86400 = 1일)
	  data.values_p : 누적 긍정 리뷰 배열
	  data.values_n : 누적 부정 리뷰 배열
	"""
	inner = data["data"]
	start = inner["start"]
	step = inner["step"]
	values_p = inner["values_p"]
	values_n = inner["values_n"]

	rows = []
	length = min(len(values_p), len(values_n))
	for i in range(length):
		ts = start + step * i
		dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")

		cum_p = values_p[i]
		cum_n = values_n[i]
		cum_total = cum_p + cum_n

		# 일별 증가량 (첫 날은 그 자체가 증가량)
		if i == 0:
			delta_p = cum_p
			delta_n = cum_n
		else:
			delta_p = cum_p - values_p[i - 1]
			delta_n = cum_n - values_n[i - 1]
		delta_total = delta_p + delta_n

		# 긍정 비율
		ratio_p = round(cum_p / cum_total, 6) if cum_total > 0 else None

		rows.append({
			"appid": appid,
			"name": name,
			"date": dt,
			"cum_positive": cum_p,
			"cum_negative": cum_n,
			"cum_total": cum_total,
			"daily_positive": delta_p,
			"daily_negative": delta_n,
			"daily_total": delta_total,
			"positive_ratio": ratio_p,
		})
	return rows


# ──────────────────────────────────────────────
# 4) 메인
# ──────────────────────────────────────────────
def main():
	apps = load_appids(INPUT_CSV)
	print(f"[INFO] {len(apps)}개 앱 로드 완료.")

	all_rows: list[dict] = []
	session = requests.Session()

	for idx, app in enumerate(apps, 1):
		appid, name = app["appid"], app["name"]
		print(f"({idx}/{len(apps)}) appid={appid}  {name}")

		data = fetch_reviews(appid, session)
		if data is None:
			continue

		rows = parse_review_data(appid, name, data)
		all_rows.extend(rows)
		print(f"  → {len(rows)}일치 데이터 수집")

		if idx < len(apps):
			time.sleep(REQUEST_DELAY)

	# CSV 저장
	if not all_rows:
		print("[WARN] 수집된 데이터가 없습니다.")
		return

	fieldnames = [
		"appid", "name", "date",
		"cum_positive", "cum_negative", "cum_total",
		"daily_positive", "daily_negative", "daily_total",
		"positive_ratio",
	]
	
	import os
	os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
	
	with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		writer.writerows(all_rows)

	print(f"\n[DONE] {len(all_rows)}행 → {OUTPUT_CSV} 저장 완료.")


if __name__ == "__main__":
	main()