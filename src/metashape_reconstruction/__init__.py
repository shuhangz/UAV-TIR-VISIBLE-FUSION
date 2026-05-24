"""Metashape 摄影测量重建包。

仅在 Metashape Python 环境中可用（通过 metashape.exe -r 调用）。
在普通 python.exe 环境下导入不会报错，但 PhotogrammetryEngine 不可用。
"""

try:
    from .photogrammetry import PhotogrammetryEngine
except ImportError:
    PhotogrammetryEngine = None
