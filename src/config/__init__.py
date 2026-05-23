"""配置与运行时数据模型包。

这里导出所有运行阶段会用到的配置类型、参数解析函数和校验工具。
"""

from .runtime_models import (
    ConfigError,
    EnvironmentParameters,
    RadiometryParams,
    RuntimeConfig,
    TwmmParams,
    parse_environment_parameters,
    require_existing_paths,
)
