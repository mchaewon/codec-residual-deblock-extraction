"""
07. Residual |r| 의 DoG(Difference of Gaussians) 파라미터 sweep (원본: HM/analysis/DoG_normal.py)

조합 (p, sigma1, sigma2, gamma) 마다
  abs01 = |r| / quantile(p)  ->  |G(sigma1) - G(sigma2)| / max  ->  ^gamma
를 만들고
  edge  = Sobel magnitude 평균                 (클수록 경계가 강함)
  grid  = FFT 에서 주기 8/16/32 축 주파수 주변 에너지 / 평균 (클수록 블록 격자 성분이 강함)
  score = edge - w_grid * grid
로 순위를 매겨 상위 topk png 와 summary csv 를 저장.

예)
  python analysis/07_residual_dog_sweep.py --codec HEVC --scene fern --qp 42 --poc 1
"""

import argparse
import itertools
import os

import numpy as np
import cv2

from common.io_utils import add_common_args, resolve_inputs, read_residual_y, output_dir


# ============================
# map 생성
# ============================

def robust_abs01(Y, p=99.0, eps=1e-6):
    s = np.percentile(np.abs(Y), p) + eps
    return np.clip(np.abs(Y).astype(np.float32) / s, 0.0, 1.0)


def dog_abs(abs01, sigma1=1.0, sigma2=2.5, eps=1e-6):
    a = abs01.astype(np.float32)
    g1 = cv2.GaussianBlur(a, (0, 0), sigma1)
    g2 = cv2.GaussianBlur(a, (0, 0), sigma2)
    dog = g1 - g2
    A = np.abs(dog)
    A = A / (A.max() + eps)  # 0..1
    return A


def tone_gamma(A01, gamma=0.7):
    return np.clip(A01, 0.0, 1.0) ** float(gamma)


def save_01_as_png(A01, path):
    img = (np.clip(A01, 0.0, 1.0) * 255.0).astype(np.uint8)
    cv2.imwrite(path, img)


# ============================
# 점수
# ============================

def edge_score(A01):
    """에지 점수: Sobel magnitude 평균 (클수록 경계가 강함)"""
    a = A01.astype(np.float32)
    gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    return float(mag.mean())


def _ring_energy(Fmag, cy, cx, y, x, r):
    """FFT magnitude에서 (y,x) 주변 반경 r 원의 평균 에너지"""
    H, W = Fmag.shape
    yy, xx = np.ogrid[:H, :W]
    dist2 = (yy - y) ** 2 + (xx - x) ** 2
    mask = dist2 <= (r * r)
    if mask.sum() == 0:
        return 0.0
    return float(Fmag[mask].mean())


def grid_score_fft(A01, periods=(8, 16, 32), radius=3, eps=1e-9):
    """
    블록(격자) 점수: 주기 p에 해당하는 축 주파수 위치(±W/p,0)와 (0,±H/p) 주변의 에너지 합
    클수록 격자 성분이 강함 (나쁨)
    """
    a = A01.astype(np.float32)
    H, W = a.shape
    F = np.fft.fftshift(np.fft.fft2(a))
    Fmag = np.abs(F).astype(np.float32)

    # DC 주변 제거
    cy, cx = H // 2, W // 2
    Fmag[cy-1:cy+2, cx-1:cx+2] = 0.0

    total = 0.0
    for p in periods:
        dx = int(round(W / p))
        dy = int(round(H / p))
        if dx > 0 and 0 <= cx - dx < W and 0 <= cx + dx < W:
            total += _ring_energy(Fmag, cy, cx, cy, cx - dx, radius)
            total += _ring_energy(Fmag, cy, cx, cy, cx + dx, radius)
        if dy > 0 and 0 <= cy - dy < H and 0 <= cy + dy < H:
            total += _ring_energy(Fmag, cy, cx, cy - dy, cx, radius)
            total += _ring_energy(Fmag, cy, cx, cy + dy, cx, radius)

    # 전체 평균으로 정규화
    denom = float(Fmag.mean()) + eps
    return float(total / denom)


def combined_score(edge, grid, w_grid=1.0):
    """
    최종 점수: edge는 크고, grid는 작을수록 좋게
    score = edge - w_grid * grid
    """
    return float(edge - w_grid * grid)


# ============================
# sweep
# ============================

