# 双光谱热红外与可见光三维点云生成程序

**项目目标**：用 DJI H30T 的可见光与热红外影像，生成带温度信息的三维点云。

整个处理流程从原始无人机影像到最终的热富集点云，共 9 个阶段：
1. 配置与元数据加载
2. 双光谱系统标定
3. 影像去畸变与预处理
4. 跨光谱匹配与单应性（TWMM）
5. 热红外辐射校正与温度提取
6. 多视角摄影测量重建（Metashape）
7. 可见光重投影与可见性判断
8. 点云热富集
9. 结果导出与质检报告

---

## 快速开始

### 前置要求

1. **Python 3.9+** 与 pip
2. **Agisoft Metashape Professional 2.2.1**（绿色免安装专业版，必须通过其内部集成的 Python 环境执行代码）
3. **ExifTool 13.48+**（用于提取相机元数据）
4. **项目依赖包安装与执行（极其重要）**

> ⚠️ **注意**：由于 Metashape 的授权及环境独占性，代码必须在 Metashape 内部集成的 Python 环境中运行，不能使用系统外部的 Python 虚拟环境。

#### 安装依赖到 Metashape 内部
打开 PowerShell，执行以下命令（请根据你的实际路径调整 `D:\OneDrive\Desktop\techical_route_new`）：
```powershell
& "path/to/metashape/App/Metashape/python/python.exe" -m pip install -r "path/to/requirements.txt"
```

#### 在 Metashape 内部执行主脚本
安装完依赖后，必须通过 `metashape.exe -r` 参数来执行主入口脚本：
```powershell
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py"
```

#### 其他关键说明

- **Metashape**：本项目使用的是绿色免安装版的 Metashape Professional 2.2.1，解压后通过其内部 Python 环境执行代码。
- **ExifTool**：需要独立安装（Windows: 下载 exe；macOS/Linux: brew install exiftool）

### 数据准备

项目的标准目录结构应为：

```
workspace_root/
├── test_Arctic/              # 业务处理数据集
│   ├── rgb_dir/             # 可见光图像（RGB JPG/PNG）
│   ├── tiff_dir/            # 热红外 TIFF 主输入帧（推荐使用）
│   ├── thermal_dir/         # 热红外 JPG 预览（可选）
│   └── 航线参数.txt         # 飞行元数据
├── M400-H30T-CALIB-CHESSBOARD/  # 标定数据集
│   ├── RGB/                 # 棋盘格标定板的可见光图像
│   └── NIR/                 # 棋盘格标定板的热红外图像
├── src/                     # 所有 Python 代码包
│   ├── config/              # 配置管理
│   ├── calibration/         # 双光谱标定
│   ├── preprocess/          # 影像去畸变与预处理
│   ├── matching/            # 跨光谱匹配
│   ├── radiometry/          # 热辐射校正
│   ├── metashape_reconstruction/  # 摄影测量重建
│   ├── geometry/            # 重投影与几何计算
│   ├── enrichment/          # 点云热富集
│   ├── pipeline_io/         # 输入输出管理
│   └── validation/          # 质检与验证
├── docs/references/         # 中文参考文献
├── H30T_RGB.xml             # RGB 初始标定参数
├── H30T_NIR.xml             # 热红外初始标定参数
├── TWMM-main/               # 跨光谱匹配库
├── metadata_all.json        # 相机元数据（需手动或 exiftool 生成）
├── requirements.txt         # Python 依赖
└── main.py                  # 主入口脚本
```

### 生成 metadata_all.json

**metadata_all.json 需要手动生成**，方式如下：

```bash
# 使用 exiftool 提取所有影像的元数据
exiftool -json test_Arctic/rgb_dir/*.JPG > metadata_all.json
```

或同时提取热红外和可见光元数据：

```bash
exiftool -json test_Arctic/rgb_dir/*.JPG test_Arctic/tiff_dir/*.TIFF > metadata_all.json
```

**注意**：该文件记录了相机的焦距、感光度、曝光时间、传感器温度等关键参数，后续阶段（尤其是热辐射校正）依赖它。

