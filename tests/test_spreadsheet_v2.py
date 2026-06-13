"""
钉钉在线表格 (传统 Spreadsheet) REST API 测试 — 使用正确的 API 路径

API Base: /v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}/...
权限: Document.Workbook.Read, Document.Workbook.Write
"""

import asyncio
import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("DINGTALK_Client_ID")
APP_SECRET = os.getenv("DINGTALK_Client_Secret")
BASE_URL = "https://api.dingtalk.com"


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{BASE_URL}/v1.0/oauth2/accessToken",
        json={"appKey": APP_KEY, "appSecret": APP_SECRET},
    )
    return resp.json().get("accessToken", "")


def header(token: str):
    return {"x-acs-dingtalk-access-token": token, "Content-Type": "application/json"}


def icon(status: int) -> str:
    return "O" if 200 <= status < 300 else "X"


async def main():
    print("=" * 65)
    print("  钉钉在线表格 (Spreadsheet) API 测试 (正确路径)")
    print("=" * 65)

    async with httpx.AsyncClient(timeout=30) as c:
        token = await get_token(c)
        print(f"  Token: {token[:20]}...")
        print()

        results = {}

        # ═══════════════════════════════════════════════════
        # 1. 获取 workspace / 知识库 (需要先有 workspace)
        # ═══════════════════════════════════════════════════
        print(">>> Step 1: 获取 workspace/knowledgeBase")

        # 尝试获取用户可访问的 workspace
        ws_tests = [
            ("获取知识库列表", "GET", "/v1.0/doc/knowledgeBases"),
            ("获取团队空间", "GET", "/v1.0/doc/workspaces"),
            ("列出我的文档", "GET", "/v1.0/doc/me/dentries"),
            ("Drive-列出空间", "GET", "/v1.0/drive/spaces"),
        ]
        for name, method, path in ws_tests:
            try:
                resp = await c.request(method, f"{BASE_URL}{path}", headers=header(token))
                msg = resp.json() if resp.text else {}
                results[f"{method} {path}"] = (resp.status_code, msg)
                print(f"  [{icon(resp.status_code)}] {method} {path} (HTTP {resp.status_code})")
                if resp.status_code == 200:
                    print(f"     -> {json.dumps(msg, ensure_ascii=False)[:300]}")
            except Exception as e:
                results[f"{method} {path}"] = (0, str(e))
                print(f"  [X] {method} {path}: {e}")

        print()

        # ═══════════════════════════════════════════════════
        # 2. 尝试创建 workbook 文档 (需要 workspaceId)
        # ═══════════════════════════════════════════════════
        print(">>> Step 2: 尝试创建 Workbook 文档")

        # 如果有 operatorId, 尝试用这个
        # 先用 dingtalk-mcp 的 searchDepartment 等方式获取 operatorId
        # 这里先用一个简单的方法: 搜索用户
        print("  先尝试获取 operatorId...")
        try:
            resp = await c.request(
                "POST",
                f"{BASE_URL}/v1.0/contact/users/search",
                headers=header(token),
                json={"offset": 0, "size": 1},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("dataList", []) or data.get("list", [])
                if items:
                    user = items[0]
                    userid = user.get("userId", "") or user.get("userid", "")
                    print(f"  [O] 获取到 userId: {userid}")
                    # 获取详情得到 unionId
                    resp2 = await c.request(
                        "GET",
                        f"{BASE_URL}/v1.0/contact/users/{userid}",
                        headers=header(token),
                    )
                    if resp2.status_code == 200:
                        detail = resp2.json()
                        unionid = detail.get("unionId", "") or detail.get("unionid", "")
                        print(f"  [O] unionId: {unionid}")
                    else:
                        print(f"  [X] getUser 失败: {resp2.status_code}")
                        unionid = ""
                else:
                    print("  [X] 搜索用户返回空")
                    unionid = ""
            else:
                print(f"  [X] searchUser 失败: {resp.status_code} - {resp.text[:200]}")
                unionid = ""
        except Exception as e:
            print(f"  [X] 异常: {e}")
            unionid = ""

        # 尝试不同的 workspace 创建路径
        print()
        print("  尝试创建 workbook:")
        create_tests = [
            ("创建 workbook-路径1", "POST", "/v1.0/doc/workbooks", {"name": "MCP测试表格", "operatorId": unionid} if unionid else None),
            ("创建 workbook-路径2", "POST", "/v1.0/doc/workspaces/default/docs", {"name": "MCP测试表格", "docType": "WORKBOOK", "operatorId": unionid} if unionid else None),
        ]
        for name, method, path, body in create_tests:
            try:
                resp = await c.request(method, f"{BASE_URL}{path}", headers=header(token), json=body)
                msg = resp.json() if resp.text else {}
                results[f"{method} {path}"] = (resp.status_code, msg)
                print(f"  [{icon(resp.status_code)}] {method} {path} (HTTP {resp.status_code})")
                if resp.status_code < 300:
                    print(f"     -> {json.dumps(msg, ensure_ascii=False)[:300]}")
            except Exception as e:
                results[f"{method} {path}"] = (0, str(e))
                print(f"  [X] {method} {path}: {e}")

        print()

        # ═══════════════════════════════════════════════════
        # 3. 尝试访问已有的 workbook (如果有 workbookId)
        # ═══════════════════════════════════════════════════
        print(">>> Step 3: 测试 Spreadsheet 核心 API (用占位 workbookId)")
        print("  (如果下面路径不再返回404，说明路径结构正确)")

        dummy_wb = "test123"
        dummy_sheet = "Sheet1"

        spreadsheet_tests = [
            ("获取所有工作表", "GET", f"/v1.0/doc/workbooks/{dummy_wb}/sheets"),
            ("获取单元格区域", "GET", f"/v1.0/doc/workbooks/{dummy_wb}/sheets/{dummy_sheet}/ranges/A1:B2"),
            ("更新单元格区域", "PUT", f"/v1.0/doc/workbooks/{dummy_wb}/sheets/{dummy_sheet}/ranges/A1:B2"),
        ]
        for name, method, path in spreadsheet_tests:
            try:
                body = {"values": [["测试1", "测试2"], ["测试3", "测试4"]]} if method == "PUT" else None
                resp = await c.request(method, f"{BASE_URL}{path}", headers=header(token), json=body)
                msg = resp.json() if resp.text else {}
                error_code = resp.status_code
                reason = msg.get("message", "")[:120] if isinstance(msg, dict) else ""
                results[f"{method} {path}"] = (error_code, msg)
                print(f"  [{icon(error_code)}] {method} {path}")
                print(f"     HTTP {error_code}: {reason}")
            except Exception as e:
                results[f"{method} {path}"] = (0, str(e))

        print()

        # ═══════════════════════════════════════════════════
        # 4. 尝试用 MCP 已有的 token 调用 spreadsheets
        # ═══════════════════════════════════════════════════
        print(">>> Step 4: 尝试已知的 AI 表格路径模式检查")

        notable_tests = [
            ("AI表格-获取sheets", "GET", "/v1.0/notable/bases/test/sheets"),
        ]
        for name, method, path in notable_tests:
            try:
                resp = await c.request(method, f"{BASE_URL}{path}", headers=header(token))
                msg = resp.json() if resp.text else {}
                results[f"{method} {path}"] = (resp.status_code, msg)
                print(f"  [{icon(resp.status_code)}] {method} {path} (HTTP {resp.status_code})")
            except Exception as e:
                results[f"{method} {path}"] = (0, str(e))

    # ═══════════════════════════════════════════════════
    # 汇总
    # ═══════════════════════════════════════════════════
    print()
    print("=" * 65)
    print("  汇总")
    print("=" * 65)

    not_found = 0
    permission_denied = 0
    success = 0
    other = 0

    for key, (status, data) in results.items():
        icon_str = icon(status) if isinstance(status, int) else "X"
        print(f"  {icon_str} {key} (HTTP {status})")
        if isinstance(status, int):
            if 200 <= status < 300:
                success += 1
            elif status == 404:
                not_found += 1
            elif status == 403:
                permission_denied += 1
            else:
                other += 1

    print()
    print(f"  成功: {success} | 404: {not_found} | 403: {permission_denied} | 其他: {other}")


if __name__ == "__main__":
    asyncio.run(main())
