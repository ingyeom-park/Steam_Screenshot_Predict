"""
07a_preprocess_pc_requirements.py
================================================================================
[입력 파일]
    data/interim/02_steam_appdetails_summary.csv

[출력 파일]
    data/interim/07_preprocess/07a_pc_requirements.csv
    data/interim/07_preprocess/07a_parse_failures.csv

파싱 대상:
  hw_ram_gb      : pc_minimum에서 RAM 용량 추출 (GB 단위 통일)
  hw_storage_gb  : pc_minimum에서 Storage 용량 추출 (GB 단위 통일)
  hw_has_gpu_req : pc_minimum + pc_recommended 전체에서 GPU 키워드 탐지 → 0/1

제외 결정:
  hw_directx     : 69.9%가 중앙값 대체 → 신뢰 불가, 제외
  hw_has_cpu_req : 97%가 1 → 분산 없음, 정보량 없음, 제외

결측 처리:
  hw_ram_gb, hw_storage_gb 파싱 실패 시 → 중앙값 대체
  parse_success = False 로 기록 (07a_parse_failures.csv에 별도 저장)

검토 권장:
  07a_parse_failures.csv를 열어서 파싱 실패 패턴 확인 후
  정규식 보완 여부 결정
================================================================================
"""

import pandas as pd
import numpy as np
import re
from project_paths import APPDETAILS_SUMMARY_CSV, PARSE_FAILURES_CSV, PC_REQUIREMENTS_CSV

IN_CSV   = APPDETAILS_SUMMARY_CSV
OUT_CSV  = PC_REQUIREMENTS_CSV
FAIL_CSV = PARSE_FAILURES_CSV

GPU_KW = [
    "nvidia", "geforce", "amd", "radeon",
    "gtx", "rtx", "rx ", "vram",
    "graphics card", "gpu", "intel hd", "intel iris",
]


def strip_html(text):
    if pd.isna(text):
        return ""
    return re.sub(r"<[^>]+>", " ", str(text))


def parse_ram_gb(text):
    """
    패턴 우선순위:
    1) "8 GB RAM" / "512 MB RAM"       — RAM 명시
    2) "Memory: 8 GB" / "RAM: 512 MB"  — 섹션 헤더 뒤
    3) "1+ gigs of RAM"                — gigs 단위
    4) "1GB of RAM" / "1GB Ram"        — of/접미 패턴
    MB는 1024로 나눠 GB 변환
    """
    # 1순위: "X GB RAM" / "X MB RAM"
    m = re.search(r"(\d+[\.,]?\d*)\s*(gb|mb)\s*(?:of\s+)?ram", text, re.IGNORECASE)
    if m:
        val  = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return round(val if unit == "gb" else val / 1024, 3)

    # 2순위: Memory / RAM 섹션 헤더 뒤
    m = re.search(r"(?:memory|ram)\s*[:\-]?\s*(\d+[\.,]?\d*)\+?\s*(gb|mb)", text, re.IGNORECASE)
    if m:
        val  = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return round(val if unit == "gb" else val / 1024, 3)

    # 3순위: "1+ gigs of RAM" / "2 gigs RAM"
    m = re.search(r"(\d+[\.,]?\d*)\+?\s*gigs?\s*(?:of\s+)?ram?", text, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(",", "."))
        return round(val, 3)  # gigs = GB

    # 4순위: "1GB Ram" / "1 GB of RAM"
    m = re.search(r"(\d+[\.,]?\d*)\s*(gb|mb)\s*(?:of\s+)?ram?", text, re.IGNORECASE)
    if m:
        val  = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return round(val if unit == "gb" else val / 1024, 3)

    return np.nan


def parse_storage_gb(text):
    """
    패턴 우선순위:
    1) "Storage: 2 GB available space"
    2) "Hard Drive: 500 MB"
    3) "2 GB" (storage 컨텍스트 근처)
    """
    # 1순위: storage/hard/disk 섹션 뒤
    m = re.search(
        r"(?:storage|hard\s*drive|hard\s*disk|disk\s*space|available\s*space|hdd|ssd)"
        r"\s*[:\-]?\s*(\d+[\.,]?\d*)\s*(gb|mb)",
        text, re.IGNORECASE
    )
    if m:
        val  = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return round(val if unit == "gb" else val / 1024, 3)

    # 2순위: "X GB available"
    m = re.search(r"(\d+[\.,]?\d*)\s*(gb|mb)\s+available", text, re.IGNORECASE)
    if m:
        val  = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        return round(val if unit == "gb" else val / 1024, 3)

    return np.nan


