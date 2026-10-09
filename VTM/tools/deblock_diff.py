# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.colors as mcolors

# def load_yuv(path, width, height):
#     data = np.fromfile(path, dtype=np.uint8)
#     Y  = data[:width*height].reshape(height, width)
#     Cb = data[width*height : width*height + (width//2)*(height//2)].reshape(height//2, width//2)
#     Cr = data[width*height + (width//2)*(height//2):].reshape(height//2, width//2)
#     return Y, Cb, Cr

# def visualize_diff(before_path, after_path, width, height, poc=0, save=True):
#     before_Y, _, _ = load_yuv(before_path, width, height)
#     after_Y,  _, _ = load_yuv(after_path,  width, height)

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
#     HEIGHT = 760   # ← 실제 해상도로 변경
#     POC    = 1      # ← 보고 싶은 POC 번호

#     visualize_diff(
#         before_path=f"./deblock_output/before/deblock_000{POC}.yuv",
#         after_path =f"./deblock_output/after/deblock_000{POC}.yuv",
#         width=WIDTH,
#         height=HEIGHT,
#         poc=POC,
#         save=True
#     )



import numpy as np
import matplotlib.pyplot as plt

def load_yuv(path, width, height, bit_depth=10):
    dtype = np.uint16 if bit_depth > 8 else np.uint8
    max_val = (1 << bit_depth) - 1

    data = np.fromfile(path, dtype=dtype)
    Y  = data[:width*height].reshape(height, width)
    Cb = data[width*height : width*height + (width//2)*(height//2)].reshape(height//2, width//2)
    Cr = data[width*height + (width//2)*(height//2):].reshape(height//2, width//2)
    return Y, Cb, Cr, max_val

def visualize_diff(before_path, after_path, width, height, poc=0, bit_depth=10, save=True):
    max_val = (1 << bit_depth) - 1

    before_Y, _, _, _ = load_yuv(before_path, width, height, bit_depth)
    after_Y,  _, _, _ = load_yuv(after_path,  width, height, bit_depth)

    diff = after_Y.astype(np.int32) - before_Y.astype(np.int32)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(f"Deblocking Difference Map  |  POC={poc}  |  Resolution={width}x{height}  |  {bit_depth}bit", fontsize=14)

    # 1. Before (Y)
    before_vis = (before_Y.astype(np.float32) / max_val * 255).astype(np.uint8)
    axes[0][0].imshow(before_vis, cmap='gray', vmin=0, vmax=255)
    axes[0][0].set_title("Before Deblocking (Y)")
    axes[0][0].axis('off')

    # 2. After (Y)
    after_vis = (after_Y.astype(np.float32) / max_val * 255).astype(np.uint8)
    axes[0][1].imshow(after_vis, cmap='gray', vmin=0, vmax=255)
    axes[0][1].set_title("After Deblocking (Y)")
    axes[0][1].axis('off')

    # 3. Abs Difference
    diff_abs = np.abs(diff)
    axes[0][2].imshow(diff_abs, cmap='hot', vmin=0, vmax=diff_abs.max() if diff_abs.max() > 0 else 1)
    axes[0][2].set_title(f"Abs Difference (max={diff_abs.max()})")
    axes[0][2].axis('off')
    plt.colorbar(axes[0][2].images[0], ax=axes[0][2])

    # 4. Signed Difference
    vmax = max(abs(diff.min()), abs(diff.max()), 1)
    im = axes[1][0].imshow(diff, cmap='RdBu_r', vmin=-vmax, vmax=vmax)
    axes[1][0].set_title("Signed Difference (Red=+, Blue=-)")
    axes[1][0].axis('off')
    plt.colorbar(im, ax=axes[1][0])

    # 5. Changed pixels mask
    mask = (diff != 0).astype(np.uint8) * 255
    axes[1][1].imshow(before_vis, cmap='gray', vmin=0, vmax=255)
    axes[1][1].imshow(mask, cmap='Reds', alpha=0.5, vmin=0, vmax=255)
    changed_px = (diff != 0).sum()
    axes[1][1].set_title(f"Changed Pixels on Image\n(changed: {changed_px} px, {changed_px / (width*height) * 100:.2f}%)")
    axes[1][1].axis('off')

    # 6. Histogram
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

    if save:
        out_path = f"./deblock_output/diff_map_poc{poc}.png"
        plt.savefig(out_path, dpi=150, bbox_inches='tight')
        print(f"저장됨: {out_path}")

    plt.show()

    # 통계
    print(f"\n[POC {poc} 통계]")
    print(f"  bit depth         : {bit_depth}bit (max={max_val})")
    print(f"  차이 발생 픽셀 수 : {changed_px} / {width*height} ({changed_px/(width*height)*100:.2f}%)")
    print(f"  최대 차이         : {diff.max()}")
    print(f"  최소 차이         : {diff.min()}")
    print(f"  평균 절댓값 차이  : {np.abs(diff).mean():.4f}")
    mse = np.mean(diff.astype(np.float64)**2)
    if mse > 0:
        psnr = 10 * np.log10((max_val**2) / mse)
        print(f"  PSNR (Y)          : {psnr:.2f} dB")
    else:
        print(f"  PSNR (Y)          : inf (차이 없음)")


if __name__ == "__main__":
    WIDTH     = 1008
    HEIGHT    = 760
    POC       = 1
    BIT_DEPTH = 8   # ← 8 또는 10

    visualize_diff(
        before_path=f"./deblock_output/before/deblock_000{POC}.yuv",
        after_path =f"./deblock_output/after/deblock_000{POC}.yuv",
        width=WIDTH,
        height=HEIGHT,
        poc=POC,
        bit_depth=BIT_DEPTH,
        save=True
    )
    
    # before = np.fromfile("./deblock_output/before/deblock_0001.yuv", dtype=np.uint16)
    # after  = np.fromfile("./deblock_output/after/deblock_0001.yuv",  dtype=np.uint16)

    # diff = after.astype(np.int32) - before.astype(np.int32)
    # print(f"max diff: {diff.max()}")
    # print(f"min diff: {diff.min()}")
    # print(f"non-zero: {(diff != 0).sum()}")