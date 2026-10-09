# VTM (H.266/VVC) — residual / deblocking 추출 기능 추가본

VVC 참조 소프트웨어 VTM 의 **디코더(DecoderApp)** 에 다음 부수 출력을 추가한 버전이다.

- **residual frame**: inverse transform 직후의 Y residual (`residual_XXXX.yuv`)
- **deblocking 전/후 프레임**: `DecLib::executeLoopFilters` 에서 `deblockingFilterPic` 직전/직후의 복원 프레임 (`deblock/{before,after}/deblock_XXXX.yuv`)

인코더 동작과 비트스트림, 복원 영상(`-o`)은 바뀌지 않는다. 바뀐 내용 전체는 [patches/residual_deblock_vs_upstream.patch](patches/residual_deblock_vs_upstream.patch).
upstream 원래 README 는 [README_upstream.md](README_upstream.md) 로 이름만 바꿔 두었다.

폴더 이름은 upstream 저장소 이름인 `VVCSoftware_VTM` 에서 `VTM` 으로 바꿨다. 이 폴더명을 경로로 쓰던 곳은 `VTM.py` 의 절대경로뿐이었다(아래에서 상대경로로 바꿈).
upstream 파일(`README_upstream.md`, `.gitlab-ci.yml`)에 남은 `VVCSoftware_VTM` 은 저장소 URL 이라 그대로 두었다.

## 기반 upstream

| 항목 | 값 |
|---|---|
| 이름 / 버전 | VTM (VVC Test Model), `VTM-23.14` |
| 저장소 | https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM.git (`master`) |
| 기준 커밋 | `ba166fd31acc050329d40012cd945b52023fdf57` (2026-02-05) |
| 라이선스 | BSD 3-Clause, [COPYING](COPYING). 원본 저작권 표기를 유지한다 |

수정 판정은 `git -c core.fileMode=false diff` 기준이다. 권한만 바뀐 파일과 심볼릭 링크가 풀린 `cfg/keystore/ca/d8e118e3.0` 은 수정으로 보지 않았다.

## 수정한 파일

| 파일 | 수정/추가 | 내용 (함수 단위) |
|---|---|---|
| `source/App/DecoderApp/DecAppCfg.h` | 수정 | 멤버 `m_residualDir`, `m_deblockDir` |
| `source/App/DecoderApp/DecAppCfg.cpp` | 수정 | `DecAppCfg::parseCfg`: 옵션 `--ResidualDir`, `--DeblockDir` 등록 |
| `source/App/DecoderApp/DecApp.cpp` | 수정 | `xCreateDecLib`: `setDeblockDir()`, ResidualDir `mkdir`. `xWriteOutput` / `xFlushOutput`: `neededForOutput` 인 픽처마다(실제 출력 조건과 무관하게) residual 버퍼의 Y 를 conformance window 로 크롭해 `residual_%04d.yuv` (POC+1) 로 쓰고 `destroyResidualBuffer()`. 실패 시 stderr 에 `[ResOut] Failed to open` |
| `source/Lib/DecoderLib/DecLib.h` | 수정 | `DecLib::setDeblockDir()` → deblocking filter 로 전달 |
| `source/Lib/DecoderLib/DecLib.cpp` | 수정 | `DecLib::executeLoopFilters`: `deblockingFilterPic` 앞뒤로 `saveYUVForDebug(cs, "before"/"after")` |
| `source/Lib/CommonLib/DeblockingFilter.h` | 수정 | 멤버 `m_deblockDir`, `setDeblockDir()` (dir, dir/before, dir/after 를 `mkdir`), `saveYUVForDebug()` 선언 |
| `source/Lib/CommonLib/DeblockingFilter.cpp` | 수정 | `DeblockingFilter::saveYUVForDebug`: `picture->getRecoBuf()` 의 Y/Cb/Cr 를 0..255 clip 후 uint8 로 `deblock_%04d.yuv` (POC+1) 저장 |
| `source/Lib/CommonLib/Picture.h/.cpp` | 수정 | 멤버 `m_residualBuffer`, `getResidualBuffer`, `createResidualBuffer` (`cs->area` 크기 = coded 크기), `clearResidualBuffer`, `destroyResidualBuffer`. `Picture::destroy` 에서 해제 |
| `source/Lib/DecoderLib/DecSlice.cpp` | 수정 | `DecSlice::decompressSlice`: residual 버퍼가 없으면 생성, 픽처 첫 슬라이스(`getFirstCtuRsAddrInSlice()==0`)에서 0 초기화. 이전 시도(주석 처리된 코드 블록)가 남아 있음 |
| `source/Lib/DecoderLib/DecCu.cpp` | 수정 | `DecCu::xIntraRecBlk`: inverse transform(+joint CbCr) 직후, chroma residual scaling·복원 전에 TU residual 을 프레임 버퍼로 복사. `DecCu::xDecodeInterTU`: 같은 위치에서 inter TU residual 복사 |
| `VTM.py` | 추가 | 데이터셋 일괄 인코딩 + residual/deblock 추출 |
| `vtm.sh` | 추가 | fern 인코딩/디코딩 예시 명령 |
| `tools/*.py` | 추가 | 보조 스크립트 (아래) |
| `patches/residual_deblock_vs_upstream.patch` | 추가 | upstream 대비 소스 diff |

