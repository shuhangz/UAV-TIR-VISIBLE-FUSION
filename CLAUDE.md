# CLAUDE.md

## 项目概述

本项目是**双光谱热红外与可见光三维点云生成程序**，使用 DJI H30T 无人机的可见光与热红外影像，生成带温度信息的三维点云。面向不熟悉编程的大学生科研场景。

**核心流程**（9 个阶段）：
1. 配置与元数据加载
2. 双光谱系统标定（棋盘格）
3. 影像去畸变与预处理
4. 跨光谱匹配与单应性（TWMM 算法）
5. 热红外辐射校正与温度提取
6. 多视角摄影测量重建（Metashape）
7. 可见光重投影与可见性判断
8. 点云热富集
9. 结果导出与质检报告

**技术栈**：Python 3.9+, OpenCV, PyTorch, Agisoft Metashape Professional 2.2.1

## 关键约束

- **必须通过 Metashape 引擎执行**：代码不能用 `python main.py` 运行，必须通过 Metashape 的 `metashape.exe -r main.py` 调用
- **热红外 TIFF 是主输入**，JPG 仅用于预览和人工检查
- **TWMM 核心算法不要重写**，只通过适配器集成
- **先几何一致性，再热信息融合**

## 代码入口

- `main.py` — 全局主程序入口（根目录），负责时序组装调度
- `src/config/config_manager.py` — 配置管理器
- `src/config/runtime_models.py` — 数据模型定义

## 项目结构

代码包统一放在 `src/` 目录下，`main.py` 通过 `sys.path` 引导自动找到它们。运行时只需执行 `metashape.exe -r main.py`，无需关心 `src/` 内部结构。

## 模块目录

| 目录 | 职责 |
|------|------|
| `src/config/` | 配置管理、参数校验、运行清单 |
| `src/calibration/` | 棋盘格检测、双光谱标定 |
| `src/preprocess/` | 影像去畸变、CLAHE、Otsu |
| `src/matching/` | TWMM 适配、跨光谱匹配、单应性 |
| `src/radiometry/` | 热红外温度矩阵提取与辐射校正 |
| `src/geometry/` | 三维重投影、可见性判断 |
| `src/enrichment/` | 点云热富集、多视图融合 |
| `src/pipeline_io/` | 文件读写、日志、清单 |
| `src/validation/` | 质检报告、评估指标 |
| `src/metashape_reconstruction/` | Metashape 摄影测量重建 |
| `TWMM-main/` | 第三方跨光谱匹配库（不要修改） |

## 文档体系（优先级从高到低）

1. **AGENTS.md** — 全局设计统治文档（冲突时以此为准）
2. **docs/dataset_profile.md** — 数据集物理事实（影像尺寸、标定板几何）
3. **docs/runtime_config.md** — 运行配置与参数规范
4. **docs/architecture.md** — 系统架构与数据流
5. **docs/file_formats.md** — 数据格式与字段契约
6. **docs/matching_algorithm.md** — TWMM 匹配算法细节
7. **docs/radiometry_model.md** — 热辐射校正模型
8. **docs/reconstruction_and_enrichment.md** — 重建与点云富集

## 常用命令

```bash
# 安装依赖到 Metashape 内部 Python
& "path/to/metashape/App/Metashape/python/python.exe" -m pip install -r requirements.txt

# 执行全链路
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py"

# 生成元数据文件
exiftool -json test_Arctic/rgb_dir/*.JPG > metadata_all.json
```

## 修改纪律

- 修改匹配算法 → 先更新 AGENTS.md + docs/matching_algorithm.md
- 修改标定/辐射/重建/富集 → 先更新对应设计文档，再更新代码
- 修改数据格式 → 先更新 docs/file_formats.md
- 修改运行参数 → 先更新 docs/runtime_config.md
- 数据集物理尺寸变化 → 先更新 docs/dataset_profile.md

## 给 Claude 的提示

- 这是一个科研项目，用户是不熟悉编程的大学生，解释时请用通俗易懂的语言
- 修改代码前先阅读相关 docs/ 文档了解设计约束
- 不要随意重写 TWMM 核心算法，只修改适配器层
- 代码必须在 Metashape 环境中运行，无法直接用 python 执行
- 项目已有完善的文档体系，修改时请遵循"先更新文档，再更新代码"的原则
