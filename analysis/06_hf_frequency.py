"""
06. Residual / Deblock diff / Pure texture 의 고주파(HF) 성분 비교 (원본: HM/analysis/fft_heat.py)

입력 맵 (05 와 같은 정규화 + smoothing)
  residual_smooth = gaussian(|r| / q99.5, sigma=0.5)
  deblock_smooth  = gaussian(log1p|d| / q99.9, sigma=2.0)
  pure_texture    = clip(residual_smooth - deblock_smooth, 0, 1)
HF 추출 4가지 (각 결과는 |hf| / q99.5 로 0~1 정규화)
  fft         : FFT soft high-pass mask (cutoff=0.8, transition=0.1) -> IFFT
  wavelet     : wavedec2(haar, level=2) 에서 approximation 을 0 으로 -> waverec2
  laplacian   : scipy.ndimage.laplace
  gaussian_hp : x - gaussian(x, sigma=1.5)
출력: hf_{residual,deblock,pure_texture}_{method}.npy + hf_method_comparison_<tag>.png

analysis/samples/hf_deblock.npy, hf_residual.npy 는 이 스크립트의 wavelet 결과와 같다
(HEVC fern QP32 POC=1, all-intra). 재생성:
  python analysis/06_hf_frequency.py --codec HEVC --scene fern --qp 32 --poc 1 --export-samples analysis/samples
"""

import argparse
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter, laplace
import pywt

from common.io_utils import (add_common_args, resolve_inputs, read_residual_y, read_deblock_y,
                             normalize_dblk, normalize_residual_abs, normalize_map, output_dir, tag)

METHODS = ["fft", "wavelet", "laplacian", "gaussian_hp"]


def compute_fft_magnitude(signal_2d):
    fft = np.fft.fft2(signal_2d)
    fft_shift = np.fft.fftshift(fft)
    mag = np.log1p(np.abs(fft_shift))
    return mag / (mag.max() + 1e-6)


# ============================
# HF 추출 함수들
# ============================

def make_soft_hf_mask(H, W, cutoff=0.3, transition=0.1):
    cy, cx = H // 2, W // 2
    max_r = min(cy, cx)
    y_idx, x_idx = np.mgrid[0:H, 0:W]
    dist_norm = np.sqrt((y_idx - cy) ** 2 + (x_idx - cx) ** 2) / max_r
    mask = np.clip((dist_norm - cutoff) / transition + 0.5, 0, 1)
    return mask.astype(np.float32)


def extract_hf_only_fft(signal_2d, cutoff=0.3, transition=0.1):
    H, W = signal_2d.shape
    fft = np.fft.fft2(signal_2d)
    fft_shift = np.fft.fftshift(fft)
    mask = make_soft_hf_mask(H, W, cutoff, transition)
    fft_hf = fft_shift * mask
    hf_spatial = np.fft.ifft2(np.fft.ifftshift(fft_hf)).real
    return normalize_map(hf_spatial, p=99.5)


def extract_hf_only_wavelet(signal_2d, wavelet="haar", level=2):
    signal_2d = signal_2d.astype(np.float32)
    coeffs = pywt.wavedec2(signal_2d, wavelet=wavelet, level=level)

    # approximation(저주파) 계수만 0 으로, detail 계수는 그대로
    hf_coeffs = [np.zeros_like(coeffs[0], dtype=np.float32)]
    for detail in coeffs[1:]:
        cH, cV, cD = detail
        hf_coeffs.append((cH, cV, cD))

    hf_spatial = pywt.waverec2(hf_coeffs, wavelet=wavelet)

    H, W = signal_2d.shape
    hf_spatial = hf_spatial[:H, :W]
    return normalize_map(hf_spatial, p=99.5)


def extract_hf_only_laplacian(signal_2d):
    signal_2d = signal_2d.astype(np.float32)
    hf_spatial = laplace(signal_2d)
    return normalize_map(hf_spatial, p=99.5)


def extract_hf_only_gaussian_hp(signal_2d, sigma=1.5):
    signal_2d = signal_2d.astype(np.float32)
    low = gaussian_filter(signal_2d, sigma=sigma)
    hf_spatial = signal_2d - low
    return normalize_map(hf_spatial, p=99.5)


def extract_hf_map(signal_2d, method, cfg):
    if method == "fft":
        return extract_hf_only_fft(signal_2d, cutoff=cfg.cutoff, transition=cfg.transition)
    elif method == "wavelet":
        return extract_hf_only_wavelet(signal_2d, wavelet=cfg.wavelet, level=cfg.level)
    elif method == "laplacian":
        return extract_hf_only_laplacian(signal_2d)
    elif method == "gaussian_hp":
        return extract_hf_only_gaussian_hp(signal_2d, sigma=cfg.sigma)
    else:
        raise ValueError(f"Unsupported HF extraction method: {method}")


