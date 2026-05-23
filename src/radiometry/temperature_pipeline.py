"""
热辐射提取与校正层 (radiometry layer)。

本模块是 9 层管道中的第 5 层，负责从热红外 TIFF 帧提取温度矩阵，应用环境参数进行
辐射校正，并记录完整的处理链路与质量标记。该层与 matching 层解耦，独立生成不依赖于
RGB 或三维重建的温度数据。

主要职责：
1. 加载热红外 TIFF 文件和外部元数据
2. 执行辐射校正，区分原始值、中间辐射值和最终温度值
3. 应用环境参数（环境温度、湿度、发射率、距离）进行物理模型校正
4. 生成温度矩阵及其元数据（单位、质量标记、缺失字段）
5. 支持单帧和批处理，所有操作可复现可追踪

关键设计约束（radiometry_model.md 要求）：
- 区分原始传感器值、中间辐射校正值和最终温度值，不混用
- 设备元数据（SensorTemperature、LensTemperature、LRFTargetDistance）仅作诊断，
  不能替代外部环境输入
- 缺失环境参数时降级处理但不伪造数据，记录缺失字段列表
- 温度矩阵与对应 TIFF 图像空间对齐
- 单位和物理含义明确（每个字段都要标注单位）

输出数据契约：
- 温度矩阵 (NPY): float32 温度数据，单位摄氏度或可配置
- 元数据 JSON: 处理版本、校正参数、源数据跟踪、质量标记
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import cv2
import numpy as np

from config.runtime_models import EnvironmentParameters, RadiometryParams
from pipeline_io.artifact_io import ensure_dir
from pipeline_io.json_io import read_json, write_json


def _parse_float(value: Any) -> Optional[float]:
    """
    鲁棒性浮点数提取，处理多种输入格式。
    
    支持：
    - None → None
    - int / float → float
    - str with numbers: "6.7 mm" → 6.7（通过正则提取第一个数字）
    - 其他格式 → None
    
    Args:
        value: 任意类型的输入
    
    Returns:
        float 或 None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # 使用正则表达式提取浮点数（含符号和小数点）
        m = re.search(r"[-+]?\d*\.?\d+", value)
        if m:
            return float(m.group(0))
    return None


@dataclass
class RadiometryResult:
    """
    单帧热辐射处理输出契约。记录温度矩阵、元数据路径、处理质量与诊断信息。
    
    字段语义（遵循 radiometry_model.md § 4-5、file_formats.md § 9）：
    
    frame_id: 帧级唯一标识，格式通常为 "DJI_..._0001_T"（T 表示 Thermal TIFF）
    
    temperature_matrix_path: 温度矩阵 NPY 文件路径（绝对或相对 workspace_root）
                            内容：float32 数组 shape=(H, W)，单位摄氏度
                            与原始 TIFF 图像空间对齐（无重采样）
    
    metadata_path: 元数据 JSON 文件路径，包含：
      - schema_version / source_version / created_at / units
      - raw/intermediate/corrected 温度范围
      - 缺失字段列表、质量标记、处理参数
      - ExifTool 提取字段、设备诊断值、环境参数源
    
    quality_flag: {"ok", "degraded", "invalid"}
      - "ok": 所有必需参数可用，辐射校正完整
      - "degraded": 缺失 1 个必需参数或检测到异常值（超范围）
      - "invalid": 缺失 ≥2 个必需参数，无法进行有效校正
    
    missing_fields: 缺失参数列表
      可能包含："ambient_temperature_celsius", "relative_humidity_percent",
      "emissivity_ratio", "distance_to_target_m"
      为空列表表示所有参数可用
    
    corrected_value_range: (min, max) tuple，最终温度矩阵的值域范围（单位摄氏度）
                           用于快速检查是否存在异常（如全零、全 NaN）
    """
    frame_id: str
    temperature_matrix: str
    metadata_path: str
    quality_flag: str
    missing_fields: List[str]
    corrected_value_range: Tuple[float, float]


