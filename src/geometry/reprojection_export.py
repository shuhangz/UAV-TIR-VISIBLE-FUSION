"""三维点云重投影与可见性导出。

该模块把重建得到的三维点投影到各相机成像平面，并通过 Z-buffer 近似
判断遮挡关系，生成后续热富集所需的二维观测记录。
"""

import logging
from typing import Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)

class ReprojectionExporter:
    def __init__(self, point_cloud: Any, camera_params: Dict[str, Dict[str, Any]]) -> None:
        """保存点云与相机参数，并定义遮挡判定容差。

        z_buffer_tolerance 用于吸收浮点误差和轻微深度抖动，避免把几何上
        几乎同深度的点误判为遮挡点。
        """
        self.point_cloud = point_cloud
        self.camera_params = camera_params
        self.z_buffer_tolerance = 0.05 # 5cm depth tolerance for occlusion

    def export_reprojections(self) -> Dict[str, List[Dict[str, Any]]]:
        """为每个三维点生成跨相机的重投影记录。

        返回值按 point_id 聚合，每个点可对应多个相机观测记录。只有位于
        相机前方、落在图像范围内且未被深度缓冲判定为遮挡的观测才会保留。
        """
        points = self.point_cloud.points
        num_points = points.shape[0]
        reprojection_dict = {f"point_{i:06d}": [] for i in range(num_points)}
        logger.info(f"Computing reprojections & occlusions for {num_points} points.")

        # Process per camera for efficient Z-Buffer generation
        for cam_id, params in self.camera_params.items():
            # 单个相机一轮处理，先算相机坐标，再做投影和遮挡判定。
            K = params.get("K")
            pose = params.get("pose")
            width, height = int(params.get("width", 4000)), int(params.get("height", 3000))
            
            # Inverse pose for World-to-Camera
            R_cam = pose[0:3, 0:3].T
            t_cam = -R_cam @ pose[0:3, 3]
            
            # Transform all points to camera space
            points_cam = (R_cam @ points.T).T + t_cam
            depths = points_cam[:, 2]
            
            # Project to image plane
            points_proj = (K @ points_cam.T).T
            u = (points_proj[:, 0] / depths).astype(np.float32)
            v = (points_proj[:, 1] / depths).astype(np.float32)

            # Valid in-front-of-camera and within image bounds
            valid_mask = (depths > 0) & (u >= 0) & (u < width - 1) & (v >= 0) & (v < height - 1)
            
            # Build Z-buffer for occlusion detection
            z_buffer = np.full((height, width), np.inf, dtype=np.float32)
            valid_indices = np.where(valid_mask)[0]
            
            # 将连续坐标四舍五入到像素格，记录每个像素位置的最小深度。
            u_int = np.round(u[valid_indices]).astype(np.int32)
            v_int = np.round(v[valid_indices]).astype(np.int32)
            d_valid = depths[valid_indices]

            # Populate Z-buffer (Min depth per pixel)
            for idx, ui, vi, d in zip(valid_indices, u_int, v_int, d_valid):
                if d < z_buffer[vi, ui]:
                    z_buffer[vi, ui] = d

            # Generate final reprojection records
            for idx in valid_indices:
                point_id = f"point_{idx:06d}"
                px_u, px_v, pt_depth = u[idx], v[idx], depths[idx]
                
                # Check occlusion state using Z-buffer
                ui, vi = int(round(px_u)), int(round(px_v))
                is_occluded = pt_depth > (z_buffer[vi, ui] + self.z_buffer_tolerance)
                
                if not is_occluded:
                    # 仅保留可见点，后续富集层会基于这些观测做跨视角融合。
                    reprojection_dict[point_id].append({
                        "camera_id": cam_id,
                        "x": float(px_u),
                        "y": float(px_v),
                        "distance_to_center": float(np.sqrt((px_u - width/2)**2 + (px_v - height/2)**2)),
                        "visibility_state": "visible",
                        "occlusion_state": "not_occluded"
                    })

        logger.info("Reprojection and visibility state computation completed.")
        return reprojection_dict