### 执行全链路

> **注意**：不可以使用 `python main.py`，必须通过 Metashape 引擎来调用！

```powershell
# 默认使用 workspace_root 的数据进行完整处理
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py"

# （可选）通过参数指定（注：在作为脚本传递给 Metashape 时，若需附加脚本参数，可在脚本后空一格再加上，如）：
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py" run_all

# 指定自定义配置文件（JSON 格式）
& "path/to/metashape/App/Metashape/metashape.exe" -r "path/to/main.py" --config-file path/to/custom_config.json
```

---

## 模块与工作流

### 0. 配置层（src/config/）

- **职责**：加载运行参数、管理工作区路径、生成可审计的运行清单
- **关键文件**：
  - `config_manager.py`：配置管理器，处理参数校验与路径规范化
  - `runtime_models.py`：数据模型定义（DatasetProfile, EnvironmentParameters 等）

### 1. 标定层（src/calibration/）

- **职责**：用棋盘格目标完成双光谱系统标定
- **输入**：`M400-H30T-CALIB-CHESSBOARD/RGB` 和 `M400-H30T-CALIB-CHESSBOARD/NIR`
- **输出**：相机矩阵、畸变系数、重投影误差、质量标记
- **方法**：OpenCV 棋盘格检测 + 相机标定（Zhang 2000）

### 2. 预处理层（src/preprocess/）

- **职责**：影像去畸变与前处理
- **输入**：原始 RGB/热红外影像 + 标定结果
- **输出**：几何校正后的图像
- **处理**：
  - RGB：CLAHE 对比度归一化
  - 热红外：灰度反转 + Otsu 自动二值化 + 局部对比度增强

### 3. 匹配层（src/matching/）

- **职责**：跨光谱特征匹配与单应性估计（基于 TWMM）
- **输入**：去畸变后的 RGB 与热红外图像对
- **输出**：对应点、异常值剔除结果、单应性矩阵
- **核心文件**：`twmm_adapter.py`（TWMM 的包装接口）

### 4. 热辐射层（src/radiometry/）

- **职责**：从热红外 TIFF 提取温度矩阵
- **输入**：热红外 TIFF 主帧 + metadata_all.json + 环境参数
- **输出**：温度矩阵（°C 或 K）+ 元数据记录
- **依赖**：DJI SDK、ExifTool 字段、环境温度、相对湿度

### 5. 重建层（src/metashape_reconstruction/photogrammetry.py）

- **职责**：多视角立体重建生成稠密点云
- **输入**：RGB 影像组 + 内参
- **输出**：三维点云、相机姿态、深度图
- **流程**：特征匹配 → 相机对齐 → 深度图构建 → 稠密云生成

### 6. 重投影层（src/geometry/reprojection_export.py）

- **职责**：建立 3D 点与 2D 图像的对应关系
- **输入**：点云 + Metashape 项目 + RGB 标定
- **输出**：重投影坐标、误差、可见性标记

### 7. 热富集层（src/enrichment/thermal_enrichment.py）

- **职责**：为点云赋予温度属性
- **输入**：重投影记录 + 温度矩阵 + 单应性矩阵
- **输出**：带温度的点云 (XYZ, RGB, Temperature)
- **策略**：双线性插值 + 可见性过滤 + 多视图融合

### 8. 导出层（src/validation/ 和 src/pipeline_io/）

- **职责**：点云导出与质检报告生成
- **输出**：PLY/LAS 格式点云、匹配对叠加图、温度分布直方图、质量评分

---

## 常见参数与配置

### 配置文件示例（custom_config.json）

```json
{
  "workspace_root": "/path/to/workspace",
  "input_dataset_root": "/path/to/workspace/test_Arctic",
  "calibration_dataset_root": "/path/to/workspace/M400-H30T-CALIB-CHESSBOARD",
  "metadata_json": "/path/to/workspace/metadata_all.json",
  "stage_selection": ["calibration", "preprocess", "matching", "radiometry", "metashape", "geometry", "enrichment", "export"],
  "photogrammetry": {
    "downscale_align": 1,
    "downscale_depth": 4
  },
  "environment": {
    "air_temperature_celsius": 25.0,
    "relative_humidity_percent": 50.0
  }
}
```

