# codec_final — AVC / HEVC / VVC residual & blocking artifact 추출·분석

## 1. 목적

AVC(JM), HEVC(HM), VVC(VTM) 세 참조 디코더에서 **residual frame** 과 **deblocking 전/후 프레임**을 같은 방식으로 뽑아낸다.
deblocking 전/후 차이는 blocking artifact 가 어디에 얼마나 강하게 있는지 추정하는 데 쓴다.
이렇게 뽑은 데이터로 코덱별 residual 과 blocking artifact 의 관계를 분석하기 위한 도구와 코드를 모았다.

- `JM/`, `HM/`, `VTM/`: 공식 참조 소프트웨어에 추출 기능을 추가한 소스
- `analysis/`: 추출한 데이터를 분석하는 Python 스크립트. 지금까지의 결과도 여기에 정리했다 → [analysis/README.md](analysis/README.md)

## 2. 코드 수정 방향

- **인코더는 건드리지 않고 디코더만 수정했다.** 추가 코드는 공용 라이브러리(HM TLibCommon, VTM CommonLib)에도 일부 있지만, 디코더에서만 켜진다.
- **비트스트림과 복원 영상은 바뀌지 않는다.** 디코딩 중의 버퍼를 읽어서 파일로 쓰기만 하는 부수 출력이다.
- **세 코덱의 사용법과 출력 형식을 맞췄다.**
  - 옵션: `ResidualDir`, `DeblockDir`
  - 출력: `<ResidualDir>/residual_XXXX.yuv`, `<DeblockDir>/{before,after}/deblock_XXXX.yuv`
  - 프레임마다 파일 1개. 번호는 1부터, 표시 순서(POC+1)를 따른다.
- 각 코덱 폴더의 `patches/residual_deblock_vs_upstream.patch` 에 upstream 대비 소스 diff 가 들어 있다.

코덱별로 손댄 위치:

| 코덱 | 옵션 지정 | residual 을 복사하는 곳 | deblock before/after 를 저장하는 곳 | residual 파일을 쓰는 곳 |
|---|---|---|---|---|
| JM (AVC) | `-p ResidualDir=... -p DeblockDir=...` (`configfile.h`) | `decode_one_macroblock`: MB 마다 `복원 − 예측` | `exit_picture`: `DeblockPicture` 앞뒤 | `exit_picture` (deblocking 직전) |
| HM (HEVC) | `--ResidualDir --DeblockDir` (`TAppDecCfg`) | `TComTrQuant::invRecurTransformNxN` (inter), `TDecCu::xIntraRecBlk` (intra) | `TComLoopFilter::loopFilterPic` 진입 시 / 수평+수직 후 | `TAppDecTop::xWriteOutput`, `xFlushOutput` |
| VTM (VVC) | `--ResidualDir --DeblockDir` (`DecAppCfg`) | `DecCu::xDecodeInterTU` (inter), `DecCu::xIntraRecBlk` (intra) | `DecLib::executeLoopFilters`: `deblockingFilterPic` 앞뒤 | `DecApp::xWriteOutput`, `xFlushOutput` |

출력 포맷:

| | JM | HM | VTM |
|---|---|---|---|
| residual | Y, int16, **coded 크기**(1008x768) | Y, int16, **크롭**(1008x756) | Y, int16, **크롭**(1008x756) |
| deblock | YUV420, uint8, coded(1008x768) | YUV420, uint8, coded(1008x760) | YUV420, uint8, coded(1008x760) |
| 번호 | 표시 순서 번호 + 1 | POC + 1 | POC + 1 |

괄호 안 크기는 1008x756 입력일 때다. deblock 은 세 코덱 모두 0..255 로 clip 한 uint8 이라 **8-bit 전용**이다.

## 3. 용어

