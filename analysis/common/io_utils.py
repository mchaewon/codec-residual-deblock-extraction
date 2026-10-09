"""
residual / deblock YUV 를 읽고 정규화하는 공통 함수.

디코더가 쓰는 파일 포맷 (JM / HM / VTM 수정본 기준, 각 코덱 README 참고)
  residual_XXXX.yuv        : Y 만, int16 (little endian)
                             HEVC/VVC = conformance window 로 크롭된 크기 (예: 1008x756)
                             AVC      = 크롭 안 된 coded 크기 (예: 1008x768)
  deblock/{before,after}/  : Y/Cb/Cr 4:2:0 전체, uint8 (0..255 clip), 크롭 안 된 coded 크기
                             (HEVC/VVC 예: 1008x760, AVC 예: 1008x768)

=> 두 맵을 같이 쓰려면 항상 크롭된 표시 크기(width x height)의 위쪽/왼쪽 영역으로 맞춘다.
"""

import os
import numpy as np

ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(ANALYSIS_DIR)
OUTPUT_DIR = os.path.join(ANALYSIS_DIR, "outputs")

# codec 이름 -> 출력 폴더 이름 (HM.py / VTM.py 의 Compressed/<dataset>/<CODEC>/... 규칙)
CODECS = ("AVC", "HEVC", "VVC")

# coded 크기 정렬 단위: AVC 는 매크로블록(16), HEVC/VVC 는 이 레포 설정에서 최소 CU(8)
_ALIGN = {"AVC": 16, "HEVC": 8, "VVC": 8}

# HM.py / VTM.py 가 만드는 기본 데이터 루트 (AVC 는 배치 스크립트가 없어 경로를 직접 지정)
_DEFAULT_ROOT = {
    "HEVC": os.path.join(REPO_DIR, "HM", "Compressed", "LLFF"),
    "VVC": os.path.join(REPO_DIR, "VTM", "Compressed", "LLFF"),
    "AVC": None,
}


# ============================
# 크기
# ============================

def coded_size(width, height, codec):
    """디코더가 크롭 없이 저장하는 coded 크기 (deblock yuv, AVC residual)."""
    a = _ALIGN[codec]
    return (width + a - 1) // a * a, (height + a - 1) // a * a


def residual_stored_size(width, height, codec):
    """residual yuv 에 실제로 저장된 크기."""
    if codec == "AVC":
        return coded_size(width, height, codec)
    return width, height


def crop(a, height, width):
    """위쪽/왼쪽 기준으로 (height, width) 만큼 자름."""
    if a.shape[0] < height or a.shape[1] < width:
        raise ValueError(f"crop target {height}x{width} is larger than array {a.shape}")
    return a[:height, :width]


# ============================
# 읽기
# ============================

def _sample_dtype(bit_depth):
    return np.uint8 if bit_depth <= 8 else np.uint16


