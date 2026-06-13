"""
钉钉在线表格 (传统 Spreadsheet) REST API 直接测试

官方 dingtalk-mcp npm 包不包含传统电子表格模块，
但钉钉开放平台有完整的 Spreadsheet API。
本脚本直接通过 HTTP 调用底层 REST API 来测试。
"""

import asyncio
import json
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("DINGTALK_Client_ID")
APP_SECRET = os.getenv("DINGTALK_Client_Secret")
BASE_URL = "https://api.dingtalk.com"


async def get_token(client: httpx.AsyncClient) -> str:
    """获取 access token"""
    resp = await client.post(
        f"{BASE_URL}/v1.0/oauth2/accessToken",
        json={"appKey": APP_KEY, "appSecret": APP_SECRET},
    )
    data = resp.json()
    return data.get("accessToken", "")


async def call_api(client: httpx.AsyncClient, token: str, method: str, path: str, **kwargs):
    """通用 API 调用"""
    headers = {
        "x-acs-dingtalk-access-token": token,
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{path}"
    resp = await client.request(method, url, headers=headers, **kwargs)
    return resp.status_code, resp.json() if resp.text else {}


def report(name: str, status: int, body: dict):
    icon = "O" if 200 <= status < 300 else "X"
    msg = body.get("message", "")[:100] if isinstance(body, dict) else str(body)[:100]
    print(f"  [{icon}] {name} (HTTP {status}) {msg}")


async def main():
    print("=" * 60)
    print("  钉钉在线表格 (Spreadsheet) REST API 测试")
    print("=" * 60)
    print()

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. 获取 token
        print(">>> Step 0: 获取 Access Token")
        token = await get_token(client)
        print(f"  Token: {token[:20]}...")
        print()

        results = {}

        # ═══════════════════════════════════════════════
        # 尝试不同的 API 路径模式
        # ═══════════════════════════════════════════════

        # 模式 1: /v1.0/doc/workbooks (文档型)
        tests_1 = [
            ("创建工作簿", "POST", "/v1.0/doc/workbooks", {"name": "MCP测试表格"}),
            ("列出工作簿", "GET", "/v1.0/doc/workbooks", None),
        ]

        # 模式 2: /v1.0/workbook/workbooks (传统型)
        tests_2 = [
            ("创建工作簿", "POST", "/v1.0/workbook/workbooks", {"name": "MCP测试表格"}),
            ("列出工作簿", "GET", "/v1.0/workbook/workbooks", None),
        ]

        # 模式 3: /v1.0/office/spreadsheets
        tests_3 = [
            ("创建表格", "POST", "/v1.0/office/spreadsheets", {"name": "MCP测试表格"}),
        ]

        all_tests = tests_1 + tests_2 + tests_3

        for name, method, path, body in all_tests:
            try:
                kwargs = {"json": body} if body else {}
                status, data = await call_api(client, token, method, path, **kwargs)
                report(f"{method} {path} ({name})", status, data)
                results[f"{method} {path}"] = (status, data)
            except Exception as e:
                print(f"  [X] {method} {path}: {e}")
                results[f"{method} {path}"] = (0, str(e))

        print()

        # ═══════════════════════════════════════════════
        # 查看已授权权限
        # ═══════════════════════════════════════════════
        print(">>> 尝试获取当前应用权限信息")
        try:
            status, data = await call_api(
                client, token, "GET", "/v1.0/oauth2/accessToken/permissions"
            )
            print(f"  权限查询: {status} - {json.dumps(data, ensure_ascii=False)[:200]}")
        except Exception as e:
            print(f"  失败: {e}")

        print()

        # ═══════════════════════════════════════════════
        # 尝试 DingTalk 文档 API 不同路径
        # ═══════════════════════════════════════════════
        print(">>> 尝试更多文档 API 路径:")

        # 修正: 带 x-acs-dingtalk-version 头的调用
        async def call_doc_api(token, method, path, **kwargs):
            headers = {
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json",
                "x-acs-dingtalk-version": "1.0",
            }
            url = f"{BASE_URL}{path}"
            resp = await client.request(method, url, headers=headers, **kwargs)
            return resp.status_code, resp.json() if resp.text else {}

        more_tests = [
            # workbook 路径 (确认存在，需要 version header)
            ("创建工作簿(带version)", "POST", "/v1.0/workbook/workbooks", {"name": "MCP测试表格"}),
            ("列出工作簿(带version)", "GET", "/v1.0/workbook/workbooks", None),
            # 文档相关路径
            ("列出文档", "GET", "/v1.0/doc/dentries", None),
            ("创建文档", "POST", "/v1.0/doc/dentries", {"name": "test", "type": "workbook"}),
            ("搜索文档", "POST", "/v1.0/doc/dentries/search", {"keyword": "test"}),
            # Drive 路径 (钉钉文档新API)
            ("Drive-列出文件", "GET", "/v1.0/drive/spaces", None),
        ]

        for name, method, path, body in more_tests:
            try:
                kwargs = {"json": body} if body else {}
                status, data = await call_doc_api(token, method, path, **kwargs)
                report(f"{method} {path} ({name})", status, data)
                results[f"{method} {path}"] = (status, data)
            except Exception as e:
                print(f"  [X] {method} {path}: {e}")
                results[f"{method} {path}"] = (0, str(e))

        # ═══════════════════════════════════════════════
        # 尝试: 查看实际有效的 API 路径 (从 MCP server 日志推导)
        # ═══════════════════════════════════════════════
        print()
        print(">>> 已知 MCP 服务实际调用的 API (从 server 日志):")
        print("  contacts:   POST /v1.0/contact/users/search")
        print("  notable:    POST /v2.0/storage/dentries/search")
        print()

        # 尝试 storage API (notable 用的)
        print(">>> 尝试存储/文档相关路径:")
        storage_tests = [
            ("列出用户空间", "GET", "/v2.0/storage/spaces", None),
            ("获取空间详情", "GET", "/v1.0/storage/spaces", None),
            ("列出知识库", "GET", "/v2.0/doc/knowledgeBases", None),
        ]
        for name, method, path, body in storage_tests:
            try:
                kwargs = {"json": body} if body else {}
                status, data = await call_doc_api(token, method, path, **kwargs)
                report(f"{method} {path} ({name})", status, data)
                results[f"{method} {path}"] = (status, data)
            except Exception as e:
                print(f"  [X] {method} {path}: {e}")
                results[f"{method} {path}"] = (0, str(e))

    # ═══════════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════════
    print()
    print("=" * 60)
    print("  汇总")
    print("=" * 60)
    success = sum(1 for s, d in results.values() if isinstance(s, int) and 200 <= s < 300)
    failed = len(results) - success
    print(f"  成功: {success} | 失败: {failed} | 总计: {len(results)}")
    print()

    for path, (status, data) in results.items():
        icon = "O" if 200 <= status < 300 else "X"
        print(f"  {icon} {path}")
        if not (200 <= status < 300) and isinstance(data, dict):
            print(f"     -> {data.get('message', '')[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
