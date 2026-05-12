from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """读取 UTF-8 编码的 JSON 文件并返回解析后的 Python 对象。

    这个函数只负责最基础的反序列化，不做 schema 校验，便于上层
    按阶段契约自行判断字段是否完整、类型是否匹配。
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    """将任意可 JSON 序列化对象写入磁盘。

    写入前会自动创建父目录，采用缩进格式和非 ASCII 保留输出，
    便于运行产物人工审计和跨阶段对比。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
