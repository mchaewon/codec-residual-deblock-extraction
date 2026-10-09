"""
05. Residual map x Deblock diff map : 교집합(blocking artifact 후보) / 차(pure texture)
(원본: HM/analysis/visual_diff_resi_deblock.py, v2)

- normalize_dblk         : log1p + quantile(p=99.9)    (deblock diff)
- normalize_residual_abs : abs + quantile(p=99.5)      (residual)
- smooth                 : residual sigma=0.5, deblock sigma=2.0 (gaussian)
- pure_texture           = clip(R - D, 0, 1)
- soft_intersection      = R * D / max
- hard_intersection      = (R > thr_r) & (D > thr_d)

residual(크롭 크기)과 deblock(coded 크기)은 io_utils 에서 같은 표시 크기로 맞춘 뒤 계산한다.

예)
  python analysis/05_residual_deblock_intersection.py --codec HEVC --scene fern --qp 32 --poc 1
"""

import argparse
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter

from common.io_utils import (add_common_args, resolve_inputs, read_residual_y, read_deblock_y,
                             normalize_dblk, normalize_residual_abs, output_dir, tag)


# ============================
# 맵 생성
# ============================

def build_maps(residual_raw, before_Y, after_Y, thr_r=0.3, thr_d=0.3, sigma_r=0.5, sigma_d=2.0):
    deblock_diff_raw = after_Y - before_Y  # 부호 있는 차

    # residual: abs + quantile
    residual_norm = normalize_residual_abs(residual_raw, p=99.5)
    # deblock diff: log1p + quantile
    deblock_norm = normalize_dblk(deblock_diff_raw, p=99.9)

    # smoothing (residual 은 약하게, deblock 은 경계 주변으로 넓게)
    residual_smooth = gaussian_filter(residual_norm, sigma=sigma_r)
    deblock_smooth = gaussian_filter(deblock_norm, sigma=sigma_d)

    # 차: residual 에서 deblock(blocking) 성분을 뺀 순수 텍스처
    pure_texture = residual_smooth - deblock_smooth
    pure_texture = np.clip(pure_texture, 0, 1)

    # soft 교집합: 두 map 의 곱
    soft_intersection = residual_smooth * deblock_smooth
    soft_intersection = soft_intersection / (soft_intersection.max() + 1e-6)

    # hard 교집합: threshold
    hard_intersection = (
        (residual_smooth > thr_r) &
        (deblock_smooth > thr_d)
    ).astype(np.float32)

    return {
        "residual_raw":      residual_raw,
        "residual_norm":     residual_smooth,
        "deblock_diff_raw":  deblock_diff_raw,
        "deblock_diff_norm": deblock_smooth,
        "pure_texture":      pure_texture,
        "soft_intersection": soft_intersection,
        "hard_intersection": hard_intersection,
        "before_Y":          before_Y,
        "after_Y":           after_Y,
    }


# ============================
# 시각화
# ============================

