import requests, datetime, json
BASE = "Your Base URL"
HDRS = {"Authorization": "Bearer Your Token"}

# 1) 健康检查
r = requests.get(f"{BASE}/health", headers=HDRS, verify=False)
print("health:", r.status_code, r.text)

# 2) 最小表单写入
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
data = {
    "wechat": "tester",
    "email": "tester@example.com",
    "original_filename": "hello.md",
    "folder_name": f"TEST_{ts}",
    "timestamp": ts,
    "duration_ms": "1234",
    "meta_json_text": json.dumps({
        "user": {"wechat": "tester", "email": "tester@example.com"},
        "timestamp": ts,
        "original_file_name": "hello.md",
        "md_files": [],
        "html_files": []
    }, ensure_ascii=False)
}
r = requests.post(f"{BASE}/api/submissions", headers=HDRS, data=data, verify=False)
print("submit:", r.status_code, r.text)