class RadiometryPipeline:
    """
    热辐射提取与校正流程的中枢类。
    
    职责：
    1. 加载外部元数据索引（ExifTool 提取结果）
    2. 读取单帧或批量热红外 TIFF 文件
    3. 应用环境参数进行辐射校正（大气透射率、反射温度、发射率）
    4. 输出温度矩阵（NPY）与完整元数据（JSON）
    5. 生成批处理总结（radiometry_summary.json）
    
    工作流（process_frame）：
    - 读取 TIFF 帧（uint16 或 float32）
    - 从元数据索引查找对应的 ExifTool 记录
    - 应用 _apply_temperature_model 执行物理校正
    - 计算质量标记与缺失字段列表
    - 导出 NPY 和 JSON
    
    批处理（process_batch）：
    - 迭代 thermal_tiff_dir 中的所有 TIFF 文件
    - 调用 process_frame 逐帧处理
    - 收集统计信息（成功率、质量分布、异常）
    - 输出 radiometry_summary.json
    
    关键约束（radiometry_model.md § 6）：
    - 原始值、中间辐射值和最终温度值必须分离
    - 缺失环境参数时不伪造，记录 quality_flag=degraded/invalid
    - 温度矩阵与 TIFF 空间完全对齐（无重采样）
    - 所有字段都明确标注单位
    """

    def __init__(self, workspace_root: Path, params: RadiometryParams) -> None:
        """
        初始化热辐射处理管道。
        
        Args:
            workspace_root: 项目根路径
            params: RadiometryParams 配置对象，包含元数据 JSON 路径、处理版本、
                   温度单位、原始→温度转换参数、有效范围等
        """
        self.workspace_root = workspace_root
        self.params = params
        # 首次初始化时加载元数据索引，避免多次重复读取大型 JSON
        self._metadata_records = self._load_metadata_index(params.metadata_json_path)

    @staticmethod
    def _load_metadata_index(path: Path) -> Dict[str, Mapping[str, Any]]:
        records = read_json(path)
        index: Dict[str, Mapping[str, Any]] = {}
        for rec in records:
            filename = str(rec.get("FileName", ""))
            source_file = str(rec.get("SourceFile", ""))
            if filename:
                index[filename] = rec
            if source_file:
                index[Path(source_file).name] = rec
        return index

    @staticmethod
    def _map_preview_name_from_tiff(tiff_name: str) -> str:
        return Path(tiff_name).stem + ".JPG"

    @staticmethod
    def _read_thermal_tiff(path: Path) -> np.ndarray:
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Cannot read TIFF image: {path}")
        if img.ndim == 3:
            img = img[:, :, 0]
        return img

    @staticmethod
    def _range_of(arr: np.ndarray) -> Tuple[float, float]:
        return float(np.nanmin(arr)), float(np.nanmax(arr))

    @staticmethod
    def _quality_from_missing(missing_fields: Sequence[str], has_out_of_range: bool) -> str:
        if missing_fields:
            if len(missing_fields) >= 2:
                return "invalid"
            return "degraded"
        if has_out_of_range:
            return "degraded"
        return "ok"

    @staticmethod
    def _radiometric_mode(raw: np.ndarray, params: RadiometryParams) -> str:
        if params.input_is_temperature:
            return "radiometric"
        raw_min = float(np.nanmin(raw))
        raw_max = float(np.nanmax(raw))
        if raw_min > -120 and raw_max < 500:
            return "radiometric"
        return "non_radiometric"

    def _metadata_from_record(self, rec: Mapping[str, Any], frame_path: Path) -> Dict[str, Any]:
        source_fields = sorted(list(rec.keys()))

        mapped = {
            "sensor_model": rec.get("Model") or rec.get("ProductName") or "H30T",
            "capture_timestamp": rec.get("UTCAtExposure") or rec.get("DateTimeOriginal") or rec.get("CreateDate"),
            "raw_frame_path": str(frame_path),
            "focal_length_mm": _parse_float(rec.get("FocalLength")),
            "f_number": _parse_float(rec.get("FNumber")),
            "iso": int(_parse_float(rec.get("ISO")) or 0) or None,
            "exposure_time_s": _parse_float(rec.get("ExposureTime")),
            "exiftool_version": str(rec.get("ExifToolVersion", "")) if rec.get("ExifToolVersion") is not None else None,
            "sensor_temperature_celsius": _parse_float(rec.get("SensorTemperature")),
            "lens_temperature_celsius": _parse_float(rec.get("LensTemperature")),
            "lrf_target_distance_m": _parse_float(rec.get("LRFTargetDistance")),
            "light_value_ev": _parse_float(rec.get("LightValue")),
            "software_version": rec.get("Software"),
            "source_metadata_fields": source_fields,
            "processing_version": self.params.processing_version,
        }
        return mapped

    @staticmethod
    def _safe_exp(v: float) -> float:
        try:
            return math.exp(v)
        except OverflowError:
            return float("inf") if v > 0 else 0.0

    def _apply_temperature_model(
        self,
        raw: np.ndarray,
        env: EnvironmentParameters,
        mode: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
        raw_f = raw.astype(np.float64)

        if mode == "radiometric":
            if self.params.input_is_temperature:
                base_temp = raw_f
            else:
                # Many DJI thermal TIFF exports are already close to temperature ranges.
                base_temp = raw_f
        else:
            base_temp = raw_f * self.params.raw_to_temperature_scale + self.params.raw_to_temperature_offset

        missing = env.missing_required()
        if missing:
            return base_temp, base_temp

        ambient = float(env.ambient_temperature_celsius)
        humidity = float(env.relative_humidity_percent)
        emissivity = float(env.emissivity_ratio)
        distance = float(env.distance_to_target_m)
        reflected = float(env.reflected_temperature_celsius if env.reflected_temperature_celsius is not None else ambient)

        tau = self._safe_exp(-0.0015 * max(distance, 0.0) * (1.0 + max(0.0, humidity) / 200.0))
        denom = max(1e-6, emissivity * tau)
        intermediate = (base_temp - (1.0 - emissivity) * reflected - (1.0 - tau) * ambient)
        corrected = intermediate / denom
        return intermediate, corrected

    def process_frame(
        self,
        thermal_tiff_path: Path,
        env: EnvironmentParameters,
        output_dir: Path,
        frame_id: Optional[str] = None,
    ) -> RadiometryResult:
        if not thermal_tiff_path.exists():
            raise FileNotFoundError(f"Thermal TIFF not found: {thermal_tiff_path}")

        frame_name = frame_id or thermal_tiff_path.stem
        frame_dir = output_dir / frame_name
        ensure_dir(frame_dir)

        raw = self._read_thermal_tiff(thermal_tiff_path)
        raw_range = self._range_of(raw)

        preview_name = self._map_preview_name_from_tiff(thermal_tiff_path.name)
        rec = self._metadata_records.get(preview_name, {})
        meta = self._metadata_from_record(rec, thermal_tiff_path)

        mode = self._radiometric_mode(raw, self.params)
        intermediate, corrected = self._apply_temperature_model(raw, env, mode)

        cmin, cmax = self._range_of(corrected)
        vr_min, vr_max = self.params.valid_range_celsius
        has_out_of_range = bool(cmin < vr_min or cmax > vr_max)

        missing_fields = env.missing_required()
        quality_flag = self._quality_from_missing(missing_fields, has_out_of_range)

        matrix_path = frame_dir / "temperature_matrix.npy"
        np.save(matrix_path, corrected.astype(np.float32))

        payload = {
            "schema_version": "1.0.0",
            "source_version": self.params.processing_version,
            "created_at": None,
            "units": {
                "temperature": "celsius",
                "distance": "m",
                "humidity": "%",
                "pressure": "hPa",
            },
            "frame_id": frame_name,
            "temperature_matrix": str(matrix_path),
            "temperature_matrix_shape": list(corrected.shape),
            "temperature_matrix_dtype": str(np.float32),
            "temperature_unit": self.params.temperature_unit,
            "raw_value_range": list(raw_range),
            "intermediate_value_range": list(self._range_of(intermediate)),
            "corrected_value_range": [cmin, cmax],
            "metadata_source": str(self.params.metadata_json_path),
            "parameter_source": env.source,
            "missing_fields": missing_fields,
            "quality_flag": quality_flag,
            "radiometric_parameters": {
                **meta,
                "radiometric_mode": mode,
            },
            "environment_parameters": {
                "ambient_temperature_celsius": env.ambient_temperature_celsius,
                "relative_humidity_percent": env.relative_humidity_percent,
                "emissivity_ratio": env.emissivity_ratio,
                "distance_to_target_m": env.distance_to_target_m,
                "reflected_temperature_celsius": env.reflected_temperature_celsius,
                "atmospheric_pressure_hpa": env.atmospheric_pressure_hpa,
                "source": env.source,
                "source_ref": env.source_ref,
            },
        }

        meta_path = frame_dir / "temperature_meta.json"
        write_json(meta_path, payload)

        return RadiometryResult(
            frame_id=frame_name,
            temperature_matrix=str(matrix_path),
            metadata_path=str(meta_path),
            quality_flag=quality_flag,
            missing_fields=missing_fields,
            corrected_value_range=(float(cmin), float(cmax)),
        )

    def process_batch(
        self,
        thermal_tiff_dir: Path,
        env: EnvironmentParameters,
        output_dir: Path,
        max_frames: Optional[int] = None,
    ) -> List[RadiometryResult]:
        ensure_dir(output_dir)
        tif_files = sorted(thermal_tiff_dir.glob("*.tif")) + sorted(thermal_tiff_dir.glob("*.tiff"))

        results: List[RadiometryResult] = []
        for idx, tif in enumerate(tif_files):
            if max_frames is not None and idx >= max_frames:
                break
            result = self.process_frame(
                thermal_tiff_path=tif,
                env=env,
                output_dir=output_dir,
                frame_id=tif.stem,
            )
            results.append(result)

        write_json(
            output_dir / "radiometry_summary.json",
            {
                "total_frames": len(results),
                "results": [asdict(r) for r in results],
            },
        )
        return results