**Residual**
- 디코더가 inverse quantization + inverse transform 으로 되살린 예측 오차 신호다 (복원 영상 = 예측 + residual 을 clip).
- 이 레포에서는 Y 성분을 부호 있는 정수(int16)로 저장한 것을 말한다.
- 코드를 확인해 보면 코덱마다 정확히 같지는 않다.
  - **HM**: inverse transform 출력 그대로. 예측에 더해 clip 하기 전 값이다.
  - **VTM**: HM 과 같은 위치에서 뽑는다. 다만 이 레포의 VTM 설정(`LMCSEnable: 1`)에서는 luma residual 이 **LMCS mapped domain** 의 값이라 원래 화소 domain 의 `복원 − 예측` 과 다르다.
  - **JM**: inverse transform 출력을 직접 뽑지 않는다. `clip(예측 + residual) − 예측` 으로 계산한다. 그래서 복원값이 0/255 로 포화된 픽셀에서는 실제 residual 보다 작다.

**Blocking artifact**
- 블록 단위 변환/양자화 때문에 블록(TU/PU/CU, AVC 는 MB/변환 블록) 경계에 생기는 불연속이다.
- 이 레포에서는 deblocking filter 가 실제로 고친 양, 즉 `after − before`(deblocking diff map)를 blocking artifact 의 위치와 강도를 대신 나타내는 지표(proxy)로 쓴다.
- 한계: deblocking 이 고친 곳이 진짜 artifact 와 1:1 로 맞지는 않는다. filter 가 놓친 artifact 도 있고, 실제 경계를 조금 고친 것도 섞인다.

## 4. 추출 방법

아래 명령은 각 코덱 폴더에서 실행한다. 표시 규칙:
- **(로컬 결과 있음)**: 이 레포에 오기 전 Linux 에서 실제로 돌려 결과가 남아 있는 명령. 출력 파일 크기를 확인했다.
- **(미검증)**: 이 레포 정리 중에는 실행해 보지 않은 명령.

빌드는 세 코덱 모두 WSL Ubuntu 20.04 + gcc 9.4 에서 확인했다. 추가 코드가 POSIX `mkdir` 을 쓰므로 Linux/macOS 를 전제로 한다(MSVC 빌드는 미검증).
`Fix:` 커밋(HM residual 저장 조건, 세 코덱의 출력 폴더 재귀 생성) 전/후 디코더 출력이 일반 사용에서 바이트 단위로 같은 것도 작은 영상으로 확인했다(각 코덱 README 참고).

### HM (HEVC) — 자세한 내용: [HM/README.md](HM/README.md)

```bash
# ① 빌드 (WSL Ubuntu 20.04 + gcc 9.4 에서 확인)
cd HM && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j && cd ..

# ② 인코딩: cfg/encoder_intra_main.cfg, QP32  (로컬 결과 있음, hm.sh)
./bin/TAppEncoderStatic -c ./cfg/encoder_intra_main.cfg -i ./data/fern_1008x756_20.yuv -b ./data/fern_ai.bin -o ./data/fern_enc_ai.yuv \
    -wdt 1008 -hgt 756 -fr 30 --FrameSkip=0 --FramesToBeEncoded=20 --InputBitDepth=8 --InputChromaFormat=420 --InternalBitDepth=8 \
    --QP=32 --ConformanceWindowMode=1

# ③ 디코딩 + 추출 (출력 폴더는 상위 폴더까지 디코더가 만든다)  (로컬 결과 있음)
./bin/TAppDecoderStatic -b ./data/fern_ai.bin -o ./data/fern_dec_ai.yuv \
    --ResidualDir=./Compressed/LLFF/HEVC/fern/QP32/residual --DeblockDir=./Compressed/LLFF/HEVC/fern/QP32/deblock

# ②+③ 데이터셋 전체 × QP 22/27/32/37/42 (로컬 결과 있음, 경로 인자화 후에는 미검증)
python HM.py --input-root ./data --dataset LLFF
```

### VTM (VVC) — 자세한 내용: [VTM/README.md](VTM/README.md)

