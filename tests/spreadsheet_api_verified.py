"""
钉钉在线表格 (传统 Spreadsheet) REST API — 已验证操作清单

测试文档: "Server-API-表格" (OG9lyrgJPzlZk5jeFz5X3ejDWzN67Mw4)
unionId: KZDkvpwM6G22ubVeRZKYRwiEiE

所有操作均通过 HTTP 直接调用验证。
"""

# ═══════════════════════════════════════════════════════
# 已验证通过的 API 操作
# ═══════════════════════════════════════════════════════

VERIFIED_OPS = {
    # Sheet 管理
    "获取所有工作表": {
        "method": "GET",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets",
        "query": "operatorId={unionId}",
        "status": "OK",
    },
    "创建工作表": {
        "method": "POST",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets",
        "query": "operatorId={unionId}",
        "body": {"name": "工作表名称"},
        "status": "OK",
    },
    "删除工作表": {
        "method": "DELETE",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}",
        "query": "operatorId={unionId}",
        "status": "OK",
    },

    # Range 读写
    "读取单元格区域": {
        "method": "GET",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}/ranges/{range}",
        "query": "operatorId={unionId}",
        "returns": "values, displayValues, formulas, backgroundColors, fontSizes, fontWeights, hyperlinks, alignments",
        "status": "OK",
    },
    "写入单元格区域": {
        "method": "PUT",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}/ranges/{range}",
        "query": "operatorId={unionId}",
        "body": {"values": [["行1列1", "行1列2"], ["行2列1", "行2列2"]]},
        "status": "OK",
    },

    # 行列操作
    "指定行上方插入行": {
        "method": "POST",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}/insertRowsBefore",
        "query": "operatorId={unionId}",
        "body": {"row": 3, "rowCount": 2},
        "status": "OK",
    },
    "指定列左侧插入列": {
        "method": "POST",
        "path": "/v1.0/doc/workbooks/{workbookId}/sheets/{sheetId}/insertColumnsBefore",
        "query": "operatorId={unionId}",
        "body": {"column": 2, "columnCount": 1},
        "status": "OK",
    },
}

# ═══════════════════════════════════════════════════════
# 待验证的 API 操作 (路径存在但未充分测试)
# ═══════════════════════════════════════════════════════

UNVERIFIED_OPS = {
    "删除行": "POST /doc/workbooks/{id}/sheets/{sid}/deleteRows  (body: {row, rowCount})",
    "删除列": "POST /doc/workbooks/{id}/sheets/{sid}/deleteColumns  (body: {column, columnCount})",
    "指定行下方插入行": "POST .../insertRowsAfter",
    "指定列右侧插入列": "POST .../insertColumnsAfter",
    "追加行": "POST .../appendRows",
    "设置行可见性": "PUT .../setRowsVisibility",
    "设置列可见性": "PUT .../setColumnsVisibility",
    "合并单元格": "POST .../mergeCells",
    "取消合并": "POST .../unmergeCells",
    "获取单元格属性": "GET .../ranges/{range}/cellProperties",
    "更新单元格属性": "PUT .../ranges/{range}/cellProperties",
    "清除单元格数据": "POST .../ranges/{range}/clear",
    "清除全部内容": "POST .../ranges/{range}/clearAll",
    "设置行高": "PUT .../rowHeight",
    "设置列宽": "PUT .../columnWidth",
    "查找匹配单元格": "POST .../find",
    "查找所有匹配": "POST .../findAll",
    "插入下拉列表": "POST .../dropdownLists",
    "删除下拉列表": "DELETE .../dropdownLists/{id}",
}

# ═══════════════════════════════════════════════════════
# 环境变量
# ═══════════════════════════════════════════════════════

REQUIRED_ENV = {
    "DINGTALK_Client_ID": "钉钉应用 AppKey",
    "DINGTALK_Client_Secret": "钉钉应用 AppSecret",
}

REQUIRED_PARAMS = {
    "unionId": "操作人的 unionId (从通讯录API获取)",
    "workbookId": "表格文档ID (从文档URL或搜索API获取)",
}

# ═══════════════════════════════════════════════════════
# Python 调用示例
# ═══════════════════════════════════════════════════════

EXAMPLE = '''
import httpx
import asyncio

BASE = "https://api.dingtalk.com"

async def get_token(appkey, appsecret):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/v1.0/oauth2/accessToken",
            json={"appKey": appkey, "appSecret": appsecret})
        return r.json()["accessToken"]

async def spreadsheet_example():
    token = "YOUR_TOKEN"
    union_id = "YOUR_UNION_ID"
    workbook_id = "YOUR_WORKBOOK_ID"
    headers = {"x-acs-dingtalk-access-token": token}

    async with httpx.AsyncClient() as c:
        # 1. 获取所有工作表
        r = await c.get(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets",
            headers=headers,
            params={"operatorId": union_id}
        )
        sheets = r.json()["value"]
        sheet_id = sheets[0]["id"]

        # 2. 读取单元格
        r = await c.get(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/ranges/A1:C10",
            headers=headers,
            params={"operatorId": union_id}
        )
        print(r.json()["values"])

        # 3. 写入单元格
        r = await c.put(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/ranges/A1:B2",
            headers={**headers, "Content-Type": "application/json"},
            params={"operatorId": union_id},
            json={"values": [["新数据1", "新数据2"], ["新数据3", "新数据4"]]}
        )

        # 4. 创建工作表
        r = await c.post(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets",
            headers={**headers, "Content-Type": "application/json"},
            params={"operatorId": union_id},
            json={"name": "新工作表"}
        )
        new_sheet_id = r.json()["id"]

        # 5. 插入行
        r = await c.post(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets/{sheet_id}/insertRowsBefore",
            headers={**headers, "Content-Type": "application/json"},
            params={"operatorId": union_id},
            json={"row": 5, "rowCount": 3}
        )

        # 6. 删除工作表
        await c.delete(
            f"{BASE}/v1.0/doc/workbooks/{workbook_id}/sheets/{new_sheet_id}",
            headers=headers,
            params={"operatorId": union_id}
        )

asyncio.run(spreadsheet_example())
'''

if __name__ == "__main__":
    print("钉钉 Spreadsheet API 已验证操作:")
    for name, info in VERIFIED_OPS.items():
        print(f"  [{info['status']}] {info['method']:6} {info['path']}")
    print(f"\n已验证: {len(VERIFIED_OPS)} 个操作")
    print(f"待验证: {len(UNVERIFIED_OPS)} 个操作 (路径已确认，需进一步测试)")
    print(f"\n完整示例见 EXAMPLE 变量")
