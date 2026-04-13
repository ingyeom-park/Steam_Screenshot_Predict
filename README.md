# ML Steam Review Count Predict

Steam 인디 게임의 출시 초기 성공 가능성을 리뷰 수 기준으로 예측하기 위한
파이프라인 프로젝트입니다.

## 현재 구조

- `pipeline/`
  단계별 수집, 정리, 피처 엔지니어링 스크립트
- `docs/`
  프로젝트 브리프와 참고 자료
- `data/raw/`
  원본 JSON, 원본 이미지, 크롤링 원본 목록
- `data/interim/`
  요약 CSV, 태그 분석 결과, 전처리 산출물
- `data/processed/`
  최종 feature matrix
- `archive/`
  현재 파이프라인에 직접 포함되지 않는 과거 실험 코드

## 경로 관리 원칙

모든 스크립트는 `pipeline/project_paths.py`를 import 해서 경로를 사용합니다.
경로를 개별 파일 안에 하드코딩하지 않습니다.

## 로컬 설정

민감한 값은 `pipeline/local_config.py`에 둡니다.
예시는 `pipeline/local_config.example.py`에 있습니다.

## 실행 순서

1. `01_steamdb_app_list.py`
2. `02a_steam_appdetails_snapshot.py`
3. `02b_steam_appdetails_summary.py`
4. `03a_steamspy_usertags.py`
5. `03b_steamspy_usertags_retry_cleanup.py` 필요 시
6. `03c_steamspy_usertags_summary_generate.py`
7. `04a_steam_screenshots.py`
8. `04b_steam_thumbnails.py`
9. `05_analyze_tags.py`
10. `06_opencv_features.py`
11. `07a_preprocess_pc_requirements.py`
12. `07b_preprocess_tfidf.py`
13. `08_feature_engineering.py`

상세 배경과 의사결정 기록은 `docs/project_brief.md`에 정리합니다.
