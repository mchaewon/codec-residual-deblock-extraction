# HM (HEVC) — residual / deblocking 추출 기능 추가본

HEVC 참조 소프트웨어 HM 의 **디코더(TAppDecoder)** 에 다음 두 가지 부수 출력을 추가한 버전이다.

- **residual frame**: inverse transform 직후의 Y residual (`residual_XXXX.yuv`)
- **deblocking 전/후 프레임**: `loopFilterPic` 진입 직후와 deblocking(수평+수직) 직후의 복원 프레임 (`deblock/{before,after}/deblock_XXXX.yuv`)

인코더 쪽 동작과 비트스트림, 복원 영상(`-o`)은 바뀌지 않는다. 바뀐 내용 전체는 [patches/residual_deblock_vs_upstream.patch](patches/residual_deblock_vs_upstream.patch) 에 있다.
upstream 원래 README 는 [README_upstream.md](README_upstream.md) 로 이름만 바꿔 그대로 두었다.

## 기반 upstream

| 항목 | 값 |
|---|---|
| 이름 / 버전 | HM (HEVC Test Model), `HM-18.0-73-gdbe8d28db` (HM-18.0 이후 73 커밋) |
| 저장소 | https://vcgit.hhi.fraunhofer.de/jvet/HM.git (`master`) |
| 기준 커밋 | `dbe8d28db3077e2f35eff000adc17377f09027a2` (2026-01-28) |
| 라이선스 | BSD 3-Clause, [COPYING](COPYING). 원본 소스의 저작권 표기는 모두 유지한다 |

수정 파일 판정은 upstream 저장소 기준 `git -c core.fileMode=false diff` 로 했다. Windows 에서 권한(mode)만 바뀐 파일과,
upstream 에서 심볼릭 링크인 `cfg/keystore/ca/d8e118e3.0` 이 일반 파일로 풀린 것(내용 동일한 인증서)은 수정으로 보지 않았다.

## 수정한 파일

| 파일 | 수정/추가 | 내용 (함수 단위) |
|---|---|---|
| `source/App/TAppDecoder/TAppDecCfg.h` | 수정 | 멤버 `m_residualDir`, `m_deblockDir` 추가 |
| `source/App/TAppDecoder/TAppDecCfg.cpp` | 수정 | `TAppDecCfg::parseCfg`: 옵션 `--ResidualDir`, `--DeblockDir` 등록 |
| `source/App/TAppDecoder/TAppDecTop.cpp` | 수정 | `xInitDecLib`: `setDeblockDir()` 호출, `ResidualDir` 를 `mkdir`. `xWriteOutput` / `xFlushOutput`: 출력 직전에 residual 버퍼의 Y 를 conformance window 로 크롭해 `residual_%04d.yuv` (번호 = POC+1) 로 쓰고 `destroyResidualBuffer()` |
| `source/Lib/TLibDecoder/TDecTop.h` | 수정 | `TDecTop::setDeblockDir()` → loop filter 로 전달 |
| `source/Lib/TLibCommon/TComLoopFilter.h` | 수정 | 멤버 `m_deblockDir`, `setDeblockDir()` (dir, dir/before, dir/after 를 `mkdir`) |
| `source/Lib/TLibCommon/TComLoopFilter.cpp` | 수정 | `TComLoopFilter::loopFilterPic`: 진입 시 `before/deblock_%04d.yuv`, 수평·수직 deblocking 후 `after/deblock_%04d.yuv` 저장 (Y/Cb/Cr, 0..255 clip 후 uint8) |
| `source/Lib/TLibCommon/TComPic.h/.cpp` | 수정 | 멤버 `m_pcPicYuvResidual`, `getPicYuvResidual`, `createResidualBuffer` (SPS 크기 = coded 크기), `clearResidualBuffer`, `destroyResidualBuffer`. `TComPic::destroy` 에서 해제 |
| `source/Lib/TLibDecoder/TDecSlice.cpp` | 수정 | `TDecSlice::decompressSlice`: 프레임 첫 슬라이스(독립 슬라이스, CTU 0)에서 residual 버퍼 생성 + 0 초기화 |
| `source/Lib/TLibCommon/TComTrQuant.cpp` | 수정 | `TComTrQuant::invRecurTransformNxN`: inverse transform 직후(cross-component prediction 전) TU residual 을 프레임 버퍼로 복사. **inter** CU 경로 |
| `source/Lib/TLibDecoder/TDecCu.cpp` | 수정 | `TDecCu::xIntraRecBlk`: inverse transform 직후(cross-component prediction 전, 복원 전) TU residual 을 프레임 버퍼로 복사. **intra** 경로 |
| `HM.py` | 추가 | 데이터셋 일괄 인코딩 + residual/deblock 추출 스크립트 |
| `hm.sh` | 추가 | fern 한 시퀀스 인코딩/디코딩 예시 명령 |
| `tools/*.py` | 추가 | 추출 결과 확인용 보조 스크립트 (아래) |
| `patches/residual_deblock_vs_upstream.patch` | 추가 | upstream 대비 소스 diff |

