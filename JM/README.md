# JM (H.264/AVC) — residual / deblocking 추출 기능 추가본

H.264/AVC 참조 소프트웨어 JM 의 **디코더(ldecod)** 에 다음 부수 출력을 추가한 버전이다.

- **residual frame**: 매크로블록 복원 직후 `복원(clip) − 예측` 으로 계산한 Y residual (`residual_XXXX.yuv`)
- **deblocking 전/후 프레임**: `DeblockPicture` 호출 직전/직후의 복원 프레임 (`deblock/{before,after}/deblock_XXXX.yuv`)

인코더(lencod) 코드는 바꾸지 않았다. 바뀐 내용 전체는 [patches/residual_deblock_vs_upstream.patch](patches/residual_deblock_vs_upstream.patch).
upstream 원래 README 는 [README_upstream.md](README_upstream.md) 로 이름만 바꿔 두었다.

## 기반 upstream

| 항목 | 값 |
|---|---|
| 이름 / 버전 | JM (H.264/AVC reference software), `JM-19.1-3-g933098b` |
| 저장소 | https://vcgit.hhi.fraunhofer.de/jvet/JM.git (`master`) |
| 기준 커밋 | `933098befc4b18f176e99db8f98c019c27ce9748` (2025-01-19) |
| 라이선스 | ITU-T / ISO/IEC 저작권 고지 [COPYRIGHT_ITU.txt](COPYRIGHT_ITU.txt), [COPYRIGHT_ISO_IEC.txt](COPYRIGHT_ISO_IEC.txt), [disclaimer.txt](disclaimer.txt) 를 유지한다 |

JM 폴더에도 upstream `.git` 이 있었으므로 수정 지점은 키워드 추정이 아니라 `git -c core.fileMode=false diff` 로 정확히 확인했다.

정리하면서 upstream 으로 되돌린 것 (원래 상태는 레포 바깥 백업에 저장):
- `disclaimer.txt`: 로컬에서 삭제돼 있던 것을 upstream 에서 복원.
- `cfg/encoder.cfg`: 로컬에서 `IntraPeriod 0→1`, `QPISlice 28→32` 로 바뀌어 있었는데, 두 값 모두 `jm.sh` 가 `-p` 로 덮어쓰므로 upstream 값으로 되돌렸다.

upstream 에 들어 있던 테스트 입력 `cfg/foreman_part_qcif.yuv`, `foreman_part_qcif_422.yuv`, `foreman_part_qcif_444.yuv` (합계 약 0.5 MB)는
레포 규칙(`*.yuv` 미업로드)에 따라 이 레포에 포함하지 않았다. `cfg/encoder.cfg` 기본 입력으로 돌리려면 upstream 저장소에서 받아야 한다.

## 수정한 파일

| 파일 | 수정/추가 | 내용 (함수 단위) |
|---|---|---|
| `source/app/ldecod/global.h` | 수정 | `InputParameters` 에 `DeblockDir[]`, `ResidualDir[]` 추가 |
| `source/app/ldecod/configfile.h` | 수정 | `Map[]` 에 `DeblockDir`, `ResidualDir` (문자열 파라미터) 등록 → `-p DeblockDir=...` 로 지정 |
| `source/app/ldecod/ldecod.c` | 수정 | `OpenDecoder`: DeblockDir, DeblockDir/before, DeblockDir/after, ResidualDir 를 `mkdir`(`_mkdir` on WIN32). `#include <sys/stat.h>` 주석 해제. 파일 머리 주석의 기여자 이름 문자 인코딩이 바뀜(기능 무관) |
| `source/app/ldecod/mbuffer.h` | 수정 | `StorablePicture` 에 `int **imgY_res` 추가 |
| `source/app/ldecod/mbuffer.c` | 수정 | `alloc_storable_picture`: `imgY_res` 를 coded 크기로 할당(`get_mem2Dint`, calloc). `free_storable_picture`: 해제 |
| `source/app/ldecod/macroblock.c` | 수정 | `decode_one_macroblock`: Y 복원 직후 MB 16x16 에 대해 `imgY_res = imgY − mb_pred[PLANE_Y]` 저장 (ResidualDir 지정 시). 디버그 `printf("[DEBUG] MB0 mb_rres ...")` 추가 (주소 0 MB 마다, 항상 출력). 파일 머리 주석 인코딩 변경 |
| `source/app/ldecod/image.c` | 수정 | 헬퍼 `save_yuv_frame` (Y/Cb/Cr, 0..255 clip, uint8), `save_residual_frame` (Y, int16) 추가. `exit_picture`: deblocking 분기 안에서 `calculate_frame_no` → residual 저장 → `before` 저장 → `DeblockPicture` (또는 JV 4:4:4 분리 평면 경로) → `after` 저장 |
| `jm.sh` | 추가 | fern 인코딩/디코딩 예시 명령 |
| `tools/*.py` | 추가 | 보조 스크립트 (아래) |
| `patches/residual_deblock_vs_upstream.patch` | 추가 | upstream 대비 소스 diff |

