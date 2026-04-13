"""
03b_steamspy_usertags_retry_cleanup.py
================================================================================
[목적]
    03a 수집 결과 중 success=False 인 JSON만 삭제해 재수집 대상으로 만든다.

[입력 폴더]
    data/raw/03_steamspy_usertags/json/
================================================================================
"""

import os, json
from project_paths import USERTAGS_JSON_DIR

RAW_DIR = USERTAGS_JSON_DIR

# 삭제 대상 목록 수집: success=False 인 JSON 파일 경로만 추출
targets = []
for fname in os.listdir(RAW_DIR):
    if not fname.endswith(".json"):
        continue
    path = RAW_DIR / fname
    f = open(path, encoding="utf-8")
    d = json.load(f)
    f.close()
    # success=False 인 파일만 삭제 대상으로 추가
    # success=True 인 파일은 건드리지 않음
    if not d.get("success"):
        targets.append(path)

print(f"삭제 대상: {len(targets)}개")
for path in targets:
    os.remove(path)
    print(f"삭제: {path.name}")

print(f"\n완료. 이제 03a를 재실행하면 {len(targets)}개만 재수집합니다.")
