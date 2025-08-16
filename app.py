import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

try:
    import streamlit as st
except ModuleNotFoundError:
    from utils.deps import install_and_import
    st = install_and_import("streamlit", "streamlit")

from services.processor import process_upload
from services.gdrive import create_subfolder, upload_file, get_drive_service
from services.mailer import send_admin_mail
from utils.fs import save_uploaded_file

APP_TITLE = "推文投稿入口（Markdown/ZIP 转微信公众号 HTML）"
MAX_UPLOAD_MB = 200


@st.cache_resource
def get_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=4)


def bytes_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def run_job(
    original_saved_path: str,
    wechat: str,
    email: str,
    original_filename: str,
    gdrive_cfg: dict,
    smtp_cfg: dict,
) -> None:
    """在后台线程执行处理、上传与通知。
    注意：不得在此函数中直接调用任何 st.* API。
    """
    try:
        user_meta = {"wechat": wechat, "email": email}

        # 1) 处理与转换
        result = process_upload(original_saved_path, user_meta)

        # 2) 上传至 Google Drive（使用主线程传入的配置构建 service）
        service = get_drive_service(gdrive_cfg)
        parent_folder_id = gdrive_cfg["folder_id"]
        folder_name = result["folder_name"]
        child_id = create_subfolder(parent_folder_id, folder_name, service=service)

        # 上传原始文件
        upload_file(child_id, result["original_file_path"], service=service)  # mime 自动识别即可

        # 上传转换产物
        for html_path in result["html_files"]:
            upload_file(child_id, html_path, mime_type="text/html", service=service)

        # 上传元数据
        upload_file(child_id, result["meta_path"], mime_type="application/json", service=service)

        # 3) 通知管理员
        folder_url = f"https://drive.google.com/drive/folders/{child_id}"
        subject = f"[新推文提交] {email} / {wechat}"
        body = (
            f"用户邮箱: {email}\n"
            f"微信号: {wechat}\n"
            f"原始文件: {original_filename}\n"
            f"Drive 文件夹: {folder_url}\n"
            f"MD 数量: {len(result['md_files'])}\n"
            f"HTML 数量: {len(result['html_files'])}\n"
        )
        send_admin_mail(subject, body, smtp_cfg=smtp_cfg)
    except Exception as e:
        # 子线程中不可用 st.*，使用 print 输出到控制台日志
        import traceback

        print("[后台任务失败]", e)
        print(traceback.format_exc())


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="centered")
    st.title(APP_TITLE)
    st.write("请上传 .md 或 .zip 文件（含 Markdown 与资源），并填写微信号与邮箱。单文件不超过 200MB。")

    with st.form(key="submit_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "上传资料（.md 或 .zip）",
            type=["md", "zip"],
            accept_multiple_files=False,
            help="支持 Markdown 文件或 ZIP 压缩包（压缩包内可包含图片等资源）"
        )
        wechat = st.text_input("微信号（必填）", placeholder="用于发送预览链接")
        email = st.text_input("邮箱（必填）", placeholder="用于审核后的邮件通知")
        submitted = st.form_submit_button("提交")

    if submitted:
        # 基础校验
        if not uploaded:
            st.error("请先选择要上传的文件。")
            return
        if not wechat.strip():
            st.error("请填写微信号。")
            return
        if not email.strip():
            st.error("请填写邮箱。")
            return

        # 大小校验（双保险）
        size_bytes: Optional[int] = getattr(uploaded, "size", None)
        if size_bytes is None:
            size_bytes = uploaded.getbuffer().nbytes
        if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
            st.error("单文件大小超过 200MB，请压缩或拆分后再上传。")
            return

        # 落盘保存
        work_dir, saved_path = save_uploaded_file(uploaded)

        # 入队后台任务（将 secrets 在主线程读取并以纯 dict 传入子线程）
        executor = get_executor()
        gdrive_cfg = dict(st.secrets["gdrive"])  # 复制为普通 dict
        smtp_cfg = dict(st.secrets["smtp"])      # 复制为普通 dict
        executor.submit(
            run_job,
            saved_path,
            wechat.strip(),
            email.strip(),
            uploaded.name,
            gdrive_cfg,
            smtp_cfg,
        )

        # 立即向用户反馈
        with st.status("已接收上传，正在后台处理…", expanded=True) as status:
            st.write("1) 文件已上传并入队处理")
            st.write("2) 解压/转换/上传至 Drive 将在后台进行")
            st.write("3) 管理员审核后会通过邮件通知您")
            time.sleep(0.8)
            status.update(label="处理任务已入队", state="complete")

        st.success("感谢您的推文贡献！待审核通过将会自动生成一份预览链接并将通过邮件通知您！")
        st.info("如需再次提交，可刷新页面或直接再次上传。")


if __name__ == "__main__":
    main()
