# Project Brief

## 1. 프로젝트 목표

Steam 게임의 출시 초기 성공 여부를 예측하는 ML 모델을 만든다.

핵심 제약은 다음과 같다.

- 출시 시점에 스토어 페이지에서 얻을 수 있는 정보만 X 피처로 사용한다.
- 출시 후 리뷰 수를 Y 변수로 사용한다.
- Trneny 2017 논문의 방법론을 기반으로 재현하고, 현재 데이터에 맞춰 확장한다.

## 2. 왜 리뷰 수를 쓰는가

초기에는 Y 변수로 동시접속자 수를 쓰려 했다.
그러나 다음 문제가 있었다.

- 게임 취향 편차가 너무 커서 예측 신호가 약했다.
- 인디 게임의 Y 값이 극단적으로 희소했다.
- 당시 전처리 수준이 낮았다.
- 일정이 급해 데이터 품질을 충분히 관리하지 못했다.

그래서 현재는 리뷰 수를 사용한다.
리뷰 수는 동시접속자 수보다 안정적이고, 논문 방향과도 맞는다.

## 3. 현재 파이프라인 구조

이번 리팩터링 이후 구조는 다음 원칙을 따른다.

- 코드는 `pipeline/`
- 문서는 `docs/`
- 원본 데이터는 `data/raw/`
- 중간 산출물은 `data/interim/`
- 최종 ML 입력은 `data/processed/`
- 과거 실험 코드는 `archive/`

모든 경로는 `pipeline/project_paths.py`에서 중앙 관리한다.
절대경로는 사용하지 않는다.

## 4. 단계별 스크립트와 산출물

### 01. SteamDB 목록 수집

- 스크립트: `pipeline/01_steamdb_app_list.py`
- 출력: `data/raw/01_steamdb_app_list/01_steamdb_app_list.csv`

### 01-extra. SteamDB 리뷰 히스토리 수집

- 스크립트: `pipeline/01_steamdb_review_history.py`
- 출력: `data/raw/01_steamdb_review_history/`
- 비고: SteamDB 로그인 쿠키가 필요하므로 `pipeline/local_config.py`를 사용한다.

### 02a. Steam AppDetails 원본 스냅샷

- 스크립트: `pipeline/02a_steam_appdetails_snapshot.py`
- 출력: `data/raw/02_steam_appdetails/json/{appid}.json`
- 임시 요약 CSV도 만들지만, 최종 요약은 02b 기준으로 본다.

### 02b. Steam AppDetails 요약 CSV

- 스크립트: `pipeline/02b_steam_appdetails_summary.py`
- 출력: `data/interim/02_steam_appdetails_summary.csv`

### 03a. SteamSpy 유저 태그 수집

- 스크립트: `pipeline/03a_steamspy_usertags.py`
- 출력: `data/raw/03_steamspy_usertags/json/{appid}.json`

### 03b. SteamSpy 실패 JSON 정리

- 스크립트: `pipeline/03b_steamspy_usertags_retry_cleanup.py`
- 역할: `success=False` JSON만 삭제해 03a 재수집 대상으로 만든다.

### 03c. SteamSpy 유저 태그 요약

- 스크립트: `pipeline/03c_steamspy_usertags_summary_generate.py`
- 출력: `data/interim/03_steamspy_usertags_summary.csv`

### 04a. 스크린샷 수집

- 스크립트: `pipeline/04a_steam_screenshots.py`
- 출력: `data/raw/04_screenshots/{appid}/ss_0.jpg ~ ss_3.jpg`

### 04b. 썸네일 수집

- 스크립트: `pipeline/04b_steam_thumbnails.py`
- 출력 이미지: `data/raw/04b_thumbnails/{appid}/thumb.jpg`
- 출력 요약: `data/interim/04b_thumbnails_summary.csv`

### 05. 태그 분석과 최종 태그 선정

- 스크립트: `pipeline/05_analyze_tags.py`
- 출력 폴더: `data/interim/05_tag_analysis/`

### 06. OpenCV 이미지 피처

- 스크립트: `pipeline/06_opencv_features.py`
- 출력: `data/interim/06_image_features/06_image_features.csv`

### 07a. PC 요구사항 파싱

- 스크립트: `pipeline/07a_preprocess_pc_requirements.py`
- 출력: `data/interim/07_preprocess/07a_pc_requirements.csv`
- 보조 출력: `data/interim/07_preprocess/07a_parse_failures.csv`

### 07b. TF-IDF 전처리

- 스크립트: `pipeline/07b_preprocess_tfidf.py`
- 출력: `data/interim/07_preprocess/07b_tfidf_features.csv`
- 보조 출력: `data/interim/07_preprocess/07b_tfidf_vocabulary.txt`
- 주의: 전체 fit 결과라 EDA 확인용이다. 모델링 본실험에서는 train-only fit을 다시 해야 한다.

### 08. 최종 feature engineering

- 스크립트: `pipeline/08_feature_engineering.py`
- 출력: `data/processed/08_features/08_features_X.csv`
- 보조 출력: `data/processed/08_features/08_feature_columns.txt`

## 5. 논문 기반 피처 목록

주요 피처 그룹은 다음과 같다.

- 메타데이터
- 카테고리 one-hot
- 장르 one-hot
- 유저 태그 binary
- 하드웨어 요구사항 파싱
- 언어 지원 binary
- 개발사 이력
- 이미지 피처
- TF-IDF 텍스트 피처

현재 프로젝트에서는 `metacritic_score`, `has_demo`, 일부 추가 OpenCV 피처도 함께 고려한다.

## 6. 아직 남아 있는 결정 사항

- 이미지 피처를 평균으로 합칠지, 표준편차까지 넣을지, 이미지별 독립 컬럼으로 둘지
- Y 변수 시간 윈도우를 7/14/30일로 볼지, 60/90/120일로 볼지
- 최종 태그 수를 몇 개로 고정할지
- 분류 후 회귀의 2단계 구조를 쓸지, 회귀만 쓸지

## 7. 운영 원칙

- 코드와 데이터의 위치를 분리한다.
- 경로는 중앙 파일에서만 관리한다.
- 민감한 값은 `pipeline/local_config.py`에 둔다.
- 원본 대용량 데이터는 Git에 올리지 않는다.
- 생성 가능한 산출물은 `data/` 아래에 두고, 필요하면 다시 생성한다.
