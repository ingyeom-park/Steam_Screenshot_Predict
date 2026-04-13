"""
01_steamdb_app_list.py
================================================================================
[목적]
    SteamDB에서 분석 대상 게임의 AppID와 게임명을 수집한다.
    이 CSV가 이후 단계의 기준 입력이 된다.

[출력 파일]
    data/raw/01_steamdb_app_list/01_steamdb_app_list.csv

[비고]
    - 수집 로직은 기존과 동일하다.
    - 경로만 새 프로젝트 구조에 맞게 정리했다.
================================================================================
"""

import time

import pandas as pd
import undetected_chromedriver as uc
from bs4 import BeautifulSoup as bs

from project_paths import APP_LIST_CSV, APP_LIST_DIR


APP_LIST_DIR.mkdir(parents=True, exist_ok=True)

# 버전 불일치 버그로, version_main 기입해주었음.
driver = uc.Chrome(version_main=145)

target_url = "https://steamdb.info/tag/492/?category=-666&cc=us&displayOnly=Game&max_release=2025-03-01&min_price=1&min_reviews=50&sort=followers_asc"
driver.get(target_url)

# 2초 했다가 봇탐지 걸렸음
time.sleep(20) 

status_code = driver.execute_script("return window.performance.getEntries()[0].responseStatus")

# 봇탐지 회피 및 웹사이트가 정상임을 확인한 후 크롤링 시작
if status_code != 200:
	print(f"status code: {status_code}")
	driver.quit()

else:
	soup = bs(driver.page_source, "html.parser")
	# DataTables_Table_0: SteamDB 게임 목록 테이블의 고정 ID
	# tbody tr: 테이블 본문의 각 게임 행
	game_rows = soup.select('#DataTables_Table_0 tbody tr')
	print(f"총 {len(game_rows)}개")
	
	data = []

	for i, row in enumerate(game_rows, 1):
		# data-appid: 각 행의 HTML 속성으로 AppID가 직접 포함되어 있음
		app_id = row.get('data-appid')
		# td:nth-of-type(3): 테이블 3번째 열이 게임명 컬럼
		name = row.select_one('td:nth-of-type(3) a')

		if app_id and name:
			data.append([app_id, name.text.strip()])
		print(f"{i} / {len(game_rows)}", end='\r')
	
		print(f"\n수집 완료: {len(data)}개")
		df = pd.DataFrame(data, columns=['AppID', 'GameName'])
		df.to_csv(APP_LIST_CSV, index=False, encoding='utf-8-sig')
		driver.quit()