# ============================
# 공통 입력 맵 / 방법별 맵
# ============================

def build_base_maps(residual_raw, before_Y, after_Y):
    deblock_diff_raw = after_Y - before_Y

    residual_norm = normalize_residual_abs(residual_raw, p=99.5)
    deblock_norm = normalize_dblk(deblock_diff_raw, p=99.9)

    residual_smooth = gaussian_filter(residual_norm, sigma=0.5)
    deblock_smooth = gaussian_filter(deblock_norm, sigma=2.0)

    pure_texture = np.clip(residual_smooth - deblock_smooth, 0, 1)

    return {
        "residual_smooth": residual_smooth,
        "deblock_smooth": deblock_smooth,
        "pure_texture": pure_texture,
        "fft_residual": compute_fft_magnitude(residual_smooth),
        "fft_deblock": compute_fft_magnitude(deblock_smooth),
        "fft_pure_texture": compute_fft_magnitude(pure_texture),
    }


def build_method_maps(base_maps, method, cfg):
    hf_residual = extract_hf_map(base_maps["residual_smooth"], method, cfg)
    hf_deblock = extract_hf_map(base_maps["deblock_smooth"], method, cfg)
    hf_pure_texture = extract_hf_map(base_maps["pure_texture"], method, cfg)

    return {
        "hf_residual": hf_residual,
        "hf_deblock": hf_deblock,
        "hf_pure_texture": hf_pure_texture,
        "fft_hf_residual": compute_fft_magnitude(hf_residual),
        "fft_hf_deblock": compute_fft_magnitude(hf_deblock),
        "fft_hf_pure": compute_fft_magnitude(hf_pure_texture),
    }


def save_method_maps(method, maps, out_dir):
    for key in ["hf_residual", "hf_deblock", "hf_pure_texture"]:
        save_path = os.path.join(out_dir, f"{key}_{method}.npy")
        np.save(save_path, maps[key].astype(np.float32))
        print(f"[Saved] {save_path}")


# ============================
# 시각화
# ============================

def draw_panel(ax, data, title, cmap="hot", xlabel=None):
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, format="%.2f")
    cbar.ax.yaxis.set_tick_params(color="white", labelcolor="white")

    ax.set_title(title, color="white", fontsize=9, fontweight="bold", pad=5)
    if xlabel:
        ax.set_xlabel(xlabel, color="#aaaaaa", fontsize=7)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#444444")
    ax.set_facecolor("#1a1a1a")


