import os
from typing import Dict, Any, Optional

try:
    import streamlit as st
except ModuleNotFoundError:
    from utils.deps import install_and_import
    st = install_and_import("streamlit", "streamlit")

try:
    from google.oauth2.service_account import Credentials
except ModuleNotFoundError:
    from utils.deps import install_and_import
    Credentials = install_and_import("google.oauth2.service_account", "google-auth").Credentials

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ModuleNotFoundError:
    from utils.deps import install_and_import
    build = install_and_import("googleapiclient.discovery", "google-api-python-client").build
    MediaFileUpload = install_and_import("googleapiclient.http", "google-api-python-client").MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service(gdrive_cfg: Optional[Dict[str, Any]] = None):
    """
    构建 Drive service。
    - 如提供 gdrive_cfg（来自主线程读取的 st.secrets["gdrive"] 副本），则使用之；
    - 否则回退读取 st.secrets（不建议在线程中调用）。
    """
    g = gdrive_cfg or st.secrets["gdrive"]
    info = dict(g)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    # 直接使用凭证构建 Drive service（云端环境无需代理）
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_subfolder(parent_folder_id: str, name: str, service=None) -> str:
    service = service or get_drive_service()
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    folder = service.files().create(body=metadata, fields="id, name").execute()
    return folder["id"]


def upload_file(parent_id: str, file_path: str, mime_type: Optional[str] = None, service=None) -> Dict[str, Any]:
    service = service or get_drive_service()
    metadata = {"name": os.path.basename(file_path), "parents": [parent_id]}
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, webViewLink, webContentLink")
        .execute()
    )
    return file
