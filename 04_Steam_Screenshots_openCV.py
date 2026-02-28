import os, csv
import cv2
import numpy as np

IMG_DIR = "(cozy)Steam Data/screenshot(4 each)"
OUT_DIR = "(cozy)Steam Data/openCV"


os.makedirs(OUT_DIR, exist_ok=True)

def colorfulness(img):
    b, g, r = cv2.split(img.astype(np.float32))
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(np.var(rg) + np.var(yb)) + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2))

def entropy(gray):
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    p = hist / (hist.sum() + 1e-12)
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())

def feats(img):
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    bright = float(np.mean(g))
    cont = float(np.std(g))
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())

    e = cv2.Canny(g, 100, 200)
    edge = float(np.mean(e > 0))

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue = float(np.mean(hsv[:, :, 0]))
    sat = float(np.mean(hsv[:, :, 1]))

    col = colorfulness(img)
    ent = entropy(g)

    return w, h, bright, cont, sharp, edge, hue, sat, col, ent

apps = [d for d in os.listdir(IMG_DIR) if os.path.isdir(f"{IMG_DIR}/{d}")]
apps = sorted(apps, key=lambda x: int(x))

img_rows = []
game_rows = []

for idx, appid in enumerate(apps, 1):
    vals = {
        "w": [], "h": [], "bright": [], "cont": [], "sharp": [],
        "edge": [], "hue": [], "sat": [], "col": [], "ent": []
    }

    ok = 0

    for i in range(4):
        p = f"{IMG_DIR}/{appid}/ss_{i}.jpg"
        if not os.path.exists(p):
            img_rows.append([appid, i, p, 0] + [""] * 10)
            continue

        img = cv2.imread(p, cv2.IMREAD_COLOR)
        if img is None:
            img_rows.append([appid, i, p, 0] + [""] * 10)
            continue

        w, h, bright, cont, sharp, edge, hue, sat, col, ent = feats(img)
        img_rows.append([appid, i, p, 1, w, h, bright, cont, sharp, edge, hue, sat, col, ent])

        vals["w"].append(w); vals["h"].append(h)
        vals["bright"].append(bright); vals["cont"].append(cont); vals["sharp"].append(sharp)
        vals["edge"].append(edge); vals["hue"].append(hue); vals["sat"].append(sat)
        vals["col"].append(col); vals["ent"].append(ent)
        ok += 1

    def agg(a):
        if len(a) == 0:
            return ["", "", "", ""]
        a = np.array(a, dtype=np.float64)
        return [float(np.mean(a)), float(np.median(a)), float(np.min(a)), float(np.max(a))]

    row = [appid, ok]
    for k in ["w","h","bright","cont","sharp","edge","hue","sat","col","ent"]:
        row += agg(vals[k])
    game_rows.append(row)

    print(f"{idx}/{len(apps)} {appid} ok={ok}")

img_csv = f"{OUT_DIR}/cv_features_per_image.csv"
game_csv = f"{OUT_DIR}/cv_features_per_game.csv"

open(img_csv, "w", encoding="utf-8-sig", newline="").write("")
open(game_csv, "w", encoding="utf-8-sig", newline="").write("")

with open(img_csv, "a", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["appid", "ss_i", "path", "ok",
                "w", "h", "bright", "cont", "sharp", "edge", "hue", "sat", "col", "ent"])
    for r in img_rows:
        w.writerow(r)

with open(game_csv, "a", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    head = ["appid", "num_ok"]
    for k in ["w","h","bright","cont","sharp","edge","hue","sat","col","ent"]:
        head += [f"{k}_mean", f"{k}_med", f"{k}_min", f"{k}_max"]
    w.writerow(head)
    for r in game_rows:
        w.writerow(r)

print("saved:", img_csv)
print("saved:", game_csv)