def visualize_comparison(base_maps, all_method_maps, cfg, save_path, show=False, dpi=150):
    methods = list(all_method_maps.keys())

    fig = plt.figure(figsize=(18, 4.8 * (len(methods) + 1)), facecolor="#0e0e0e")
    fig.suptitle(
        f"HF Extraction Method Comparison\n"
        f"(FFT cutoff={cfg.cutoff}, transition={cfg.transition} | "
        f"Wavelet={cfg.wavelet}, level={cfg.level} | "
        f"GaussianHP sigma={cfg.sigma})",
        fontsize=14, color="white", y=0.995, fontweight="bold"
    )

    # row0: original residual/deblock/pure/fft(pure)
    # row1~: each method with hf_residual / hf_deblock / hf_pure / fft(hf_pure)
    gs = gridspec.GridSpec(len(methods) + 1, 4, figure=fig, hspace=0.35, wspace=0.18)

    originals = [
        ("residual_smooth", "Original Residual"),
        ("deblock_smooth", "Original Deblock Diff"),
        ("pure_texture", "Original Pure Texture"),
        ("fft_pure_texture", "Original Pure Texture FFT"),
    ]
    for col, (key, title) in enumerate(originals):
        ax = fig.add_subplot(gs[0, col])
        cmap = "inferno" if "fft" in key else "hot"
        draw_panel(ax, base_maps[key], title, cmap=cmap)

    for row, method in enumerate(methods, start=1):
        mm = all_method_maps[method]

        if method == "fft":
            subtitle = f"FFT\ncutoff={cfg.cutoff}"
        elif method == "wavelet":
            subtitle = f"Wavelet\n{cfg.wavelet}, L{cfg.level}"
        elif method == "laplacian":
            subtitle = "Laplacian"
        else:
            subtitle = f"Gaussian HP\nsigma={cfg.sigma}"

        row_items = [
            ("hf_residual", f"{subtitle}\nHF Residual", "hot"),
            ("hf_deblock", f"{subtitle}\nHF Deblock", "hot"),
            ("hf_pure_texture", f"{subtitle}\nHF Pure Texture", "hot"),
            ("fft_hf_pure", f"{subtitle}\nHF Pure Texture FFT", "inferno"),
        ]
        for col, (key, title, cmap) in enumerate(row_items):
            ax = fig.add_subplot(gs[row, col])
            draw_panel(ax, mm[key], title, cmap=cmap)

    # stats text
    stats_ax = fig.add_axes([0.01, 0.005, 0.98, 0.03])
    stats_ax.axis("off")

    def stat_str(arr):
        return f"mean={arr.mean():.3f}, std={arr.std():.3f}, cov>0.1={(arr > 0.1).mean()*100:.1f}%"

    stats_lines = []
    for method in methods:
        mm = all_method_maps[method]
        stats_lines.append(
            f"{method}: "
            f"R[{stat_str(mm['hf_residual'])}]  "
            f"D[{stat_str(mm['hf_deblock'])}]  "
            f"P[{stat_str(mm['hf_pure_texture'])}]"
        )
    stats_ax.text(0.5, 0.5, "\n".join(stats_lines), ha="center", va="center",
                  color="#cccccc", fontsize=8, transform=stats_ax.transAxes)

    plt.tight_layout(rect=[0.03, 0.05, 1, 0.985])
    plt.savefig(save_path, dpi=dpi, bbox_inches="tight", facecolor="#0e0e0e")
    print(f"[Saved] {save_path}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(p)
    p.add_argument("--methods", nargs="+", choices=METHODS, default=METHODS)
    p.add_argument("--cutoff", type=float, default=0.8, help="FFT HF cutoff (0~1, 반경 비율)")
    p.add_argument("--transition", type=float, default=0.1, help="FFT soft mask transition")
    p.add_argument("--wavelet", default="haar")
    p.add_argument("--level", type=int, default=2, help="wavelet level")
    p.add_argument("--sigma", type=float, default=1.5, help="Gaussian HP sigma")
    p.add_argument("--export-samples", default=None, metavar="DIR",
                   help="--sample-method 결과를 DIR/hf_residual.npy, hf_deblock.npy 로도 저장")
    p.add_argument("--sample-method", choices=METHODS, default="wavelet")
    p.add_argument("--no-figure", action="store_true")
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/06_hf_frequency/<tag>")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--show", action="store_true")
    args = p.parse_args()
    if not args.show:
        matplotlib.use("Agg")

    paths = resolve_inputs(args)
    out = output_dir(os.path.join("06_hf_frequency", tag(args)), args.out_dir)

    print(f"[Config] size={args.width}x{args.height}")
    print(f"[FFT] cutoff={args.cutoff}, transition={args.transition}")
    print(f"[Wavelet] wavelet={args.wavelet}, level={args.level}")
    print(f"[Gaussian HP] sigma={args.sigma}")

    residual = read_residual_y(paths["residual"], args.width, args.height, args.codec)
    before_Y = read_deblock_y(paths["before"], args.width, args.height, args.codec, bit_depth=args.bit_depth)
    after_Y = read_deblock_y(paths["after"], args.width, args.height, args.codec, bit_depth=args.bit_depth)
    base_maps = build_base_maps(residual, before_Y, after_Y)

    methods = list(args.methods)
    if args.export_samples and args.sample_method not in methods:
        methods.append(args.sample_method)

    all_method_maps = {}
    for method in methods:
        print(f"\n[Running] {method}")
        mm = build_method_maps(base_maps, method, args)
        all_method_maps[method] = mm
        save_method_maps(method, mm, out)

        for key in ["hf_residual", "hf_deblock", "hf_pure_texture"]:
            d = mm[key]
            print(f"  {method:12s} {key:18s}: mean={d.mean():.4f}, std={d.std():.4f}, "
                  f"coverage(>0.1)={(d > 0.1).mean() * 100:.1f}%")
        r, d = mm["hf_residual"].mean(), mm["hf_deblock"].mean()
        print(f"  {method:12s} mean(hf_deblock)/mean(hf_residual) = {d / (r + 1e-12):.3f}")

    if args.export_samples:
        os.makedirs(args.export_samples, exist_ok=True)
        mm = all_method_maps[args.sample_method]
        for key in ("hf_residual", "hf_deblock"):
            path = os.path.join(args.export_samples, f"{key}.npy")
            np.save(path, mm[key].astype(np.float32))
            print(f"[Saved] {path}  ({args.sample_method})")

    if not args.no_figure:
        visualize_comparison(base_maps, {m: all_method_maps[m] for m in args.methods}, args,
                             os.path.join(out, f"hf_method_comparison_{tag(args)}.png"),
                             show=args.show, dpi=args.dpi)


if __name__ == "__main__":
    main()