def read_y_channel(path, width, height, frame_index=0, bit_depth=8,
                   stored_width=None, stored_height=None, chroma_format=420):
    """
    YUV 파일에서 frame_index 번째 프레임의 Y 만 읽어 (height, width) float32 로 반환.
    - bit_depth <= 8 : uint8, 그 이상 : uint16 (little endian, 10bit 등)
    - stored_width/height : 파일 안 plane 의 실제 크기 (coded 크기). 주면 읽은 뒤 width x height 로 크롭.
    """
    sw = stored_width or width
    sh = stored_height or height
    dtype = _sample_dtype(bit_depth)
    y_size = sw * sh
    if chroma_format == 420:
        frame_samples = y_size + 2 * (sw // 2) * (sh // 2)
    elif chroma_format == 400:
        frame_samples = y_size
    else:
        raise ValueError(f"unsupported chroma_format: {chroma_format}")

    with open(path, "rb") as f:
        f.seek(frame_index * frame_samples * np.dtype(dtype).itemsize)
        Y = np.fromfile(f, dtype=dtype, count=y_size)
    if Y.size != y_size:
        raise ValueError(f"Size mismatch: {path} (expected {y_size} samples, got {Y.size})")
    return crop(Y.reshape((sh, sw)), height, width).astype(np.float32)


def read_deblock_y(path, width, height, codec, frame_index=0, bit_depth=8, no_crop=False):
    """
    deblock/before|after/deblock_XXXX.yuv 의 Y.
    파일은 coded 크기로 저장돼 있으므로 기본은 (height, width) 표시 크기로 크롭.
    no_crop=True 면 coded 크기 그대로 반환.
    """
    cw, ch = coded_size(width, height, codec)
    if no_crop:
        return read_y_channel(path, cw, ch, frame_index, bit_depth)
    return read_y_channel(path, width, height, frame_index, bit_depth, stored_width=cw, stored_height=ch)


def read_residual_y(path, width, height, codec="HEVC", frame_index=0):
    """
    residual_XXXX.yuv (Y 만, int16) 를 (height, width) float32 로.
    AVC 는 coded 크기로 저장돼 있으므로 크롭한다.
    파일에는 Y plane 만 있으므로 frame_index 는 Y plane 크기 단위로 건너뛴다.
    """
    sw, sh = residual_stored_size(width, height, codec)
    with open(path, "rb") as f:
        f.seek(frame_index * sw * sh * 2)
        Y = np.fromfile(f, dtype=np.int16, count=sw * sh)
    if Y.size != sw * sh:
        raise ValueError(f"Size mismatch: {path} (expected {sw * sh} samples, got {Y.size})")
    return crop(Y.reshape((sh, sw)), height, width).astype(np.float32)


# ============================
# 정규화
# ============================

def normalize_dblk(x, p=99.9, eps=1e-6):
    """deblock diff: log1p(|x|) / quantile(p) -> 0~1 (작은 값 압축, 약한 경계도 살림)"""
    x = np.log1p(np.abs(x).astype(np.float32))
    s = np.percentile(x, p) + eps
    return np.clip(x / s, 0, 1)


def normalize_residual_abs(x, p=99.5, eps=1e-6):
    """residual: |x| / quantile(p) -> 0~1 (선형 비율)"""
    x = np.abs(x).astype(np.float32)
    s = np.percentile(x, p) + eps
    return np.clip(x / s, 0, 1)


# HF map 정규화도 같은 식(|x| / quantile 99.5)을 쓴다
normalize_map = normalize_residual_abs


def robust_scale_abs(Y, p=99.5, eps=1e-6):
    """|Y| 의 p 분위수 (signed 시각화 스케일)"""
    return np.percentile(np.abs(Y), p) + eps


# ============================
# 경로 / 인자
# ============================

def default_paths(root, codec, scene, qp, poc):
    """
    HM.py / VTM.py 출력 구조:
      <root>/<CODEC>/<scene>/QP<qp>/residual/residual_<poc>.yuv
      <root>/<CODEC>/<scene>/QP<qp>/deblock/{before,after}/deblock_<poc>.yuv
    poc 는 파일 번호(= POC+1) 그대로.
    """
    qp_dir = os.path.join(root, codec, scene, f"QP{qp}")
    return {
        "residual": os.path.join(qp_dir, "residual", f"residual_{poc:04d}.yuv"),
        "before": os.path.join(qp_dir, "deblock", "before", f"deblock_{poc:04d}.yuv"),
        "after": os.path.join(qp_dir, "deblock", "after", f"deblock_{poc:04d}.yuv"),
    }


def add_common_args(p, need_residual=True, need_deblock=True):
    """여러 스크립트가 같이 쓰는 인자: 크기/코덱/scene/QP/POC 와 개별 파일 경로 override."""
    g = p.add_argument_group("input")
    g.add_argument("--codec", choices=CODECS, default="HEVC",
                   help="AVC=JM, HEVC=HM, VVC=VTM (coded 크기/크롭 규칙이 달라짐)")
    g.add_argument("--width", type=int, default=1008, help="표시(크롭) 너비")
    g.add_argument("--height", type=int, default=756, help="표시(크롭) 높이")
    g.add_argument("--root", default=None,
                   help="Compressed/<dataset> 폴더. 기본: HEVC=HM/Compressed/LLFF, VVC=VTM/Compressed/LLFF")
    g.add_argument("--scene", default="fern")
    g.add_argument("--qp", type=int, default=32)
    g.add_argument("--poc", type=int, default=1, help="파일 번호 (= POC+1)")
    if need_residual:
        g.add_argument("--residual", default=None, help="residual yuv 경로 (주면 root/scene/qp/poc 무시)")
    if need_deblock:
        g.add_argument("--before", default=None, help="deblock before yuv 경로")
        g.add_argument("--after", default=None, help="deblock after yuv 경로")
        g.add_argument("--bit-depth", type=int, default=8,
                       help="deblock yuv 샘플 비트수. 현재 세 디코더 모두 8bit(uint8)로 저장")
    return g


def resolve_inputs(args):
    """args 에서 residual/before/after 경로 결정."""
    root = args.root or _DEFAULT_ROOT[args.codec]
    paths = default_paths(root, args.codec, args.scene, args.qp, args.poc) if root else {}
    out = {}
    for key in ("residual", "before", "after"):
        if not hasattr(args, key):
            continue
        v = getattr(args, key) or paths.get(key)
        if v is None:
            raise SystemExit(f"--{key} 를 지정하세요 (codec={args.codec} 은 기본 root 가 없음)")
        out[key] = v
    return out


def output_dir(name, override=None):
    """기본 출력 위치: analysis/outputs/<name>/ (.gitignore 됨)"""
    d = override or os.path.join(OUTPUT_DIR, name)
    os.makedirs(d, exist_ok=True)
    return d


def tag(args):
    """출력 파일 이름용 태그. 예: HEVC_fern_QP32_poc0001"""
    return f"{args.codec}_{args.scene}_QP{args.qp}_poc{args.poc:04d}"