### 常用命令行参数

- `--config-file`：指定配置 JSON 文件路径

### 跳过特定阶段

在配置中修改 `stage_selection` 数组，只包含需要执行的阶段名称。例如，仅执行标定和预处理：

```json
"stage_selection": ["calibration", "preprocess"]
```

---

## 输出结构

每次执行会在 `runs/` 目录下生成以下结构：

```
runs/
└── test_Arctic__<timestamp>__<checksum>/
    ├── calibration/       # 标定结果与内参
    ├── preprocess/        # 去畸变图像
    ├── matching/          # 匹配结果与单应性矩阵
    ├── radiometry/        # 温度矩阵与辐射元数据
    ├── metashape/         # 点云与相机姿态
    ├── geometry/          # 重投影记录
    ├── enrichment/        # 热富集点云
    ├── reports/           # 质检报告与统计
    └── manifest/          # 阶段执行清单与日志
```

---

## 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|--------|
| `ModuleNotFoundError: No module named 'Metashape'` | Metashape 未安装或未授权 | 安装 Metashape Professional 2.2.1 并授权 |
| `FileNotFoundError: metadata_all.json` | 元数据文件缺失 | 运行 `exiftool -json test_Arctic/rgb_dir/*.JPG > metadata_all.json` |
| `棋盘格检测率低` | 标定板图像质量差 | 检查 `M400-H30T-CALIB-CHESSBOARD/` 中的图像是否清晰 |
| 匹配点数过少 | 可见光与热红外光谱差异大或 TWMM 参数不当 | 调整 TWMM 参数或检查输入图像质量 |
| 点云密度低 | RGB 特征不足或重建参数不当 | 调整 `downscale_align` 和 `downscale_depth` 参数 |
| 温度值异常（超出范围） | 环境参数设置错误或元数据缺失 | 检查 metadata_all.json 和环保参数配置 |

---

## 文档索引

- [AGENTS.md](AGENTS.md) - 全局设计统治文档
- [docs/architecture.md](docs/architecture.md) - 系统架构与数据流
- [docs/dataset_profile.md](docs/dataset_profile.md) - 数据集物理事实与基线参数
- [docs/runtime_config.md](docs/runtime_config.md) - 运行时配置与参数规范
- [docs/file_formats.md](docs/file_formats.md) - 数据格式与契约定义
- [docs/calibration_model.md](docs/calibration_model.md) - 标定模型
- [docs/matching_algorithm.md](docs/matching_algorithm.md) - 匹配与单应性算法
- [docs/radiometry_model.md](docs/radiometry_model.md) - 热辐射校正模型
- [docs/reconstruction_and_enrichment.md](docs/reconstruction_and_enrichment.md) - 重建与点云富集
- [docs/references/技术路线参考文献.md](docs/references/技术路线参考文献.md) - 端到端流程顶层设计参考
- [docs/references/可见光与热红外影像匹配参考文献.md](docs/references/可见光与热红外影像匹配参考文献.md) - 跨光谱匹配算法参考
- [docs/references/提炼技术路线参考文献.md](docs/references/提炼技术路线参考文献.md) - 技术路线提炼指导
- [docs/references/提炼图像匹配参考文献.md](docs/references/提炼图像匹配参考文献.md) - 图像匹配提炼指导
- [docs/references/metashape_python_api_2_2_1_MinerU__20251017023519.md](docs/references/metashape_python_api_2_2_1_MinerU__20251017023519.md) - Metashape Python API 参考

---

## 许可证与引用

本项目集成了多个开源库与学术方法。核心匹配算法基于 TWMM（可见光-热红外匹配论文）。请参考 [TWMM-main/README.md](TWMM-main/README.md) 了解相关论文与引用信息。
