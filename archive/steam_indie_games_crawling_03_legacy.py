"""
steam_indie_games_crawling_03_legacy.py

과거 실험용 수집 스크립트입니다.
현재 파이프라인의 기준 파일은 아니며, 참고용으로만 보관합니다.
ITAD API 키는 개인 local 설정에 맞게 직접 입력해야 합니다.
"""

import pandas as pd
import requests
import time
import os
import re
from datetime import datetime

# Is There Any Deal의 약자입니다. (참고)
# 본인 API Key를 별도로 입력해야 합니다.
ITAD_API_KEY = ""

HEADERS = {
    # User Agent는 본인의 것을 넣을 것을 권장함
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
}
INPUT_FILENAME = "Steam_Indie_Games(Basic List).csv"

# 저장할 폴더 따로 지정했습니다.
SAVE_FOLDER = "collected_data"
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

# 에러 발생 시 로그 수집용 txt 파일입니다.
ERROR_LOG_FILE = "failure_log.txt"

# API 요청 및 실패 시 재시도하는 함수
def smart_request(url, params=None, headers=None):
    max_retries = 5 # 데이터를 찾을 수 없을 때의 최대 재시도 횟수
    base_wait = 10 # 재시도 사이의 대기시간
    
    for i in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200: return response.json() # 200은 정상임
            elif response.status_code == 429: # 429: Too many Requests!
                time.sleep(base_wait * (i + 1)) # Linear Backoff만큼 대기.
                continue
            else:
                return None 
        except requests.exceptions.RequestException:
            time.sleep(3)
            continue
    return None

# 진행상황을 시:분:초 의 형식으로 print하는 함수
def format_hms(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

# 실패 시, 어떤 게임에서 어떤 이유로 실패했는지 에러 원인을 작성하는 함수
def log_failure(appid, name, reason):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} | {appid} | {name} | {reason}\n")

# appid를 입력, ITAD api로부터 36글자의 UUID로 반환해오는 함수
def get_itad_uuid_by_appid(steam_appid):
    url = "https://api.isthereanydeal.com/games/lookup/v1"
    params = {'key': ITAD_API_KEY, 'appid': steam_appid}
    data = smart_request(url, params=params, headers=HEADERS)
    if data and data.get('found') and 'game' in data:
        return data['game']['id'], data['game']['title']
    return None, None

# 만약 appid가 없다면(결측), 게임이름을 입력해 UUID를 반환해오는 함수
def search_game_id_by_title(game_title):
    url = "https://api.isthereanydeal.com/games/search/v1"
    params = {"key": ITAD_API_KEY, "title": game_title, "results": 5}
    results = smart_request(url, params=params, headers=HEADERS)
    if results:
        for item in results:
            if item.get("type") == "game": # DLC, 사운드트랙, 소프트웨어 제외
                return item["id"], item["title"]
    return None, None

# UUID로 AppID 역추적 (이름 검색 시 필요)
def get_appid_by_uuid(uuid):
    url = "https://api.isthereanydeal.com/games/info/v2"
    params = {"key": ITAD_API_KEY, "id": uuid}
    data = smart_request(url, params=params, headers=HEADERS)
    if data:
        return data.get("appid")
    return None

# 각종 데이터 수집 (동접자, 가격, 태그 등)
def fetch_data(uuid, appid):
    # 동접자
    url_stats = "https://isthereanydeal.com/api/game/stats/"
    stats = smart_request(url_stats, params={'country': 'US', 'currency': 'USD', 'gid': uuid}, headers=HEADERS)
    players_data = stats['players']['data'] if stats and 'players' in stats and 'data' in stats['players'] else []

    # 가격
    url_price = "https://api.isthereanydeal.com/games/history/v2"
    price_data = smart_request(url_price, params={"key": ITAD_API_KEY, "id": uuid, "country": "US", "shops": "61", "since": "2000-01-01T00:00:00+00:00"}, headers=HEADERS)
    
    # 태그/리뷰 (steamspy.com에서 가져오기, isthereanydeal.com엔 없어서)
    url_spy = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    spy_data = smart_request(url_spy, headers=HEADERS)
    
    return players_data, price_data, spy_data

