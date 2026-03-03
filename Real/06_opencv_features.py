"""
06_opencv_features.py
================================================================================
[목적]
    썸네일(thumb.jpg) + 스크린샷(ss_0~ss_3.jpg) 각 이미지에서
    OpenCV 기반 시각적 피처를 추출해 CSV로 저장한다.

[입력 파일]
    Real/04b steam thumbnails/{appid}/thumb.jpg
        - 04b_steam_thumbnails.py 에서 수집한 Steam 헤더 이미지 (460x215px)
    Real/04  steam screenshots/{appid}/ss_0.jpg ~ ss_3.jpg
        - 04_steam_screenshots.py 에서 수집한 스크린샷 (최대 4장)
    Real/01  steamdb appid gamename/01_appid_gamename.csv
        - 처리할 appid 목록

[출력 파일]
    Real/06 opencv features/06_image_features.csv
        - 게임 1개당 최대 5행 (thumb 1행 + ss_0~ss_3 4행)
        - 컬럼 구성: appid, image_type, success, fail_reason + 피처 24개
        - 이 파일을 08_feature_engineering.py 에서 pivot 해서 게임별 1행으로 변환

[피처 목록 - 총 24개]
    논문 Trneny 2017 기준 5개:
        hue_bin_0 ~ hue_bin_15  HSV 색조(H) 16구간 각 픽셀 비율 (%)  -> 16개 컬럼
        avg_saturation          HSV 채도(S) 전체 픽셀 평균 (0~255)
        avg_value               HSV 명도(V) 전체 픽셀 평균 (0~255)
        distinct_colors         RGB 원본 기준 고유 색상 수 (정수)
        reduced_palette_colors  64단계 양자화 후 고유 색상 수 (정수)

    추가 4개 (2017 논문에 없는 확장 피처):
        edge_density            Canny 엣지 픽셀 비율 (%)   -> 화면 복잡도 측정
        brightness_std          HSV 명도(V) 표준편차        -> 대비 강도 측정
        warm_color_ratio        따뜻한 색 픽셀 비율 (%)    -> 색온도 경향 측정
        texture_complexity      Laplacian 분산              -> 텍스처/선명도 측정

[설계 결정 사항 및 근거]

    결정 1. 이미지별 독립 행 저장 (4장 평균 내지 않음)
        UI 스크린샷 특징: 채도 낮음, 명도 높음, 색상 수 적음
        씬 스크린샷 특징: 채도 높음, 명도 다양, 색상 수 많음
        두 성격을 평균내면 서로 상쇄되어 의미없는 중간값이 됨.
        합칠지 / 표준편차 낼지 / 독립 피처로 쓸지는
        08_feature_engineering.py 에서 pivot 방식으로 결정.

    결정 2. 리사이즈 (긴 변 기준 max 512px)
        Steam 스크린샷 원본은 대부분 1920x1080.
        원본 그대로 처리하면 처리 시간이 3~4배 늘어남.
        hue bins, saturation, value, distinct_colors 는 픽셀 비율 기반이라
        리사이즈 후에도 값이 거의 동일하게 유지됨.
        edge_density, texture_complexity 는 미세하게 달라지지만
        게임 간 상대적 순위에는 영향 없어 ML 피처로서 문제없음.
        보간법: INTER_AREA (축소 시 모아레 감소에 가장 적합).

    결정 3. reduced_palette_colors: K-means 대신 채널 양자화
        논문은 "64색 팔레트" 라고만 기술했고 K-means 를 명시하지 않음.
        K-means 사용 시 10,000 게임 x 5장 기준 수십 시간 소요 -> 사용 불가.
        대안: 각 RGB 채널을 (픽셀값 // 4) * 4 로 양자화.
            256단계 -> 64단계 (0, 4, 8, ..., 252) 로 줄어듦.
            예) 픽셀 (123, 200, 77) -> (120, 200, 76)
        K-means와 동일한 '색 다양성 측정' 의도를 충족하면서 훨씬 빠름.

    결정 4. warm_color_ratio H 범위 정의
        OpenCV H채널 범위: 0~179 (실제 색상환 360도를 절반으로 표현).
        따뜻한 색:
            빨강/주황/노랑 = 실제 색상환 0~60도   -> OpenCV H 기준 0~30
            보라/분홍      = 실제 색상환 300~360도 -> OpenCV H 기준 150~179
        차가운 색 (초록, 파랑, 청록) = OpenCV H 기준 31~149.

    결정 5. resume 지원
        OUT_CSV 가 이미 존재하면 (appid, image_type) 쌍 집합을 로드,
        이미 처리된 항목은 건너뜀. 중단 후 재시작해도 중복 처리 없음.

    결정 6. cv2.CV_64F (Laplacian 출력 타입)
        uint8 로 받으면 Laplacian 결과의 음수값이 0으로 잘려
        분산이 실제보다 작게 계산됨 -> float64 반드시 필요.
================================================================================
"""