def has_gpu_req(text):
    t = text.lower()
    return 1 if any(kw in t for kw in GPU_KW) else 0


# ──────────────────────────────────────────────────────────────
print("=" * 60)
print("[1] 데이터 로드")
print("=" * 60)

df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
df = df[df["success"] == True].copy()
df["appid"] = df["appid"].astype(str)
print(f"유효 게임: {len(df):,}개")


# ──────────────────────────────────────────────────────────────
print("\n[2] HTML 제거")

df["min_text"] = df["pc_minimum"].apply(strip_html)
df["rec_text"] = df["pc_recommended"].apply(strip_html)
df["combined"] = df["min_text"] + " " + df["rec_text"]


# ──────────────────────────────────────────────────────────────
print("\n[3] 파싱")

df["hw_ram_gb"]      = df["min_text"].apply(parse_ram_gb)
df["hw_storage_gb"]  = df["min_text"].apply(parse_storage_gb)
df["hw_has_gpu_req"] = df["combined"].apply(has_gpu_req)

ram_fail     = df["hw_ram_gb"].isna().sum()
storage_fail = df["hw_storage_gb"].isna().sum()

print(f"hw_ram_gb     파싱 성공: {len(df)-ram_fail:,}개  실패: {ram_fail:,}개 ({ram_fail/len(df)*100:.1f}%)")
print(f"hw_storage_gb 파싱 성공: {len(df)-storage_fail:,}개  실패: {storage_fail:,}개 ({storage_fail/len(df)*100:.1f}%)")
print(f"hw_has_gpu_req=1: {df['hw_has_gpu_req'].sum():,}개 ({df['hw_has_gpu_req'].mean()*100:.1f}%)")


# ──────────────────────────────────────────────────────────────
print("\n[4] 결측 처리 — 중앙값 대체")

ram_median     = df["hw_ram_gb"].median()
storage_median = df["hw_storage_gb"].median()

print(f"hw_ram_gb     중앙값: {ram_median} GB")
print(f"hw_storage_gb 중앙값: {storage_median} GB")

# parse_success: RAM 파싱 성공 기준
# storage는 아예 기재 안 한 게임이 많아 실패해도 parse_success에 영향 없음
df["parse_success"] = ~df["hw_ram_gb"].isna()

df["hw_ram_gb"]     = df["hw_ram_gb"].fillna(ram_median)
df["hw_storage_gb"] = df["hw_storage_gb"].fillna(storage_median)


# ──────────────────────────────────────────────────────────────
print("\n[5] 파싱 실패 행 저장 (검토용)")

fail_df = df[~df["parse_success"]][["appid","min_text","hw_ram_gb","hw_storage_gb"]].copy()
fail_df.to_csv(FAIL_CSV, index=False, encoding="utf-8-sig")
print(f"파싱 실패 행: {len(fail_df):,}개 -> {FAIL_CSV}")
print("  해당 파일을 열어 패턴 확인 후 정규식 보완 여부 결정 권장")


# ──────────────────────────────────────────────────────────────
print("\n[6] 저장")

out = df[["appid","hw_ram_gb","hw_storage_gb","hw_has_gpu_req","parse_success"]].copy()
out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"PC 요구사항 피처 -> {OUT_CSV}")

print("\n[분포 요약]")
print(f"  hw_ram_gb     : min={df['hw_ram_gb'].min():.2f}  median={ram_median:.2f}  max={df['hw_ram_gb'].max():.2f} GB")
print(f"  hw_storage_gb : min={df['hw_storage_gb'].min():.2f}  median={storage_median:.2f}  max={df['hw_storage_gb'].max():.2f} GB")
print(f"  hw_has_gpu_req: 0={( df['hw_has_gpu_req']==0).sum():,}개  1={(df['hw_has_gpu_req']==1).sum():,}개")
print(f"  parse_success : True={df['parse_success'].sum():,}개  False={(~df['parse_success']).sum():,}개")

print("\n완료")
