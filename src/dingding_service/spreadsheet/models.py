"""钉钉在线表格 API 的请求/响应数据模型。

本模块使用 Pydantic v2 定义所有 API 端点接收的请求体和返回的响应体，
利用 Pydantic 的 Field 校验机制保证输入数据的合法性。

数据模型分类:
    - 请求模型（CreateSheetRequest, RangeWriteRequest 等）— JSON body 校验
    - 响应模型（HealthResponse, ErrorResponse, ListSheetsResponse 等）— 序列化输出
    - 子模型（SheetInfo）— 嵌套在响应中的结构化数据块
"""

from pydantic import BaseModel, Field


class SheetInfo(BaseModel):
    """工作表基本信息。

    表示一个工作表中的单个 sheet 的元数据。

    Attributes:
        name: 工作表名称（如 "Sheet1"、"员工信息表"）
        id:   工作表的唯一标识 ID
    """

    name: str = Field(..., description="工作表显示名称", examples=["Sheet1"])
    id: str = Field(..., description="工作表唯一标识", examples=["kgqie6hm"])


class CreateSheetRequest(BaseModel):
    """创建工作表的请求体。

    用于 POST /api/sheets 接口，指定新工作表的名称。

    Examples:
        >>> CreateSheetRequest(name="员工信息表")
        CreateSheetRequest(name='员工信息表')
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="新建工作表的名称，长度 1-100 字符",
        examples=["员工信息表", "项目进度跟踪"],
    )


class RangeWriteRequest(BaseModel):
    """向单元格区域写入数据的请求体。

    用于 PUT /api/sheets/{sheet_id}/range 接口。

    Attributes:
        range:  目标区域（如 "A1:C3"）
        values: 二维数组，外层行、内层列；长度应与 range 范围匹配
    """

    range: str = Field(
        ...,
        description="要写入的单元格范围，如 'A1:C3'",
        examples=["A1:B2", "Sheet1!A1:C10"],
    )
    values: list[list] = Field(
        ...,
        description="写入的值，按行组织的二维数组；传入空列表 [] 表示清除区域内容",
        examples=[[["测试1", "测试2"], ["测试3", "测试4"]]],
    )


class InsertRowsRequest(BaseModel):
    """在指定行前插入空行的请求体。

    用于 POST /api/sheets/{sheet_id}/insertRowsBefore 接口。

    Attributes:
        row:       目标行号（从 1 开始）
        row_count: 要插入的行数，默认 1
    """

    row: int = Field(
        ...,
        ge=1,
        description="目标行号，从 1 开始计数",
        examples=[3],
    )
    row_count: int = Field(
        default=1,
        ge=1,
        le=100,
        description="要插入的行数，1-100 行",
        examples=[1, 5],
    )


class InsertColsRequest(BaseModel):
    """在指定列前插入空列的请求体。

    用于 POST /api/sheets/{sheet_id}/insertColumnsBefore 接口。

    Attributes:
        column:       目标列号（从 1 开始）
        column_count: 要插入的列数，默认 1
    """

    column: int = Field(
        ...,
        ge=1,
        description="目标列号，从 1 开始计数",
        examples=[3],
    )
    column_count: int = Field(
        default=1,
        ge=1,
        le=100,
        description="要插入的列数，1-100 列",
        examples=[1, 5],
    )


class ClearRangeRequest(BaseModel):
    """清除单元格区域内容的请求体。

    用于 POST /api/sheets/{sheet_id}/range/clear 接口。

    Attributes:
        range: 要清除的单元格范围（如 "A1:C3"），内容清空后格式保留
    """

    range: str = Field(
        ...,
        description="要清除的单元格范围，内容清空但单元格格式保留",
        examples=["A1:C3", "D5:F10"],
    )


class HealthResponse(BaseModel):
    """健康检查响应体。

    用于 GET /health 接口，反映服务状态和钉钉 API 连通性。

    Attributes:
        status:      服务状态（ok / unconfigured）
        token_valid: 钉钉 accessToken 是否有效
        workbook_id: 当前配置的默认工作簿 ID
    """

    status: str = Field(
        ...,
        description="服务健康状态：ok 表示正常，unconfigured 表示配置不完整",
        examples=["ok", "unconfigured"],
    )
    token_valid: bool = Field(
        ...,
        description="钉钉 accessToken 是否有效",
        examples=[True, False],
    )
    workbook_id: str = Field(
        ...,
        description="当前配置的默认工作簿 ID，为空表示未配置",
        examples=["wb_xxxxx", ""],
    )


class ErrorResponse(BaseModel):
    """统一错误响应体。

    所有异常处理器都使用此模型序列化错误信息，确保客户端收到一致的错误格式。

    Attributes:
        detail:     人类可读的错误描述
        error_code: 机器可读的错误码（如 E2000、E3001），用于告警和自动化处理
        request_id: 请求追踪 ID，用于日志关联（可选）
    """

    detail: str = Field(
        ...,
        description="错误详细描述",
        examples=["Failed to get token: 401 Invalid appKey"],
    )
    error_code: str | None = Field(
        default=None,
        description="错误码，用于按错误类别处理（如 E2000=token失败, E3001=频率限制）",
        examples=["E2000", "E3001"],
    )
    request_id: str | None = Field(
        default=None,
        description="请求追踪 ID，可在服务端日志中检索到本次请求的上下文",
        examples=["req_abc123"],
    )


class UserSearchResult(BaseModel):
    """用户搜索结果项。"""

    user_id: str = Field(..., description="用户 userId")
    name: str = Field(..., description="用户姓名")
    avatar: str = Field("", description="头像 URL")


class UserDetailResponse(BaseModel):
    """用户详情响应。"""

    user_id: str = Field(..., description="用户 userId")
    union_id: str = Field(..., description="用户的 unionId")
    name: str = Field(..., description="用户姓名")
    mobile: str = Field("", description="手机号")
    dept_id_list: list[int] = Field(default_factory=list, description="所属部门 ID 列表")


class DocumentItem(BaseModel):
    """文档搜索结果项。"""

    dentry_uuid: str = Field(..., description="文档 UUID（即 WORKBOOK_ID）")
    name: str = Field(..., description="文档名称")
    creator_name: str = Field("", description="创建者姓名")


class ListSheetsResponse(BaseModel):
    """工作表列表响应体。

    用于 GET /api/sheets 接口的响应。

    Attributes:
        sheets: 工作表信息列表
    """

    sheets: list[SheetInfo] = Field(
        ...,
        description="当前工作簿下的所有工作表列表",
        examples=[[{"name": "Sheet1", "id": "kgqie6hm"}]],
    )
