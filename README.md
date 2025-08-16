# Markdown 转微信公众号 HTML 工具

本工具将 Markdown 转换为符合项目中模板的微信公众号 HTML。模板位于 `templates/` 目录，生成的 HTML 将内嵌这些模板片段以满足样式要求。

## 功能与规则
- **正文区块**：除最后的结束符外，所有内容都包裹在 `templates/正文区块.html` 的 `{content}` 中。
- **空行**：遇到空行时，在当前区块末尾插入一次 `templates/空行.html`，随后结束当前区块并重启新正文区块。
- **分隔符**：`---` 或 `***` 作为分隔符，单独顶层输出 `templates/分割线.html`，并重启正文区块。
- **标题**：
  - `# 标题` -> `templates/一级标题.html`（自动递增 Part.{index}，两位数）
  - `## 标题` -> `templates/二级标题.html`
- **引用**：连续以 `>` 开头的行会合并为一个引用块，使用 `templates/引用.html`。
- **代码块**：围栏代码（``` 或 ~~~）不会使用代码模板，而是通过 `templates/文本.html` 嵌入文本，内容为 `code:` 前缀 + 代码，换行用 `\n` 字面量。
- **图片**：Markdown 图片语法会插入 `templates/图片.html` 模板。模板内置示例图片，脚本不会替换图片 URL。
- **列表/表格**：不会直接嵌入示例模板，脚本会按项目样式生成 `ul/ol/table` 的 HTML，并在 `li/td` 中嵌入文本模板样式。
- **固定区块**：
  - 文章开头：在首个正文区块内插入 `templates/关注我们_top.html`
  - 文章结尾：在最后一个正文区块内插入 `templates/关注我们_bottom.html`
  - 页面最末尾：`templates/结束符.html`

## 使用方法
```bash
# 生成同名 .html
python md2wechat.py input.md

# 指定输出路径
python md2wechat.py input.md -o out.html
```

## 目录结构
- `md2wechat.py` 转换脚本
- `templates/` 模板目录（必须存在）

## 注意事项
- 图片模板为固定示例图，如需替换为 Markdown 中的图片，请在生成后手工替换或二次开发脚本（搜索 `tpl_img`）。
- 列表缩进以 2 个空格为一个层级；不同 Markdown 编辑器的缩进可能不同，必要时先规范缩进。
- 表格支持常见管道风格（带分隔行 `| --- | --- |`）。

## 快速开始
项目已提供 `sample.md` 示例：
```bash
python md2wechat.py sample.md -o sample.html
```
转换成功后，会在项目根目录生成 `sample.html`，可在浏览器或公众号编辑器中查看效果。

---

## 投稿入口（Streamlit 应用）

本项目提供一个基于 Streamlit 的投稿入口：上传 `.md` 或包含多篇文章与资源的 `.zip`，自动转换并上报至远端 FastAPI 存储。

### 运行
```bash
pip install -r requirements.txt
streamlit run app.py
```

首次运行后，浏览器访问 `http://localhost:8501`。

### 配置 secrets（必须）
创建或编辑 `/.streamlit/secrets.toml`：

```toml
[remote]
# 远端 FastAPI 服务根地址（不要以 / 结尾）
base_url = "https://your-remote-host:8443"
# 访问令牌（如服务端需要鉴权，则必填）
token = "your-token"
# 测试环境可关闭证书校验；生产请改为 true
verify_ssl = false

[smtp]
host = "smtp.example.com"
port = 465
username = "bot@example.com"
password = "******"
from = "bot@example.com"
to_admin = "admin@example.com"
reply_to = "noreply@example.com"

# 可选：同步调试模式（将后台任务改为前台执行，便于页面直接显示错误）
[debug]
sync = false
```

### 提交流程（客户端）
- `app.py` 中的 `execute_job()` 调用 `services/processor.py` 的 `process_upload()` 完成转换：
  - 生成 `out/*.html`、`meta.json`
- `services/remote_api.py` 将上述产物打包为 `payload.zip`，并连同 `manifest` 表单字段一起 `POST` 至服务端：
  - 表单字段：`manifest`（JSON 字符串）
  - 文件字段：`payload_zip`（application/zip）
- 发送管理员邮件摘要（如配置了 SMTP）。

`manifest` 典型字段：
```json
{
  "wechat": "wx_id",
  "email": "user@example.com",
  "original_filename": "upload.zip",
  "folder_name": "20250101_foo_example.com",
  "timestamp": "20250101_120000",
  "duration_ms": 1234
}
```

### 服务端接口约定（摘要）
- `POST {base_url}/api/submissions`
  - headers: `Authorization: Bearer <token>`（如启用鉴权）
  - form-data: `manifest`（JSON 字符串）
  - files: `payload_zip`（zip，内部包含 `out/*.html`、`meta.json`、`uploads/<原始文件>`）
  - 响应示例：`{"folder": "TEST_20250101_120000"}`

项目内含 `test/server_test.py` 作为简单连通性示例（演示最小表单模式）；实际应用侧使用的是 zip+manifest 方案，详见 `services/remote_api.py`。

## 目录结构（补充）
- `app.py` Streamlit 投稿入口
- `services/processor.py` 处理上传与 Markdown 转换
- `services/remote_api.py` 打包 `payload.zip` 并提交至远端
- `services/mailer.py` 管理员通知邮件
- `templates/` 微信样式模板片段（必须存在）

## 常见问题（FAQ）
- 警告 `InsecureRequestWarning: Unverified HTTPS request ...`：
  - 在开发/内网测试可将 `verify_ssl=false`；若为公网生产，请配置有效证书并设为 `true`。
- 页面无响应或被中止：
  - 检查远端服务可达性、`base_url` 是否正确、token 是否有效；
  - 如需在页面直接看到错误细节，将 `secrets.toml` 中的 `[debug].sync = true` 临时开启同步调试。
- 提交成功但页面无“远端存储”输出：
  - 服务端应在响应 JSON 中返回 `folder` 字段；若无该字段，客户端只会显示“未创建”。

## Git 忽略
`.gitignore` 已忽略 `__pycache__/`、虚拟环境目录、构建缓存与 `/.streamlit/secrets.toml` 等敏感文件，避免误提交。
