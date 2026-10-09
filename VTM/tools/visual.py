import numpy as np
import cv2


def read_residual_y_only(filename, width, height, frame_index=0, dtype=np.int16):
    """
    YUV 파일에서 Y 성분만 읽기
    
    Args:
        filename: residual YUV 파일 경로
        width: 영상 너비
        height: 영상 높이
        frame_index: 프레임 인덱스 (기본값 0)
        dtype: 데이터 타입 (기본값 int16)
    
    Returns:
        Y: Y 성분 numpy array (height x width)
    """
    # YUV420 기준 프레임 크기 계산
    # Y = width * height
    # U = (width//2) * (height//2)
    # V = (width//2) * (height//2)
    frame_size = width * height + 2 * (width // 2) * (height // 2)
    bytes_per_sample = np.dtype(dtype).itemsize
    frame_size_bytes = frame_size * bytes_per_sample

    with open(filename, 'rb') as f:
        # 해당 프레임으로 이동
        f.seek(frame_index * frame_size_bytes)
        
        # Y 성분만 읽기
        Y = np.fromfile(f, dtype=dtype, count=width * height)

        if Y.size != width * height:
            raise ValueError(f"읽은 데이터 크기가 맞지 않습니다: {Y.size} != {width * height}")

        # reshape
        Y = Y.reshape((height, width))

    return Y


def save_residual_visualizations(Y, output_prefix):
    """
    Residual Y 성분을 시각화하여 저장
    
    Args:
        Y: Y 성분 numpy array
        output_prefix: 출력 파일 경로 prefix (확장자 제외)
    """
    # 1. numpy 파일로 저장 (원본 데이터)
    np.save(f"{output_prefix}.npy", Y)
    print(f"Saved: {output_prefix}.npy")
    
    # 2. PNG로 시각화
    max_val = np.max(np.abs(Y))
    
    if max_val == 0:
        # 모든 값이 0인 경우
        Y_vis = np.zeros_like(Y, dtype=np.uint8) + 128
    else:
        # [-max_val, max_val] → [0, 255] 매핑
        Y_norm = (Y.astype(np.float32) / max_val)  # [-1, 1]
        Y_vis = ((Y_norm + 1) * 127.5).astype(np.uint8)  # [0, 255]
    
    cv2.imwrite(f"{output_prefix}.png", Y_vis)
    print(f"Saved: {output_prefix}.png")
    
    # 3. 통계 정보 출력
    print(f"\n=== Statistics ===")
    print(f"Shape: {Y.shape}")
    print(f"Min: {Y.min()}")
    print(f"Max: {Y.max()}")
    print(f"Mean: {Y.mean():.2f}")
    print(f"Std: {Y.std():.2f}")
    print(f"Non-zero pixels: {np.count_nonzero(Y)} / {Y.size} ({np.count_nonzero(Y)/Y.size*100:.2f}%)")


# ===============================
# 실행
# ===============================

if __name__ == "__main__":
    # 설정
    RESIDUAL_FILE = "./residual_output/residual_0002.yuv"
    WIDTH = 1008
    HEIGHT = 760
    FRAME_INDEX = 0  # 첫 번째 프레임
    OUTPUT_PREFIX = "./residual_output/Y_residual_0002"  # 출력 파일 이름 (확장자 제외)
    
    # Y 성분 읽기
    print(f"Reading Y component from: {RESIDUAL_FILE}")
    Y = read_residual_y_only(RESIDUAL_FILE, WIDTH, HEIGHT, FRAME_INDEX)
    
    # 시각화 및 저장
    save_residual_visualizations(Y, OUTPUT_PREFIX)
    
    print("\nDone!")

# import numpy as np
# import cv2
# import os
# import glob


# def read_residual_y_only(filename, width, height, frame_index=0, dtype=np.int16):
#     frame_size = width * height + 2 * (width//2) * (height//2)
#     bytes_per_sample = np.dtype(dtype).itemsize
#     frame_size_bytes = frame_size * bytes_per_sample

#     with open(filename, 'rb') as f:
#         f.seek(frame_index * frame_size_bytes)
#         Y = np.fromfile(f, dtype=dtype, count=width*height)

#         if Y.size != width * height:
#             print(f"[Skip] Size mismatch in {filename}")
#             return None

#         Y = Y.reshape((height, width))

#     return Y


# def save_residual_png(Y, save_path):
#     max_val = np.max(np.abs(Y))

#     if max_val == 0:
#         Y_vis = np.zeros_like(Y, dtype=np.uint8) + 128
#     else:
#         Y_norm = (Y.astype(np.float32) / max_val)
#         Y_vis = ((Y_norm + 1) * 127.5).astype(np.uint8)

#     cv2.imwrite(save_path, Y_vis)


# def process_all_residuals(base_dir, width, height):

#     # 모든 category 탐색
#     categories = sorted(os.listdir(base_dir))

#     for category in categories:
#         category_path = os.path.join(base_dir, category)
#         if not os.path.isdir(category_path):
#             continue

#         print(f"\n=== Category: {category} ===")

#         # QP 폴더 탐색
#         qp_dirs = sorted(os.listdir(category_path))

#         for qp in qp_dirs:
#             qp_path = os.path.join(category_path, qp)
#             if not os.path.isdir(qp_path):
#                 continue

#             print(f"  -> Processing {qp}")

#             # 저장 폴더 생성
#             save_npy_dir = os.path.join(qp_path, "Y_npy")
#             save_png_dir = os.path.join(qp_path, "Y_png")

#             os.makedirs(save_npy_dir, exist_ok=True)
#             os.makedirs(save_png_dir, exist_ok=True)

#             # residual 파일 탐색
#             residual_files = sorted(
#                 glob.glob(os.path.join(qp_path, "residual_poc*.yuv"))
#             )

#             for res_file in residual_files:
#                 filename = os.path.basename(res_file)
#                 frame_id = filename.replace("residual_poc", "").replace(".yuv", "")

#                 Y_res = read_residual_y_only(res_file, width, height)

#                 if Y_res is None:
#                     continue

#                 # npy 저장
#                 npy_path = os.path.join(save_npy_dir, f"Y_{frame_id}.npy")
#                 np.save(npy_path, Y_res)

#                 # png 저장
#                 png_path = os.path.join(save_png_dir, f"Y_{frame_id}.png")
#                 save_residual_png(Y_res, png_path)

#                 print(f"    Saved frame {frame_id}")


# # ===============================
# # 실행
# # ===============================

# BASE_DIR = "./Compressed/LLFF/VVC/QP22/orchids/residual"   # ← 여기만 바꾸면 됨
# WIDTH = 1008
# HEIGHT = 756

# process_all_residuals(BASE_DIR, WIDTH, HEIGHT)