def visualize(maps, thr_r, thr_d, peak=255, save_path=None, show=False, dpi=150):
    fig = plt.figure(figsize=(22, 16), facecolor='#0e0e0e')
    fig.suptitle(
        "Residual & Deblock Diff Map Analysis  "
        "[Residual: abs+quantile(p=99.5) | Deblock: log1p+quantile(p=99.9)]",
        fontsize=13, color='white', y=0.99, fontweight='bold'
    )

    gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.4, wspace=0.15)

    # 그림 라벨은 기본 폰트(DejaVu)에 한글 글리프가 없어 영어로 표기
    panels = [
        # row 0: 원본
        (0, 0, "before_Y",         "Before Deblocking (Y)",              "gray",   "Y before deblocking"),
        (0, 1, "after_Y",          "After Deblocking (Y)",               "gray",   "Y after deblocking"),
        (0, 2, "deblock_diff_raw", "Deblock Diff (raw)",                 "RdBu_r", "after - before (signed)"),
        (0, 3, "residual_raw",     "Residual (raw)",                     "RdBu_r", "decoded residual (signed)"),
        # row 1: 정규화
        (1, 0, "deblock_diff_norm", "Deblock Diff\n[log1p+quantile]",    "hot",    "normalize_dblk"),
        (1, 1, "residual_norm",    "Residual\n[abs+quantile]",           "hot",    "normalize_residual_abs"),
        # row 2: 차 / 교집합
        (2, 0, "pure_texture",     "Pure Texture\n(Residual - Deblock)", "hot",    "residual minus deblock (texture)"),
        (2, 1, "soft_intersection", "Soft Intersection\n(R × D)",        "hot",    "blocking-artifact strength proxy"),
        (2, 2, "hard_intersection", "Hard Intersection\n(R>thr & D>thr)", "hot",   f"threshold ({thr_r}/{thr_d}) intersection"),
    ]

    for row, col, key, title, cmap, desc in panels:
        ax = fig.add_subplot(gs[row, col])
        data = maps[key]

        if key in ("deblock_diff_raw", "residual_raw"):
            vmax = np.percentile(np.abs(data), 99)
            im = ax.imshow(data, cmap=cmap, vmin=-vmax, vmax=vmax)
        elif key in ("before_Y", "after_Y"):
            # 원본은 vmax=1 이라 0..255 영상이 거의 흰색으로 포화됨 -> bit depth peak 로 수정
            im = ax.imshow(data, cmap=cmap, vmin=0, vmax=peak)
        else:
            im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1)

        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                     format='%.2f').ax.yaxis.set_tick_params(color='white', labelcolor='white')

        ax.set_title(title, color='white', fontsize=9.5, fontweight='bold', pad=5)
        ax.set_xlabel(desc, color='#aaaaaa', fontsize=7.5)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_edgecolor('#444444')
        ax.set_facecolor('#1a1a1a')

    # 설명 패널
    note_ax = fig.add_subplot(gs[1, 2:])
    note_ax.axis('off')
    note_text = (
        "normalize_dblk  (deblock diff)\n"
        "  -> log1p(|x|) / quantile(p=99.9)\n"
        "  -> compresses extremes, keeps weak edges\n\n"
        "normalize_residual_abs  (residual)\n"
        "  -> |x| / quantile(p=99.5)\n"
        "  -> linear ratio of residual magnitude\n\n"
        f"Hard threshold: R>{thr_r}, D>{thr_d}"
    )
    note_ax.text(0.05, 0.95, note_text, ha='left', va='top',
                 color='#cccccc', fontsize=9, fontfamily='monospace',
                 transform=note_ax.transAxes,
                 bbox=dict(boxstyle='round', facecolor='#1a1a1a', edgecolor='#444444', alpha=0.8))

    # 통계
    stats_ax = fig.add_axes([0.01, 0.005, 0.98, 0.03])
    stats_ax.axis('off')
    r = maps["residual_norm"]
    d = maps["deblock_diff_norm"]
    t = maps["pure_texture"]
    s = maps["soft_intersection"]
    h = maps["hard_intersection"]
    stats_text = (
        f"Residual norm: mean={r.mean():.3f}, max={r.max():.3f}  |  "
        f"Deblock norm: mean={d.mean():.3f}, max={d.max():.3f}  |  "
        f"Pure Texture: mean={t.mean():.3f}  |  "
        f"Soft Intersection: mean={s.mean():.3f}  |  "
        f"Hard Intersection: coverage={h.mean()*100:.1f}%"
    )
    stats_ax.text(0.5, 0.5, stats_text, ha='center', va='center',
                  color='#cccccc', fontsize=8.5, transform=stats_ax.transAxes)

    plt.tight_layout(rect=[0, 0.03, 1, 0.98])

    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight', facecolor='#0e0e0e')
        print(f"[Saved] {save_path}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p)
    p.add_argument("--thr-r", type=float, default=0.3, help="hard intersection residual threshold")
    p.add_argument("--thr-d", type=float, default=0.3, help="hard intersection deblock threshold")
    p.add_argument("--sigma-r", type=float, default=0.5)
    p.add_argument("--sigma-d", type=float, default=2.0)
    p.add_argument("--save-npy", action="store_true", help="pure_texture / soft / hard map 을 npy 로도 저장")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/05_residual_deblock_intersection")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--show", action="store_true")
    args = p.parse_args()
    if not args.show:
        matplotlib.use("Agg")

    paths = resolve_inputs(args)
    print(f"[Config] codec={args.codec}, size={args.width}x{args.height}")
    for k, v in paths.items():
        print(f"[Load] {k:8s} : {v}")

    residual = read_residual_y(paths["residual"], args.width, args.height, args.codec)
    before_Y = read_deblock_y(paths["before"], args.width, args.height, args.codec, bit_depth=args.bit_depth)
    after_Y = read_deblock_y(paths["after"], args.width, args.height, args.codec, bit_depth=args.bit_depth)

    maps = build_maps(residual, before_Y, after_Y, args.thr_r, args.thr_d, args.sigma_r, args.sigma_d)

    print("\n[Stats]")
    print(f"  residual_norm     : mean={maps['residual_norm'].mean():.4f}, max={maps['residual_norm'].max():.4f}")
    print(f"  deblock_diff_norm : mean={maps['deblock_diff_norm'].mean():.4f}, max={maps['deblock_diff_norm'].max():.4f}")
    print(f"  pure_texture      : mean={maps['pure_texture'].mean():.4f}, max={maps['pure_texture'].max():.4f}")
    print(f"  soft_intersection : mean={maps['soft_intersection'].mean():.4f}, max={maps['soft_intersection'].max():.4f}")
    print(f"  hard_intersection : coverage={maps['hard_intersection'].mean()*100:.2f}%")

    out = output_dir("05_residual_deblock_intersection", args.out_dir)
    if args.save_npy:
        for key in ("pure_texture", "soft_intersection", "hard_intersection"):
            np.save(os.path.join(out, f"{key}_{tag(args)}.npy"), maps[key].astype(np.float32))
    visualize(maps, args.thr_r, args.thr_d, peak=(1 << args.bit_depth) - 1, save_path=os.path.join(out, f"map_visualization_{tag(args)}.png"),
              show=args.show, dpi=args.dpi)


if __name__ == "__main__":
    main()
