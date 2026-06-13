"""集成测试 — 启动 FastAPI 服务并测试所有端点。

注意：此文件以 `python test_fastapi_integration.py` 方式直接运行，
不会被 pytest 自动收集（因函数签名中的 name 参数与 pytest fixture 冲突）。
"""

__test__ = False
import subprocess, sys, time, httpx, json

PROC = None

def start():
    global PROC
    PROC = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dingding_service.spreadsheet.main:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd="/Users/bill/code/dingding-mcp",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            r = httpx.get("http://127.0.0.1:8765/health", timeout=2)
            if r.status_code == 200: return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def test(name, method, path, **kw):
    try:
        r = httpx.request(method, f"http://127.0.0.1:8765{path}", timeout=10, **kw)
        ok = 200 <= r.status_code < 300
        print(f"  [{'OK' if ok else 'ERR'+str(r.status_code)}] {method:6} {path}")
        try:
            data = r.json()
            print(f"       {json.dumps(data, ensure_ascii=False)[:200]}")
        except Exception:
            print(f"       {r.text[:200]}")
        return ok
    except Exception as e:
        print(f"  [ERR] {method:6} {path}  {e}")
        return False

def main():
    print("Starting FastAPI on :8765...")
    if not start():
        print("FAIL: service did not start")
        sys.exit(1)
    print("Service started\n")

    results = []
    results.append(test("Health",  "GET",  "/health"))
    results.append(test("List",    "GET",  "/api/sheets"))
    results.append(test("Create",  "POST", "/api/sheets", json={"name": "MCP_API测试_请删除"}))
    results.append(test("Read",    "GET",  "/api/sheets/kgqie6hm/range?range=A1:B3"))
    results.append(test("Write",   "PUT",  "/api/sheets/kgqie6hm/range", json={"range": "A1:B2", "values": [["API测试1","API测试2"],["OK1","OK2"]]}))
    results.append(test("Verify",  "GET",  "/api/sheets/kgqie6hm/range?range=A1:B2"))
    results.append(test("InsRow",  "POST", "/api/sheets/kgqie6hm/insertRowsBefore", json={"row": 3, "row_count": 1}))
    results.append(test("InsCol",  "POST", "/api/sheets/kgqie6hm/insertColumnsBefore", json={"column": 3, "column_count": 1}))

    # restore & cleanup
    httpx.put("http://127.0.0.1:8765/api/sheets/kgqie6hm/range", timeout=10, json={
        "range": "A1:C4", "values": [["Name","Score",""],["Alice","100",""],["Bob","99",""],["Charlie","88",""]]
    })
    # delete test sheet if created
    sheets = httpx.get("http://127.0.0.1:8765/api/sheets", timeout=10).json()
    for s in sheets.get("value", []):
        if "API测试" in s.get("name", ""):
            httpx.delete(f"http://127.0.0.1:8765/api/sheets/{s['id']}", timeout=10)
            print(f"  [OK] Deleted test sheet: {s['name']}")

    print(f"\n  Passed: {sum(results)}/{len(results)}")

    PROC.terminate()

if __name__ == "__main__":
    main()
