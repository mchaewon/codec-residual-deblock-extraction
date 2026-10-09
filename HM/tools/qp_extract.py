import re
import json
from pathlib import Path


HM_LINE_RE = re.compile(
    r"""^POC\s+(\d+)\s+TId:\s*\d+\s+\(\s*([IPB])-SLICE,\s*nQP\s*\d+\s*QP\s*(\d+)\s*\)""",
    re.VERBOSE
)

def hm_log_to_qp_json(log_path: str, out_json_path: str):
    log_path = Path(log_path)
    out_json_path = Path(out_json_path)

    result = {}

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            m = HM_LINE_RE.match(line)
            if not m:
                continue

            poc = int(m.group(1))
            slc_type = m.group(2)  # 'I' / 'P' / 'B'
            qp = int(m.group(3))

            key = f"{poc + 1:06d}"  # POC+1, 6-digit zero padding
            result[key] = {"qp": qp, "type": slc_type}

    # (선택) key 기준 정렬해서 저장
    result = dict(sorted(result.items(), key=lambda kv: int(kv[0])))

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    with out_json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved {len(result)} entries to: {out_json_path}")


if __name__ == "__main__":
    hm_log_to_qp_json(
        log_path="./fern_ra_log.txt",          # HM log txt
        out_json_path="./fern_ra_qp.json"      # output json
    )