def sweep_dog_params(Y, base, out_dir,
                     p_list=(98.5, 99.0, 99.5),
                     sigma1_list=(0.8, 1.0, 1.2),
                     sigma2_list=(1.6, 2.0, 2.5, 3.0),
                     gamma_list=(0.5, 0.7, 0.9),
                     periods=(8, 16, 32),
                     fft_radius=3,
                     w_grid=1.0,
                     topk=12,
                     save_all=False):
    os.makedirs(out_dir, exist_ok=True)

    # 조합 (sigma2 > sigma1 만)
    combos = []
    for p, s1, s2, g in itertools.product(p_list, sigma1_list, sigma2_list, gamma_list):
        if s2 <= s1:
            continue
        combos.append((p, s1, s2, g))

    results = []
    vis_dir = os.path.join(out_dir, f"{base}_sweep")
    if save_all:
        os.makedirs(vis_dir, exist_ok=True)

    for idx, (p, s1, s2, g) in enumerate(combos):
        abs01 = robust_abs01(Y, p=p)
        dog01 = dog_abs(abs01, sigma1=s1, sigma2=s2)
        dog01 = tone_gamma(dog01, gamma=g)

        e = edge_score(dog01)
        gr = grid_score_fft(dog01, periods=periods, radius=fft_radius)
        sc = combined_score(e, gr, w_grid=w_grid)

        tag = f"p{p}_s1{s1}_s2{s2}_g{g}".replace(".", "p")
        if save_all:
            save_01_as_png(dog01, os.path.join(vis_dir, f"{idx:04d}_{tag}.png"))

        results.append({
            "idx": idx,
            "p": p, "sigma1": s1, "sigma2": s2, "gamma": g,
            "edge": e,
            "grid": gr,
            "score": sc,
            "tag": tag,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    top_dir = os.path.join(out_dir, f"{base}_TOP{topk}")
    os.makedirs(top_dir, exist_ok=True)

    csv_path = os.path.join(out_dir, f"{base}_sweep_summary.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("rank,idx,p,sigma1,sigma2,gamma,edge,grid,score,tag\n")
        for r, item in enumerate(results[:topk], start=1):
            f.write(f"{r},{item['idx']},{item['p']},{item['sigma1']},{item['sigma2']},{item['gamma']},"
                    f"{item['edge']:.8f},{item['grid']:.8f},{item['score']:.8f},{item['tag']}\n")

    for r, item in enumerate(results[:topk], start=1):
        abs01 = robust_abs01(Y, p=item["p"])
        dog01 = dog_abs(abs01, sigma1=item["sigma1"], sigma2=item["sigma2"])
        dog01 = tone_gamma(dog01, gamma=item["gamma"])

        name = f"rank{r:02d}_score{item['score']:.4f}_edge{item['edge']:.4f}_grid{item['grid']:.4f}_{item['tag']}.png"
        save_01_as_png(dog01, os.path.join(top_dir, name))

    print(f"\n[Done] Sweep finished: {len(results)} configs")
    print(f"Saved: {csv_path}")
    print(f"TopK images: {top_dir}\n")
    for i, item in enumerate(results[:topk], start=1):
        print(f"#{i} score={item['score']:.4f}  edge={item['edge']:.4f}  grid={item['grid']:.4f}  "
              f"p={item['p']} s1={item['sigma1']} s2={item['sigma2']} g={item['gamma']}")

    return results, csv_path, top_dir


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p, need_deblock=False)
    p.add_argument("--p-list", type=float, nargs="+", default=[98.5, 99.0, 99.5])
    p.add_argument("--sigma1-list", type=float, nargs="+", default=[0.8, 1.0, 1.2])
    p.add_argument("--sigma2-list", type=float, nargs="+", default=[1.6, 2.0, 2.5, 3.0])
    p.add_argument("--gamma-list", type=float, nargs="+", default=[0.5, 0.7, 0.9])
    p.add_argument("--periods", type=int, nargs="+", default=[8, 16, 32])
    p.add_argument("--fft-radius", type=int, default=3)
    p.add_argument("--w-grid", type=float, default=1.0, help="grid 억제를 더 중요시하면 1.5~3.0")
    p.add_argument("--topk", type=int, default=12)
    p.add_argument("--save-all", action="store_true", help="모든 조합 이미지 저장 (용량 큼)")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/07_residual_dog_sweep/<scene>")
    args = p.parse_args()

    yuv = resolve_inputs(args)["residual"]
    Y = read_residual_y(yuv, args.width, args.height, args.codec)
    out = output_dir(os.path.join("07_residual_dog_sweep", args.scene), args.out_dir)
    base = f"{args.codec}_QP{args.qp}_{os.path.splitext(os.path.basename(yuv))[0]}"

    sweep_dog_params(Y, base, out,
                     p_list=tuple(args.p_list), sigma1_list=tuple(args.sigma1_list),
                     sigma2_list=tuple(args.sigma2_list), gamma_list=tuple(args.gamma_list),
                     periods=tuple(args.periods), fft_radius=args.fft_radius,
                     w_grid=args.w_grid, topk=args.topk, save_all=args.save_all)


if __name__ == "__main__":
    main()
