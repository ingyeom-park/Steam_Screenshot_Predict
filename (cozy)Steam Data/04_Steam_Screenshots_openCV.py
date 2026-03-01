import os, csv
import cv2
import numpy as np

IMG_DIR = r"(cozy)Steam Data\03_Steam_Screenshot(4 each)"
OUT_DIR = r"(cozy)Steam Data\04_Steam_Screenshots_openCV"

os.makedirs(OUT_DIR, exist_ok=True)


def colorfulness(img):
    b, g, r = cv2.split(img.astype(np.float32))
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(np.var(rg) + np.var(yb)) + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2))


def entropy(gray):
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    p    = hist / (hist.sum() + 1e-12)
    p    = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def extract_features(img):
    h, w    = img.shape[:2]
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bright  = float(np.mean(gray))
    cont    = float(np.std(gray))
    sharp   = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges   = cv2.Canny(gray, 100, 200)
    edge    = float(np.mean(edges > 0))
    hsv     = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue     = float(np.mean(hsv[:, :, 0]))
    sat     = float(np.mean(hsv[:, :, 1]))
    col     = colorfulness(img)
    ent     = entropy(gray)
    return w, h, bright, cont, sharp, edge, hue, sat, col, ent


def aggregate(vals):
    if len(vals) == 0:
        return [""]
    arr = np.array(vals, dtype=np.float64)
    return [float(np.mean(arr))]

apps = sorted([d for d in os.listdir(IMG_DIR) if os.path.isdir(f"{IMG_DIR}/{d}")], key=lambda f: int(f))

img_rows  = []
game_rows = []

for idx, appid in enumerate(apps, 1):
    vals = {k: [] for k in ["w", "h", "bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"]}
    valid_count = 0

    for i in range(4):
        img_path = f"{IMG_DIR}/{appid}/ss_{i}.jpg"
        if not os.path.exists(img_path):
            img_rows.append([appid, i, img_path, 0] + [""] * 10)
            continue

        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            img_rows.append([appid, i, img_path, 0] + [""] * 10)
            continue

        w, h, bright, cont, sharp, edge, hue, sat, col, ent = extract_features(img)
        img_rows.append([appid, i, img_path, 1, w, h, bright, cont, sharp, edge, hue, sat, col, ent])

        for k, v in zip(vals.keys(), [w, h, bright, cont, sharp, edge, hue, sat, col, ent]):
            vals[k].append(v)
        valid_count += 1

    row = [appid, valid_count]
    for k in ["w", "h", "bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"]:
        row += aggregate(vals[k])
    game_rows.append(row)

    print(f"{idx}/{len(apps)} {appid} valid={valid_count}")


img_csv  = f"{OUT_DIR}/cv_features_per_image.csv"
game_csv = f"{OUT_DIR}/cv_features_per_game.csv"

with open(img_csv, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["appid", "ss_i", "path", "ok",
                     "w", "h", "bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"])
    writer.writerows(img_rows)

with open(game_csv, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    head   = ["appid", "num_ok"]
    for k in ["w", "h", "bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"]:
        head += [f"{k}_mean"]
    writer.writerow(head)
    writer.writerows(game_rows)

print("saved:", img_csv)
print("saved:", game_csv)