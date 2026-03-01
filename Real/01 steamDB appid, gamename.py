import undetected_chromedriver as uc
from bs4 import BeautifulSoup as bs
import time
import pandas as pd

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
	game_rows = soup.select('#DataTables_Table_0 tbody tr')
	print(f"총 {len(game_rows)}개")
	
	data = []

	for i, row in enumerate(game_rows, 1):
		app_id = row.get('data-appid')
		name = row.select_one('td:nth-of-type(3) a')

		if app_id and name:
			data.append([app_id, name.text.strip()])
		print(f"{i} / {len(game_rows)}", end='\r')
	
	print(f"\n수집 완료: {len(data)}개")
	df = pd.DataFrame(data, columns=['AppID', 'GameName'])
	df.to_csv(r'Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv', index=False, encoding='utf-8-sig')
	driver.quit()