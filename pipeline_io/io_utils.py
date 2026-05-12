import logging
import os

import cv2
import numpy as np

logger = logging.getLogger(__name__)

def safe_imread(path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """读取图像文件，优先走 OpenCV，失败后回退到字节流解码。

    这个函数主要解决 Windows 路径、特殊 TIFF 编码或 OpenCV 直接读图
    失败的情况。调用方不需要关心底层是 imread 还是 imdecode，只要最终
    能拿到 numpy 图像数组即可。
    """
    try:
        # 某些 OpenCV 版本会暴露 utils.logging，用于临时压低 TIFF 读图噪音。
        if hasattr(cv2, 'utils') and hasattr(cv2.utils, 'logging'):
            old_log_level = cv2.utils.logging.getLogLevel()
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
            try:
                img = cv2.imread(str(path), flags)
            finally:
                cv2.utils.logging.setLogLevel(old_log_level)
        else:
            img = cv2.imread(str(path), flags)
        
        if img is not None:
            return img
    except Exception:
        pass
    
    # OpenCV 直接读取失败时，回退到“先读原始字节再解码”的方式。
    logger.warning(f"cv2.imread failed for {path}, falling back to imdecode")
    with open(path, 'rb') as f:
        img_array = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(img_array, flags)

def safe_imwrite(path: str, img: np.ndarray) -> bool:
    """保存图像，优先使用 OpenCV 写盘，失败后回退到编码后写字节流。

    返回值表示最终是否成功写入。该函数适合用于需要兼容 TIFF、PNG、JPG
    且路径可能包含特殊字符或上层目录尚未创建的场景。
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        success = cv2.imwrite(str(path), img)
        if success:
            return True
    except Exception:
        pass
    
    logger.warning(f"cv2.imwrite failed for {path}, falling back to imencode")
    # 根据文件扩展名选择编码格式，再手动写入字节流。
    ext = os.path.splitext(path)[1]
    success, img_array = cv2.imencode(ext, img)
    if success:
        with open(path, 'wb') as f:
            f.write(img_array.tobytes())
        return True
    return False