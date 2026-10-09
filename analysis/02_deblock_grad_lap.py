"""
02. Deblock diff map 의 Sobel gradient / Laplacian (원본: HM/analysis/deblock_grad.py)

D = |after_Y - before_Y| 에 대해 Sobel X/Y, gradient magnitude, Laplacian 을 계산해
개별 png + heatmap + 2x4 summary figure 로 저장.

예)
  python analysis/02_deblock_grad_lap.py --codec HEVC --scene fern --qp 32 --poc 1
"""

import argparse
import os

import numpy as np
import cv2
import matplotlib
import matplotlib.pyplot as plt

from common.io_utils import add_common_args, resolve_inputs, read_deblock_y, output_dir, tag


def normalize_for_vis(x):
    """시각화용 0~255 min-max 정규화"""
    x = x.astype(np.float32)
    x_min = x.min()
    x_max = x.max()

    if x_max - x_min < 1e-8:
        return np.zeros_like(x, dtype=np.uint8)

    x_norm = (x - x_min) / (x_max - x_min)
    return (x_norm * 255.0).clip(0, 255).astype(np.uint8)


def save_gray_image(path, img):
    cv2.imwrite(path, img)


def save_heatmap_image(path, img, cmap="jet"):
    plt.figure(figsize=(8, 6))
    plt.imshow(img, cmap=cmap)
    plt.colorbar()
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight", pad_inches=0.1)
    plt.close()


def compute_grad_lap(D):
    """
    D: deblocking diff map = |after_Y - before_Y|
    Sobel gradient / Laplacian 계산
    """
    D = D.astype(np.float32)

    # 주의:
    # axis=0/1 기준 scipy sobel과 달리,
    # cv2.Sobel은 dx=1이면 x방향(가로), dy=1이면 y방향(세로)
    gx = cv2.Sobel(D, cv2.CV_32F, dx=1, dy=0, ksize=3)
    gy = cv2.Sobel(D, cv2.CV_32F, dx=0, dy=1, ksize=3)

    grad_mag = np.sqrt(gx ** 2 + gy ** 2)

    lap = cv2.Laplacian(D, cv2.CV_32F, ksize=3)
    lap_abs = np.abs(lap)

    grad_mean = grad_mag.mean()
    lap_mean = lap_abs.mean()

    return gx, gy, grad_mag, lap, lap_abs, grad_mean, lap_mean


def visualize_all(before_y, after_y, D, gx, gy, grad_mag, lap, lap_abs, save_dir, prefix="sample", dpi=200):
    os.makedirs(save_dir, exist_ok=True)

    before_vis = normalize_for_vis(before_y)
    after_vis = normalize_for_vis(after_y)
    D_vis = normalize_for_vis(D)
    gx_vis = normalize_for_vis(np.abs(gx))
    gy_vis = normalize_for_vis(np.abs(gy))
    grad_mag_vis = normalize_for_vis(grad_mag)
    lap_vis = normalize_for_vis(lap)
    lap_abs_vis = normalize_for_vis(lap_abs)

    # 개별 gray png
    save_gray_image(os.path.join(save_dir, f"{prefix}_before_y.png"), before_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_after_y.png"), after_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_diff_map.png"), D_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_gx_abs.png"), gx_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_gy_abs.png"), gy_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_grad_mag.png"), grad_mag_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_lap_signed.png"), lap_vis)
    save_gray_image(os.path.join(save_dir, f"{prefix}_lap_abs.png"), lap_abs_vis)

    # heatmap
    save_heatmap_image(os.path.join(save_dir, f"{prefix}_grad_mag_heatmap.png"), grad_mag, cmap="jet")
    save_heatmap_image(os.path.join(save_dir, f"{prefix}_lap_abs_heatmap.png"), lap_abs, cmap="jet")

    # summary
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))

    axes[0, 0].imshow(before_vis, cmap="gray")
    axes[0, 0].set_title("Before Deblock (Y)")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(after_vis, cmap="gray")
    axes[0, 1].set_title("After Deblock (Y)")
    axes[0, 1].axis("off")

    axes[0, 2].imshow(D_vis, cmap="gray")
    axes[0, 2].set_title("D = |After - Before|")
    axes[0, 2].axis("off")

    axes[0, 3].imshow(grad_mag, cmap="jet")
    axes[0, 3].set_title("Gradient Magnitude")
    axes[0, 3].axis("off")

    axes[1, 0].imshow(gx_vis, cmap="gray")
    axes[1, 0].set_title("|Sobel X|")
    axes[1, 0].axis("off")

    axes[1, 1].imshow(gy_vis, cmap="gray")
    axes[1, 1].set_title("|Sobel Y|")
    axes[1, 1].axis("off")

    axes[1, 2].imshow(lap, cmap="bwr")
    axes[1, 2].set_title("Laplacian (signed)")
    axes[1, 2].axis("off")

    axes[1, 3].imshow(lap_abs, cmap="jet")
    axes[1, 3].set_title("|Laplacian|")
    axes[1, 3].axis("off")

    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, f"{prefix}_summary.png"), dpi=dpi, bbox_inches="tight")
    plt.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p, need_residual=False)
    p.add_argument("--frame-index", type=int, default=0, help="yuv 안의 프레임 index (디코더 출력은 파일당 1프레임)")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/02_deblock_grad_lap")
    p.add_argument("--dpi", type=int, default=200)
    args = p.parse_args()
    matplotlib.use("Agg")

    paths = resolve_inputs(args)
    print(f"Before YUV size: {os.path.getsize(paths['before'])}, After YUV size: {os.path.getsize(paths['after'])}")

    before_y = read_deblock_y(paths["before"], args.width, args.height, args.codec, args.frame_index, args.bit_depth)
    after_y = read_deblock_y(paths["after"], args.width, args.height, args.codec, args.frame_index, args.bit_depth)

    # Deblocking diff map
    D = np.abs(after_y.astype(np.int32) - before_y.astype(np.int32)).astype(np.float32)

    # Gradient / Laplacian
    gx, gy, grad_mag, lap, lap_abs, grad_mean, lap_mean = compute_grad_lap(D)

    print(f"[INFO] before_y shape      : {before_y.shape}, dtype={before_y.dtype}")
    print(f"[INFO] after_y shape       : {after_y.shape}, dtype={after_y.dtype}")
    print(f"[INFO] D shape             : {D.shape}, dtype={D.dtype}")
    print(f"[INFO] grad_mag.mean()     : {grad_mean:.6f}")
    print(f"[INFO] |laplace(D)|.mean() : {lap_mean:.6f}")

    save_dir = output_dir("02_deblock_grad_lap", args.out_dir)
    visualize_all(before_y, after_y, D, gx, gy, grad_mag, lap, lap_abs,
                  save_dir=save_dir, prefix=tag(args), dpi=args.dpi)
    print(f"[INFO] 저장 완료: {save_dir}")


if __name__ == "__main__":
    main()