## 추가된 디코더 파라미터와 출력

| 파라미터 | 출력 |
|---|---|
| `-p ResidualDir="<dir>"` | `<dir>/residual_XXXX.yuv` |
| `-p DeblockDir="<dir>"` | `<dir>/before/deblock_XXXX.yuv`, `<dir>/after/deblock_XXXX.yuv` |

`XXXX` = `frame_no + 1`. `frame_no` 는 JM 의 `calculate_frame_no` 값(`IDR 기준 번호 + POC / poc_scale`)으로, 프레임 코딩에서는 **표시 순서 번호**(0부터)다. 즉 HM/VTM 의 POC+1 과 같은 의미로 1부터 붙는다.

### 데이터 포맷

| | residual | deblock before / after |
|---|---|---|
| 컴포넌트 | Y 만 | Y, Cb, Cr (4:2:0 planar, 4:0:0 이면 Y 만) |
| 자료형 | int16 (`int` 버퍼를 int16 으로 캐스팅), 부호 있음 | uint8, `iClip3(0,255)` |
| 해상도 | **크롭 안 함**, MB 정렬 coded 크기 (예: 1008x768) | **크롭 안 함**, coded 크기 (예: 1008x768) |
| 파일 크기 (1008x756 입력) | 1008×768×2 = 1,548,288 B | 1008×768×1.5 = 1,161,216 B |
| 값의 의미 | `imgY(복원, 0..255 clip 후) − 예측`. **clip 후 값**이라 HM/VTM 의 inverse transform 출력과 포화 픽셀에서 다를 수 있다 | deblocking 직전 / 직후 복원 영상 |
| 저장 시점 | `exit_picture` 에서 deblocking 직전 | `exit_picture` 의 `DeblockPicture` 전후 |

HM/VTM 과 달리 **residual 도 크롭되지 않는다**. 1008x756 입력이면 residual/deblock 모두 768행이고, 분석 시 위쪽 756행만 쓴다 (`analysis/common/io_utils.py` 의 `--codec AVC` 가 처리).

## 빌드

upstream 과 같다 (CMake). Linux 기준 `bin/lencod_static`, `bin/ldecod_static` 가 생긴다.

```bash
cd JM
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j
```

- 기존 산출물은 Linux gcc 9.4 빌드. 위 명령은 이 레포에서 다시 실행해 보지 않았다 (**미검증**).
- WIN32 경로는 `_mkdir` 를 쓰지만 `<direct.h>` include 가 없어 MSVC 에서 컴파일 경고/오류가 날 수 있다 (**미검증**).

## 인코딩 → 디코딩(추출) 예시

`jm.sh` 기준 (JM 폴더에서 실행, 데이터는 `jm_data/`). 사용 cfg: 인코더 `cfg/encoder.cfg`, 디코더 `cfg/decoder.cfg`.
`jm.sh` 에서 활성인 줄은 RA 인코딩뿐이고 AI 인코딩과 두 디코딩은 주석이다. 아래는 AI 예시를 펼쳐 쓴 것이다.

```bash
# 인코딩 (all-intra, QP32, 20프레임)
./bin/lencod_static -d ./cfg/encoder.cfg -p InputFile="./jm_data/fern_1008x756_20.yuv" -p OutputFile="./jm_data/fern_enc_ai.264" \
    -p ReconFile="./jm_data/fern_recon_ai.yuv" -p SourceWidth=1008 -p SourceHeight=756 -p OutputWidth=1008 -p OutputHeight=756 \
    -p QPISlice=32 -p IntraPeriod=1 -p NumberBFrames=0 -p FramesToBeEncoded=20 | tee ./jm_data/fern_ai_log.txt

# 디코딩 + 추출
./bin/ldecod_static -d ./cfg/decoder.cfg -p DeblockDir="./jm_data/deblock_ai" -p ResidualDir="./jm_data/residual_ai" \
    -p OutputFile="./jm_data/fern_dec_ai.264" -p RefFile="./jm_data/fern_recon_ai.yuv" -p InputFile="./jm_data/fern_enc_ai.264"
```

