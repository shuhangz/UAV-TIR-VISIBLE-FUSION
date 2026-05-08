**概述**

- **目的**: 本文档说明如何使用仓库中的三份核心模块来完成「配置与数据入口」→「光学系统标定」→「图像去畸变」的最小流程。
- **相关文件**: [config_manager.py](config_manager.py)、[calibrator.py](calibrator.py)、[undistort.py](undistort.py)

**功能摘要**

- **ConfigManager**: 管理运行上下文、创建 `runs/<run_id>/...` 目录结构、导出运行清单、提供常用路径（通过 `get_calibration_output_path()`、`get_stage_dir()` 等接口）。
- **DualSpectralCalibrator**: 棋盘格检测与相机标定。主要方法 `calibrate(image_paths, sensor_name, is_tir=False)` 返回标定结果字典，`save_calibration(result, config)` 将结果合并写入审计文件（由 `ConfigManager.get_calibration_output_path()` 指定）。
- **ImageUndistorter**: 使用标定结果重建相机矩阵并对单张图像执行去畸变（裁切 ROI），保存去畸变图像并写入 sidecar 元数据（`<output>_meta.json`）。对热红外 TIFF 会尝试保留原始标签（若安装了 `tifffile` 或 Pillow）。

**开发/运行前准备**

- 激活项目虚拟环境并安装依赖（在仓库根）:

```powershell
& .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**快速验证（smoke-test）**

- 仓库内自带的快速测试脚本: `scripts/tmp_test_undistort.py`。运行命令：

```powershell
python scripts\tmp_test_undistort.py
```

该脚本会读取 `test_1/rgb_dir/` 的示例 RGB 图像，构造一个简单的 dummy calibration，运行 `ImageUndistorter.process_image()` 并把结果写到 `runs/debug_undistort/`。

**详细使用说明与示例**

**1) 初始化运行上下文（ConfigManager）**

- 示例（Python）:

```python
from config_manager import ConfigManager

# 使用默认工作目录及默认 dataset
cfg = ConfigManager()
print('run dir:', cfg.run_dir)
```

- 要点: `ConfigManager` 支持三种传参方式：无参数（使用当前工作目录）、传入字典 `user_config`、或传入 JSON 配置文件路径字符串。

**2) 标定（DualSpectralCalibrator）**

- 标定流程（示例脚本）:

```python
from config_manager import ConfigManager
from calibrator import DualSpectralCalibrator
import glob, os

cfg = ConfigManager()
calib_root = cfg.runtime_config.calibration_dataset_root
rgb_images = sorted(glob.glob(os.path.join(calib_root, '*.JPG')))

cal = DualSpectralCalibrator(cfg)
result_rgb = cal.calibrate(rgb_images, sensor_name='RGB', is_tir=False)
cal.save_calibration(result_rgb, cfg)
print('Saved:', cfg.get_calibration_output_path())
```

- 输出: `save_calibration()` 将把标定结果合并写入到 `runs/<run_id>/calibration/sensors_calibration_<run_id>.json`（或由 `ConfigManager.get_calibration_output_path()` 指定的路径），内容在 `sensors` 字段下按 `sensor_name` 索引。

**3) 去畸变（ImageUndistorter）**

- 用已保存的标定结果去畸变一张图像（示例）：

```python
from config_manager import ConfigManager
from undistort import ImageUndistorter
import json, os

cfg = ConfigManager()
with open(cfg.get_calibration_output_path(), 'r', encoding='utf-8') as f:
		calib_all = json.load(f)

# 选择具体传感器名（由标定时传入的 sensor_name）
calib = calib_all['sensors']['RGB']
und = ImageUndistorter(calib)
in_path = 'test_1/rgb_dir/DJI_20250821214815_0921_W.JPG'
out_path = os.path.join(cfg.dirs['undistorted'], 'out_rgb.png')
und.process_image(in_path, out_path, is_tir=False)
```

- 批处理: 遍历输入目录，针对每张图片调用 `process_image()` 并把输出写到 `cfg.dirs['undistorted']`。

**输出与 sidecar**

- `ImageUndistorter.process_image()` 会输出去畸变图像（RGB → PNG, TIR → TIFF）和一个同名的 meta 文件（`<output>_meta.json`），其中包含 `undistortion_model`、`output_size`、`calibration_ref`、并在能读取到原始 TIFF 标签时将其保存在 `original_tiff_tags`。

**注意事项与常见问题**

- TIFF 读写：
	- 当前实现尝试用 OpenCV 保存 TIFF；但 OpenCV 对 32-bit float TIFF 的写支持和标签保持有限。若需要保留位深和 TIFF 标签，建议在运行环境中安装 `tifffile`（已列入 `requirements.txt`）并改用 `tifffile.imwrite()` 保存输出（见下面示例）。

```python
import tifffile
# 假设 dst_cropped 为浮点 numpy 数组，orig_meta 为从原始 TIFF 读取的标签字典
tifffile.imwrite(out_tiff_path, dst_cropped.astype(orig_dtype), metadata=orig_meta)
```

- 检测率与质量门槛: `DualSpectralCalibrator.calibrate()` 在找不到角点时不会抛异常，而是返回带 `quality_flag`（例如 `FAIL_NO_BOARD`）的 JSON，便于流水线审计。若检测率低，请检查棋盘格尺寸、图像对比度，以及 `dataset_profile.chessboard_size` 是否与实际内角点匹配。
- 非 ASCII 路径: `io_utils.safe_imread()` 提供了对 Windows 含中文路径的 fallback 读取策略，优先使用 `cv2.imread()`，失败后用 `cv2.imdecode()`。

**建议改进（可选）**

- 优先使用 `tifffile.imwrite()` 保存去畸变的 TIR，以保留原始位深与标签；若需要，我可以直接把 `undistort.py` 中 TIR 写入部分改为优先用 `tifffile` 并添加单元测试。
- 为批处理添加并发/映射模式（`use_remap`、`alpha` 等参数）以加速大量图片的去畸变处理。

**总结**

- 三个文件已实现完整的最小工作流（配置 → 标定 → 去畸变）。按上文步骤可以完成本地 smoke-test，并导出去畸变图像与 sidecar 元数据。若你希望我把示例脚本保存为仓库内可直接运行的脚本（或把 `undistort.py` 修改为优先用 `tifffile` 写入），请回复“请修改并提交 patch”。

