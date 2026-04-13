"""
00_project_brief.py
================================================================================
[안내]
    이 파일은 예전 위치에 남겨 둔 참고용 문서다.
    현재 기준 브리프는 docs/project_brief.md 이다.
    새 구조는 pipeline/, docs/, data/, archive/ 를 기준으로 본다.

[새 Claude 에게]
    이 파일을 가장 먼저 읽어라.
    이 프로젝트의 목적, 현재까지 완료된 작업, 미결정 사항, 다음 단계가
    모두 여기에 정리되어 있다.
    첨부된 01~06 파이썬 파일과 논문 PDF 는 이 기획서를 읽은 후에 참조하라.
================================================================================

================================================================================
1. 프로젝트 목표
================================================================================

Steam 게임의 출시 초기 성공 여부를 예측하는 ML 모델을 만든다.

핵심 제약:
    - 런치 시점에 스토어 페이지에서 얻을 수 있는 정보만 X 피처로 사용
    - 출시 후 리뷰 수를 Y 변수로 사용
    - 논문 Trneny 2017 의 방법론을 기반으로 재현 및 확장

목적:
    - 포트폴리오용 프로젝트
    - 논문 재현 + 현재(2025) 데이터로 결과 비교

================================================================================
2. 왜 이 방향인가 (실패 이력 포함)
================================================================================

[실패한 접근]
    초기에는 Y 변수로 concurrent players (동시접속자 수) 를 사용하려 했다.
	원래는 판매량을 보고자 했으나 제공되지 않아 동시접속자 수로 Y를 결정.
    결과: R² = 0.05 ~ 0.25 수준으로 매우 낮은 성능.

    실패 원인 2가지:
        1) Taste variance: 게임 취향은 편차가 극도로 커서 예측이 어려움
        2) 희소성: 인디 게임의 75% 가 평균 동시접속자 15명 이하
                   대부분 0에 가까운 Y 값 -> 모델이 배울 신호가 없음
		3) 전처리: 팀원들의 실력이 없어 전처리가 매우 미흡했음
		4) 속도에 급급함: 시간이 별로 없었기 때문에 정확도가 매우 낮았음

[현재 접근]
    Y 변수를 리뷰 수 (review count) 로 변경.
        - 동시접속자보다 안정적이고 노이즈가 적음
        - 논문 Trneny 2017 과 동일한 방향
    필터 기준을 강화해 데이터 품질 확보.
        - 리뷰 50개 이상, 가격 $1 이상, 2025년 3월 이전 출시, Early Access 제외

================================================================================
3. 논문 Trneny 2017 요약
================================================================================

    제목: Predicting the success of Steam games before release
    저자: Trneny (2017)

    핵심 방법론:
        - 스토어 페이지 정보만으로 출시 전 예측
        - 분류(성공/실패) + 회귀(리뷰 수) 2단계 모델
        - 피처: 메타데이터 + 스크린샷 이미지 + 설명 텍스트

    논문 기준 피처 목록:
        메타데이터:
            categories one-hot      (Single-player, Multi-player 등)
            genres one-hot          (Action, RPG 등)
            user tags binary 52개   (2D, Horror, RPG 등)
            hardware requirements   (CPU/GPU/RAM/Storage/DirectX 파싱)
            language support 10개   (영어, 한국어 등 binary)
            developer history       (이전 게임 수, max/min 리뷰, Gini 계수)
            ESRB rating
            DRM 여부
            sequel 여부
            텍스트 길이

        이미지 (스크린샷 기반):
            HSV Hue 16 bins
            avg_saturation
            avg_value
            distinct_colors
            reduced_palette_colors (64색 팔레트)

        텍스트:
            TF-IDF top 50 (detailed_description 기반)

    우리가 추가한 피처 (논문에 없는 것):
        metacritic_score    (JSON 에서 추출)
        has_demo            (JSON 에서 추출)
        이미지 추가 4개:
            edge_density
            brightness_std
            warm_color_ratio
            texture_complexity

================================================================================
4. 데이터셋
================================================================================

    수집 기준 (SteamDB 필터):
        - 게임 타입만 (DLC, OST 등 제외)
        - 리뷰 50개 이상
        - 가격 $1 이상 (무료 게임 제외)
        - 2025년 3월 이전 출시
        - Early Access 제외 (02b 에서 플래그로 추가 필터링)

    수집 결과:
        - 총 10,019개 게임
        - 수집 시점: 2025년 3월

    Y 변수:
        log(1 + review_count) 를 사용 예정
        시간 윈도우 옵션: 7/14/30일 vs 60/90/120일 (08에서 결정)

================================================================================
5. 스크립트 현황
================================================================================

[완료]
    01_steamDB_appid_gamename.py
        SteamDB 크롤링 -> AppID + 게임명 CSV
        출력: Real/01 steamDB appid gamename/01_appid_gamename.csv

    02a_steam_appdetails_snapshot.py
        Steam API 호출 -> 게임별 원본 JSON 저장
        출력: Real/02 steam appdetails snapshot/02_Steam_Appdetails_snapshot_raw/{appid}.json
        주의: 임시 CSV 도 생성되나 불완전 (has_demo 등 누락) -> 사용 금지

    02b_steam_appdetails_summary.py
        원본 JSON -> 완전한 요약 CSV 생성 (has_demo, metacritic_score, esrb_rating 포함)
        출력: Real/02 steam appdetails snapshot/02_Steam_Appdetails_summary.csv
        -> 08_feature_engineering.py 의 메인 입력 파일

    03a_steamspy_usertags.py
        SteamSpy API 호출 -> 유저 태그 JSON 저장
        출력: Real/03 steamspy usertags/03_UserTags_raw/{appid}.json

    03b_steamspy_usertags_retry_cleanup.py
        success=False JSON 삭제 -> 03a 재실행으로 재수집
        03a 실패 건 있을 때만 사용

    03c_steamspy_usertags_summary_generate.py
        태그 JSON -> 요약 CSV 생성
        출력: Real/03 steamspy usertags/03_UserTags_summary.csv

    04_steam_screenshots.py
        02a JSON 에서 스크린샷 URL 추출 -> 최대 4장 다운로드
        출력: Real/04 steam screenshots/{appid}/ss_0.jpg ~ ss_3.jpg

    04b_steam_thumbnails.py
        Steam CDN 에서 썸네일(header.jpg) 다운로드
        출력: Real/04b steam thumbnails/{appid}/thumb.jpg

    05_analyze_tags.py
        태그 빈도 분석 -> 제외 기준 적용 -> 최종 태그 목록 확정
        출력:
            Real/05 analyze tags/05_tag_exclusion_table.csv
            Real/05 analyze tags/05_selected_tags_final.csv  <- 08 에서 사용
            Real/05 analyze tags/05_tag_selection_report.png

    06_opencv_features.py
        썸네일 + 스크린샷 각 이미지에서 OpenCV 피처 9종 추출
        출력: Real/06 opencv features/06_image_features.csv
            구조: 게임 1개당 최대 5행 (thumb + ss_0~ss_3)
            컬럼: appid, image_type, success, fail_reason + 피처 24개

[미작성]
    07 없음 (번호 의도적으로 건너뜀)

    08_feature_engineering.py   <- 다음 작업
        모든 수집 데이터를 합쳐 ML 용 피처 행렬 생성
        (상세 내용은 아래 6번 참조)

    09_modeling.py
        ML 모델 학습 및 평가

================================================================================
6. 08_feature_engineering.py 에서 해야 할 것 (다음 작업)
================================================================================

입력 파일:
    Real/02 steam appdetails snapshot/02_Steam_Appdetails_summary.csv
    Real/03 steamspy usertags/03_UserTags_summary.csv
    Real/05 analyze tags/05_selected_tags_final.csv
    Real/06 opencv features/06_image_features.csv

처리 목록:

    [메타데이터 피처]
    categories one-hot
        02b CSV 의 categories 컬럼 ("|" 구분) -> split -> get_dummies

    genres one-hot
        02b CSV 의 genres 컬럼 ("|" 구분) -> split -> get_dummies

    user tags binary
        03c CSV 의 tags 컬럼 (JSON 문자열) -> json.loads
        05 CSV 의 최종 태그 목록 기준으로 binary(0/1) 생성

    hardware requirements 파싱
        02b CSV 의 pc_minimum, pc_recommended (HTML 포함 원문)
        BeautifulSoup 으로 HTML 제거 후 정규식으로 파싱
        추출 항목: CPU 코어 수, GPU 등급, RAM(GB), Storage(GB), DirectX 버전

    language support binary
        02b CSV 의 supported_languages (HTML 포함 원문)
        10개 언어 기준 binary: 영어/한국어/일본어/중국어(간체)/중국어(번체)/
                                프랑스어/독일어/스페인어/포르투갈어/러시아어

    developer history
        02b CSV 의 developers 컬럼 기준
        해당 개발사의 이전 게임 수, 이전 게임들의 max/min 리뷰 수, Gini 계수
        주의: 현재 게임은 제외하고 계산 (data leakage 방지)

    TF-IDF top 50
        02b CSV 의 detailed_description 컬럼
        HTML 태그 제거 후 TF-IDF 적용, 상위 50개 단어 피처

    기타 수치 피처
        price_initial (센트 -> 달러 변환)
        achievements_total
        screenshots_count
        movies_count
        short_desc_len
        detailed_desc_len
        has_website
        has_demo
        metacritic_score (결측값 처리 필요, 없는 게임 많음)
        esrb_rating (label encoding 또는 one-hot)

    [이미지 피처]
    06_image_features.csv pivot 방식 결정 필요 (미결정 사항 참조)

    [Y 변수]
    Steam API 로 리뷰 수 별도 수집 필요
    또는 02b 의 recommendations_total 활용 가능 (리뷰 수와 유사)
    log(1 + review_count) 변환 적용

================================================================================
7. 미결정 사항 (새 Claude 가 헷갈릴 수 있는 것들)
================================================================================

    [미결정 1] 이미지 피처 pivot 방식
        06_image_features.csv 는 게임당 최대 5행 (thumb + ss_0~ss_3).
        08 에서 이걸 게임당 1행으로 만드는 방식 3가지:
            A) 평균   : thumb + ss_0~3 각 피처의 평균 -> 게임당 24개 피처
            B) std 추가: 평균 + 이미지 간 표준편차    -> 게임당 48개 피처
            C) 독립   : 이미지별 독립 컬럼            -> 게임당 120개 피처
        어떤 방식이 성능에 좋은지는 ablation study 로 확인 예정.

    [미결정 2] Y 변수 시간 윈도우
        출시 후 며칠치 리뷰를 Y 로 쓸지 결정 안 됨.
        옵션 A: 단기 (7/14/30일)  - 런치 임팩트 측정
        옵션 B: 중기 (60/90/120일) - 더 안정적인 누적 리뷰 수
        두 윈도우를 모두 실험해서 비교할 예정.

    [미결정 3] 최종 태그 수
        05_analyze_tags.py 실행 결과에 따라 달라짐.
        논문은 52개였으나 현재 데이터 기준으로 다를 수 있음.

    [미결정 4] 분류 vs 회귀
        논문은 2단계 (분류 후 회귀) 를 사용.
        우리도 동일하게 할지, 회귀만 할지 미결정.
        일단 회귀 단독으로 시작하고 2단계 추가 여부 결정.

================================================================================
8. 코드 스타일 규칙
================================================================================

    - try/except 블록 사용 금지
    - with 문 (context manager) 사용 금지 -> open().close() 패턴 사용
    - 과도한 주석 금지, 필요한 설명만
	- 01에서 06까지의 파이썬 파일에 있는 주석은 클로드에게 충분한 설명을 제공하기 위해 작성된 것
    - 파일명은 번호_설명 형식 유지 (예외: 02a/02b, 03a/03b/03c 처럼 서브 번호 가능)
    - 경로는 raw string (r"...") 사용
    - resume 기능 필수 (중단 후 재시작 지원)
    - 진행률 출력: 처리 수 / 전체 수 + ETA 포함
	- AI가 작성한 것과 같은 코딩 스타일은 절대적으로 금지함

================================================================================
9. 디렉토리 구조
================================================================================

    Real/
        01 steamDB appid gamename/
            01_appid_gamename.csv
        02 steam appdetails snapshot/
            02_Steam_Appdetails_snapshot_raw/{appid}.json  (10,019개)
            02_Steam_Appdetails_summary.csv                (02b 생성, 완전한 버전)
        03 steamspy usertags/
            03_UserTags_raw/{appid}.json
            03_UserTags_summary.csv
        04 steam screenshots/
            {appid}/ss_0.jpg ~ ss_3.jpg
        04b steam thumbnails/
            {appid}/thumb.jpg
            04b_thumbnails_summary.csv
        05 analyze tags/
            05_tag_exclusion_table.csv
            05_selected_tags_final.csv
            05_tag_selection_report.png
        06 opencv features/
            06_image_features.csv

================================================================================
"""
