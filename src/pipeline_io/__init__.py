"""通用 I/O 辅助包。

提供 JSON、CSV 与图像读写的基础工具，供各阶段共享使用。
"""

from .json_io import read_json, write_json
from .artifact_io import ensure_dir, write_csv_rows
