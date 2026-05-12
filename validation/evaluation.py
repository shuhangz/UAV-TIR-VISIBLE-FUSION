"""质量导出与序列化辅助函数。

该模块负责把热富集后的点云导出为可审计的 PLY 文件，字段顺序与
docs/file_formats.md 中的产物契约保持一致，方便后续人工检查和自动化
回归对比。
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

def export_thermal_point_cloud_ply(point_cloud, output_path: str):
    """导出热富集点云为 ASCII PLY。

    点云对象需要至少提供以下数组属性：points、colors、temperature、
    support_views、fusion_weights。导出的顶点字段顺序固定为：
    x, y, z, r, g, b, temperature, support_view_count, fusion_weight。
    """
    points = point_cloud.points
    colors = point_cloud.colors
    temps = point_cloud.temperature
    views = point_cloud.support_views
    weights = point_cloud.fusion_weights
    
    num_points = points.shape[0]
    
    try:
        with open(output_path, "w") as f:
            # PLY 头部必须先声明顶点数量和每个字段的类型。
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {num_points}\n")
            f.write("property float x\nproperty float y\nproperty float z\n")
            f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
            f.write("property float temperature\n")
            f.write("property int support_view_count\n")
            f.write("property float fusion_weight\n")
            f.write("end_header\n")
            
            for i in range(num_points):
                # 每行输出一个点：几何、颜色、温度以及融合质量信息。
                x, y, z = points[i]
                r, g, b = colors[i]
                temp = temps[i]
                view_c = views[i]
                weight = weights[i]
                
                # 缺失温度显式写成 NaN，便于下游区分“无值”和“零值”。
                temp_str = f"{temp:.4f}" if not np.isnan(temp) else "NaN"
                
                f.write(f"{x:.4f} {y:.4f} {z:.4f} {r} {g} {b} {temp_str} {view_c} {weight:.4f}\n")
                
        logger.info(f"Successfully exported thermally enriched point cloud to {output_path}")
    except Exception as e:
        logger.exception(f"Failed to export PLY: {e}")