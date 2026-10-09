# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.colors as mcolors

# def load_yuv(path, width, height):
#     data = np.fromfile(path, dtype=np.uint8)
#     Y  = data[:width*height].reshape(height, width)
#     # Cb = data[width*height : width*height + (width//2)*(height//2)].reshape(height//2, width//2)
#     # Cr = data[width*height + (width//2)*(height//2):].reshape(height//2, width//2)
#     return Y

# def visualize_diff(before_path, after_path, width, height, poc=0, save=True):
#     before_Y= load_yuv(before_path, width, height)
#     after_Y = load_yuv(after_path,  width, height)

#     diff = after_Y.astype(np.int32) - before_Y.astype(np.int32)
    
#     fig, axes = plt.subplots(2, 3, figsize=(18, 10))
#     fig.suptitle(f"Deblocking Difference Map  |  POC={poc}  |  Resolution={width}x{height}", fontsize=14)

#     # 1. Deblocking 전 (Y채널)
#     before_vis = np.clip(before_Y, 0, 255).astype(np.uint8)
#     axes[0][0].imshow(before_vis, cmap='gray', vmin=0, vmax=255)
#     axes[0][0].set_title("Before Deblocking (Y)")
#     axes[0][0].axis('off')

#     # 2. Deblocking 후 (Y채널)
#     after_vis = np.clip(after_Y, 0, 255).astype(np.uint8)
#     axes[0][1].imshow(after_vis, cmap='gray', vmin=0, vmax=255)
#     axes[0][1].set_title("After Deblocking (Y)")
#     axes[0][1].axis('off')

#     # 3. Difference map (절댓값, 증폭)
#     diff_abs = np.abs(diff)
#     axes[0][2].imshow(diff_abs, cmap='hot', vmin=0, vmax=diff_abs.max() if diff_abs.max() > 0 else 1)
#     axes[0][2].set_title(f"Abs Difference (max={diff_abs.max()})")
#     axes[0][2].axis('off')
#     plt.colorbar(axes[0][2].images[0], ax=axes[0][2])

#     # 4. Difference map (부호 포함, diverging colormap)
#     vmax = max(abs(diff.min()), abs(diff.max()), 1)
#     im = axes[1][0].imshow(diff, cmap='RdBu_r', vmin=-vmax, vmax=vmax)
#     axes[1][0].set_title("Signed Difference (Red=+, Blue=-)")
#     axes[1][0].axis('off')
#     plt.colorbar(im, ax=axes[1][0])

#     # 5. Difference가 발생한 영역만 마스크로 표시
#     mask = (diff != 0).astype(np.uint8) * 255
#     axes[1][1].imshow(before_Y, cmap='gray', vmin=0, vmax=1023)
#     axes[1][1].imshow(mask, cmap='Reds', alpha=0.5, vmin=0, vmax=255)
#     axes[1][1].set_title(f"Changed Pixels on Image\n(changed: {mask.sum()//255} px, {mask.sum()//255 / (width*height) * 100:.2f}%)")
#     axes[1][1].axis('off')

#     # 6. Difference 히스토그램
#     nonzero_diff = diff[diff != 0]
#     if len(nonzero_diff) > 0:
#         axes[1][2].hist(nonzero_diff.flatten(), bins=50, color='steelblue', edgecolor='black')
#         axes[1][2].set_title("Histogram of Non-zero Differences")
#         axes[1][2].set_xlabel("Pixel Value Difference")
#         axes[1][2].set_ylabel("Count")
#         axes[1][2].axvline(0, color='red', linestyle='--')
#     else:
#         axes[1][2].text(0.5, 0.5, "No difference\n(Deblocking had no effect)",
#                         ha='center', va='center', transform=axes[1][2].transAxes, fontsize=12)
#         axes[1][2].set_title("Histogram of Differences")

#     plt.tight_layout()

#     if save:
#         out_path = f"diff_map_poc{poc}.png"
#         plt.savefig(out_path, dpi=150, bbox_inches='tight')
#         print(f"저장됨: {out_path}")

#     plt.show()

#     # 통계 출력
#     print(f"\n[POC {poc} 통계]")
#     print(f"  차이 발생 픽셀 수 : {(diff != 0).sum()} / {width*height} ({(diff != 0).sum()/(width*height)*100:.2f}%)")
#     print(f"  최대 차이         : {diff.max()}")
#     print(f"  최소 차이         : {diff.min()}")
#     print(f"  평균 절댓값 차이  : {np.abs(diff).mean():.4f}")
#     print(f"  PSNR (Y)          : ", end="")
#     mse = np.mean(diff.astype(np.float64)**2)
#     if mse > 0:
#         psnr = 10 * np.log10((1023**2) / mse)
#         print(f"{psnr:.2f} dB")
#     else:
#         print("inf (차이 없음)")


# # =====================
# # 실행 예시
# # =====================
# if __name__ == "__main__":
#     WIDTH  = 1008   # ← 실제 해상도로 변경
#     HEIGHT = 768   # ← 실제 해상도로 변경
#     POC    = 3      # ← 보고 싶은 POC 번호

#     visualize_diff(
#         before_path=f"./deblock/before/deblock_000{POC}.yuv",
#         after_path =f"./deblock/after/deblock_000{POC}.yuv",
#         width=WIDTH,
#         height=HEIGHT,
#         poc=POC,
#         save=True
#     )




import os
import re
import glob
import numpy as np
import matplotlib.pyplot as plt

# 파일명 패턴: deblock_0001.yuv
_DEBLOCK_RE = re.compile(r"^deblock_(\d+)\.yuv$")