import os, csv, time
import numpy as np
import cv2
import pandas as pd


# ── 경로 설정 ──────────────────────────────────────────────────────────────
APPID_CSV      = r"Real\01 steamDB appid, gamename\01 steamDB appid, gamename.csv"
THUMB_DIR      = r"Real\04b steam thumbnails"      # 04b 수집 결과
SCREENSHOT_DIR = r"Real\04 steam screenshots"       # 04 수집 결과
OUT_DIR        = r"Real\06 opencv features"
OUT_CSV        = os.path.join(OUT_DIR, "06_image_features.csv")

os.makedirs(OUT_DIR, exist_ok=True)


# ── 이미지 경로 생성 함수 ──────────────────────────────────────────────────
def get_image_paths(appid):
    """
    appid 하나에 대해 처리할 이미지 목록을 반환.

    매개변수:
        appid (str): Steam 게임 고유 ID

    반환값:
        list of (image_type, file_path)
            image_type : 'thumb' | 'ss_0' | 'ss_1' | 'ss_2' | 'ss_3'
                         CSV 의 image_type 컬럼에 그대로 저장됨.
                         08 에서 pivot 시 컬럼 접두사로 사용됨.
                         예) thumb_avg_saturation, ss_0_avg_saturation
            file_path  : 실제 파일 경로 문자열.
                         파일이 없어도 그대로 반환 (존재 여부는 extract_features 에서 체크).
    """
    paths = [("thumb", os.path.join(THUMB_DIR, appid, "thumb.jpg"))]
    for i in range(4):
        paths.append((f"ss_{i}", os.path.join(SCREENSHOT_DIR, appid, f"ss_{i}.jpg")))
    return paths


# ── 피처 컬럼 정의 ─────────────────────────────────────────────────────────
# 출력 CSV 피처 컬럼 순서를 여기서 명시적으로 고정.
# 08_feature_engineering.py 가 이 순서를 그대로 참조하므로 변경 금지.

HUE_COLS = [f"hue_bin_{i}" for i in range(16)]
# hue_bin_0  : H 0~11   (빨강)
# hue_bin_1  : H 11~22  (주황)
# hue_bin_2  : H 22~34  (노랑)
# hue_bin_3  : H 34~45  (연두)
# hue_bin_4  : H 45~56  (초록)
# hue_bin_5  : H 56~67  (초록)
# hue_bin_6  : H 67~78  (청록)
# hue_bin_7  : H 78~90  (청록)
# hue_bin_8  : H 90~101 (하늘)
# hue_bin_9  : H 101~112(파랑)
# hue_bin_10 : H 112~123(파랑)
# hue_bin_11 : H 123~135(남색)
# hue_bin_12 : H 135~146(보라)
# hue_bin_13 : H 146~157(보라)
# hue_bin_14 : H 157~168(분홍)
# hue_bin_15 : H 168~179(빨강 경계)
# 값의 의미: 해당 구간에 속하는 픽셀이 전체 픽셀 대비 몇 %인지

FEAT_COLS = (
    HUE_COLS
    + [
        "avg_saturation",           # 논문 피처 2
        "avg_value",                # 논문 피처 3
        "distinct_colors",          # 논문 피처 4
        "reduced_palette_colors",   # 논문 피처 5
        "edge_density",             # 추가 피처 1
        "brightness_std",           # 추가 피처 2
        "warm_color_ratio",         # 추가 피처 3
        "texture_complexity",       # 추가 피처 4
    ]
)

# 최종 CSV 컬럼 순서: 식별자 4개 + 피처 24개
ALL_COLS = ["appid", "image_type", "success", "fail_reason"] + FEAT_COLS


