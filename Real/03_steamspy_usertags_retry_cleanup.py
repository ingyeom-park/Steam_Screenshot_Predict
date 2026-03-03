import os, json

RAW_DIR = r"Real\03 steamspy usertags\03_UserTags_raw"

targets = []
for fname in os.listdir(RAW_DIR):
    if not fname.endswith(".json"):
        continue
    path = os.path.join(RAW_DIR, fname)
    f = open(path, encoding="utf-8")
    d = json.load(f)
    f.close()
    if not d.get("success"):
        targets.append(path)

print(f"삭제 대상: {len(targets)}개")
for path in targets:
    os.remove(path)
    print(f"삭제: {os.path.basename(path)}")

print(f"\n완료. 이제 03_steamspy_usertags.py 재실행하면 {len(targets)}개만 재수집합니다.")
