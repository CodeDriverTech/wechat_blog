import smtplib
from email.message import EmailMessage

try:
    import streamlit as st
except ModuleNotFoundError:
    from utils.deps import install_and_import
    st = install_and_import("streamlit", "streamlit")


def send_admin_mail(subject: str, body: str, smtp_cfg: dict | None = None) -> None:
    """发送管理员通知邮件。
    - 优先使用传入的 smtp_cfg（建议在主线程读取 st.secrets 后传入），
    - 未传入时回退到 st.secrets["smtp"]。
    支持 465(SSL) 与 587(STARTTLS)。
    """
    cfg = smtp_cfg or st.secrets["smtp"]
    host = cfg.get("host")
    port = int(cfg.get("port", 465))
    username = cfg.get("username")
    password = cfg.get("password")
    from_addr = cfg.get("from", username)
    to_addr = cfg.get("to_admin")
    reply_to = cfg.get("reply_to", from_addr)

    if not all([host, port, username, password, from_addr, to_addr]):
        raise RuntimeError("SMTP 配置不完整，请检查 .streamlit/secrets.toml 中的 [smtp] 配置")

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    
    # 优先按端口选择协议；若失败则尝试另一种
    if port == 465:
        try:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(username, password)
                server.send_message(msg)
                return
        except Exception:
            # 回退到 STARTTLS
            with smtplib.SMTP(host, 587, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
                return
    else:
        try:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
                return
        except Exception:
            # 回退到 SSL 465
            with smtplib.SMTP_SSL(host, 465, timeout=30) as server:
                server.login(username, password)
                server.send_message(msg)
