"""
钉钉 Spreadsheet 完整功能测试
已知: unionId=KZDkvpwM6G22ubVeRZKYRwiEiE, userId=03682521170340644
"""

import asyncio, json, httpx, os
from dotenv import load_dotenv

load_dotenv()

APP_KEY = os.getenv("DINGTALK_Client_ID")
APP_SECRET = os.getenv("DINGTALK_Client_Secret")
BASE = "https://api.dingtalk.com"
UNION_ID = "KZDkvpwM6G22ubVeRZKYRwiEiE"


async def get_token(c):
    r = await c.post(
        f"{BASE}/v1.0/oauth2/accessToken", json={"appKey": APP_KEY, "appSecret": APP_SECRET}
    )
    return r.json()["accessToken"]


def H(t):
    return {"x-acs-dingtalk-access-token": t}


def J(t):
    return {"x-acs-dingtalk-access-token": t, "Content-Type": "application/json"}


def ok(s):
    return 200 <= s < 300


def R(name, status, body=""):
    print(f"  [{'OK' if ok(status) else 'E' + str(status)}] {name}  {str(body)[:150]}")


async def main():
    print("=" * 60)
    print("  钉钉 Spreadsheet 完整测试")
    print(f"  unionId: {UNION_ID}")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30) as c:
        token = await get_token(c)

        # ════════════════════════════════════════════
        # 1. 获取/创建 workbook
        # ════════════════════════════════════════════
        print("\n--- 1. 获取 workbookId ---")
        wb_id = ""

        # 1a: 搜索已有文档
        print("  搜索文档...")
        r = await c.request(
            "POST",
            f"{BASE}/v2.0/storage/dentries/search",
            headers=J(token),
            json={
                "operatorId": UNION_ID,
                "keyword": "",
                "option": {"dentryCategories": ["alidoc"], "creatorIds": [], "maxResults": 20},
            },
        )
        R("storage搜索", r.status_code, r.text[:250])
        if ok(r.status_code):
            items = r.json().get("dataList", []) or r.json().get("items", [])
            for item in items[:5]:
                print(
                    f"    {item.get('name', '?')} [{item.get('dentryType', '?')}] -> {item.get('dentryUuid', '')[:40]}"
                )

        # 1b: 获取知识库列表
        print("  获取知识库...")
        r = await c.request(
            "GET",
            f"{BASE}/v1.0/doc/knowledgeBases",
            headers=H(token),
            params={"operatorId": UNION_ID},
        )
        R("知识库", r.status_code, r.text[:200])

        # 1c: 获取团队空间
        print("  获取团队空间...")
        r = await c.request(
            "GET", f"{BASE}/v1.0/doc/workspaces", headers=H(token), params={"operatorId": UNION_ID}
        )
        R("workspaces", r.status_code, r.text[:300])

        # 1d: 创建 workbook
        print("  创建 workbook...")
        r = await c.request(
            "POST",
            f"{BASE}/v1.0/doc/workbooks",
            headers=J(token),
            params={"operatorId": UNION_ID},
            json={"name": "MCP测试表格_请删除"},
        )
        R("POST /doc/workbooks", r.status_code, r.text[:300])
        if ok(r.status_code):
            wb_id = r.json().get("id", "") or r.json().get("dentryUuid", "")

        # 1e: 用旧版 API 创建文档 (oapi)
        if not wb_id:
            print("  尝试旧版 oapi 创建...")
            ot = token  # same token
            # oapi 创建知识库文档
            r = await c.request(
                "POST",
                "https://oapi.dingtalk.com/topapi/doc/create",
                headers={"Content-Type": "application/json"},
                params={"access_token": ot},
                json={"name": "MCP测试表格", "doc_type": "workbook"},
            )
            R("oapi doc/create", r.status_code, r.text[:200])

        if not wb_id:
            print(
                "\n  [BLOCKED] 无法创建 workbook, 尝试用已知 Notable baseId 测试 Spreadsheet API 路径兼容性"
            )
            # 尝试用 notable 的 baseId 访问 spreadsheet API
            print("  尝试 notable->spreadsheet 路径互操作...")
            r = await c.request(
                "GET",
                f"{BASE}/v1.0/doc/workbooks/test123/sheets",
                headers=H(token),
                params={"operatorId": UNION_ID},
            )
            R("GET /doc/workbooks/test123/sheets", r.status_code, r.text[:200])

            r = await c.request(
                "GET",
                f"{BASE}/v1.0/notable/bases/test/sheets",
                headers=H(token),
                params={"operatorId": UNION_ID},
            )
            R("GET /notable/bases/test/sheets", r.status_code, r.text[:200])
            return

        print(f"\n  [OK] workbookId = {wb_id}\n")

        # ════════════════════════════════════════════
        # 2. Sheet 操作
        # ════════════════════════════════════════════
        B = f"{BASE}/v1.0/doc/workbooks/{wb_id}"
        sheet_id = "Sheet1"

        # 获取所有 sheet
        r = await c.request("GET", f"{B}/sheets", headers=H(token), params={"operatorId": UNION_ID})
        R("GET sheets", r.status_code, r.text[:300])
        if ok(r.status_code):
            sheets = r.json().get("value", []) or r.json().get("sheets", [])
            if sheets:
                sheet_id = sheets[0].get("id", sheet_id)

        # 创建新 sheet
        r = await c.request(
            "POST",
            f"{B}/sheets",
            headers=J(token),
            params={"operatorId": UNION_ID},
            json={"name": "MCP测试Sheet"},
        )
        R("POST create sheet", r.status_code, r.text[:200])
        new_sid = None
        if ok(r.status_code):
            new_sid = r.json().get("id", "")

        # ════════════════════════════════════════════
        # 3. Range 读写
        # ════════════════════════════════════════════
        sid = sheet_id

        # 写入
        r = await c.request(
            "PUT",
            f"{B}/sheets/{sid}/ranges/A1:C3",
            headers=J(token),
            params={"operatorId": UNION_ID},
            json={
                "values": [
                    ["MCP列1", "MCP列2", "MCP列3"],
                    ["数据A", "数据B", "数据C"],
                    ["数据D", "数据E", "数据F"],
                ]
            },
        )
        R("PUT range A1:C3", r.status_code, r.text[:200])

        # 读取
        r = await c.request(
            "GET",
            f"{B}/sheets/{sid}/ranges/A1:C3",
            headers=H(token),
            params={"operatorId": UNION_ID},
        )
        R("GET range A1:C3", r.status_code, r.text[:300])

        # ════════════════════════════════════════════
        # 4. 行列操作
        # ════════════════════════════════════════════
        r = await c.request(
            "POST",
            f"{B}/sheets/{sid}/insertRowsBefore",
            headers=J(token),
            params={"operatorId": UNION_ID},
            json={"row": 2, "rowCount": 1},
        )
        R("insertRowsBefore(row=2)", r.status_code, r.text[:200])

        r = await c.request(
            "POST",
            f"{B}/sheets/{sid}/insertColumnsBefore",
            headers=J(token),
            params={"operatorId": UNION_ID},
            json={"column": 2, "columnCount": 1},
        )
        R("insertColsBefore(col=2)", r.status_code, r.text[:200])

        # ════════════════════════════════════════════
        # 5. 单元格属性
        # ════════════════════════════════════════════
        r = await c.request(
            "GET",
            f"{B}/sheets/{sid}/ranges/A1:B2/cellProperties",
            headers=H(token),
            params={"operatorId": UNION_ID},
        )
        R("GET cellProperties", r.status_code, r.text[:200])

        # ════════════════════════════════════════════
        # 6. 清理
        # ════════════════════════════════════════════
        if new_sid:
            r = await c.request(
                "DELETE", f"{B}/sheets/{new_sid}", headers=H(token), params={"operatorId": UNION_ID}
            )
            R("DELETE test sheet", r.status_code)

        # 清除测试数据
        r = await c.request(
            "POST",
            f"{B}/sheets/{sid}/ranges/A1:C3/clear",
            headers=H(token),
            params={"operatorId": UNION_ID},
        )
        R("clear range A1:C3", r.status_code, r.text[:150])

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
