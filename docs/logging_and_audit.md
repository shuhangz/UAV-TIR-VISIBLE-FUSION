# logging_and_audit.md

## 1. 文档目的

本文档定义本项目的运行日志与审计轨迹规范。它只描述“如何记录一次运行发生了什么”，不描述算法实现，也不描述阶段内部的数值公式。

## 2. 设计目标

- 运行时能从控制台快速看见阶段进度。
- 运行结束后能从单个日志文件回放整次执行。
- 任何失败都应带有阶段名、异常信息和上下文摘要。
- 日志只增强可观察性，不改变业务逻辑和数据契约。

## 3. 日志输出位置

- 控制台：显示阶段开始、完成、失败、耗时和摘要信息。
- 文件：`runs/<run_id>/logs/run.log`
- 文件滚动：按大小滚动保留最近的运行痕迹，避免单次长任务无限增长。

## 4. 日志内容范围

- `main.py` 记录全局运行上下文、阶段状态和总耗时。
- `calibration` 记录角点检测、标定结果写入和回退情况。
- `preprocess` 记录去畸变输出路径、裁切信息和图像尺寸。
- `matching` 记录匹配对数量、置信摘要和输出位置。
- `radiometry` 记录帧数、质量标记和温度矩阵输出。
- `metashape` 记录照片数量、对齐、深度图和点云抽取状态。
- `geometry` 记录重投影点数与可见性统计。
- `enrichment` 记录覆盖率、支持视角数和富集输出。
- `validation` 记录 PLY 导出结果。

## 5. 级别约定

- `DEBUG`：细粒度诊断信息、边界值和内部摘要。
- `INFO`：阶段开始、完成、输出路径、统计摘要。
- `WARNING`：可降级但不致命的问题。
- `ERROR`：阶段失败、文件写入失败、外部环境不可用。
- `EXCEPTION`：保留堆栈的失败日志，默认用于阶段异常。

## 6. 运行时边界

- 不把第三方库的内部输出当作本项目业务日志。
- 不用 `logging.basicConfig()` 在多个模块里重复初始化根日志器。
- 业务模块只拿 `logging.getLogger(__name__)` 记录消息，由入口统一配置 handler。

## 7. 与其他文档的关系

- [AGENTS.md](../AGENTS.md) 定义日志体系在工程中的职责边界。
- [docs/architecture.md](architecture.md) 定义日志与 io / validation 的关系。
- [docs/runtime_config.md](runtime_config.md) 定义 `log_level` 等运行参数。
- [docs/file_formats.md](file_formats.md) 定义 `runs/<run_id>/logs/` 的落盘位置。