"""
03b_steamspy_usertags_retry_cleanup.py
================================================================================
[목적]
    03a_steamspy_usertags.py 수집 후 success=False 인 JSON 파일을 전부 삭제한다.
    삭제 후 03a 를 재실행하면 삭제된 appid 만 재수집된다.

[사용 시점]
    03a 실행 완료 후 FAILED 출력이 있을 때 사용.
    실행 순서:
        03a 실행 -> 실패 건 확인 -> 03b 실행 -> 03a 재실행 (반복)
        -> 실패 건 없어지면 03c 실행

[삭제 대상]
    RAW_DIR 내 JSON 파일 중 {"success": False} 인 파일.
    {"success": True} 인 파일은 건드리지 않음.

[입력/출력]
    입력: Real/03 steamspy usertags/03_UserTags_raw/ 내 JSON 파일들
    출력: 없음 (파일 삭제만 수행)

[다음 단계]
    이 파일 실행 후 03a_steamspy_usertags.py 를 재실행.
================================================================================
"""

import os, json

RAW_DIR = r"Real\03 steamspy usertags\03_UserTags_raw"

# 삭제 대상 목록 수집: success=False 인 JSON 파일 경로만 추출
targets = []
for fname in os.listdir(RAW_DIR):
    if not fname.endswith(".json"):
        continue
    path = os.path.join(RAW_DIR, fname)
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
    print(f"삭제: {os.path.basename(path)}")

print(f"\n완료. 이제 03a_steamspy_usertags.py 재실행하면 {len(targets)}개만 재수집합니다.")