def load_yuv420p8_y_only(path, width, height):
    """
    YUV420p 8-bit 파일에서 Y 채널만 로드
    """
    data = np.fromfile(path, dtype=np.uint8)
    need = width * height
    if data.size < need:
        return None
    Y = data[:need].reshape(height, width)
    return Y

def visualize_diff_once(before_path, after_path, width, height, poc, save_path=None, show=False):
    """
    before/after 한 쌍의 deblock yuv에 대해 diff 시각화 + 통계
    (Y 채널만 사용)
    """
    before_Y = load_yuv420p8_y_only(before_path, width, height)
    after_Y  = load_yuv420p8_y_only(after_path,  width, height)
    if before_Y is None or after_Y is None:
        print(f"[Skip] size mismatch: {before_path} / {after_path}")
        return None

    diff = after_Y.astype(np.int32) - before_Y.astype(np.int32)
    diff_abs = np.abs(diff)

    # --- figure ---
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"Deblocking Difference Map | POC={poc} | {width}x{height}", fontsize=14)

    axes[0, 0].imshow(before_Y, cmap="gray", vmin=0, vmax=255)
    axes[0, 0].set_title("Before Deblocking (Y)")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(after_Y, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title("After Deblocking (Y)")
    axes[0, 1].axis("off")

    im2 = axes[0, 2].imshow(diff_abs, cmap="hot", vmin=0, vmax=max(int(diff_abs.max()), 1))
    axes[0, 2].set_title(f"Abs Difference (max={int(diff_abs.max())})")
    axes[0, 2].axis("off")
    plt.colorbar(im2, ax=axes[0, 2])

    vmax = max(int(abs(diff.min())), int(abs(diff.max())), 1)
    im3 = axes[1, 0].imshow(diff, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    axes[1, 0].set_title("Signed Difference (Red=+, Blue=-)")
    axes[1, 0].axis("off")
    plt.colorbar(im3, ax=axes[1, 0])

    mask = (diff != 0).astype(np.uint8) * 255
    axes[1, 1].imshow(before_Y, cmap="gray", vmin=0, vmax=255)
    axes[1, 1].imshow(mask, cmap="Reds", alpha=0.5, vmin=0, vmax=255)
    changed = int((diff != 0).sum())
    axes[1, 1].set_title(f"Changed Pixels Overlay\n(changed: {changed} px, {changed/(width*height)*100:.2f}%)")
    axes[1, 1].axis("off")

    nonzero_diff = diff[diff != 0]
    if nonzero_diff.size > 0:
        axes[1, 2].hist(nonzero_diff.flatten(), bins=50, color="steelblue", edgecolor="black")
        axes[1, 2].set_title("Histogram of Non-zero Differences")
        axes[1, 2].set_xlabel("Pixel Value Difference")
        axes[1, 2].set_ylabel("Count")
        axes[1, 2].axvline(0, color="red", linestyle="--")
    else:
        axes[1, 2].text(0.5, 0.5, "No difference\n(Deblocking had no effect)",
                        ha="center", va="center", transform=axes[1, 2].transAxes, fontsize=12)
        axes[1, 2].set_title("Histogram of Differences")

    plt.tight_layout()

    if save_path is not None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        # print(f"[Saved] {save_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)

    # --- stats ---
    mse = float(np.mean(diff.astype(np.float64) ** 2))
    psnr = float("inf") if mse == 0 else 10.0 * np.log10((255.0 ** 2) / mse)

    stats = {
        "changed_px": changed,
        "changed_pct": changed / (width * height) * 100.0,
        "diff_max": int(diff.max()),
        "diff_min": int(diff.min()),
        "abs_mean": float(np.abs(diff).mean()),
        "mse": mse,
        "psnr_y": psnr,
    }
    return stats

def parse_poc_from_filename(path):
    name = os.path.basename(path)
    m = _DEBLOCK_RE.match(name)
    if not m:
        return None
    return int(m.group(1))

def process_all_scenes_qps(base_dir, width, height, out_root="./deblock_diff_vis", show=False):

    before_dir = os.path.join(base_dir, "before")
    after_dir  = os.path.join(base_dir, "after")

    before_files = sorted(glob.glob(os.path.join(before_dir, "deblock_*.yuv")))
  
    for bf in before_files:
        poc = parse_poc_from_filename(bf)
        if poc is None:
            continue
        af = os.path.join(after_dir, f"deblock_{poc:04d}.yuv")
        if not os.path.exists(af):
            print(f"[Warn] missing after: {af}")
            continue

        save_path = os.path.join(out_root, f"diff_map_{poc:04d}.png")
        stats = visualize_diff_once(bf, af, width, height, poc, save_path=save_path, show=show)

        if stats is None:
            continue
        psnr_val = stats['psnr_y']
        if psnr_val == float('inf'):
            psnr_str = "inf"
        else:
            psnr_str = f"{psnr_val:.2f} dB"

        print(
            f"  POC {poc:04d} | changed {stats['changed_px']} ({stats['changed_pct']:.2f}%) "
            f"| max {stats['diff_max']} min {stats['diff_min']} "
            f"| abs_mean {stats['abs_mean']:.4f} "
            f"| PSNR(Y) {psnr_str}"
        )
# =====================
# 실행
# =====================
if __name__ == "__main__":
    BASE_DIR = "./deblock_ra"  # scene들이 있는 폴더
    WIDTH  = 1008
    HEIGHT = 768  # 너 스크린샷 기준 756이 맞아 보여서 760 -> 756로 권장

    process_all_scenes_qps(
        base_dir=BASE_DIR,
        width=WIDTH,
        height=HEIGHT,
        out_root="./deblock_ra/deblock_diff_vis",
        show=False  # True면 매번 창 띄움 (매우 느림)
    )