`DeblockingFilter` 와 `Picture` 는 CommonLib 이지만 residual 버퍼 생성과 `saveYUVForDebug` 호출은 DecoderLib 에만 있어 인코더에서는 실행되지 않는다(코드 확인).

## 추가된 디코더 옵션과 출력

| 옵션 | 출력 |
|---|---|
| `--ResidualDir=<dir>` | `<dir>/residual_XXXX.yuv` |
| `--DeblockDir=<dir>` | `<dir>/before/deblock_XXXX.yuv`, `<dir>/after/deblock_XXXX.yuv` |

`XXXX` = **POC+1** (4자리).

### 데이터 포맷

| | residual | deblock before / after |
|---|---|---|
| 컴포넌트 | Y 만 | Y, Cb, Cr (4:2:0 planar) |
| 자료형 | `Pel` = int16 (기본 빌드), 부호 있음 | uint8, `Clip3(0,255)` |
| 해상도 | conformance window 로 **크롭** (예: 1008x756) | **크롭 안 함**, coded 크기 (예: 1008x760) |
| 파일 크기 (1008x756 입력) | 1,524,096 B | 1,149,120 B |
| 값의 의미 | inverse quantization + inverse transform 결과, 예측에 더해 clip 하기 전. **LMCS 가 켜져 있으면 luma 는 mapped domain 의 residual** (아래 한계 2) | deblocking 전 / 후 복원 영상 (SAO, ALF 적용 전) |
| 저장 시점 | 픽처 출력 루프(`xWriteOutput`/`xFlushOutput`) | `executeLoopFilters` 의 deblocking 앞뒤 |

로컬에서 만든 `vtm_data/residual_{ai,ra}`, `vtm_data/deblock_{ai,ra}` 의 파일 크기가 위 값과 일치하는 것을 확인했다.

## 빌드

upstream 과 같다 (CMake). Linux 기준 `bin/EncoderAppStatic`, `bin/DecoderAppStatic` 가 생긴다.

```bash
cd VTM
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j
```

- 기존 산출물은 Linux 빌드. 위 명령은 이 레포에서 다시 실행해 보지 않았다 (**미검증**).
- 추가 코드가 POSIX `mkdir(path, 0755)` 를 쓰므로 **MSVC(Windows) 빌드는 안 될 가능성이 높다 (미검증)**.

## 인코딩 → 디코딩(추출) 예시

`vtm.sh` 기준 (VTM 폴더에서 실행, 데이터는 `vtm_data/`). 사용 cfg: `cfg/encoder_intra_vtm.cfg` (AI), `cfg/encoder_randomaccess_vtm.cfg` (RA).
`vtm.sh` 에서 활성인 줄은 RA 디코딩뿐이고 나머지는 주석이다. 아래는 AI 예시를 펼친 것이다.

```bash
./bin/EncoderAppStatic -c ./cfg/encoder_intra_vtm.cfg -i ./vtm_data/fern_1008x756_20.yuv -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_enc_ai.yuv \
    --FrameRate=30 -wdt 1008 -hgt 756 --QP=32 --TemporalSubsampleRatio=1 --InputBitDepth=8 --InputChromaFormat=420 \
    --InternalBitDepth=8 --FrameSkip=0 --FramesToBeEncoded=20 | tee ./vtm_data/fern_ai_log.txt

./bin/DecoderAppStatic -b ./vtm_data/fern_ai.bin -o ./vtm_data/fern_ai.yuv --ResidualDir="./vtm_data/residual_ai" --DeblockDir="./vtm_data/deblock_ai"
```

`VTM.py` 는 HM.py 와 같은 방식으로 아래 구조를 만든다 (비트스트림 확장자 `.vvc`).

```
VTM/Compressed/<dataset>/VVC/<scene>/QPxx/
  comp_result/<scene>_<W>x<H>_<N>.{vvc,yuv,txt}
  residual/residual_XXXX.yuv
  deblock/before/deblock_XXXX.yuv
  deblock/after/deblock_XXXX.yuv
```

```bash
python VTM.py                              # 기본: VTM/bin, VTM/cfg/encoder_intra_vtm.cfg, VTM/data/LLFF, 출력 VTM/Compressed/LLFF
python VTM.py --input-root /path/to/data --cfg cfg/encoder_randomaccess_vtm.cfg
```

**경로 수정 (이 레포에 올리면서 한 것)**
- `VTM.py`: `/home/<user>/.../VVCSoftware_VTM/...` 절대경로를 스크립트 위치(`VTM/`) 기준 상대경로 기본값 + 인자(`--enc --dec --cfg --input-root --output-root --dataset`)로 바꿨다. 로직과 인코더/디코더 옵션은 그대로다.
- `vtm.sh`: `./data/...` → 실제 데이터 폴더인 `./vtm_data/...` 로 맞췄다. 주석 처리된 AI 디코딩 줄은 원래 `bin/` 안에서 `../data` 를 보던 것이라 VTM 폴더 기준(`./bin/DecoderAppStatic`, `./vtm_data/...`)으로 맞췄다. RA 디코딩의 `--ResidualDir="./residual_ra" --DeblockDir="./deblock_ra"` 도 실제 결과 위치인 `./vtm_data/residual_ra`, `./vtm_data/deblock_ra` 로 바꿨다.
- `vtm_data/` 는 데이터라 `.gitignore` 로 올리지 않는다.

