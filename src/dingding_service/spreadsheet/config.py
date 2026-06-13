"""应用配置管理。

本模块使用 pydantic-settings 从环境变量 / .env 文件读取配置，
并提供类型安全的应用设置对象。

支持的环境变量:
    DINGTALK_Client_ID      — 钉钉应用的 AppKey / ClientId
    DINGTALK_Client_Secret  — 钉钉应用的 AppSecret / ClientSecret
    WORKBOOK_ID             — 默认操作的工作簿 ID
    OPERATOR_UNION_ID       — 默认操作人的 unionId
    HOST                    — 服务监听地址（默认 0.0.0.0）
    PORT                    — 服务监听端口（默认 8000）
    LOG_LEVEL               — 日志级别（默认 INFO）

Usage:
    from .config import Settings
    settings = Settings()
    print(settings.dingtalk_client_id)
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。

    从环境变量和 .env 文件加载，支持通过 Pydantic 的别名机制
    将环境变量名映射为 Python 风格的属性名。

    Attributes:
        dingtalk_client_id:     钉钉应用的 AppKey（ClientId）
        dingtalk_client_secret: 钉钉应用的 AppSecret（ClientSecret）
        workbook_id:            默认操作的工作簿唯一标识
        operator_union_id:      默认操作人的钉钉 unionId
        host:                   HTTP 服务监听地址
        port:                   HTTP 服务监听端口
        log_level:              日志输出级别（DEBUG / INFO / WARNING / ERROR）
    """

    dingtalk_client_id: str = Field(
        default="",
        alias="DINGTALK_Client_ID",
        description="钉钉应用的 AppKey（ClientId），用于获取 accessToken",
        examples=["dingxxxxx"],
    )
    dingtalk_client_secret: str = Field(
        default="",
        alias="DINGTALK_Client_Secret",
        description="钉钉应用的 AppSecret（ClientSecret），用于获取 accessToken",
        examples=["your_secret_here"],
    )
    workbook_id: str = Field(
        default="",
        alias="WORKBOOK_ID",
        description="默认的钉钉表格文档 ID，所有 API 操作的默认目标工作簿",
        examples=["wb_xxxxx"],
    )
    operator_union_id: str = Field(
        default="",
        alias="OPERATOR_UNION_ID",
        description="默认操作人的钉钉 unionId，用于权限校验",
        examples=["union_xxxxx"],
    )
    host: str = Field(
        default="0.0.0.0",
        alias="HOST",
        description="HTTP 服务监听地址",
        examples=["0.0.0.0", "127.0.0.1"],
    )
    port: int = Field(
        default=8000,
        alias="PORT",
        ge=1,
        le=65535,
        description="HTTP 服务监听端口",
        examples=[8000, 8080],
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="日志输出级别",
        examples=["DEBUG", "INFO", "WARNING"],
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )
