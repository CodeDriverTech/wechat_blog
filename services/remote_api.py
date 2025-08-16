import json
import os
import zipfile
from pathlib import Path
from typing import Dict, Any

try:
    import requests
except ModuleNotFoundError:
    from utils.deps import install_and_import
    requests = install_and_import("requests", "requests")


def _build_payload_zip(result: Dict[str, Any]) -> str:
    """
    基于 process_upload() 的返回结果，打包 payload.zip：
    - 包含 out/*.html
    - 包含 meta.json
    - 可选包含原始文件（放入 uploads/ 下）
    返回 zip 文件的绝对路径。
    """
    work_dir = Path(result["work_dir"])  # 绝对路径
    zip_path = work_dir / "payload.zip"
    html_files = result.get("html_files", [])
    meta_path = Path(result["meta_path"])  # 绝对路径
    original_file_path = Path(result["original_file_path"])  # 可能不在 work_dir 内

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 写入 HTML 产物（放回相对路径 out/xxx.html）
        for p in html_files:
            p = Path(p)
            try:
                arcname = str(Path("out") / p.name)
                zf.write(p, arcname)
            except FileNotFoundError:
                # 忽略缺失
                pass

        # 写入 meta.json（放在根目录）
        if meta_path.exists():
            zf.write(meta_path, "meta.json")

        # 写入原始文件（放在 uploads/ 下）
        if original_file_path.exists():
            arcname = str(Path("uploads") / original_file_path.name)
            zf.write(original_file_path, arcname)

    return str(zip_path)


def post_submission_zip(base_url: str, token: str, manifest: Dict[str, Any], zip_path: str, verify_ssl: bool = True) -> Dict[str, Any]:
    """
    以 zip+manifest 方式提交到远端 FastAPI。
    返回响应 JSON。
    """
    url = base_url.rstrip("/") + "/api/submissions"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    files = {
        "payload_zip": (os.path.basename(zip_path), open(zip_path, "rb"), "application/zip"),
    }
    data = {
        "manifest": json.dumps(manifest, ensure_ascii=False),
    }
    try:
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=60, verify=verify_ssl)
        resp.raise_for_status()
        return resp.json()
    finally:
        # 关闭文件句柄
        try:
            files["payload_zip"][1].close()
        except Exception:
            pass


def send_to_remote(result: Dict[str, Any], manifest: Dict[str, Any], remote_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    高层封装：根据 result 构建 zip 并提交。
    remote_cfg 需要包含：
      - base_url: 远端 API 根地址
      - token:    API Token（可空）
      - verify_ssl: bool 是否校验证书（缺省 True）
    返回响应 JSON。
    """
    base_url = remote_cfg.get("base_url")
    token = remote_cfg.get("token", "")
    verify_ssl = bool(remote_cfg.get("verify_ssl", True))

    if not base_url:
        raise ValueError("remote.base_url 不能为空")

    zip_path = _build_payload_zip(result)
    return post_submission_zip(base_url, token, manifest, zip_path, verify_ssl=verify_ssl)
