"""
01. Deblocking diff map 시각화 (원본: HM/analysis/deblock_diff.py)

diff = after_Y - before_Y  (deblocking filter 가 실제로 바꾼 값)
6 패널: before / after / |diff| / signed diff / 변경 픽셀 overlay / non-zero diff 히스토그램

예)
  python analysis/01_deblock_diff.py --codec HEVC --scene fern --qp 32 --poc 1
  python analysis/01_deblock_diff.py --before b.yuv --after a.yuv --width 1008 --height 756
"""

import argparse
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from common.io_utils import (add_common_args, resolve_inputs, read_deblock_y,
                             coded_size, output_dir, tag)


def visualize_diff(before_Y, after_Y, peak, title, out_path=None, show=False, dpi=150):
    height, width = before_Y.shape
    diff = after_Y.astype(np.int32) - before_Y.astype(np.int32)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"Deblocking Difference Map  |  {title}  |  Resolution={width}x{height}", fontsize=14)

    # 1. before
    axes[0][0].imshow(before_Y, cmap='gray', vmin=0, vmax=peak)
    axes[0][0].set_title("Before Deblocking (Y)")
    axes[0][0].axis('off')

    # 2. after
    axes[0][1].imshow(after_Y, cmap='gray', vmin=0, vmax=peak)
    axes[0][1].set_title("After Deblocking (Y)")
    axes[0][1].axis('off')

    # 3. |diff|
    diff_abs = np.abs(diff)
    axes[0][2].imshow(diff_abs, cmap='hot', vmin=0, vmax=diff_abs.max() if diff_abs.max() > 0 else 1)
    axes[0][2].set_title(f"Abs Difference (max={diff_abs.max()})")
    axes[0][2].axis('off')
    plt.colorbar(axes[0][2].images[0], ax=axes[0][2])

    # 4. signed diff
    vmax = max(abs(diff.min()), abs(diff.max()), 1)
    im = axes[1][0].imshow(diff, cmap='RdBu_r', vmin=-vmax, vmax=vmax)
    axes[1][0].set_title("Signed Difference (Red=+, Blue=-)")
    axes[1][0].axis('off')
    plt.colorbar(im, ax=axes[1][0])

    # 5. 변경된 픽셀 overlay  (원본은 vmax=1023 고정 -> bit depth 기준 peak 로 수정)
    mask = (diff != 0).astype(np.uint8) * 255
    axes[1][1].imshow(before_Y, cmap='gray', vmin=0, vmax=peak)
    axes[1][1].imshow(mask, cmap='Reds', alpha=0.5, vmin=0, vmax=255)
    axes[1][1].set_title(f"Changed Pixels on Image\n(changed: {mask.sum()//255} px, {mask.sum()//255 / (width*height) * 100:.2f}%)")
    axes[1][1].axis('off')

    # 6. non-zero diff 히스토그램
    nonzero_diff = diff[diff != 0]
    if len(nonzero_diff) > 0:
        axes[1][2].hist(nonzero_diff.flatten(), bins=50, color='steelblue', edgecolor='black')
        axes[1][2].set_title("Histogram of Non-zero Differences")
        axes[1][2].set_xlabel("Pixel Value Difference")
        axes[1][2].set_ylabel("Count")
        axes[1][2].axvline(0, color='red', linestyle='--')
    else:
        axes[1][2].text(0.5, 0.5, "No difference\n(Deblocking had no effect)",
                        ha='center', va='center', transform=axes[1][2].transAxes, fontsize=12)
        axes[1][2].set_title("Histogram of Differences")

    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=dpi, bbox_inches='tight')
        print(f"저장됨: {out_path}")
    if show:
        plt.show()
    plt.close(fig)

    print_stats(diff, peak)
    return diff


def print_stats(diff, peak):
    height, width = diff.shape
    print(f"\n[통계]")
    print(f"  차이 발생 픽셀 수 : {(diff != 0).sum()} / {width*height} ({(diff != 0).sum()/(width*height)*100:.2f}%)")
    print(f"  최대 차이         : {diff.max()}")
    print(f"  최소 차이         : {diff.min()}")
    print(f"  평균 절댓값 차이  : {np.abs(diff).mean():.4f}")
    print(f"  PSNR (Y, peak={peak}) : ", end="")
    mse = np.mean(diff.astype(np.float64)**2)
    if mse > 0:
        psnr = 10 * np.log10((peak**2) / mse)
        print(f"{psnr:.2f} dB")
    else:
        print("inf (차이 없음)")

    # 추가 통계: 변화량 빈도 / 부호 대칭 / 8 픽셀 격자 근처 집중도
    nz = diff[diff != 0]
    if nz.size:
        vals, cnts = np.unique(nz, return_counts=True)
        order = np.argsort(-cnts)[:8]
        print("  변화량 빈도 상위  : " + ", ".join(f"{int(vals[i]):+d}:{int(cnts[i])}" for i in order))
        print(f"  부호              : +{(nz > 0).sum()} / -{(nz < 0).sum()}")
        yy, xx = np.nonzero(diff)
        dx = np.minimum(xx % 8, 8 - xx % 8)
        dy = np.minimum(yy % 8, 8 - yy % 8)
        near = ((dx <= 2) | (dy <= 2)).mean() * 100
        print(f"  8px 격자선 ±2px 이내 비율 : {near:.2f}% (균일 분포라면 {(1 - (3/8)**2) * 100:.2f}%)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p, need_residual=False)
    p.add_argument("--no-crop", action="store_true",
                   help="크롭하지 않고 coded 크기 전체로 계산 (예: HEVC 1008x760)")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/01_deblock_diff")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--show", action="store_true")
    args = p.parse_args()
    if not args.show:
        matplotlib.use("Agg")

    paths = resolve_inputs(args)
    before_Y = read_deblock_y(paths["before"], args.width, args.height, args.codec, bit_depth=args.bit_depth, no_crop=args.no_crop)
    after_Y = read_deblock_y(paths["after"], args.width, args.height, args.codec, bit_depth=args.bit_depth, no_crop=args.no_crop)
    peak = (1 << args.bit_depth) - 1

    out = output_dir("01_deblock_diff", args.out_dir)
    suffix = "_coded" if args.no_crop else ""
    out_path = os.path.join(out, f"diff_map_{tag(args)}{suffix}.png")
    if args.no_crop:
        print(f"[Info] coded size {coded_size(args.width, args.height, args.codec)} 로 계산")
    visualize_diff(before_Y, after_Y, peak, f"{args.codec} {args.scene} QP{args.qp} POC={args.poc}",
                   out_path=out_path, show=args.show, dpi=args.dpi)


if __name__ == "__main__":
    main()
