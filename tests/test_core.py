r"""核心模块单元测试。

运行方式（Metashape Python 环境）：
    "C:\soft\Metashape\App\Metashape\python\python.exe" -m pytest tests/test_core.py -v

或使用系统 Python（需已安装依赖）：
    python -m pytest tests/test_core.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# 路径引导：确保 src/ 在 Python 搜索路径中
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ===========================================================================
# 1. 运行环境与依赖测试
# ===========================================================================

class TestEnvironment:
    """验证 Metashape Python 环境和核心依赖是否就绪。"""

    def test_python_version(self):
        assert sys.version_info >= (3, 9), f"需要 Python >= 3.9，当前: {sys.version}"

    def test_numpy(self):
        import numpy as np
        assert hasattr(np, "array")

    def test_opencv(self):
        import cv2
        assert hasattr(cv2, "imread")

    def test_tifffile(self):
        import tifffile
        assert hasattr(tifffile, "imread")

    def test_pil(self):
        from PIL import Image
        assert hasattr(Image, "open")

    def test_yaml(self):
        import yaml
        assert hasattr(yaml, "safe_load")

    def test_scipy(self):
        import scipy
        assert hasattr(scipy, "__version__")

    def test_pandas(self):
        import pandas as pd
        assert hasattr(pd, "DataFrame")


# ===========================================================================
# 2. 模块导入测试
# ===========================================================================

class TestModuleImports:
    """验证 src/ 下所有业务模块均可被正常导入。"""

    @pytest.mark.parametrize("module_name", [
        "config.runtime_models",
        "config.config_manager",
        "calibration.calibrator",
        "preprocess.undistort",
        "matching",
        "matching.twmm_adapter",
        "radiometry",
        "radiometry.temperature_pipeline",
        "enrichment.thermal_enrichment",
        "geometry.reprojection_export",
        "pipeline_io.json_io",
        "pipeline_io.logging_setup",
        "pipeline_io.artifact_io",
        "pipeline_io.io_utils",
        "validation.evaluation",
    ])
    def test_import(self, module_name):
        __import__(module_name)

    def test_metashape_sdk_unavailable_outside_engine(self):
        """在 python.exe 直接运行时，Metashape SDK 应正确报告不可用。"""
        try:
            import Metashape
            pytest.skip("Metashape SDK 已安装（可能在 metashape.exe 环境中）")
        except ImportError:
            pass  # 预期行为

    def test_photogrammetry_import_without_sdk(self):
        """photogrammetry.py 在无 SDK 时应优雅降级，PhotogrammetryEngine 为 None。"""
        try:
            import Metashape
            pytest.skip("Metashape SDK 已安装，跳过此测试")
        except ImportError:
            from metashape_reconstruction import PhotogrammetryEngine
            assert PhotogrammetryEngine is None, "无 SDK 时 PhotogrammetryEngine 应为 None"


# ===========================================================================
# 3. 配置管理器测试
# ===========================================================================

class TestConfigManager:
    """测试 config_manager.ConfigManager 的核心功能。"""

    def test_basic_init(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={"workspace_root": str(tmp_path)})
        assert mgr.workspace_root == str(tmp_path)
        assert mgr.run_id is not None
        assert os.path.isdir(mgr.run_dir)

    def test_metashape_paths_from_config(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={
            "workspace_root": str(tmp_path),
            "metashape_paths": {
                "metashape_exe": "C:/test/metashape.exe",
                "python_exe": "C:/test/python.exe",
            }
        })
        assert mgr.metashape_paths["metashape_exe"] == "C:/test/metashape.exe"
        assert mgr.metashape_paths["python_exe"] == "C:/test/python.exe"

    def test_metashape_paths_from_env(self, tmp_path, monkeypatch):
        from config.config_manager import ConfigManager
        monkeypatch.setenv("METASHAPE_EXE", "D:/env/metashape.exe")
        monkeypatch.setenv("METASHAPE_PYTHON", "D:/env/python.exe")
        mgr = ConfigManager(user_config={"workspace_root": str(tmp_path)})
        assert mgr.metashape_paths["metashape_exe"] == "D:/env/metashape.exe"
        assert mgr.metashape_paths["python_exe"] == "D:/env/python.exe"

    def test_metashape_paths_config_overrides_env(self, tmp_path, monkeypatch):
        from config.config_manager import ConfigManager
        monkeypatch.setenv("METASHAPE_EXE", "D:/env/metashape.exe")
        mgr = ConfigManager(user_config={
            "workspace_root": str(tmp_path),
            "metashape_paths": {"metashape_exe": "C:/config/metashape.exe"}
        })
        assert mgr.metashape_paths["metashape_exe"] == "C:/config/metashape.exe"

    def test_workspace_dirs_created(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={"workspace_root": str(tmp_path)})
        for subdir in ["manifest", "logs", "calibration", "undistorted",
                        "matching", "radiometry", "metashape", "geometry",
                        "enrichment", "validation", "reports"]:
            assert os.path.isdir(mgr.dirs[subdir]), f"缺少目录: {subdir}"

    def test_run_manifest_generated(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={"workspace_root": str(tmp_path)})
        manifest_path = Path(mgr.dirs["manifest"]) / "run_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["run_id"] == mgr.run_id
        assert "metashape_paths" in manifest

    def test_stage_selection_normalize(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={
            "workspace_root": str(tmp_path),
            "stage_selection": ["calibration", "reconstruction", "matching"],
        })
        assert "metashape" in mgr.runtime_config.stage_selection
        assert "reconstruction" not in mgr.runtime_config.stage_selection

    def test_calibration_output_path(self, tmp_path):
        from config.config_manager import ConfigManager
        mgr = ConfigManager(user_config={"workspace_root": str(tmp_path)})
        path = mgr.get_calibration_output_path()
        assert path.endswith(".json")
        assert mgr.run_id in path


# ===========================================================================
# 4. 运行时数据模型测试
# ===========================================================================

class TestRuntimeModels:
    """测试 runtime_models 中的数据类与校验逻辑。"""

    def test_twmm_params_valid(self):
        from config.runtime_models import TwmmParams
        params = TwmmParams(
            patch_size=40, search_radius=60, level_max=4,
            crop_size=(1024, 1024),
        )
        params.validate()  # 不应抛异常

    def test_twmm_params_invalid_patch_size(self):
        from config.runtime_models import TwmmParams, ConfigError
        params = TwmmParams(
            patch_size=0, search_radius=60, level_max=4,
            crop_size=(1024, 1024),
        )
        with pytest.raises(ConfigError, match="patch_size"):
            params.validate()

    def test_twmm_params_invalid_scale(self):
        from config.runtime_models import TwmmParams, ConfigError
        params = TwmmParams(
            patch_size=40, search_radius=60, level_max=4,
            crop_size=(1024, 1024),
            scale={"thermal": 1.0},  # 缺少 visible
        )
        with pytest.raises(ConfigError, match="scale"):
            params.validate()

    def test_environment_params_defaults(self):
        from config.runtime_models import EnvironmentParameters
        env = EnvironmentParameters()
        assert env.missing_required() == []
        assert env.ambient_temperature_celsius == -1.0
        assert env.emissivity_ratio == 0.97

    def test_environment_params_missing(self):
        from config.runtime_models import EnvironmentParameters
        env = EnvironmentParameters(
            ambient_temperature_celsius=None,
            relative_humidity_percent=None,
        )
        missing = env.missing_required()
        assert "ambient_temperature_celsius" in missing
        assert "relative_humidity_percent" in missing

    def test_parse_environment_parameters(self):
        from config.runtime_models import parse_environment_parameters
        env = parse_environment_parameters({
            "ambient_temperature_celsius": 25.0,
            "relative_humidity_percent": 60.0,
        })
        assert env.ambient_temperature_celsius == 25.0
        assert env.emissivity_ratio == 0.97  # 默认值


# ===========================================================================
# 5. JSON I/O 测试
# ===========================================================================

class TestJsonIO:
    """测试 pipeline_io.json_io 的读写功能。"""

    def test_write_and_read(self, tmp_path):
        from pipeline_io.json_io import read_json, write_json
        data = {"key": "值", "number": 42, "nested": {"a": [1, 2, 3]}}
        path = tmp_path / "test.json"
        write_json(path, data)
        loaded = read_json(path)
        assert loaded["key"] == "值"
        assert loaded["number"] == 42
        assert loaded["nested"]["a"] == [1, 2, 3]

    def test_write_creates_parent_dirs(self, tmp_path):
        from pipeline_io.json_io import write_json
        path = tmp_path / "a" / "b" / "c" / "data.json"
        write_json(path, {"ok": True})
        assert path.exists()

    def test_unicode_preserved(self, tmp_path):
        from pipeline_io.json_io import read_json, write_json
        data = {"中文键": "中文值", "emoji": "test"}
        path = tmp_path / "unicode.json"
        write_json(path, data)
        raw = path.read_text(encoding="utf-8")
        assert "中文键" in raw  # ensure_ascii=False
        loaded = read_json(path)
        assert loaded["中文键"] == "中文值"


# ===========================================================================
# 6. 日志配置测试
# ===========================================================================

class TestLoggingSetup:
    """测试 pipeline_io.logging_setup 的日志配置。"""

    def test_configure_creates_log_file(self, tmp_path):
        from pipeline_io.logging_setup import configure_run_logging
        log_file = configure_run_logging(tmp_path, console_level=9999)
        assert log_file.exists()
        assert log_file.name == "run.log"

    def test_log_file_is_writable(self, tmp_path):
        from pipeline_io.logging_setup import configure_run_logging
        import logging
        configure_run_logging(tmp_path, console_level=9999)
        logger = logging.getLogger("test_writable")
        logger.info("测试消息")
        log_file = tmp_path / "logs" / "run.log"
        content = log_file.read_text(encoding="utf-8")
        assert "测试消息" in content


# ===========================================================================
# 7. PLY 导出测试
# ===========================================================================

class TestPlyExport:
    """测试 validation.evaluation 的 PLY 导出。"""

    def test_export_basic(self, tmp_path):
        from validation.evaluation import export_thermal_point_cloud_ply

        class FakePointCloud:
            points = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
            colors = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
            temperature = np.array([25.5, np.nan], dtype=np.float32)
            support_views = np.array([2, 0], dtype=np.int32)
            fusion_weights = np.array([0.8, 0.0], dtype=np.float32)

        output_path = str(tmp_path / "test.ply")
        export_thermal_point_cloud_ply(FakePointCloud(), output_path)

        with open(output_path, "r") as f:
            content = f.read()
        assert "ply" in content
        assert "element vertex 2" in content
        assert "25.5000" in content
        assert "NaN" in content


# ===========================================================================
# 8. 热富集器测试
# ===========================================================================

class TestThermalEnricher:
    """测试 enrichment.thermal_enrichment 的核心逻辑。"""

    def test_bilinear_interpolate(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        enricher = ThermalEnricher(
            homography=np.eye(3),
            thermal_data={},
            config={"thermal_extraction": {"thermal_resolution": "4x4"}},
        )
        img = np.array([[1, 2], [3, 4]], dtype=np.float32)
        # 中心点应为 (1+2+3+4)/4 = 2.5
        val = enricher.bilinear_interpolate(img, 0.5, 0.5)
        assert abs(val - 2.5) < 1e-5

    def test_bilinear_interpolate_nan(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        enricher = ThermalEnricher(
            homography=np.eye(3),
            thermal_data={},
            config={"thermal_extraction": {"thermal_resolution": "4x4"}},
        )
        img = np.array([[1, np.nan], [3, 4]], dtype=np.float32)
        val = enricher.bilinear_interpolate(img, 0.5, 0.5)
        assert np.isnan(val)

    def test_candidate_keys(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        keys = ThermalEnricher._candidate_keys("DJI_0001_W")
        assert "DJI_0001_W" in keys
        assert "DJI_0001_T" in keys

    def test_candidate_keys_rgb(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        keys = ThermalEnricher._candidate_keys("DJI_RGB_001")
        assert "DJI_T_001" in keys
        assert "DJI_NIR_001" in keys

    def test_resolve_homography_dict(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        H = np.eye(3, dtype=np.float32)
        result = ThermalEnricher._resolve_homography({"cam_001": H}, "cam_001")
        np.testing.assert_array_equal(result, H)

    def test_resolve_homography_single(self):
        from enrichment.thermal_enrichment import ThermalEnricher
        H = np.eye(3, dtype=np.float32)
        result = ThermalEnricher._resolve_homography(H, "any_camera")
        np.testing.assert_array_equal(result, H)

    def test_enrich_point_cloud(self):
        from enrichment.thermal_enrichment import ThermalEnricher

        # 构造一个 2 点的点云和 1 张热图
        class FakePC:
            points = np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32)
            colors = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)

        thermal_img = np.full((100, 100), 25.0, dtype=np.float32)
        H = np.eye(3, dtype=np.float32)

        enricher = ThermalEnricher(
            homography={"DJI_0001_T": H},
            thermal_data={"DJI_0001_T": thermal_img},
            config={"thermal_extraction": {"thermal_resolution": "100x100"}},
        )

        reprojection = {
            "point_000000": [{"camera_id": "DJI_0001_T", "x": 50.0, "y": 50.0, "distance_to_center": 100.0}],
            "point_000001": [],  # 无观测
        }

        result = enricher.enrich_point_cloud(FakePC(), reprojection)
        assert result.temperature[0] == pytest.approx(25.0)
        assert np.isnan(result.temperature[1])
        assert result.support_views[0] == 1
        assert result.support_views[1] == 0
