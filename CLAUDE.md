# CLAUDE.md

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.

---

## 项目概述

双光谱热红外与可见光三维点云生成程序。使用 DJI H30T 无人机的可见光与热红外影像，生成带温度信息的三维点云。面向不熟悉编程的大学生科研场景。

核心流程（9 阶段）：配置加载 → 双光谱标定 → 影像去畸变 → TWMM 跨光谱匹配 → 热红外辐射校正 → Metashape 摄影测量重建 → 可见光重投影 → 点云热富集 → 结果导出与质检

## 技术栈

- Python 3.9+, OpenCV, PyTorch
- Agisoft Metashape Professional 2.2.1（代码必须通过 `metashape.exe -r main.py` 执行，不能直接 `python main.py`）

## 关键约束

- 热红外 TIFF 是主输入，JPG 仅用于预览
- TWMM 核心算法不要重写，只通过适配器集成（`TWMM-main/` 为第三方库）
- 先几何一致性，再热信息融合

## 代码入口

- `main.py` — 全局主程序入口（根目录），负责时序组装调度
- `src/config/config_manager.py` — 配置管理器
- `src/config/runtime_models.py` — 数据模型定义

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

## 文档体系（优先级从高到低）

1. **AGENTS.md** — 全局设计统治文档（冲突时以此为准）
2. **docs/dataset_profile.md** — 数据集物理事实
3. **docs/runtime_config.md** — 运行配置与参数规范
4. **docs/architecture.md** — 系统架构与数据流
5. **docs/file_formats.md** — 数据格式与字段契约

## 修改纪律

- 修改匹配算法 → 先更新 AGENTS.md + docs/matching_algorithm.md
- 修改标定/辐射/重建/富集 → 先更新对应设计文档，再更新代码
- 修改数据格式 → 先更新 docs/file_formats.md
- 修改运行参数 → 先更新 docs/runtime_config.md
- 数据集物理尺寸变化 → 先更新 docs/dataset_profile.md

## 常用命令

```bash
# 安装依赖到 Metashape 内部 Python
& "path/to/metashape/App/Metashape/python/python.exe" -m pip install -r requirements.txt

# 执行全链路
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py"

# 生成元数据文件
exiftool -json test_Arctic/rgb_dir/*.JPG > metadata_all.json
```

## 给 Claude 的提示
- 修改代码前先阅读相关 docs/ 文档了解设计约束
- 不要随意重写 TWMM 核心算法，只修改适配器层
- 代码必须在 Metashape 环境中运行，无法直接用 python 执行
- 项目已有完善的文档体系，修改时请遵循"先更新文档，再更新代码"的原则
