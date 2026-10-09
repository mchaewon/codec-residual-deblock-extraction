import re
import json
from pathlib import Path


def parse_vtm_log(log_path, output_json):

    pattern = re.compile(
        r"POC\s+(\d+).*?\(\s*.*?,\s*([IPB])-SLICE,\s*QP\s*(\d+)"
    )

    result = {}

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                poc = int(m.group(1))
                slice_type = m.group(2)
                qp = int(m.group(3))

                key = f"{poc+1:06d}"

                result[key] = {
                    "qp": qp,
                    "type": slice_type
                }

    # key 정렬
    result = dict(sorted(result.items(), key=lambda x: int(x[0])))

    with open(output_json, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Saved {len(result)} frames → {output_json}")


if __name__ == "__main__":
    parse_vtm_log(
        "./fern_ra_log.txt",
        "./fern_ra_qp.json"
    )