- `jm.sh` 의 디코더 `OutputFile` 은 이름이 `.264` 지만 실제로는 **디코딩된 YUV** 가 써진다(원래 스크립트 그대로 둠).
- HM.py/VTM.py 같은 일괄 스크립트는 없다. HM/VTM 과 같은 `Compressed/<dataset>/AVC/<scene>/QPxx/{residual,deblock}` 구조로 쓰려면 위 명령의 경로를 그렇게 지정하면 된다.

**jm.sh 경로 수정 (이 레포에 올리면서 한 것)**: 원래 모든 경로가 `./data/...` 였는데 실제 데이터 폴더는 `jm_data/` 라서 `./jm_data/...` 로 맞췄다. 명령과 옵션은 그대로다.
`jm_data/` 는 데이터라 `.gitignore` 로 올리지 않는다.

확인 방법: `residual_ai/residual_0001.yuv` 가 1,548,288 B, `deblock_ai/after/deblock_0001.yuv` 가 1,161,216 B, 파일 수가 프레임 수(20)와 같으면 된다
(로컬 `jm_data/` 의 ai/ra 결과가 실제로 이렇다).

## tools/

`jm_data/` 에 있던 보조 스크립트를 내용 수정 없이 옮겼다. 경로가 현재 작업 폴더 기준이므로 `jm_data/` 안에서 `python ../tools/<script>.py` 로 실행한다.

| 파일 | 하는 일 | 기본 입력 → 출력 |
|---|---|---|
| `tools/deblock_visual.py` | 모든 POC 의 before/after diff map png (Y, **1008x768** 로 읽음) | `./deblock_ra/{before,after}` → `./deblock_ra/deblock_diff_vis/` |
| `tools/resi_visual.py` | 모든 residual 의 Y 를 npy/png (**1008x768**) | `./residual_ra/` → `./residual_ra/Y_npy`, `Y_png` |
| `tools/qp_extract.py` | JM 인코더 로그(`00000(IDR) ...` 줄)에서 프레임별 type/QP 를 json 으로 | `fern_ra_log.txt` → `fern_ra_qp.json` |

`analysis/01_deblock_diff.py`, `analysis/03_residual_visual.py` 와 기능이 일부 겹친다(합치지 않음).

## 알려진 한계 / 주의 (코드로 확인, 수정하지 않음)

1. **deblocking 이 꺼진 픽처는 아무것도 저장하지 않음**: 저장 코드가 `exit_picture` 의 `if (!iDeblockMode && bDeblockEnable...)` 안에 있다. 픽처의 모든 슬라이스가 `disable_deblocking_filter_idc == 1` 이면 residual 도 저장되지 않는다.
2. **residual 정의가 HM/VTM 과 다름**: inverse transform 출력이 아니라 `clip(예측+residual) − 예측` 이다. 복원값이 0 또는 255 로 포화된 픽셀에서는 실제 residual 보다 작다.
3. **크롭 안 함**: residual 과 deblock 모두 MB 정렬 크기(예: 768행)로 저장된다.
4. **폴더 생성이 한 단계뿐**: `mkdir` 한 번이라 상위 폴더가 없으면 실패한다(에러 메시지 없음).
5. **8-bit 전용**: deblock 덤프는 0..255 clip 후 uint8.
6. **디버그 출력**: `decode_one_macroblock` 이 주소 0 MB 마다 `[DEBUG] MB0 mb_rres min=.., max=..` 를 stdout 에 찍는다(ResidualDir 지정 여부와 무관). 디코딩 결과에는 영향 없음.
7. `mbuffer.c` 의 `memset(..., size_y*size_x*sizeof(uint16))` 은 `int` 버퍼의 절반만 지우지만, 버퍼가 `calloc` 으로 할당돼 이미 0 이므로 실제 영향은 없다.
8. `image.c` 의 `save_residual_frame` 주석("128 bias로 저장")은 코드와 다르다. 실제로는 bias 없이 int16 으로 저장한다.
9. residual 버퍼는 ResidualDir 를 안 줘도 모든 픽처에 할당된다(메모리만 더 씀).
10. `decode_one_macroblock` 의 residual 계산은 프레임(progressive) 코딩에서만 확인했다. field / MBAFF, I_PCM 매크로블록에서의 동작은 확인하지 않았다.
