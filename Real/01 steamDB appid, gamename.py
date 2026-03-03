"""
01_steamDB_appid_gamename.py
================================================================================
[목적]
    SteamDB에서 분석 대상 게임의 AppID와 게임명을 수집한다.
    이 목록이 이후 모든 스크립트(02~06)의 처리 대상 기준이 된다.

[수집 URL 및 필터 조건]
    URL: https://steamdb.info/tag/492/
        tag/492 = "Games" 카테고리 (DLC, OST, 소프트웨어 등 제외)
    필터 파라미터:
        category=-666       : 게임만 (앱 타입 필터)
        cc=us               : 미국 기준 가격
        displayOnly=Game    : 게임만 표시
        max_release=2025-03-01 : 2025년 3월 이전 출시 (런치 후 데이터 안정화 목적)
        min_price=1         : 무료 게임 제외 (가격 정보 없는 게임 제외)
        min_reviews=50      : 리뷰 50개 미만 제외 (Y변수 신뢰도 확보)
        sort=followers_asc  : 팔로워 오름차순 (수집 순서 일관성 유지)

    Early Access 게임은 URL 필터로 직접 제외하지 않았으나,
    02_steam_appdetails 에서 'early_access' 플래그로 추가 필터링함.

[출력 파일]
    Real/01 steamDB appid, gamename/01 steamDB appid, gamename.csv
        컬럼: AppID, GameName
        총 수집 기준: 10,019개 (2025년 3월 수집 기준)

[기술적 선택 사항]
    - undetected_chromedriver 사용 이유:
        SteamDB는 일반 requests/selenium 접근 시 봇 탐지(Cloudflare)로 차단됨.
        uc.Chrome은 봇 탐지 우회를 위한 패치된 ChromeDriver.
    - version_main=145:
        설치된 Chrome 버전과 ChromeDriver 버전 불일치 버그 발생으로
        Chrome 버전을 직접 명시해 해결.
    - time.sleep(20):
        2초로 설정 시 봇 탐지에 걸린 이력 있음 -> 20초로 늘려 해결.
        페이지가 완전히 로드되고 Cloudflare 검사가 통과될 때까지 대기.
    - status_code 확인:
        window.performance.getEntries()[0].responseStatus 로 실제 HTTP 응답 코드 확인.
        200이 아니면 봇 탐지 또는 오류로 판단하고 즉시 종료.

[다음 단계]
    이 파일에서 생성된 CSV의 AppID 컬럼을
    02_steam_appdetails_snapshot.py 에서 순회하며 Steam API 호출에 사용.
================================================================================
"""

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
	df.to_csv(r'Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv', index=False, encoding='utf-8-sig')
	driver.quit()