# ── 피처 추출 함수 ─────────────────────────────────────────────────────────
def extract_features(img_path):
    """
    이미지 파일 1장에서 피처 24개를 추출해 딕셔너리로 반환.

    매개변수:
        img_path (str): 처리할 이미지 파일 경로

    반환값:
        dict
            success (bool)       : True 면 피처 24개 모두 float 값.
                                   False 면 피처 24개 모두 None.
            fail_reason (str)    : 실패 사유.
                                   '' | 'file_not_found' | 'imread_failed'
            hue_bin_0 ~ hue_bin_15 (float): HSV Hue 16구간 픽셀 비율 (%)
            avg_saturation (float)         : 채도 평균
            avg_value (float)              : 명도 평균
            distinct_colors (int)          : RGB 고유 색상 수
            reduced_palette_colors (int)   : 양자화 후 고유 색상 수
            edge_density (float)           : Canny 엣지 비율 (%)
            brightness_std (float)         : 명도 표준편차
            warm_color_ratio (float)       : 따뜻한 색 비율 (%)
            texture_complexity (float)     : Laplacian 분산

    처리 흐름:
        파일 존재 체크
        -> cv2.imread (BGR 읽기)
        -> 리사이즈 (긴 변 max 512px, INTER_AREA)
        -> cv2.cvtColor BGR->HSV
        -> H, S, V 채널 분리
        -> 피처 9종 계산 (hue 16bins, sat, val, distinct, reduced, edge, std, warm, laplacian)
    """
    # 실패 시 반환할 기본값: 피처 전부 None
    result = {col: None for col in FEAT_COLS}
    result['success']     = False
    result['fail_reason'] = ''

    # ── 파일 존재 체크 ─────────────────────────────────────────────────────
    # ss_1~ss_3 은 스크린샷이 4장 미만인 게임에서 없을 수 있음.
    # thumb 도 Steam CDN 에서 404 가 났으면 없을 수 있음.
    if not os.path.exists(img_path):
        result['fail_reason'] = 'file_not_found'
        return result

    # ── 이미지 읽기 ────────────────────────────────────────────────────────
    # cv2.imread: 파일을 BGR 순서로 읽음.
    # BGR = Blue-Green-Red. 일반적인 RGB 와 첫/마지막 채널이 반대.
    # 반환값: numpy array shape (height, width, 3), dtype uint8
    # 읽기 실패 시 (파일 손상, 지원 안 되는 포맷) None 반환.
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        result['fail_reason'] = 'imread_failed'
        return result

    # ── 리사이즈 ───────────────────────────────────────────────────────────
    # h, w: 현재 이미지의 높이(height), 너비(width) 픽셀 수
    # scale: 긴 변을 512로 맞추기 위한 비율
    # INTER_AREA: 픽셀 면적 기반 보간. 축소 시 모아레 없이 가장 깔끔.
    h, w = img_bgr.shape[:2]
    if max(h, w) > 512:
        scale   = 512 / max(h, w)
        img_bgr = cv2.resize(
            img_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA
        )

    # ── HSV 변환 ───────────────────────────────────────────────────────────
    # img_hsv shape: (height, width, 3), dtype uint8
    # 채널 0 = H (Hue, 색조)       : 0~179  OpenCV는 360도를 절반으로 표현
    # 채널 1 = S (Saturation, 채도): 0~255  0=무채색, 255=최대 채도
    # 채널 2 = V (Value, 명도)     : 0~255  0=검정, 255=최대 밝기
    img_hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H        = img_hsv[:, :, 0]    # shape (h, w) 2D array
    S        = img_hsv[:, :, 1]    # shape (h, w) 2D array
    V        = img_hsv[:, :, 2]    # shape (h, w) 2D array
    total_px = H.size               # 리사이즈 후 전체 픽셀 수 (h * w)

    # ══════════════════════════════════════════════════════════════════════
    # [논문 피처 1] hue_bin_0 ~ hue_bin_15
    # HSV Hue 16 bins: 색조를 16구간으로 나눈 픽셀 비율 (%)
    # ══════════════════════════════════════════════════════════════════════
    # cv2.calcHist 인자:
    #   [img_hsv]   : 히스토그램 계산할 이미지 (리스트로 감싸야 함)
    #   [0]         : 사용할 채널 인덱스 (0 = H 채널)
    #   None        : 마스크 없음 (전체 이미지 사용)
    #   [16]        : bin 수 (16등분)
    #   [0, 180]    : H 값 범위 (0~179)
    # 반환값: shape (16, 1) float32 array -> flatten() 으로 (16,) 으로 변환
    # 각 값의 의미: 해당 bin 에 속하는 픽셀 수 (절대값)
    # -> total_px 로 나눠 비율(%)로 변환
    hist = cv2.calcHist([img_hsv], [0], None, [16], [0, 180])
    hist = hist.flatten()
    for i, val in enumerate(hist):
        result[f"hue_bin_{i}"] = round(float(val) / total_px * 100, 4)

    # ══════════════════════════════════════════════════════════════════════
    # [논문 피처 2] avg_saturation: 채도 평균
    # ══════════════════════════════════════════════════════════════════════
    # S 채널 전체 픽셀의 산술 평균.
    # 높을수록(~255): 색이 선명하고 진함 (RPG, 판타지 등 화려한 게임)
    # 낮을수록(~0)  : 회색조에 가까움 (흑백 픽셀아트, 미니멀 게임 등)
    result['avg_saturation'] = round(float(S.mean()), 4)

    # ══════════════════════════════════════════════════════════════════════
    # [논문 피처 3] avg_value: 명도 평균
    # ══════════════════════════════════════════════════════════════════════
    # V 채널 전체 픽셀의 산술 평균.
    # 높을수록(~255): 전반적으로 밝은 이미지 (캐주얼, 퍼즐 등)
    # 낮을수록(~0)  : 전반적으로 어두운 이미지 (호러, 다크 판타지 등)
    result['avg_value'] = round(float(V.mean()), 4)

    # ══════════════════════════════════════════════════════════════════════
    # [논문 피처 4] distinct_colors: RGB 원본 고유 색상 수
    # ══════════════════════════════════════════════════════════════════════
    # 이미지에 등장하는 서로 다른 RGB 색상이 몇 종류인지 카운트.
    # 픽셀아트: 수십~수백 (의도적으로 제한된 팔레트)
    # 실사 3D: 수십만~백만 이상 (연속적인 색상 그라디언트)
    #
    # 구현:
    #   img_rgb : BGR -> RGB 변환 (색상 의미를 직관적으로 유지)
    #   pixels  : shape (total_px, 3) 으로 reshape
    #   packed  : R*65536 + G*256 + B 로 각 픽셀을 단일 int64 로 패킹
    #             (채널당 0~255 이므로 범위 겹침 없음, 최대 16,777,215)
    #   np.unique: 고유값 추출 후 .size 로 카운트
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pixels  = img_rgb.reshape(-1, 3)
    packed  = (pixels[:, 0].astype(np.int64) * 65536
             + pixels[:, 1].astype(np.int64) * 256
             + pixels[:, 2].astype(np.int64))
    result['distinct_colors'] = int(np.unique(packed).size)

    # ══════════════════════════════════════════════════════════════════════
    # [논문 피처 5] reduced_palette_colors: 양자화 후 고유 색상 수
    # ══════════════════════════════════════════════════════════════════════
    # 논문 정의: "64색 팔레트로 줄인 후 고유 색상 수"
    # 논문은 K-means 를 명시하지 않음.
    #
    # K-means 미사용 이유:
    #   10,000 게임 x 5장 x K-means 수렴까지 수십 회 반복 = 수십 시간
    #
    # 대체 방법: 각 채널을 4의 배수로 양자화
    #   연산: (픽셀값 // 4) * 4
    #   결과: 각 채널이 0, 4, 8, ..., 252 의 64가지 값만 가짐
    #   예)  (123, 200,  77)
    #     -> (120, 200,  76)
    #   distinct_colors 와 동일한 패킹 방식으로 고유값 카운트.
    #   논문 의도(색 다양성 측정)를 동일하게 달성.
    quantized = (pixels // 4) * 4
    packed_q  = (quantized[:, 0].astype(np.int64) * 65536
               + quantized[:, 1].astype(np.int64) * 256
               + quantized[:, 2].astype(np.int64))
    result['reduced_palette_colors'] = int(np.unique(packed_q).size)

    # ══════════════════════════════════════════════════════════════════════
    # [추가 피처 1] edge_density: Canny 엣지 픽셀 비율 (%)
    # ══════════════════════════════════════════════════════════════════════
    # Canny edge detection: 이미지에서 경계선(엣지) 픽셀을 검출.
    # 결과(edges): 0(배경) 또는 255(엣지) 인 이진 이미지, shape (h, w)
    #
    # 매개변수:
    #   gray        : 그레이스케일 변환 이미지 (Canny 는 단채널 입력)
    #   threshold1=50 : 이 값 이하인 후보 엣지는 제거 (약한 엣지 기준)
    #   threshold2=150: 이 값 이상인 엣지는 강한 엣지로 확정
    #   두 값 사이   : 강한 엣지에 인접한 경우만 엣지로 인정 (hysteresis)
    #   50/150 : 일반적으로 가장 많이 쓰이는 표준 임계값 조합
    #
    # 엣지 픽셀 수 계산: edges.sum() / 255
    #   (엣지 픽셀값이 255 이므로 255 로 나누면 픽셀 개수가 됨)
    # 비율(%): 엣지 픽셀 수 / total_px * 100
    #
    # 높을수록: 경계선이 많고 복잡한 UI 또는 정밀한 그래픽
    # 낮을수록: 넓은 배경, 단순한 구성
    gray  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    result['edge_density'] = round(
        float(edges.sum() / 255) / total_px * 100, 4)

    # ══════════════════════════════════════════════════════════════════════
    # [추가 피처 2] brightness_std: 명도 표준편차
    # ══════════════════════════════════════════════════════════════════════
    # V 채널 전체 픽셀의 표준편차.
    # avg_value 가 '전체적인 밝기 수준' 이라면,
    # brightness_std 는 '밝은 곳과 어두운 곳의 차이가 얼마나 큰가' 를 측정.
    #
    # 높을수록: 밝은 영역과 어두운 영역이 함께 존재 (강한 명암 대비)
    #           -> 호러, 액션, 다크 판타지 게임에서 높게 나타남
    # 낮을수록: 전체적으로 균일한 밝기
    #           -> 캐주얼, 퍼즐, 미니멀리스트 게임에서 낮게 나타남
    result['brightness_std'] = round(float(V.std()), 4)

    # ══════════════════════════════════════════════════════════════════════
    # [추가 피처 3] warm_color_ratio: 따뜻한 색 비율 (%)
    # ══════════════════════════════════════════════════════════════════════
    # OpenCV H채널 0~179 와 실제 색상환 0~360 의 대응:
    #   OpenCV H = 실제 색상환 각도 / 2
    #
    # 따뜻한 색 범위:
    #   빨강/주황/노랑 = 실제 0~60도    -> OpenCV H 기준 0~30
    #   보라/분홍      = 실제 300~360도  -> OpenCV H 기준 150~179
    # 차가운 색 범위 = OpenCV H 기준 31~149 (초록, 파랑, 청록)
    #
    # warm_mask: 따뜻한 색에 해당하는 픽셀 위치가 True 인 bool array
    #   shape (h, w), dtype bool
    # warm_mask.sum(): True 픽셀 수 (= 따뜻한 색 픽셀 수)
    #
    # 활용:
    #   판타지/RPG: 따뜻한 색 비율 높은 경향
    #   SF/공포    : 차가운 색 비율 높은 경향 (= warm_color_ratio 낮음)
    warm_mask = (H <= 30) | (H >= 150)
    result['warm_color_ratio'] = round(
        float(warm_mask.sum()) / total_px * 100, 4)

    # ══════════════════════════════════════════════════════════════════════
    # [추가 피처 4] texture_complexity: Laplacian 분산
    # ══════════════════════════════════════════════════════════════════════
    # Laplacian 필터: 이미지의 2차 미분을 계산.
    # 엣지와 텍스처가 있는 곳에서 절댓값이 크고, 평탄한 영역에서는 0에 가까움.
    # 그 결과의 분산(variance) = 전체적인 텍스처 복잡도 지표.
    #
    # cv2.CV_64F 사용 이유:
    #   Laplacian 결과에는 음수값이 포함됨.
    #   출력 타입을 uint8 로 지정하면 음수가 0으로 잘려버림 (클리핑).
    #   -> 분산이 실제보다 훨씬 작게 계산되어 피처가 왜곡됨.
    #   float64(CV_64F) 로 받아야 음수까지 정확히 보존됨.
    #
    # 높을수록: 텍스처가 복잡하고 선명한 이미지
    # 낮을수록: 흐릿하거나 단색 배경 위주의 이미지
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    result['texture_complexity'] = round(float(laplacian.var()), 4)

    result['success']     = True
    result['fail_reason'] = ''
    return result


# ── resume: 이미 처리된 (appid, image_type) 로드 ──────────────────────────
# OUT_CSV 가 존재하면 처리된 (appid, image_type) 쌍을 집합으로 로드.
# 메인 루프에서 이 집합에 있는 항목은 건너뜀.
# -> 중단 후 재시작해도 중복 처리, 중복 행 발생 없음.
done_keys = set()
if os.path.exists(OUT_CSV):
    df_done = pd.read_csv(OUT_CSV, encoding='utf-8-sig',
                          usecols=['appid', 'image_type'])
    for _, row in df_done.iterrows():
        done_keys.add((str(row['appid']), row['image_type']))
    print(f"이미 처리: {len(done_keys):,}건  ->  재개 모드")

# ── AppID 목록 로드 ────────────────────────────────────────────────────────
# appids: 처리할 appid 문자열 리스트. 예) ['570', '730', '1091500', ...]
df_ids = pd.read_csv(APPID_CSV, encoding='utf-8-sig')
appids = df_ids['AppID'].astype(str).tolist()
print(f"전체 AppID: {len(appids):,}개  |  처리 이미지 최대: {len(appids)*5:,}장")

# ── CSV 출력 파일 열기 (append 모드) ──────────────────────────────────────
# 'a' 모드: 재시작 시 기존 내용 보존 + 새 행만 추가.
# done_keys 가 비어 있을 때(최초 실행)만 헤더 한 줄 작성.
csv_file = open(OUT_CSV, 'a', encoding='utf-8-sig', newline='')
writer   = csv.DictWriter(csv_file, fieldnames=ALL_COLS)
if len(done_keys) == 0:
    writer.writeheader()


# ── 메인 처리 루프 ────────────────────────────────────────────────────────
total_games = len(appids)
processed   = 0    # 이번 실행에서 처리한 이미지 수 (성공 + 실패 합산)
success_cnt = 0    # 피처 추출 성공 수
fail_cnt    = 0    # 피처 추출 실패 수 (파일 없음 포함)
start_time  = time.time()

for i, appid in enumerate(appids, 1):
    # img_paths: [(image_type, file_path), ...] 최대 5쌍
    img_paths = get_image_paths(appid)

    for img_type, img_path in img_paths:
        # resume 체크: 이미 처리된 항목 건너뜀
        if (appid, img_type) in done_keys:
            continue

        # 피처 추출
        feats = extract_features(img_path)

        # CSV 행 조립
        # image_type 값:
        #   "thumb"       : 썸네일 (Steam 헤더 이미지, 460x215px)
        #   "ss_0"~"ss_3" : 스크린샷 첫 번째~네 번째
        row = {
            "appid"       : appid,
            "image_type"  : img_type,
            "success"     : feats.pop("success"),
            "fail_reason" : feats.pop("fail_reason"),
        }
        row.update(feats)    # 피처 24개 추가
        writer.writerow(row)
        processed += 1

        if row["success"]:
            success_cnt += 1
        else:
            fail_cnt += 1

    # 게임 단위로 디스크에 기록.
    # flush 하지 않으면 메모리에만 쌓여 있다가 중단 시 마지막 버퍼가 손실됨.
    csv_file.flush()

    # 진행률 출력: 처음 5개 + 이후 100게임마다
    if i % 100 == 0 or i <= 5:
        elapsed      = time.time() - start_time
        avg_per_game = elapsed / i
        eta_sec      = avg_per_game * (total_games - i)
        print(f"[{i:>5}/{total_games}] appid={appid:<8}  "
              f"처리:{processed}  성공:{success_cnt}  실패:{fail_cnt}  "
              f"ETA {int(eta_sec//60)}m {int(eta_sec%60):02d}s")

csv_file.close()

print(f"\\n완료")
print(f"  처리: {processed:,}건  |  성공: {success_cnt:,}  |  실패: {fail_cnt:,}")
print(f"  저장: {OUT_CSV}")
print(f"  -> 08_feature_engineering.py 에서 pivot 해 게임별 피처 행렬 생성 예정")
print(f"     pivot 방식 옵션:")
print(f"       1) 평균   : thumb + ss_0~3 각 피처의 평균 -> 게임당 24개 피처")
print(f"       2) std    : 이미지 간 표준편차 추가       -> 게임당 48개 피처")
print(f"       3) 독립   : 이미지별 독립 컬럼            -> 게임당 120개 피처")
