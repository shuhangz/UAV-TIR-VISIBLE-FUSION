"""跨光谱匹配包。

对外只暴露 TWMM 适配器与匹配结果数据结构，避免上层直接依赖底层
算法实现细节。
"""

from .twmm_adapter import TwmmAdapter, MatchResult
