import re
import tempfile
from pathlib import Path
from typing import Tuple


def _safe_filename(name: str) -> str:
    # 仅保留常见安全字符，其他替换为下划线
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\-\.\u4e00-\u9fa5]", "_", name)
    return name


def save_uploaded_file(uploaded_file) -> Tuple[str, str]:
    """
    将 Streamlit UploadedFile 落盘到独立的工作目录，返回 (work_dir, saved_path)
    """
    work_dir = Path(tempfile.mkdtemp(prefix="wxblog_"))
    filename = _safe_filename(uploaded_file.name)
    saved_path = work_dir / filename
    saved_path.write_bytes(uploaded_file.getbuffer())
    return str(work_dir), str(saved_path)
