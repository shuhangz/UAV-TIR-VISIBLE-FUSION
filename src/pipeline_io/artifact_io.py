from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence


def ensure_dir(path: Path) -> None:
    """确保目录存在。

    这是产物写入前的统一入口，避免上层在多个地方重复调用 mkdir。
    """
    path.mkdir(parents=True, exist_ok=True)


def write_csv_rows(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    """写出带表头的 CSV 行集合。

    用于匹配、重投影、质检等阶段导出结构化中间结果。函数不会强制
    处理数据类型，调用方需要保证每一列的字段顺序与下游契约一致。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(list(header))
        for row in rows:
            writer.writerow(list(row))
