import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from md2wechat import render_wechat_html


def _find_md_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.md") if p.is_file()]


def process_upload(original_file_path: str, user_meta: Dict[str, str]) -> Dict[str, Any]:
    """
    读取用户上传资料：
      - 若为 zip：解压后批量转换所有 .md
      - 若为 md：直接转换
    返回信息包含工作目录、输出目录、产物与元数据路径、建议的 Drive 子文件夹名。
    """
    work_dir = Path(tempfile.mkdtemp(prefix="wxblog_"))
    uploads_dir = work_dir / "uploads"
    out_dir = work_dir / "out"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    src_name = os.path.basename(original_file_path)

    md_paths: List[Path] = []
    if src_name.lower().endswith(".zip"):
        with zipfile.ZipFile(original_file_path, "r") as zf:
            zf.extractall(uploads_dir)
        md_paths = _find_md_files(uploads_dir)
    else:
        # 将单个文件拷贝到 uploads 目录，保持结构一致
        dst = uploads_dir / src_name
        shutil.copy2(original_file_path, dst)
        if src_name.lower().endswith(".md"):
            md_paths = [dst]
        else:
            md_paths = []

    html_files: List[str] = []
    for md_path in md_paths:
        text = md_path.read_text(encoding="utf-8")
        html = render_wechat_html(text)
        out_html = out_dir / (md_path.stem + ".html")
        out_html.write_text(html, encoding="utf-8")
        html_files.append(str(out_html))

    # 生成元数据
    ts = time.strftime("%Y%m%d_%H%M%S")
    folder_name = f"{ts}_{user_meta.get('email', 'unknown').replace('@', '_')}"
    meta = {
        "user": user_meta,
        "timestamp": ts,
        "original_file_name": src_name,
        "md_files": [str(p.relative_to(work_dir)) for p in md_paths],
        "html_files": [str(Path(p).relative_to(work_dir)) for p in html_files],
    }
    meta_path = work_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "work_dir": str(work_dir),
        "out_dir": str(out_dir),
        "md_files": [str(p) for p in md_paths],
        "html_files": html_files,
        "meta_path": str(meta_path),
        "folder_name": folder_name,
        "original_file_path": original_file_path,
    }
