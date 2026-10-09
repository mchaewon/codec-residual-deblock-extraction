import os
import glob
import subprocess
import re
import argparse

# ================= 설정 구역 =================
# 기본 경로는 이 스크립트가 있는 HM/ 폴더 기준 상대경로. 명령행 인자로 바꿀 수 있음.
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

HM_ENC_PATH = os.path.join(ROOT_DIR, "bin", "TAppEncoderStatic")
HM_DEC_PATH = os.path.join(ROOT_DIR, "bin", "TAppDecoderStatic")
CONFIG_PATH = os.path.join(ROOT_DIR, "cfg", "encoder_intra_main.cfg")

INPUT_DIR = os.path.join(ROOT_DIR, "data")

# dataset 이름 지정
DATASET_NAME = "LLFF"

INPUT_DIR = os.path.join(INPUT_DIR, DATASET_NAME)

# 최상위 Compressed 경로: ./Compressed/dataset_name/
OUTPUT_BASE_DIR = os.path.join(
    ROOT_DIR,
    "Compressed",
    DATASET_NAME
)

# QP 리스트
QP_LIST = [22, 27, 32, 37, 42]

# ===========================================================================

def run_encoding():
    yuv_files = glob.glob(os.path.join(INPUT_DIR, "*.yuv"))

    # 예: fern_1008x756_20.yuv  -> (scene_name, w, h, frames)
    filename_pattern = re.compile(r"(.+)_(\d+)x(\d+)_(\d+)\.yuv")

    if not yuv_files:
        print(f"경고: {INPUT_DIR} 에서 .yuv 파일을 찾을 수 없습니다.")
        return

    for input_path in yuv_files:
        filename = os.path.basename(input_path)
        match = filename_pattern.match(filename)

        if not match:
            print(f"[Skip] 파일명 형식 오류: {filename}")
            continue

        scene_name, width, height, frames = match.groups()

        for qp in QP_LIST:
            # ===========================
            # ✅ 폴더 구조 (요구사항 반영)
            # ./Compressed/dataset_name/HEVC/scene_name/QP*/...
            # ===========================

            qp_dir = os.path.join(
                OUTPUT_BASE_DIR,
                "HEVC",
                scene_name,
                f"QP{qp}"
            )

            comp_dir = os.path.join(qp_dir, "comp_result")
            residual_dir = os.path.join(qp_dir, "residual")

            deblock_root = os.path.join(qp_dir, "deblock")
            deblock_before_dir = os.path.join(deblock_root, "before")
            deblock_after_dir = os.path.join(deblock_root, "after")

            os.makedirs(comp_dir, exist_ok=True)
            os.makedirs(residual_dir, exist_ok=True)
            os.makedirs(deblock_before_dir, exist_ok=True)
            os.makedirs(deblock_after_dir, exist_ok=True)

            # ===========================
            # ✅ 출력 파일 경로
            # ===========================
            base_name = os.path.splitext(filename)[0]

            bitstream_path = os.path.join(comp_dir, f"{base_name}.hevc")
            recon_path = os.path.join(comp_dir, f"{base_name}.yuv")
            log_path = os.path.join(comp_dir, f"{base_name}.txt")

            # ===========================
            # ✅ Encoding
            # ===========================
            cmd = [
                HM_ENC_PATH,
                "-c", CONFIG_PATH,
                "-i", input_path,
                "-b", bitstream_path,
                "-o", recon_path,
                f"--SourceWidth={width}",
                f"--SourceHeight={height}",
                "-fr", "30",
                "--FrameSkip=0",
                f"--FramesToBeEncoded={frames}",
                "--InputBitDepth=8",
                "--InputChromaFormat=420",
                "--InternalBitDepth=8",
                f"--QP={qp}",
                "--ConformanceWindowMode=1"
            ]

            print(f"\nEncoding {scene_name} | QP {qp}")

            with open(log_path, "w") as log_file:
                result = subprocess.run(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True
                )

            if result.returncode != 0:
                print(f"[Error] Encoding 실패: {filename} (QP {qp})")
                continue

            print("  ✓ Encoding 완료")

            # ===========================
            # ✅ Decoding + Residual/Deblock 저장
            #   - residual:  residual/residual_%04d.yuv (decoder가 그렇게 저장한다고 가정)
            #   - deblock:   deblock/before/deblock_%04d.yuv, deblock/after/deblock_%04d.yuv
            # ===========================
            decoder_cmd = [
                HM_DEC_PATH,
                "-b", bitstream_path,
                "-o", recon_path,
                f"--ResidualDir={residual_dir}",
                f"--DeblockDir={deblock_root}"
            ]

            print("  → Residual/Deblock 추출 중...")
            subprocess.run(decoder_cmd)
            print("  ✓ Residual/Deblock 저장 완료")

    print("\n=== 모든 작업 완료 ===")


def parse_args():
    p = argparse.ArgumentParser(description="HM encode + residual/deblock extraction for every <scene>_<W>x<H>_<N>.yuv")
    p.add_argument("--enc", default=HM_ENC_PATH, help="TAppEncoderStatic path")
    p.add_argument("--dec", default=HM_DEC_PATH, help="TAppDecoderStatic path")
    p.add_argument("--cfg", default=CONFIG_PATH, help="encoder cfg")
    p.add_argument("--input-root", default=os.path.join(ROOT_DIR, "data"), help="folder containing <dataset>/*.yuv")
    p.add_argument("--output-root", default=ROOT_DIR, help="Compressed/<dataset>/... is created under this folder")
    p.add_argument("--dataset", default=DATASET_NAME)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    HM_ENC_PATH, HM_DEC_PATH, CONFIG_PATH = args.enc, args.dec, args.cfg
    INPUT_DIR = os.path.join(args.input_root, args.dataset)
    OUTPUT_BASE_DIR = os.path.join(args.output_root, "Compressed", args.dataset)
    run_encoding()
