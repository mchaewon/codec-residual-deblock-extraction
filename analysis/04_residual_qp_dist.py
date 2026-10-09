"""
04. QP 별 residual 분포 overlay (원본: HM/analysis/resi_dist.py 의 compare_qp_distributions_*)

<root>/<CODEC>/<scene>/QPxx/residual/*.yuv 를 QP 별로 모아 한 그래프에 히스토그램을 겹쳐 그림.
  <scene>_frame<k>_qp_overlay_hist.png          : density
  <scene>_frame<k>_qp_overlay_hist_log.png      : density, log y
  <scene>_frame<k>_qp_overlay_abs_hist_log.png  : |residual|, log y
추가로 QP 별 통계(0 비율, 표준편차, p99|r|, max|r|)를 출력한다.

예)
  python analysis/04_residual_qp_dist.py --codec HEVC --scene fern
  python analysis/04_residual_qp_dist.py --codec HEVC --all-scenes
"""

import argparse
import glob
import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from common.io_utils import CODECS, _DEFAULT_ROOT, read_residual_y, output_dir


def collect_values_from_residual_dir(residual_dir, width, height, codec, frame_index=0, pattern="*.yuv"):
    """residual_dir 안의 모든 yuv 에서 Y 를 읽어 values concat 반환"""
    yuv_files = sorted(glob.glob(os.path.join(residual_dir, pattern)))
    vals = []

    for fp in yuv_files:
        try:
            Y = read_residual_y(fp, width, height, codec, frame_index=frame_index)
        except ValueError:
            continue
        vals.append(Y.flatten())

    if len(vals) == 0:
        return None
    return np.concatenate(vals, axis=0)


def _qp_sorted(qp_to_values):
    return sorted(qp_to_values.items(), key=lambda x: int(x[0].replace("QP", "")))


def plot_qp_overlaid_hists(qp_to_values, out_dir, title_prefix, bins=400, dpi=100):
    """qp_to_values: dict { "QP22": np.ndarray, "QP27": np.ndarray, ... }"""
    os.makedirs(out_dir, exist_ok=True)

    # 모든 QP 공통 bin
    all_vals = np.concatenate(list(qp_to_values.values()), axis=0)
    vmin, vmax = float(all_vals.min()), float(all_vals.max())
    bin_edges = np.linspace(vmin, vmax, bins + 1)

    # 1) density
    plt.figure(figsize=(10, 6))
    for qp, vals in _qp_sorted(qp_to_values):
        plt.hist(vals, bins=bin_edges, histtype="step", linewidth=1.5, density=True, label=qp)
    plt.title(f"{title_prefix} - Residual Distribution (density)")
    plt.xlabel("Residual value")
    plt.ylabel("Density")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{title_prefix}_qp_overlay_hist.png"), dpi=dpi)
    plt.close()

    # 2) density, log y
    plt.figure(figsize=(10, 6))
    for qp, vals in _qp_sorted(qp_to_values):
        plt.hist(vals, bins=bin_edges, histtype="step", linewidth=1.5, density=True, label=qp)
    plt.yscale("log")
    plt.title(f"{title_prefix} - Residual Distribution (log y, density)")
    plt.xlabel("Residual value")
    plt.ylabel("Density (log)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{title_prefix}_qp_overlay_hist_log.png"), dpi=dpi)
    plt.close()

    # 3) |residual|, log y
    abs_all = np.abs(all_vals)
    abs_edges = np.linspace(0, float(abs_all.max()), bins + 1)

    plt.figure(figsize=(10, 6))
    for qp, vals in _qp_sorted(qp_to_values):
        plt.hist(np.abs(vals), bins=abs_edges, histtype="step", linewidth=1.5, density=True, label=qp)
    plt.yscale("log")
    plt.title(f"{title_prefix} - |Residual| Distribution (log y, density)")
    plt.xlabel("|Residual|")
    plt.ylabel("Density (log)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"{title_prefix}_qp_overlay_abs_hist_log.png"), dpi=dpi)
    plt.close()

    print(f"[Saved] Overlay plots -> {out_dir}")


def print_qp_stats(qp_to_values):
    for qp, v in _qp_sorted(qp_to_values):
        a = np.abs(v)
        print(f"  {qp}: zero={np.mean(v == 0)*100:5.1f}%  std={v.std():6.2f}  "
              f"p99|r|={np.percentile(a, 99):5.0f}  max|r|={a.max():5.0f}")


def compare_qp_distributions_for_category(codec_root, category, width, height, codec, out_dir,
                                          frame_index=0, bins=400, pattern="*.yuv", dpi=100):
    """codec_root/category/QPxx/residual/*.yuv 를 QP 별로 모아서 한 그래프에 overlay"""
    cat_path = os.path.join(codec_root, category)
    assert os.path.isdir(cat_path), f"Category not found: {cat_path}"

    qp_to_values = {}
    for qp in sorted(os.listdir(cat_path)):
        if not qp.startswith("QP"):
            continue
        residual_dir = os.path.join(cat_path, qp, "residual")
        if not os.path.isdir(residual_dir):
            continue

        vals = collect_values_from_residual_dir(residual_dir, width, height, codec,
                                                frame_index=frame_index, pattern=pattern)
        if vals is None:
            print(f"[Skip] No readable yuv in {category}/{qp}/residual")
            continue

        qp_to_values[qp] = vals
        print(f"[Load] {category}/{qp}: {vals.size} samples")

    if len(qp_to_values) < 2:
        print("[Warn] Need at least 2 QPs to compare.")
        return

    print_qp_stats(qp_to_values)
    title_prefix = f"{category}_frame{frame_index}"
    plot_qp_overlaid_hists(qp_to_values, out_dir=out_dir, title_prefix=title_prefix, bins=bins, dpi=dpi)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--codec", choices=CODECS, default="HEVC")
    p.add_argument("--root", default=None,
                   help="Compressed/<dataset> 폴더. 기본: HEVC=HM/Compressed/LLFF, VVC=VTM/Compressed/LLFF")
    p.add_argument("--scene", default="fern")
    p.add_argument("--all-scenes", action="store_true", help="root/<CODEC>/ 아래 모든 scene")
    p.add_argument("--width", type=int, default=1008)
    p.add_argument("--height", type=int, default=756)
    p.add_argument("--pattern", default="*.yuv",
                   help="residual 폴더 안에서 읽을 파일 (예: residual_0001.yuv 만 보려면 그 이름)")
    p.add_argument("--frame-index", type=int, default=0)
    p.add_argument("--bins", type=int, default=400)
    p.add_argument("--dpi", type=int, default=100)
    p.add_argument("--out-dir", default=None, help="기본: analysis/outputs/04_residual_qp_dist")
    args = p.parse_args()
    matplotlib.use("Agg")

    root = args.root or _DEFAULT_ROOT[args.codec]
    if root is None:
        raise SystemExit("--root 를 지정하세요")
    codec_root = os.path.join(root, args.codec)
    out_root = output_dir("04_residual_qp_dist", args.out_dir)

    scenes = sorted(d for d in os.listdir(codec_root) if os.path.isdir(os.path.join(codec_root, d))) \
        if args.all_scenes else [args.scene]
    for sc in scenes:
        compare_qp_distributions_for_category(codec_root, sc, args.width, args.height, args.codec,
                                              out_dir=os.path.join(out_root, sc),
                                              frame_index=args.frame_index, bins=args.bins,
                                              pattern=args.pattern, dpi=args.dpi)


if __name__ == "__main__":
    main()
