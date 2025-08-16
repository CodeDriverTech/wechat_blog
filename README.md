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

- Windows 用户如无 `python` 命令，可使用 `py`：
```bash
py md2wechat.py input.md -o out.html
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
