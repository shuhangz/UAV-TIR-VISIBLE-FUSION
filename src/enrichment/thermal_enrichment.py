"""热红外点云富集。

该模块根据重投影记录和单应性矩阵，把 RGB 坐标映射到热红外图像中，
再按视角权重融合多视图温度值，为每个三维点补充热属性。
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, Sequence

logger = logging.getLogger(__name__)

class ThermalEnricher:
    def __init__(self, homography: np.ndarray, thermal_data: Dict[str, np.ndarray], config: Dict[str, Any]) -> None:
        """初始化热富集器。

        homography 可以是单个单应矩阵，也可以是按相机 ID 索引的字典；
        thermal_data 需要提供热红外温度矩阵；config 用于读取热红外分辨率。
        """
        self.homography = homography
        self.thermal_data = thermal_data
        thermal_res_str = config.get("thermal_extraction", {}).get("thermal_resolution", "1280x1024")
        w_str, h_str = thermal_res_str.split("x")
        self.thermal_w, self.thermal_h = int(w_str), int(h_str)
        self.epsilon = 1e-4

    @staticmethod
    def _candidate_keys(camera_id: Optional[str]) -> Sequence[str]:
        """生成同一航片在不同模态下可能使用的键名。

        项目里常见的命名是 *_W / *_T / *_RGB，因此这里做一次轻量映射，
        以便重投影记录和热图缓存可以互相匹配。
        """
        if not camera_id:
            return []

        candidates = [camera_id]
        if camera_id.endswith("_W"):
            candidates.append(camera_id[:-2] + "_T")
        if camera_id.endswith("_RGB"):
            candidates.append(camera_id[:-4] + "_T")
        if "RGB" in camera_id:
            candidates.append(camera_id.replace("RGB", "T"))
            candidates.append(camera_id.replace("RGB", "NIR"))

        unique_candidates = []
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            unique_candidates.append(candidate)
            seen.add(candidate)
        return unique_candidates

    @staticmethod
    def _resolve_homography(homography: Any, camera_id: Optional[str]) -> Optional[np.ndarray]:
        """按相机 ID 解析单应性矩阵。

        如果传入的是字典，则优先查找与当前相机匹配的条目；如果传入的
        本来就是单个矩阵，则直接返回其 numpy 形式。
        """
        if isinstance(homography, dict):
            for candidate in ThermalEnricher._candidate_keys(camera_id):
                if candidate in homography:
                    return np.asarray(homography[candidate], dtype=np.float32)
            return None
        if homography is None:
            return None
        return np.asarray(homography, dtype=np.float32)

    def bilinear_interpolate(self, img: np.ndarray, u: float, v: float) -> float:
        """在热图上进行双线性插值。

        热红外温度矩阵通常是连续物理量，但单应映射得到的坐标是浮点值，
        因此需要在相邻四个像素之间做平滑插值。
        """
        u0, v0 = int(np.floor(u)), int(np.floor(v))
        u1, v1 = min(u0 + 1, img.shape[1] - 1), min(v0 + 1, img.shape[0] - 1)
        
        alpha, beta = u - u0, v - v0
        T00, T10 = img[v0, u0], img[v0, u1]
        T01, T11 = img[v1, u0], img[v1, u1]
        
        # 若四邻域里有缺失温度，则当前插值结果也视为无效。
        if np.isnan([T00, T10, T01, T11]).any():
            return np.nan
            
        return (1 - alpha) * (1 - beta) * T00 + alpha * (1 - beta) * T10 + \
               (1 - alpha) * beta * T01 + alpha * beta * T11

    def enrich_point_cloud(self, point_cloud: Any, reprojection_data: Dict[str, list]) -> Any:
        """把热信息写回点云对象。

        对每个三维点，遍历其可见观测记录，映射到对应热图后取温度，
        再按“离光学中心越近权重越大”的策略融合多视图结果。
        """
        num_points = point_cloud.points.shape[0]
        temperatures = np.full((num_points,), np.nan, dtype=np.float32)
        support_views = np.zeros((num_points,), dtype=np.int32)
        fusion_weights = np.zeros((num_points,), dtype=np.float32)

        valid_count = 0
        for idx in range(num_points):
            point_id = f"point_{idx:06d}"
            observations = reprojection_data.get(point_id, [])
            
            t_sum, w_sum, views = 0.0, 0.0, 0
            for obs in observations:
                cam_id = obs.get("camera_id")
                thermal_cam_id = None
                # 找到与当前 RGB 观测对应的热红外缓存键。
                for candidate in self._candidate_keys(cam_id):
                    if candidate in self.thermal_data:
                        thermal_cam_id = candidate
                        break

                thermal_img = self.thermal_data.get(thermal_cam_id) if thermal_cam_id is not None else None
                
                if thermal_img is None:
                    continue

                homography = self._resolve_homography(self.homography, cam_id)
                if homography is None:
                    continue

                # 用单应矩阵把 RGB 平面坐标映射到热红外平面坐标。
                rgb_h = np.array([obs["x"], obs["y"], 1.0], dtype=np.float32)
                th_h = homography @ rgb_h
                u, v = th_h[0] / th_h[2], th_h[1] / th_h[2]

                if 0 <= u < self.thermal_w and 0 <= v < self.thermal_h:
                    temp_val = self.bilinear_interpolate(thermal_img, u, v)
                    if not np.isnan(temp_val):
                        # 视角加权：距离图像中心越远，权重越低。
                        dist_to_center = obs.get("distance_to_center", self.epsilon)
                        weight = 1.0 / (dist_to_center + self.epsilon)
                        
                        t_sum += weight * temp_val
                        w_sum += weight
                        views += 1
            
            if views > 0:
                temperatures[idx] = t_sum / w_sum
                support_views[idx] = views
                fusion_weights[idx] = w_sum
                valid_count += 1

        logger.info(f"Thermal enrichment complete. Coverage: {(valid_count/num_points)*100:.2f}%")
        # 将富集结果直接挂回点云对象，方便后续导出与质检。
        point_cloud.temperature = temperatures
        point_cloud.support_views = support_views
        point_cloud.fusion_weights = fusion_weights
        return point_cloud