# 게임 타입 판별 (싱글/멀티/혼합)
def determine_game_type(tags_str):
    if not isinstance(tags_str, str): return "single"
    tags = tags_str.lower()
    is_single = 'singleplayer' in tags or 'single-player' in tags
    multi_keywords = ['multiplayer', 'co-op', 'mmo', 'pvp', 'team-based', 'online', 'shared/split screen', 'esports']
    is_multi = any(k in tags for k in multi_keywords)
    
    if is_single and is_multi: return "mixed"
    elif is_multi: return "multi"
    else: return "single"

# 메인 코드 루프
def main():
    # CSV 로드
    if not os.path.exists(INPUT_FILENAME):
        print(f"오류: '{INPUT_FILENAME}' 파일을 찾을 수 없음.")
        return
    
    df_games = pd.read_csv(INPUT_FILENAME)
    total_games = len(df_games)
    print(f"목록 로드 성공: 총 {total_games}개")
    
    start_total_time = time.time()

    for index, row in df_games.iterrows():
        iter_start = time.time()
        
        # 1. 기초 정보 파싱
        raw_appid = row.get('steam_appid') # NaN일 수 있음
        raw_name = str(row.get('name', 'Unknown'))
        
        steam_appid = None
        uuid = None
        title = raw_name
        is_success = False
        fail_reason = ""
        
        try:
            # 2. ID 확보 단계 (CSV -> Search)
            # (1) CSV에 유효한 AppID가 있는 경우
            if pd.notna(raw_appid) and str(raw_appid).replace('.0','').isdigit() and int(raw_appid) > 0:
                steam_appid = int(raw_appid)
                uuid, fetched_title = get_itad_uuid_by_appid(steam_appid)
                if fetched_title: title = fetched_title
            
            # (2) CSV에 없거나 조회가 안 된 경우 -> 이름 검색 시도
            if not uuid:
                uuid, fetched_title = search_game_id_by_title(raw_name)
                if uuid:
                    if fetched_title: title = fetched_title
                    # UUID는 찾았는데 AppID를 모르는 상태 -> 역추적
                    steam_appid = get_appid_by_uuid(uuid)
            
            # ID 확보 실패 시 중단
            if not uuid:
                fail_reason = "UUID 조회 불가 (검색 실패)"
                raise ValueError(fail_reason)
            if not steam_appid:
                # AppID가 없으면 파일명 생성 및 SteamSpy 조회가 불가능하므로 중요
                fail_reason = "Steam AppID 확인 불가" 
                raise ValueError(fail_reason)

            # 3. 파일 저장 경로 확인 (이어하기)
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(' ', '_')
            filename = f"{steam_appid}_{safe_title}_SteamData.csv"
            save_path = os.path.join(SAVE_FOLDER, filename)
            
            if os.path.exists(save_path):
                # 이미 존재하면 스킵 (성공으로 간주하거나 별도 표시)
                fail_reason = "파일 이미 존재 (Skip)"
                # 로직 상 성공으로 치고 넘어갈지, 스킵 로그를 띄울지 선택. 여기선 성공 처리 후 스킵.
                is_success = True 
                # 데이터 수집 생략하고 바로 결과 출력으로 이동
            
            else:
                # 4. 데이터 수집
                players_raw, price_raw, spy_data = fetch_data(uuid, steam_appid)
                
                if not players_raw:
                    fail_reason = "동접자 데이터 없음"
                    raise ValueError(fail_reason)

                # 5. 데이터 가공 (Merge & Fill)
                # (1) Players
                p_list = [{"Date": pd.to_datetime(datetime.fromtimestamp(p[0]/1000).date()), "Players": p[1]} for p in players_raw]
                df_daily = pd.DataFrame(p_list).groupby("Date")["Players"].mean().astype(int).reset_index().set_index("Date")
                
                # (2) Price
                pr_list = []
                if price_raw:
                    for p in price_raw:
                        deal = p.get("deal", {})
                        if not deal: continue
                        ts = p.get("timestamp")
                        if ts:
                            pr_list.append({
                                "Date": pd.to_datetime(datetime.fromisoformat(ts).date()),
                                "Price": deal.get("price", {}).get("amount"),
                                "Regular_Price": deal.get("regular", {}).get("amount"),
                                "Discount_Pct": deal.get("cut"),
                                "Currency": deal.get("price", {}).get("currency")
                            })
                
                # (3) Merge
                if pr_list:
                    df_price = pd.DataFrame(pr_list).drop_duplicates(subset=["Date"], keep="last").set_index("Date")
                    df_final = df_daily.join(df_price, how="left")
                    cols_fill = ["Price", "Regular_Price", "Currency"]
                    df_final[cols_fill] = df_final[cols_fill].ffill().bfill()
                    df_final["Discount_Pct"] = df_final["Discount_Pct"].ffill().fillna(0)
                else:
                    df_final = df_daily
                    for c in ["Price", "Regular_Price", "Discount_Pct", "Currency"]: df_final[c] = None

                # (4) Meta Info & Type
                if not spy_data: spy_data = {}
                tags_str = ", ".join(sorted(spy_data.get("tags", {}), key=spy_data.get("tags", {}).get, reverse=True)) if spy_data.get("tags") else ""
                
                # 리뷰 라벨 계산
                pos = spy_data.get("positive", 0)
                neg = spy_data.get("negative", 0)
                total = pos + neg
                ratio = (pos/total*100) if total > 0 else 0
                if total < 50: label = "Need more reviews"
                elif ratio >= 95 and total >= 500: label = "Overwhelmingly Positive"
                elif ratio >= 80: label = "Very Positive"
                elif ratio >= 70: label = "Mostly Positive"
                elif ratio >= 40: label = "Mixed"
                elif ratio >= 20: label = "Mostly Negative"
                else: label = "Overwhelmingly Negative"

                df_final = df_final.reset_index()
                df_final["AppID"] = steam_appid
                df_final["Game_Title"] = title
                df_final["Type"] = determine_game_type(tags_str)
                df_final["Review_Label"] = label
                df_final["Review_Ratio(%)"] = round(ratio, 2)
                df_final["Total_Reviews"] = total
                df_final["Positives"] = pos
                df_final["Negatives"] = neg
                df_final["All_Tags"] = tags_str
                
                # 컬럼 순서 정렬 [1안 적용 완료]
                target_cols = [
                    "AppID", "Game_Title", "Date",        # 식별자
                    "Players", "Price", "Discount_Pct",   # 핵심 지표
                    "Regular_Price", "Currency",          # 보조 지표
                    "Type", "Review_Label", "Review_Ratio(%)", 
                    "Total_Reviews", "Positives", "Negatives", "All_Tags" # 게임 속성
                ]
                final_cols = [c for c in target_cols if c in df_final.columns]
                df_final = df_final[final_cols]
                
                # 저장
                df_final.to_csv(save_path, index=False, encoding='utf-8-sig')
                is_success = True

        except Exception as e:
            fail_reason = str(e)
            is_success = False
        
        # 6. 결과 출력 및 로그
        iter_end = time.time()
        duration = format_hms(iter_end - iter_start)
        total_elapsed = format_hms(iter_end - start_total_time)
        
        display_appid = steam_appid if steam_appid else (raw_appid if pd.notna(raw_appid) else "Unknown")
        
        if is_success:
            if fail_reason == "파일 이미 존재 (Skip)":
                print(f"[{index+1}/{total_games}] 스킵 ⏭️ | {duration} | {total_elapsed} | {title}")
            else:
                print(f"[{index+1}/{total_games}] 성공 ✅ | {duration} | {total_elapsed} | {title}")
        else:
            print(f"[{index+1}/{total_games}] 실패 ❌ | {duration} | {total_elapsed} | {raw_name} ({fail_reason})")
            log_failure(display_appid, raw_name, fail_reason)

    print(f"\n모든 작업이 완료되었습니다. 소요시간 : {total_elapsed}")

if __name__ == "__main__":
    main()