```bash
# ① 빌드 (WSL Ubuntu 20.04 + gcc 9.4 에서 확인)
cd VTM && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j && cd ..

# ② 인코딩: cfg/encoder_intra_vtm.cfg, QP32  (로컬 결과 있음, vtm.sh)
./bin/EncoderAppStatic -c ./cfg/encoder_intra_vtm.cfg -i ./vtm_data/fern_1008x756_20.yuv -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_enc_ai.yuv \
    --FrameRate=30 -wdt 1008 -hgt 756 --QP=32 --TemporalSubsampleRatio=1 --InputBitDepth=8 --InputChromaFormat=420 \
    --InternalBitDepth=8 --FrameSkip=0 --FramesToBeEncoded=20

# ③ 디코딩 + 추출  (로컬 결과 있음)
./bin/DecoderAppStatic -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_ai.yuv \
    --ResidualDir=./Compressed/LLFF/VVC/fern/QP32/residual --DeblockDir=./Compressed/LLFF/VVC/fern/QP32/deblock

# ②+③ 데이터셋 전체 (로컬 결과 없음 → 미검증)
python VTM.py --input-root ./data --dataset LLFF
```

### JM (AVC) — 자세한 내용: [JM/README.md](JM/README.md)

```bash
# ① 빌드 (WSL Ubuntu 20.04 + gcc 9.4 에서 확인)
cd JM && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j && cd ..

# ② 인코딩: cfg/encoder.cfg, all-intra QP32  (로컬 결과 있음, jm.sh)
./bin/lencod_static -d ./cfg/encoder.cfg -p InputFile="./jm_data/fern_1008x756_20.yuv" -p OutputFile="./jm_data/fern_enc_ai.264" \
    -p ReconFile="./jm_data/fern_recon_ai.yuv" -p SourceWidth=1008 -p SourceHeight=756 -p OutputWidth=1008 -p OutputHeight=756 \
    -p QPISlice=32 -p IntraPeriod=1 -p NumberBFrames=0 -p FramesToBeEncoded=20

# ③ 디코딩 + 추출 (cfg/decoder.cfg). 아래처럼 Compressed 구조로 쓰는 것은 미검증, jm_data/ 로 쓰는 jm.sh 원래 경로는 로컬 결과 있음
./bin/ldecod_static -d ./cfg/decoder.cfg -p InputFile="./jm_data/fern_enc_ai.264" -p OutputFile="./jm_data/fern_dec_ai.yuv" \
    -p RefFile="./jm_data/fern_recon_ai.yuv" \
    -p ResidualDir="./Compressed/LLFF/AVC/fern/QP32/residual" -p DeblockDir="./Compressed/LLFF/AVC/fern/QP32/deblock"
```

JM 에는 HM.py/VTM.py 같은 일괄 스크립트가 없다.

### ④ 출력 폴더 구조 (HM.py / VTM.py 와 위 명령 기준)

```
<codec>/Compressed/<dataset>/<AVC|HEVC|VVC>/<scene>/QPxx/
  comp_result/            # 비트스트림, 복원 yuv, 인코더 로그 (HM.py / VTM.py)
  residual/residual_0001.yuv ...
  deblock/before/deblock_0001.yuv ...
  deblock/after/deblock_0001.yuv ...
```

### ⑤ 확인 방법

파일 수가 프레임 수와 같고, 각 파일 크기가 아래 값이면 정상이다 (1008x756 입력 기준).

| | residual (W×H×2 B) | deblock (Wc×Hc×1.5 B) |
|---|---|---|
| JM | 1008×768×2 = 1,548,288 | 1008×768×1.5 = 1,161,216 |
| HM | 1008×756×2 = 1,524,096 | 1008×760×1.5 = 1,149,120 |
| VTM | 1008×756×2 = 1,524,096 | 1008×760×1.5 = 1,149,120 |

```bash
ls -l Compressed/LLFF/HEVC/fern/QP32/residual | head
ls Compressed/LLFF/HEVC/fern/QP32/deblock/after | wc -l
python analysis/01_deblock_diff.py --codec HEVC --root HM/Compressed/LLFF --scene fern --qp 32 --poc 1   # 레포 루트에서, 그림 + 통계
```

## 5. 레포 구조

