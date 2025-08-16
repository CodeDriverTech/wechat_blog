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

APP_TITLE = "CodeDriver推文投稿入口（MD/ZIP 转公众号 HTML）"
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


def execute_job(
    original_saved_path: str,
    wechat: str,
    email: str,
    original_filename: str,
    gdrive_cfg: dict,
    smtp_cfg: dict,
):
    """执行任务并返回结果摘要，供同步调试或异步上报使用。"""
    import traceback
    start_ts = time.time()
    child_id = None
    folder_url = None
    uploaded_ok = []
    errors = []
    result = None

    try:
        user_meta = {"wechat": wechat, "email": email}

        # 1) 处理与转换
        result = process_upload(original_saved_path, user_meta)

        # 2) 上传至 Google Drive（使用主线程传入的配置构建 service）
        service = get_drive_service(gdrive_cfg)
        parent_folder_id = gdrive_cfg["folder_id"]
        folder_name = result["folder_name"]
        child_id = create_subfolder(parent_folder_id, folder_name, service=service)
        folder_url = f"https://drive.google.com/drive/folders/{child_id}"

        # 2.1 上传原始文件
        try:
            upload_file(child_id, result["original_file_path"], service=service)
            uploaded_ok.append(result["original_file_path"])
        except Exception as e:
            errors.append(f"原始文件上传失败: {e!r}")

        # 2.2 上传转换产物
        for html_path in result.get("html_files", []):
            try:
                upload_file(child_id, html_path, mime_type="text/html", service=service)
                uploaded_ok.append(html_path)
            except Exception as e:
                errors.append(f"HTML 上传失败 {html_path}: {e!r}")

        # 2.3 上传元数据
        try:
            upload_file(child_id, result["meta_path"], mime_type="application/json", service=service)
            uploaded_ok.append(result["meta_path"])
        except Exception as e:
            errors.append(f"元数据上传失败: {e!r}")
    except Exception as e:
        errors.append(f"处理/建链路失败: {e!r}\n{traceback.format_exc()}")

    # 3) 发送管理员通知（成功或失败）
    duration = int((time.time() - start_ts) * 1000)
    try:
        if errors:
            subject = f"[推文提交失败告警] {email} / {wechat}"
        else:
            subject = f"[新推文提交] {email} / {wechat}"

        lines = [
            f"用户邮箱: {email}",
            f"微信号: {wechat}",
            f"原始文件: {original_filename}",
            f"耗时: {duration}ms",
            f"Drive 文件夹: {folder_url or '未创建'}",
            f"成功上传: {len(uploaded_ok)} 个",
            f"MD 数量: {len(result['md_files']) if result else 'N/A'}",
            f"HTML 数量: {len(result['html_files']) if result else 'N/A'}",
        ]
        if uploaded_ok:
            lines.append("成功文件:\n" + "\n".join(uploaded_ok))
        if errors:
            lines.append("错误详情:\n" + "\n".join(errors))
        body = "\n".join(lines)
        send_admin_mail(subject, body, smtp_cfg=smtp_cfg)
    except Exception as mail_e:
        # 邮件失败仅打印日志
        print("[管理员邮件发送失败]", mail_e)
        print(traceback.format_exc())

    return {
        "child_id": child_id,
        "folder_url": folder_url,
        "uploaded_ok": uploaded_ok,
        "errors": errors,
        "result": result,
        "duration_ms": duration,
    }


def run_job(
    original_saved_path: str,
    wechat: str,
    email: str,
    original_filename: str,
    gdrive_cfg: dict,
    smtp_cfg: dict,
) -> None:
    """在后台线程执行处理、上传与通知（异步）。"""
    execute_job(
        original_saved_path,
        wechat,
        email,
        original_filename,
        gdrive_cfg,
        smtp_cfg,
    )


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

        # 读取调试开关：secrets.debug.sync = true 时，同步执行以在页面展示错误
        debug_sync = False
        try:
            debug_sync = bool(st.secrets.get("debug", {}).get("sync", False))
        except Exception:
            debug_sync = False

        gdrive_cfg = dict(st.secrets["gdrive"])  # 复制为普通 dict
        smtp_cfg = dict(st.secrets["smtp"])      # 复制为普通 dict

        if debug_sync:
            with st.status("正在处理（同步调试模式）…", expanded=True) as status:
                st.write("1) 开始解压/转换/上传")
                summary = execute_job(
                    saved_path,
                    wechat.strip(),
                    email.strip(),
                    uploaded.name,
                    gdrive_cfg,
                    smtp_cfg,
                )
                status.update(label="处理完成", state="complete")

            if summary["errors"]:
                st.error("发生错误，详情如下：")
                st.code("\n".join(summary["errors"]))
            else:
                st.success("上传成功！")
            if summary["folder_url"]:
                st.write(f"Drive 文件夹: {summary['folder_url']}")
            if summary.get("result"):
                st.caption("处理摘要：")
                st.json({
                    "md_files": summary["result"].get("md_files"),
                    "html_files": summary["result"].get("html_files"),
                    "meta_path": summary["result"].get("meta_path"),
                })
        else:
            # 入队后台任务（将 secrets 在主线程读取并以纯 dict 传入子线程）
            executor = get_executor()
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
