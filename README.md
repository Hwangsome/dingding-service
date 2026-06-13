# 钉钉在线表格 REST API 服务

基于 FastAPI 构建，封装钉钉 OpenAPI 的表格文档操作能力，提供 RESTful 接口操作钉钉在线表格（传统 Spreadsheet）。

## 前置准备

### 1. 注册钉钉开发者

访问 [钉钉开放平台](https://open.dingtalk.com)，使用钉钉扫码登录。

### 2. 创建企业内部应用

1. 进入「应用开发」→「企业内部应用」→「创建应用」
2. 填写应用名称、描述，选择「H5 微应用」
3. 创建完成后进入应用详情页

### 3. 获取应用凭证

在应用详情页 →「凭证与基础信息」中复制：

| 凭证 | 说明 |
|------|------|
| **AppKey** (`Client ID`) | 对应环境变量 `DINGTALK_Client_ID` |
| **AppSecret** (`Client Secret`) | 对应环境变量 `DINGTALK_Client_Secret` |

### 4. 开通 API 权限

在应用详情页 →「权限管理」中，逐一申请并开通以下权限：

| 权限点 | 用途 | 是否必须 |
|--------|------|----------|
| `qyapi_addresslist_search` | 搜索通讯录用户，获取操作人的 userId/unionId | **必须** |
| `Storage.Dentry.Search` | 搜索钉钉文档/表格，获取 workbookId | **必须** |
| `Document.Workbook.Read` | 读取在线表格数据（工作表、单元格） | **必须** |
| `Document.Workbook.Write` | 写入在线表格数据（创建/删除工作表、写入单元格、插入行列） | **必须** |

> 点击权限旁的「申请」按钮，审批通常即时生效。

### 5. 设置应用可见范围

在「版本管理与发布」→「可见范围」中添加需要使用此服务的成员（至少包含你自己）。

> 如果不设置可见范围，通讯录搜索将返回空结果，无法获取 unionId。

### 6. 获取操作人 unionId

<details>
<summary>方法一：通过旧版 API 获取（推荐，无需额外权限）</summary>

```bash
# 1. 获取 token
curl "https://oapi.dingtalk.com/gettoken?appkey={AppKey}&appsecret={AppSecret}"

# 2. 获取部门用户列表（dept_id=1 为根部门）
curl -X POST "https://oapi.dingtalk.com/topapi/v2/user/list?access_token={token}" \
  -H "Content-Type: application/json" \
  -d '{"dept_id":1,"cursor":0,"size":10}'

# 返回的 unionid 即为 OPERATOR_UNION_ID
```
</details>

<details>
<summary>方法二：通过新版 API 获取（需要 qyapi_addresslist_search 权限）</summary>

```bash
# 1. 获取 token
curl -X POST "https://api.dingtalk.com/v1.0/oauth2/accessToken" \
  -H "Content-Type: application/json" \
  -d '{"appKey":"{AppKey}","appSecret":"{AppSecret}"}'

# 2. 搜索用户
curl -X POST "https://api.dingtalk.com/v1.0/contact/users/search" \
  -H "Content-Type: application/json" \
  -H "x-acs-dingtalk-access-token: {token}" \
  -d '{"queryWord":"你的姓名","offset":0,"size":5}'

# 3. 用 userId 获取详情（包含 unionId）
curl "https://api.dingtalk.com/v1.0/contact/users/{userId}" \
  -H "x-acs-dingtalk-access-token: {token}"
```
</details>

### 7. 获取目标工作簿 ID (workbookId)

<details>
<summary>方法一：从钉钉文档 URL 提取（最简单）</summary>

在钉钉客户端打开目标表格文档，复制链接。URL 格式为：

```
https://alidocs.dingtalk.com/i/nodes/{workbookId}
```

`{workbookId}` 即为 `WORKBOOK_ID` 环境变量值。
</details>

<details>
<summary>方法二：通过 API 搜索（需要 Storage.Dentry.Search 权限）</summary>

```bash
curl -X POST "https://api.dingtalk.com/v2.0/storage/dentries/search" \
  -H "Content-Type: application/json" \
  -H "x-acs-dingtalk-access-token: {token}" \
  -d '{
    "operatorId":"{unionId}",
    "keyword":"表格",
    "option":{"dentryCategories":["alidoc"],"creatorIds":[],"maxResults":10}
  }'
# 返回结果中 dentryUuid 即为 workbookId
```
</details>

---

## 快速启动

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入上面的凭证

# 启动服务
uv run dingding-spreadsheet
```

服务启动后访问 http://localhost:8000/docs 查看 Swagger 文档。

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `DINGTALK_Client_ID` | 钉钉应用 AppKey | 是 |
| `DINGTALK_Client_Secret` | 钉钉应用 AppSecret | 是 |
| `WORKBOOK_ID` | 目标表格文档 ID | 是 |
| `OPERATOR_UNION_ID` | 操作人 unionId | 是 |
| `HOST` | 监听地址（默认 `0.0.0.0`） | 否 |
| `PORT` | 监听端口（默认 `8000`） | 否 |
| `LOG_LEVEL` | 日志级别（默认 `INFO`） | 否 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查（含 Token 状态） |
| `GET` | `/api/sheets` | 获取所有工作表列表 |
| `POST` | `/api/sheets` | 创建新工作表 |
| `GET` | `/api/sheets/{sheet_id}` | 获取工作表元信息 |
| `DELETE` | `/api/sheets/{sheet_id}` | 删除指定工作表 |
| `GET` | `/api/sheets/{sheet_id}/range` | 读取单元格区域 |
| `PUT` | `/api/sheets/{sheet_id}/range` | 写入单元格区域 |
| `POST` | `/api/sheets/{sheet_id}/range/clear` | 清除单元格区域 |
| `POST` | `/api/sheets/{sheet_id}/insertRowsBefore` | 在指定行上方插入行 |
| `POST` | `/api/sheets/{sheet_id}/insertColumnsBefore` | 在指定列左侧插入列 |

## Docker 启动

```bash
docker compose up -d
```

## 测试

```bash
uv run pytest tests/ -v
```

## 开发命令

```bash
make install    # 安装依赖（含开发工具）
make test       # 运行测试
make lint       # 代码检查（ruff）
make format     # 代码格式化（ruff）
make typecheck  # 类型检查（mypy）
make all        # lint + typecheck + test 一条龙
make run        # 启动服务
```

## 项目结构

```
dingding-service/
├── src/dingding_service/spreadsheet/
│   ├── main.py          # FastAPI 应用入口 + 生命周期
│   ├── routes.py        # RESTful 路由定义
│   ├── client.py        # 钉钉 API HTTP 客户端
│   ├── config.py        # pydantic-settings 配置管理
│   ├── models.py        # Pydantic 请求/响应模型
│   └── errors.py        # 异常处理 + 错误码
├── tests/               # 42 个单元测试
├── .github/workflows/   # CI/CD (lint → typecheck → test)
├── Makefile             # 开发快捷命令
├── Dockerfile
├── docker-compose.yml
└── .env.example
```
