"""钉钉在线表格 REST API 服务包。

本包提供基于 FastAPI 的钉钉在线表格（Spreadsheet）操作接口，
封装了钉钉 OpenAPI 的工作表、单元格、行列操作和文档搜索能力。

子模块:
    config: 配置管理（pydantic-settings 环境变量加载）
    client: 钉钉 HTTP 客户端（Token 管理 + API 调用）
    models: Pydantic 请求/响应数据模型
    routes: FastAPI APIRouter 路由定义
    errors: 异常定义与全局错误处理器
    main:   FastAPI 应用工厂与入口点

快速启动:
    from dingding_service.spreadsheet import app, main
    # 或者直接: python -m uvicorn dingding_service.spreadsheet.main:app
"""

from .main import app, main

__all__ = ["app", "main"]
"""公开的模块导出项。

- app:  FastAPI 应用实例，可直接用于 uvicorn 部署
- main: 模块入口函数，适合脚本启动
"""