`TComTrQuant`, `TComLoopFilter`, `TComPic` 는 인코더와 같이 쓰는 TLibCommon 이지만, residual 버퍼는 디코더의 `TDecSlice` 에서만 만들고
`m_deblockDir` 도 디코더에서만 설정하므로 인코더에서는 추가 코드가 실행되지 않는다(코드 확인, 인코더 출력 비교는 하지 않음).

## 추가된 디코더 옵션과 출력

| 옵션 | 출력 |
|---|---|
| `--ResidualDir=<dir>` | `<dir>/residual_XXXX.yuv` |
| `--DeblockDir=<dir>` | `<dir>/before/deblock_XXXX.yuv`, `<dir>/after/deblock_XXXX.yuv` |

`XXXX` = **POC+1** (4자리). 디코딩 순서가 아니라 POC 기준이므로 RA 에서도 표시 순서대로 번호가 붙는다.

### 데이터 포맷

| | residual | deblock before / after |
|---|---|---|
| 컴포넌트 | Y 만 | Y, Cb, Cr (4:2:0 planar) |
| 자료형 | `Pel` = int16 (little endian), 부호 있음 | uint8, `Clip3(0,255)` |
| 해상도 | conformance window 로 **크롭** (예: 1008x756) | **크롭 안 함**, coded 크기 (예: 1008x760) |
| 파일 크기 (1008x756 입력) | 1008×756×2 = 1,524,096 B | 1008×760×1.5 = 1,149,120 B |
| 값의 의미 | inverse quantization + inverse transform 결과. 예측에 더하고 clip 하기 전 값 | deblocking 전: 예측+residual 복원(clip) 영상 / 후: deblocking 만 적용, SAO 적용 전 |
| 저장 시점 | 픽처 출력(`xWriteOutput`/`xFlushOutput`) 때 | `TDecGop::filterPicture` → `loopFilterPic` 안 (SAO 전) |

residual(756행)과 deblock(760행)은 크기가 다르다. 같이 분석할 때는 deblock 의 위쪽 756행만 쓴다 (`analysis/common/io_utils.py` 가 자동으로 맞춤).

## 빌드

upstream 과 같다 (CMake). Linux 기준, 아래 명령으로 `bin/TAppEncoderStatic`, `bin/TAppDecoderStatic` 가 생긴다.

```bash
cd HM
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j
```

- 이 폴더의 기존 산출물은 Linux gcc 9.4 로 빌드된 것이다. 위 명령은 **이 레포에서 다시 실행해 보지는 않았다 (미검증)**.
- 추가 코드는 `mkdir(path, 0755)` (POSIX `sys/stat.h`) 를 쓰므로 **MSVC(Windows) 빌드는 안 될 가능성이 높다 (미검증)**.

## 인코딩 → 디코딩(추출) 예시

`hm.sh` 기준 (HM 폴더에서 실행, 입력 `./data/fern_1008x756_20.yuv`, all-intra, QP32, 20프레임).
사용 cfg: `cfg/encoder_intra_main.cfg` (주석 처리된 RA 예시는 `cfg/encoder_randomaccess_main.cfg`).

```bash
./bin/TAppEncoderStatic -c ./cfg/encoder_intra_main.cfg -i ./data/fern_1008x756_20.yuv -b ./data/fern_ai.bin -o ./data/fern_enc_ai.yuv \
    -wdt 1008 -hgt 756 -fr 30 --FrameSkip=0 --FramesToBeEncoded=20 --InputBitDepth=8 --InputChromaFormat=420 --InternalBitDepth=8 \
    --QP=32 --ConformanceWindowMode=1 | tee ./data/fern_ai_log.txt

./bin/TAppDecoderStatic -b ./data/fern_ai.bin -o ./data/fern_dec_ai.yuv --ResidualDir="./residual_ai" --DeblockDir="./deblock_ai"
```

`HM.py` 는 `data/<dataset>/*.yuv` (파일명 `<scene>_<W>x<H>_<N>.yuv`) 전부를 QP 22/27/32/37/42 로 인코딩하고 다음 구조로 추출한다.

```
HM/Compressed/<dataset>/HEVC/<scene>/QPxx/
  comp_result/<scene>_<W>x<H>_<N>.{hevc,yuv,txt}   # 비트스트림 / 복원 / 인코더 로그
  residual/residual_XXXX.yuv
  deblock/before/deblock_XXXX.yuv
  deblock/after/deblock_XXXX.yuv
```

```bash
python HM.py                              # 기본: HM/bin, HM/cfg/encoder_intra_main.cfg, HM/data/LLFF, 출력 HM/Compressed/LLFF
python HM.py --input-root /path/to/data --dataset LLFF --cfg cfg/encoder_randomaccess_main.cfg
```

