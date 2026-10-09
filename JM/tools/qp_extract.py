import re
import json
from pathlib import Path


# 예:
# 00000(IDR)  577384   32  34.348  ...
# 00008( P )  351688   32  34.609  ...
# 00002( B )  328824   33  32.270  ...
JM_LINE_RE = re.compile(
    r"""^
    (\d{5})              # frame index (POC)
    \(\s*([A-Z]{1,3})\s*\)   # type token: IDR / P / B / etc
    \s+\d+               # bits (or Bit/pic)
    \s+(\d+)             # QP
    """,
    re.VERBOSE
)

def parse_jm_avc_log(log_path: str, out_json_path: str):
    log_path = Path(log_path)
    out_json_path = Path(out_json_path)

    result = {}

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            # JM 로그에는 00000(NVB) 같은 라인도 있는데 QP가 없어서 자연히 매치 안 됨
            m = JM_LINE_RE.match(line)
            if not m:
                continue

            poc = int(m.group(1))
            token = m.group(2).strip()  # IDR / P / B ...
            qp = int(m.group(3))

            # type 정규화: IDR, I 등은 모두 I로 취급
            if token in ("IDR", "I"):
                slc_type = "I"
            elif token == "P":
                slc_type = "P"
            elif token == "B":
                slc_type = "B"
            else:
                # 혹시 모르는 타입 토큰이 나오면 그대로 저장(원하면 continue로 무시 가능)
                slc_type = token

            key = f"{poc + 1:06d}"   # POC+1, 6자리
            result[key] = {"qp": qp, "type": slc_type}

    # (선택) key 기준 정렬
    result = dict(sorted(result.items(), key=lambda kv: int(kv[0])))

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    with out_json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved {len(result)} entries to: {out_json_path}")


if __name__ == "__main__":
    parse_jm_avc_log(
        log_path="fern_ra_log.txt",
        out_json_path="fern_ra_qp.json"
    )