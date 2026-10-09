"""
03. Residual (Y) 시각화
  - 기본      : signed residual 을 max|r| 로 [-1,1] 정규화한 png + 원본 npy + 통계
                (원본: HM/analysis/visual.py)
  - --variants: |r| 를 p=99.5 분위수로 정규화한 뒤 signed / abs / DoG / Sobel / Laplacian /
                wavelet-high 6종 png (원본: HM/analysis/resi_dist.py 의 visualize_residual_variants)

예)
  python analysis/03_residual_visual.py --codec HEVC --scene trex --qp 32 --poc 1
  python analysis/03_residual_visual.py --residual-dir HM/Compressed/LLFF/HEVC/room/QP22/residual --variants
"""

import argparse
import glob
import os

import numpy as np
import cv2

from common.io_utils import (add_common_args, resolve_inputs, read_residual_y,
                             robust_scale_abs, output_dir)


# ============================
# 기본: signed residual png + npy + 통계  (visual.py)
# ============================

def save_residual_visualizations(Y, output_prefix):
    """Residual Y 를 npy 와 [-max,max]->[0,255] png 로 저장하고 통계 출력"""
    np.save(f"{output_prefix}.npy", Y.astype(np.int16))  # 디코더 출력과 같은 int16
    print(f"Saved: {output_prefix}.npy")

    max_val = np.max(np.abs(Y))
    if max_val == 0:
        Y_vis = np.zeros_like(Y, dtype=np.uint8) + 128
    else:
        Y_norm = (Y.astype(np.float32) / max_val)  # [-1, 1]
        Y_vis = ((Y_norm + 1) * 127.5).astype(np.uint8)  # [0, 255]

    cv2.imwrite(f"{output_prefix}.png", Y_vis)
    print(f"Saved: {output_prefix}.png")

    print(f"\n=== Statistics ===")
    print(f"Shape: {Y.shape}")
    print(f"Min: {Y.min()}")
    print(f"Max: {Y.max()}")
    print(f"Mean: {Y.mean():.2f}")
    print(f"Std: {Y.std():.2f}")
    print(f"Non-zero pixels: {np.count_nonzero(Y)} / {Y.size} ({np.count_nonzero(Y)/Y.size*100:.2f}%)")


# ============================
# --variants  (resi_dist.py)
# ============================

def to_uint8_signed(Y, s):
    # [-s, s] -> [0, 255]
    Yc = np.clip(Y, -s, s).astype(np.float32) / s
    return ((Yc + 1.0) * 127.5).astype(np.uint8)


def to_uint8_01(A01):
    # [0, 1] -> [0, 255]
    A01 = np.clip(A01, 0.0, 1.0)
    return (A01 * 255.0).astype(np.uint8)


def normalize_abs01(Y, s):
    # |Y| / s -> [0, 1]
    return np.clip(np.abs(Y).astype(np.float32) / s, 0.0, 1.0)


def dog_map(abs01, sigma1=1.0, sigma2=2.5):
    a = to_uint8_01(abs01)
    g1 = cv2.GaussianBlur(a, (0, 0), sigma1)
    g2 = cv2.GaussianBlur(a, (0, 0), sigma2)
    dog = (g1.astype(np.float32) - g2.astype(np.float32))
    dog = dog / (np.max(np.abs(dog)) + 1e-6)  # [-1,1]
    dog_vis = ((dog + 1.0) * 127.5).astype(np.uint8)
    return dog, dog_vis


def sobel_map(abs01):
    a = to_uint8_01(abs01)
    gx = cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    mag01 = mag / (mag.max() + 1e-6)
    return mag01, to_uint8_01(mag01)


def laplacian_map(abs01):
    a = to_uint8_01(abs01)
    lap = cv2.Laplacian(a, cv2.CV_32F, ksize=3)
    lap = lap / (np.max(np.abs(lap)) + 1e-6)  # [-1,1]
    lap_vis = ((lap + 1.0) * 127.5).astype(np.uint8)
    return lap, lap_vis


def wavelet_high_map(abs01):
    # 1-level 근사: 1/2 다운샘플 후 업샘플한 low 를 빼서 high 성분만
    a = abs01.astype(np.float32)
    low = cv2.resize(a, (a.shape[1]//2, a.shape[0]//2), interpolation=cv2.INTER_AREA)
    low_up = cv2.resize(low, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_LINEAR)
    high = a - low_up
    high = high / (np.max(np.abs(high)) + 1e-6)  # [-1,1]
    high_vis = ((high + 1.0) * 127.5).astype(np.uint8)
    return high, high_vis


def save_residual_variants(Y, out_dir, base):
    s = robust_scale_abs(Y, p=99.5)
    signed_vis = to_uint8_signed(Y, s)               # signed residual
    abs01 = normalize_abs01(Y, s)                    # |res| in [0,1]
    abs_vis = to_uint8_01(abs01)

    _, dog_vis = dog_map(abs01)
    _, sobel_vis = sobel_map(abs01)
    _, lap_vis = laplacian_map(abs01)
    _, wav_vis = wavelet_high_map(abs01)

    cv2.imwrite(os.path.join(out_dir, f"{base}_signed.png"), signed_vis)
    cv2.imwrite(os.path.join(out_dir, f"{base}_abs.png"), abs_vis)
    cv2.imwrite(os.path.join(out_dir, f"{base}_dog.png"), dog_vis)
    cv2.imwrite(os.path.join(out_dir, f"{base}_sobel.png"), sobel_vis)
    cv2.imwrite(os.path.join(out_dir, f"{base}_lap.png"), lap_vis)
    cv2.imwrite(os.path.join(out_dir, f"{base}_wavehigh.png"), wav_vis)
    print("[Saved]", base)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p, need_deblock=False)
    p.add_argument("--residual-dir", default=None, help="이 폴더의 residual_*.yuv 전부 처리 (주면 --residual 무시)")
    p.add_argument("--variants", action="store_true", help="DoG/Sobel/Laplacian/wavelet-high 변형 png 도 저장")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/03_residual_visual")
    args = p.parse_args()

    if args.residual_dir:
        files = sorted(glob.glob(os.path.join(args.residual_dir, "residual_*.yuv")))
    else:
        files = [resolve_inputs(args)["residual"]]

    out = output_dir("03_residual_visual", args.out_dir)
    for fp in files:
        base = f"{args.codec}_{os.path.splitext(os.path.basename(fp))[0]}"
        if not args.residual_dir:
            base = f"{args.codec}_{args.scene}_QP{args.qp}_{os.path.splitext(os.path.basename(fp))[0]}"
        print(f"Reading Y component from: {fp}")
        Y = read_residual_y(fp, args.width, args.height, args.codec)
        save_residual_visualizations(Y, os.path.join(out, base))
        if args.variants:
            save_residual_variants(Y, out, base)
    print("\nDone!")


if __name__ == "__main__":
    main()
