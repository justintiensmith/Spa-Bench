from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


def clean(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def main() -> None:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    book = pd.ExcelFile(input_path)
    result: dict[str, dict] = {}
    for sheet in book.sheet_names:
        frame = pd.read_excel(input_path, sheet_name=sheet, header=None, nrows=40)
        while len(frame.columns) and frame.iloc[:, -1].isna().all():
            frame = frame.iloc[:, :-1]
        while len(frame) and frame.iloc[-1].isna().all():
            frame = frame.iloc[:-1]
        result[sheet] = {
            "shape": [int(frame.shape[0]), int(frame.shape[1])],
            "values": [[clean(value) for value in row] for row in frame.itertuples(index=False, name=None)],
        }
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output_path}")
    for sheet, data in result.items():
        print(f"\n### {sheet} {data['shape']}")
        for row in data["values"][:15]:
            print(row)


if __name__ == "__main__":
    main()
