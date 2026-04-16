"""
project_paths.py
공통 경로 정의 파일.

파이프라인 스크립트는 개별 파일 안에서 경로 문자열을 반복하지 않고,
이 파일의 상수를 import 해서 사용한다.
폴더 구조를 다시 바꾸더라도 이 파일만 수정하면 된다.
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

DOCS_DIR = ROOT_DIR / "docs"
DOCS_REFERENCES_DIR = DOCS_DIR / "references"
ARCHIVE_DIR = ROOT_DIR / "archive"
PIPELINE_DIR = ROOT_DIR / "pipeline"

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

APP_LIST_DIR = RAW_DIR / "01_steamdb_app_list"
APP_LIST_CSV = APP_LIST_DIR / "01_steamdb_app_list_10.csv"

STEAMDB_REVIEW_DIR = RAW_DIR / "01_steamdb_review_history"
STEAMDB_REVIEW_CSV = STEAMDB_REVIEW_DIR / "01_steamdb_review_history.csv"
STEAMDB_REVIEW_DONE_CSV = STEAMDB_REVIEW_DIR / "01_steamdb_review_done_appids.csv"
STEAMDB_REVIEW_FAILED_CSV = STEAMDB_REVIEW_DIR / "01_steamdb_review_failed_appids.csv"

APPDETAILS_DIR = RAW_DIR / "02_steam_appdetails"
APPDETAILS_JSON_DIR = APPDETAILS_DIR / "json"
APPDETAILS_SUMMARY_CSV = INTERIM_DIR / "02_steam_appdetails_summary.csv"

USERTAGS_DIR = RAW_DIR / "03_steamspy_usertags"
USERTAGS_JSON_DIR = USERTAGS_DIR / "json"
USERTAGS_SUMMARY_CSV = INTERIM_DIR / "03_steamspy_usertags_summary.csv"

SCREENSHOTS_DIR = RAW_DIR / "04_screenshots"
THUMBNAILS_DIR = RAW_DIR / "04b_thumbnails"
THUMBNAILS_SUMMARY_CSV = INTERIM_DIR / "04b_thumbnails_summary.csv"

TAG_ANALYSIS_DIR = INTERIM_DIR / "05_tag_analysis"
TAG_EXCLUSION_CSV = TAG_ANALYSIS_DIR / "05_tag_exclusion_table.csv"
SELECTED_TAGS_CSV = TAG_ANALYSIS_DIR / "05_selected_tags_final.csv"
TAG_SELECTION_REPORT_PNG = TAG_ANALYSIS_DIR / "05_tag_selection_report.png"

IMAGE_FEATURES_DIR = INTERIM_DIR / "06_image_features"
IMAGE_FEATURES_CSV = IMAGE_FEATURES_DIR / "06_image_features.csv"

PREPROCESS_DIR = INTERIM_DIR / "07_preprocess"
PC_REQUIREMENTS_CSV = PREPROCESS_DIR / "07a_pc_requirements.csv"
PARSE_FAILURES_CSV = PREPROCESS_DIR / "07a_parse_failures.csv"
TFIDF_FEATURES_CSV = PREPROCESS_DIR / "07b_tfidf_features.csv"
TFIDF_VOCAB_TXT = PREPROCESS_DIR / "07b_tfidf_vocabulary.txt"

FEATURES_DIR = PROCESSED_DIR / "08_features"
FEATURES_X_CSV = FEATURES_DIR / "08_features_X.csv"
FEATURE_COLUMNS_TXT = FEATURES_DIR / "08_feature_columns.txt"

PROJECT_BRIEF_MD = DOCS_DIR / "project_brief.md"
REFERENCE_PAPER_PDF = (
    DOCS_REFERENCES_DIR / "machine_learning_for_predicting_success_of_video_games.pdf"
)


BASE_DIRS = [
    DOCS_DIR,
    DOCS_REFERENCES_DIR,
    ARCHIVE_DIR,
    PIPELINE_DIR,
    DATA_DIR,
    RAW_DIR,
    INTERIM_DIR,
    PROCESSED_DIR,
    APP_LIST_DIR,
    STEAMDB_REVIEW_DIR,
    APPDETAILS_DIR,
    APPDETAILS_JSON_DIR,
    USERTAGS_DIR,
    USERTAGS_JSON_DIR,
    SCREENSHOTS_DIR,
    THUMBNAILS_DIR,
    TAG_ANALYSIS_DIR,
    IMAGE_FEATURES_DIR,
    PREPROCESS_DIR,
    FEATURES_DIR,
]

for base_dir in BASE_DIRS:
    base_dir.mkdir(parents=True, exist_ok=True)