확인 방법: residual 파일 1,524,096 B, deblock 파일 1,149,120 B, 파일 수 = 프레임 수.

## tools/

`vtm_data/` 와 VTM 루트에 있던 보조 스크립트를 내용 수정 없이 옮겼다. 경로가 현재 작업 폴더 기준이므로 데이터 폴더 안에서 `python ../tools/<script>.py` 로 실행한다.

| 파일 | 원래 위치 | 하는 일 | 기본 입력 → 출력 |
|---|---|---|---|
| `tools/deblock_visual.py` | `vtm_data/` | 모든 POC 의 before/after diff map png (Y, 1008x756) | `./deblock_ra/{before,after}` → `./deblock_ra/deblock_diff_vis/` |
| `tools/resi_visual.py` | `vtm_data/` | 모든 residual 의 Y 를 npy/png | `./residual_ra/` → `Y_npy`, `Y_png` |
| `tools/qp_extract.py` | `vtm_data/` | VTM 인코더 로그에서 POC 별 slice type/QP json (키 = POC+1) | `./fern_ra_log.txt` → `./fern_ra_qp.json` |
| `tools/deblock_diff.py` | VTM 루트 | POC 1개의 diff map 6패널 + 통계, `bit_depth` 인자 있음 | `./deblock_output/{before,after}/deblock_0001.yuv` (1008x760, 8bit) → `./deblock_output/diff_map_poc1.png` |
| `tools/visual.py` | VTM 루트 | residual 1개를 npy/png + 통계 | `./residual_output/residual_0002.yuv` (1008x**760** 으로 읽음) |

- `tools/deblock_diff.py` 의 `load_yuv` 기본값은 `bit_depth=10` 이지만 `__main__` 에서 8 을 넘긴다. 현재 디코더는 8-bit 로 저장하므로 다른 곳에서 함수만 가져다 쓸 때는 `bit_depth=8` 을 줘야 한다.
- `tools/visual.py` 의 기본 `HEIGHT = 760` 은 현재 residual 파일(756행, 크롭됨)보다 커서 그대로 실행하면 크기 불일치 에러가 난다. `HEIGHT = 756` 으로 바꿔 써야 한다(크롭 추가 전 출력용 설정으로 보임, 수정하지 않음).
- `tools/visual.py` 의 `read_residual_y_only` 는 프레임 크기를 Y+Cb+Cr 로 계산한다. residual 파일에는 Y 만 있으므로 `frame_index` 가 0 이 아니면 위치가 틀린다(기본 0 이라 그대로는 문제 없음).
- `analysis/01_deblock_diff.py`, `analysis/03_residual_visual.py` 와 기능이 겹친다(합치지 않음).

## 알려진 한계 / 주의 (코드로 확인, 수정하지 않음)

1. **8-bit 전용 deblock 덤프**: 0..255 clip 후 uint8. 10-bit 내부 비트심도에서는 값이 깨진다. 이전 분석 코드 일부가 VVC deblock 을 uint16 으로 읽었는데, 현재 디코더 출력과 맞지 않는다(`analysis/` 에서는 고침).
2. **LMCS**: `encoder_intra_vtm.cfg`, `encoder_randomaccess_vtm.cfg` 모두 `LMCSEnable: 1` 이다. VVC 에서 LMCS 가 켜지면 luma residual 은 forward-mapped domain 에서 예측에 더해진 뒤 inverse mapping 된다. 따라서 저장된 Y residual 은 `복원 − 예측`(원래 domain)과 같지 않다. HM 과 값의 스케일을 직접 비교할 때 주의.
3. **크기 불일치**: residual 은 크롭(756행), deblock 은 coded(760행).
4. **폴더 생성이 한 단계뿐**: `mkdir` 한 번이라 상위 폴더가 없으면 실패한다. ResidualDir 쪽은 열기 실패 시 stderr 에 메시지가 나오지만 deblock 쪽은 stdout 에 `[DBF] Failed to open` 만 찍는다.
5. residual 버퍼는 `--ResidualDir` 를 안 줘도 모든 픽처에 만들어진다(출력은 없음).
6. Y 만 파일로 쓴다(버퍼에는 Cb/Cr 도 복사됨). chroma 는 joint CbCr 역변환 후, LMCS chroma residual scaling 전 값이다.
7. `DecAppCfg.cpp` 에서 추가한 옵션 뒤 `#if JVET_S0257_DUMP_360SEI_MESSAGE` 줄 들여쓰기가 흐트러져 있다(기능 영향 없음).
8. HM 의 "residual 저장 조건이 `-o` 에 묶이는" 문제는 VTM 에는 없다(`!m_residualDir.empty()` 로 검사).