**HM.py 경로 수정 (이 레포에 올리면서 한 것)**: 원래 `/home/<user>/...` 절대경로가 박혀 있던 `HM_ENC_PATH`, `HM_DEC_PATH`, `CONFIG_PATH`, `INPUT_DIR`, 출력 루트를
스크립트 위치(`HM/`) 기준 상대경로 기본값 + 인자(`--enc --dec --cfg --input-root --output-root --dataset`)로 바꿨다. 인코딩/디코딩 로직과 옵션은 그대로다.
`hm.sh` 는 원래 상대경로라 수정하지 않았다. `hm.sh` 의 AI 디코딩은 `HM/residual_ai`, `HM/deblock_ai` 에, RA 예시(주석)는 `./data/...` 에 쓴다.

확인 방법: 파일 크기 = 해상도 × dtype. 예) `ls -l residual_ai` 에서 각 파일이 1,524,096 B, `deblock_ai/after` 가 1,149,120 B 이고 파일 수가 프레임 수(20)와 같으면 된다.

## tools/

추출 결과를 빠르게 눈으로 확인하는 보조 스크립트. 원래 `HM/analysis/새 폴더/data/` 에 있던 것을 내용 수정 없이 복사했다.
경로가 현재 작업 폴더 기준(`./deblock_ra`, `./residual_ra`, `./fern_ra_log.txt`)으로 박혀 있으므로 그 폴더들이 있는 곳에서 실행한다.

| 파일 | 하는 일 | 기본 입력 → 출력 |
|---|---|---|
| `tools/deblock_visual.py` | 모든 POC 의 before/after diff map png (Y, 1008x756 으로 읽음) | `./deblock_ra/{before,after}` → `./deblock_ra/deblock_diff_vis/` |
| `tools/resi_visual.py` | 모든 residual 의 Y 를 npy/png 로 | `./residual_ra/` → `./residual_ra/Y_npy`, `Y_png` |
| `tools/qp_extract.py` | HM 인코더 로그에서 POC 별 slice type / QP 를 json 으로 (키 = POC+1, 6자리) | `./fern_ra_log.txt` → `./fern_ra_qp.json` |

`analysis/` 의 정리된 스크립트(`01_deblock_diff.py`, `03_residual_visual.py`)와 기능이 일부 겹친다. 코덱별로 그대로 두기 위해 합치지 않았다.

## 알려진 한계 / 주의 (코드로 확인, 수정하지 않음)

1. **(수정됨, `Fix:` 커밋) residual 저장 조건이 `-o` 에 묶여 있었음**: 원래 `TAppDecTop::xWriteOutput` 의 조건이 `!m_residualDir.empty()` 가 아니라 `!m_reconFileName.empty()` 였다.
   - 그래서 `--ResidualDir` 없이 `-o` 만 주면 `"/residual_XXXX.yuv"` (루트 경로)에 쓰려고 시도했고,
   - `--ResidualDir` 만 주고 `-o` 를 안 주면 `xWriteOutput` 에서 나가는 픽처의 residual 은 빠지고 마지막 `xFlushOutput` 분만 저장됐다.
   - 지금은 `xWriteOutput` / `xFlushOutput` 모두 `!m_residualDir.empty()` 로 검사한다. `-o` 유무와 관계없이 `--ResidualDir` 를 주면 출력되는 모든 프레임이 저장된다.
   - `hm.sh`, `HM.py` 처럼 `-o` 와 `--ResidualDir` 를 같이 주는 경우의 출력은 바뀌지 않는다.
2. **폴더 생성이 한 단계뿐**: `ResidualDir`, `DeblockDir` 는 `mkdir` 를 한 번만 하므로 상위 폴더가 없으면 생성에 실패하고 파일도 써지지 않는다(에러 메시지 없음). `HM.py` 는 미리 `os.makedirs` 한다.
3. **8-bit 전용**: deblock 덤프는 `Clip3(0,255)` 후 uint8 로 저장한다. 10-bit 입력/내부 비트심도에서는 값이 잘려 깨진다. residual 은 int16 이라 영향 없음.
4. **크기 불일치**: residual 은 크롭(756행), deblock 은 coded(760행). 분석 시 맞춰야 한다.
5. residual 버퍼는 `--ResidualDir` 를 안 줘도 모든 픽처에 대해 만들어진다(메모리만 더 씀, 출력은 없음).
6. Y 만 파일로 쓴다. 버퍼에는 Cb/Cr residual 도 복사되지만 저장하지 않는다.
7. `TAppDecCfg.cpp` 에서 추가한 옵션 뒤 `#if JVET_X0048_X0103_FILM_GRAIN` 줄의 들여쓰기가 흐트러져 있다(기능 영향 없음).
8. residual 은 `sizeof(Pel)` 로 쓴다. 기본 빌드(`RExt__HIGH_BIT_DEPTH_SUPPORT=0`)에서 `Pel`=int16 이고, 이 매크로를 1 로 빌드하면 int32 로 바뀌어 파일 포맷이 달라진다.
9. 4:4:4 RExt 의 cross-component prediction 이 켜진 경우 저장되는 chroma residual 은 CCP 전 값이다(Y 는 영향 없음, 파일에도 Y 만 저장).