```
codec_final/
├─ README.md                 # 이 파일
├─ LICENSE                   # MIT (이 레포에서 새로 작성한 코드)
├─ .gitignore
├─ JM/                       # H.264/AVC JM 19.1 + 추출 기능   → JM/README.md
│  ├─ patches/residual_deblock_vs_upstream.patch
│  ├─ tools/                 # 결과 확인용 보조 스크립트
│  ├─ jm.sh
│  └─ README_upstream.md     # upstream README (이름만 변경)
├─ HM/                       # HEVC HM 18.0+ + 추출 기능       → HM/README.md
│  ├─ patches/ … tools/ … HM.py, hm.sh, README_upstream.md
├─ VTM/                      # VVC VTM 23.14 + 추출 기능        → VTM/README.md
│  ├─ patches/ … tools/ … VTM.py, vtm.sh, README_upstream.md
└─ analysis/                 # 분석 스크립트와 결과           → analysis/README.md
   ├─ 01_deblock_diff.py … 07_residual_dog_sweep.py
   ├─ common/io_utils.py
   ├─ figures/               # README 에 쓴 대표 그림
   ├─ samples/               # hf_deblock.npy, hf_residual.npy
   └─ requirements.txt
```

- 코덱별 README: [JM/README.md](JM/README.md), [HM/README.md](HM/README.md), [VTM/README.md](VTM/README.md)
- 분석 결과 요약:
  - HEVC fern QP32 첫 프레임에서 deblocking 은 Y 의 18.7% 를 대부분 ±1~3 만큼 고친다.
  - 고친 픽셀의 99.4% 가 8픽셀 격자선 근처에 있다.
  - 자세한 내용과 미확인 항목: [analysis/README.md](analysis/README.md)

## 라이선스 / 출처

**HM / JM / VTM 폴더는 각각 upstream 라이선스를 따른다 (각 폴더의 COPYING 또는 라이선스 고지 파일 참고).**
upstream 소스 파일에 추가·수정한 코드(`source/` 안의 변경, `patches/` 의 diff)도 해당 파일의 upstream 라이선스를 따른다.

| 폴더 | 라이선스 | 파일 | 출처 |
|---|---|---|---|
| `HM/` | BSD 3-Clause | [HM/COPYING](HM/COPYING) | https://vcgit.hhi.fraunhofer.de/jvet/HM |
| `VTM/` | BSD 3-Clause | [VTM/COPYING](VTM/COPYING) | https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM |
| `JM/` | ITU-T / ISO/IEC 저작권 고지 | [COPYRIGHT_ITU.txt](JM/COPYRIGHT_ITU.txt), [COPYRIGHT_ISO_IEC.txt](JM/COPYRIGHT_ISO_IEC.txt), [disclaimer.txt](JM/disclaimer.txt) | https://vcgit.hhi.fraunhofer.de/jvet/JM |

원본 소스의 저작권 표기는 모두 그대로 두었다.

**이 레포에서 새로 작성한 파일은 MIT 라이선스**다 ([LICENSE](LICENSE)).
- 대상: `analysis/` 전체, 각 코덱 폴더의 `tools/`, `HM/HM.py`, `VTM/VTM.py`, `HM/hm.sh`, `JM/jm.sh`, `VTM/vtm.sh`, 이 README 와 각 코덱의 `README.md`.

## 올리지 않는 것 (.gitignore)

| 대상 | 이유 |
|---|---|
| `*.yuv`, `*.bin`, `*.264`, `*.hevc`, `*.vvc`, `*.npy`(samples 제외), `Compressed/`, `JM/jm_data/`, `VTM/vtm_data/` | 영상·비트스트림·추출 데이터. 수백 MB~수 GB 이고 스크립트로 다시 만들 수 있다. 예외로 upstream JM 테스트 입력 `JM/cfg/foreman_part_qcif*.yuv` 3개(약 0.5 MB)는 올린다 |
| `build/`, `bin/`, `lib/`, `*.o`, `*.a`, 실행 파일 | 빌드 산출물 |
| `*.log`, `*_log.txt`, JM `bin/*.dat`, `leakybucketparam.cfg` | 실행 로그와 인코더가 만드는 임시 파일 |
| `analysis/outputs/`, `HM/analysis/` | 분석 출력. 원본 analysis 는 정리본(`analysis/`)과 중복 |
| `*.zip` | 로컬 백업 압축 파일 |
| `*.key`, `*.pem` | upstream `cfg/keystore` 의 예시 키(SEI 서명 테스트용, 추출 기능과 무관). 키 파일 형식은 올리지 않는다 |
