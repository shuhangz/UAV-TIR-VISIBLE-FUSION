"""运行日志配置工具。

这个模块只负责把项目的运行期日志统一到控制台和 run 目录下的日志文件，
不承载业务逻辑。设计目标是：
- 运行过程中能看到阶段级进度
- 结束后能通过单个日志文件回溯完整执行轨迹
- 文件日志尽量详细，控制台日志保持可读
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union


def configure_run_logging(run_dir: Union[str, Path], *, console_level: int = logging.INFO) -> Path:
    """配置整个进程的日志输出。

    Args:
        run_dir: 当前运行的输出目录，日志会写入其下的 logs 目录。
        console_level: 控制台输出级别，文件日志固定为 DEBUG。

    Returns:
        日志文件路径。
    """
    run_dir = Path(run_dir)
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.captureWarnings(True)
    root_logger.debug("Run logging configured: %s", log_file)
    return log_file