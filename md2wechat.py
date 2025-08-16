# -*- coding: utf-8 -*-
"""
Markdown 转公众号 HTML 转换脚本（无第三方依赖）

规则实现要点：
1. 除结束符外的所有内容，都会包裹在 `正文区块.html` 的 {content} 中；
2. 遇到空行：在当前正文区块末尾插入一次 `空行.html`，随后结束本区块并开启新的正文区块；
3. 分隔符（--- 或 ***）顶层输出：关闭当前正文区块，单独输出 `分割线.html`，之后开启新的正文区块；
4. Markdown 元素映射：
   - # -> `一级标题.html`（仅 #）
   - ## -> `二级标题.html`（仅 ##）
   - > -> `引用.html`
   - 图片 ![alt](url) -> 插入 `图片.html`（不修改链接，后续人工替换）
   - 列表/表格 -> 代码生成（不直接嵌入示例模板）
5. 代码块（```lang ... ``` 或 ~~~）：不使用代码模板，转为 `文本.html`，内容为：
   `code:` + 代码，换行以 \n 表示（单个文本模板承载）
6. `关注我们_top.html`、`关注我们_bottom.html`、`结束符.html` 必须存在并按要求位置输出。
7. 注意缩进与嵌套；

用法：
python md2wechat.py input.md -o output.html

作者：Cascade
"""

import os
import re
import sys
import argparse
from typing import List, Tuple, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(ROOT, 'templates')

# 模板文件名常量
TPL_NAMES = {
    'root': '正文区块.html',
    'text': '文本.html',
    'h1': '一级标题.html',
    'h2': '二级标题.html',
    'quote': '引用.html',
    'img': '图片.html',
    'hr': '分割线.html',
    'blank': '空行.html',
    'follow_top': '关注我们_top.html',
    'follow_bottom': '关注我们_bottom.html',
    'end': '结束符.html',
}


def read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def html_escape(text: str) -> str:
    """最小必要转义。"""
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
    )


def load_tpl(name_key: str, tpl_dir: str) -> str:
    path = os.path.join(tpl_dir, TPL_NAMES[name_key])
    if not os.path.exists(path):
        raise FileNotFoundError(f'缺少模板: {path}')
    return read_file(path)


# 列表样式映射（与示例保持一致的循环）
UL_TYPES = ['disc', 'square', 'circle']  # 深度 1,2,3 轮转
OL_TYPES = ['decimal', 'lower-alpha', 'lower-roman', 'upper-alpha']  # 深度循环


def ul_type_by_depth(depth: int) -> str:
    idx = (depth - 1) % len(UL_TYPES)
    return UL_TYPES[idx]


def ol_type_by_depth(depth: int) -> str:
    idx = (depth - 1) % len(OL_TYPES)
    return OL_TYPES[idx]


# Markdown 简单识别正则
RE_H1 = re.compile(r"^\s*#\s+(.*)$")
RE_H2 = re.compile(r"^\s*##\s+(.*)$")
RE_BLOCKQUOTE = re.compile(r"^\s*>\s?(.*)$")
RE_HR = re.compile(r"^\s*([*-])\1\1[\s*-]*$")  # --- 或 ***
RE_OL = re.compile(r"^(\s*)(\d+)[\.)]\s+(.*)$")
RE_UL = re.compile(r"^(\s*)([\-\+\*])\s+(.*)$")
RE_IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


class Parser:
    """将 Markdown 文本解析为微信 HTML，依赖本地 templates。"""

    def __init__(self, md_text: str, tpl_dir: Optional[str] = None):
        self.lines = md_text.splitlines()
        self.pos = 0
        self.h1_count = 0
        # 模板目录（可配置）
        self.tpl_dir = tpl_dir or os.path.join(ROOT, 'templates')

        # 运行期模板缓存
        self.tpl_root = load_tpl('root', self.tpl_dir)
        self.tpl_text = load_tpl('text', self.tpl_dir)
        self.tpl_h1 = load_tpl('h1', self.tpl_dir)
        self.tpl_h2 = load_tpl('h2', self.tpl_dir)
        self.tpl_quote = load_tpl('quote', self.tpl_dir)
        self.tpl_img = load_tpl('img', self.tpl_dir)
        self.tpl_hr = load_tpl('hr', self.tpl_dir)
        self.tpl_blank = load_tpl('blank', self.tpl_dir)
        self.tpl_follow_top = load_tpl('follow_top', self.tpl_dir)
        self.tpl_follow_bottom = load_tpl('follow_bottom', self.tpl_dir)
        self.tpl_end = load_tpl('end', self.tpl_dir)

        # 输出拼装
        self.result_parts: List[str] = []  # 顶层输出（含分割线）
        self.curr_block_parts: List[str] = []  # 当前正文区块内容
        self.block_opened = False

    # -------------- 辅助：正文区块控制 --------------
    def _open_block_if_needed(self):
        if not self.block_opened:
            self.curr_block_parts = []
            # 每篇开头插入关注我们_top
            if not self.result_parts:  # 第一块
                self.curr_block_parts.append(self.tpl_follow_top)
            self.block_opened = True

    def _close_block_if_needed(self):
        if self.block_opened:
            content = ''.join(self.curr_block_parts)
            block_html = self.tpl_root.replace('{content}', content)
            self.result_parts.append(block_html)
            self.curr_block_parts = []
            self.block_opened = False

    def _add_blank_and_restart(self):
        # 空行：在当前区块末尾追加空行模板，然后关闭并重启
        self._open_block_if_needed()
        self.curr_block_parts.append(self.tpl_blank)
        self._close_block_if_needed()
        # 新区块稍后按需开启

    def _add_hr_and_restart(self):
        # 分隔符：关闭当前区块，单独输出分割线，然后重启
        self._close_block_if_needed()
        self.result_parts.append(self.tpl_hr)
        # 新区块稍后按需开启

    # -------------- 解析主循环 --------------
    def parse(self) -> str:
        code_fence = None  # '```' 或 '~~~'
        code_lines: List[str] = []

        while self.pos < len(self.lines):
            line = self.lines[self.pos]

            # 代码块状态机
            if code_fence:
                if line.strip().startswith(code_fence):
                    # 结束代码块
                    raw_code = '\n'.join(code_lines)
                    text = 'code:' + raw_code.replace('\\', '\\\\').replace('\n', r'\n')
                    self._open_block_if_needed()
                    self.curr_block_parts.append(
                        self.tpl_text.replace('{content}', html_escape(text))
                    )
                    code_fence, code_lines = None, []
                else:
                    code_lines.append(line)
                self.pos += 1
                continue

            # 空行
            if line.strip() == '':
                self._add_blank_and_restart()
                self.pos += 1
                continue

            # 分隔符（--- 或 ***）
            if RE_HR.match(line):
                self._add_hr_and_restart()
                self.pos += 1
                continue

            # 代码围栏开始
            stripped = line.lstrip()
            if stripped.startswith('```'):
                code_fence = '```'
                code_lines = []
                self.pos += 1
                continue
            if stripped.startswith('~~~'):
                code_fence = '~~~'
                code_lines = []
                self.pos += 1
                continue

            # 图片（每出现一次图片，插入一次图片模板）
            if RE_IMG.search(line):
                self._open_block_if_needed()
                # 忽略图片 URL，使用模板原样插入
                self.curr_block_parts.append(self.tpl_img)
                # 如果行中还包含其他可见文字，作为文本插入
                text_only = RE_IMG.sub('', line).strip()
                if text_only:
                    self.curr_block_parts.append(
                        self.tpl_text.replace('{content}', html_escape(text_only))
                    )
                self.pos += 1
                continue

            # 标题
            m1 = RE_H1.match(line)
            if m1:
                self.h1_count += 1
                title = html_escape(m1.group(1).strip())
                idx = f"{self.h1_count:02d}"
                self._open_block_if_needed()
                self.curr_block_parts.append(
                    self.tpl_h1.replace('{index}', idx).replace('{title}', title)
                )
                self.pos += 1
                continue

            m2 = RE_H2.match(line)
            if m2:
                title = html_escape(m2.group(1).strip())
                self._open_block_if_needed()
                self.curr_block_parts.append(
                    self.tpl_h2.replace('{title}', title)
                )
                self.pos += 1
                continue

            # 引用块（连续的 > 行合并）
            mq = RE_BLOCKQUOTE.match(line)
            if mq:
                self._open_block_if_needed()
                quote_lines = [mq.group(1)]
                self.pos += 1
                while self.pos < len(self.lines):
                    nxt = self.lines[self.pos]
                    mq2 = RE_BLOCKQUOTE.match(nxt)
                    if mq2:
                        quote_lines.append(mq2.group(1))
                        self.pos += 1
                    else:
                        break
                content = '<br>'.join(html_escape(s) for s in quote_lines)
                self.curr_block_parts.append(
                    self.tpl_quote.replace('{content}', content)
                )
                continue

            # 列表（有序 / 无序，含嵌套）
            if RE_OL.match(line) or RE_UL.match(line):
                self._open_block_if_needed()
                html, new_pos = self._parse_list(self.pos)
                self.curr_block_parts.append(html)
                self.pos = new_pos
                continue

            # 表格（简单管道风格）
            if '|' in line:
                maybe_table_html, consumed = self._parse_table(self.pos)
                if consumed > 0:
                    self._open_block_if_needed()
                    self.curr_block_parts.append(maybe_table_html)
                    self.pos += consumed
                    continue

            # 普通文本（聚合连续非空、非特殊行到一段）
            self._open_block_if_needed()
            paras = [line]
            self.pos += 1
            while self.pos < len(self.lines):
                peek = self.lines[self.pos]
                if (peek.strip() == '' or RE_HR.match(peek) or RE_H1.match(peek) or RE_H2.match(peek)
                        or RE_BLOCKQUOTE.match(peek) or RE_OL.match(peek) or RE_UL.match(peek)
                        or '|' in peek or peek.lstrip().startswith(('```', '~~~')) or RE_IMG.search(peek)):
                    break
                paras.append(peek)
                self.pos += 1
            text = html_escape('\n'.join(p.strip() for p in paras))
            self.curr_block_parts.append(
                self.tpl_text.replace('{content}', text)
            )

        # 收尾：在最后一个正文区块尾部插入关注我们_bottom，然后输出结束符
        self._open_block_if_needed()
        self.curr_block_parts.append(self.tpl_follow_bottom)
        self._close_block_if_needed()
        self.result_parts.append(self.tpl_end)

        return ''.join(self.result_parts)

    # -------------- 列表解析 --------------
    def _parse_list(self, start: int) -> Tuple[str, int]:
        """
        解析从 start 开始的列表（有序/无序，含嵌套），返回 (html, 新位置)
        简单基于缩进（空格数量）判定层级。
        """
        items: List[Tuple[int, str, str]] = []  # (depth, type, text) type: 'ul'/'ol'

        i = start
        while i < len(self.lines):
            line = self.lines[i]
            mol = RE_OL.match(line)
            mul = RE_UL.match(line)
            if mol:
                indent = len(mol.group(1).replace('\t', '    '))
                depth = indent // 2 + 1  # 2 空格为一级缩进
                text = mol.group(3).strip()
                items.append((depth, 'ol', text))
                i += 1
                continue
            elif mul:
                indent = len(mul.group(1).replace('\t', '    '))
                depth = indent // 2 + 1
                text = mul.group(3).strip()
                items.append((depth, 'ul', text))
                i += 1
                continue
            else:
                break

        # 根据 items 构建嵌套 HTML
        html_parts: List[str] = []
        stack: List[Tuple[str, int]] = []  # (list_type, depth)

        def open_list(list_type: str, depth: int):
            if list_type == 'ul':
                style = f"list-style-type: {ul_type_by_depth(depth)};padding-left: 1.2em;color: rgb(37, 37, 37);width: fit-content;"
                html_parts.append(f'<ul style="{style}" class="list-paddingleft-1">')
            else:
                style = f"list-style-type: {ol_type_by_depth(depth)};padding-left: 1.2em;color: rgb(37, 37, 37);width: fit-content;"
                html_parts.append(f'<ol style="{style}" class="list-paddingleft-1">')
            stack.append((list_type, depth))

        def close_list():
            if not stack:
                return
            list_type, _ = stack.pop()
            html_parts.append('</ul>' if list_type == 'ul' else '</ol>')

        def close_to_depth(target_depth: int):
            while stack and stack[-1][1] > target_depth:
                close_list()

        # 列表项样式 wrapper（参照示例）
        def li_content_span(text: str) -> str:
            safe = html_escape(text)
            return (
                '<section style="margin-bottom: 8px;font-size: 15px;color:#333333;letter-spacing: 1px;" '
                'data-mpa-md-content="t" data-mpa-md-key="{key}" data-mpa-md-template="30005">'
                '<span leaf="">{text}</span>'
                '</section>'
            ).replace('{text}', safe)

        for depth, typ, text in items:
            # 打开/关闭到对应深度
            if not stack or depth > stack[-1][1]:
                open_list(typ, depth)
            else:
                # 若类型变化或深度变化，先收缩到 (depth-1) 后再开
                while stack and (stack[-1][1] > depth or stack[-1][0] != typ):
                    close_list()
                if not stack or stack[-1][1] < depth or stack[-1][0] != typ:
                    open_list(typ, depth)

            # 输出 li 项
            key = 'ordered-list' if typ == 'ol' else 'bullet-list'
            li_html = li_content_span(text).replace('{key}', key)
            html_parts.append('<li>')
            html_parts.append(li_html)
            html_parts.append('</li>')

        # 关闭所有未闭合列表
        while stack:
            close_list()

        return ''.join(html_parts), i

    # -------------- 表格解析 --------------
    def _parse_table(self, start: int) -> Tuple[str, int]:
        """尝试从 start 解析 markdown 表格，解析成功返回 (html, 消费行数)，否则 ("", 0)。"""
        lines = self.lines
        i = start
        if i >= len(lines) or '|' not in lines[i]:
            return '', 0

        rows: List[List[str]] = []

        # 识别表头与分隔行（如 | --- | --- |）
        def split_row(s: str) -> List[str]:
            # 去掉首尾竖线后按 | 分割
            s2 = s.strip()
            if s2.startswith('|'):
                s2 = s2[1:]
            if s2.endswith('|'):
                s2 = s2[:-1]
            return [c.strip() for c in s2.split('|')]

        header = split_row(lines[i])
        if i + 1 < len(lines):
            sep = split_row(lines[i + 1])
        else:
            return '', 0

        # 分隔判断：每个单元格至少包含 ---
        def is_sep(cells: List[str]) -> bool:
            if not cells:
                return False
            for c in cells:
                if set(c.replace(':', '').replace('-', '')):
                    return False
                if c.count('-') < 3:
                    return False
            return True

        if not is_sep(sep):
            return '', 0

        # 收集数据行
        i += 2
        while i < len(lines) and '|' in lines[i] and lines[i].strip() != '':
            rows.append(split_row(lines[i]))
            i += 1

        # 生成 HTML（参考示例样式）
        td_wrapper_prefix = (
            '<section data-mpa-md-key="text" style="font-size: 15px;color: rgb(51, 51, 51);letter-spacing: 1px;" '
            'data-mpa-md-template="30005">'
        )
        td_wrapper_suffix = '</section>'

        html_parts = ['<table>', '  <tbody>']
        # 表头行（使用普通 span）
        html_parts.append('    <tr>')
        for cell in header:
            html_parts.append('      <td>')
            html_parts.append('        <section>')
            html_parts.append(f'          <span leaf="">{html_escape(cell)}</span>')
            html_parts.append('        </section>')
            html_parts.append('      </td>')
        html_parts.append('    </tr>')

        # 数据行
        for row in rows:
            html_parts.append('    <tr>')
            for cell in row:
                html_parts.append('      <td>')
                html_parts.append('        <section>')
                html_parts.append('          ' + td_wrapper_prefix)
                html_parts.append(f'            <span leaf="">{html_escape(cell)}</span>')
                html_parts.append('          ' + td_wrapper_suffix)
                html_parts.append('        </section>')
                html_parts.append('      </td>')
            html_parts.append('    </tr>')

        html_parts.append('  </tbody>')
        html_parts.append('</table>')

        return '\n'.join(html_parts), (i - start)


def render_wechat_html(md_text: str, templates_dir: Optional[str] = None) -> str:
    """对外接口：将 Markdown 文本渲染为微信公众号 HTML。

    参数：
    - md_text: Markdown 源文本
    - templates_dir: 模板目录路径；为 None 时默认使用项目根目录下的 `templates/`
    返回：拼装完成的 HTML 字符串
    """
    parser = Parser(md_text, tpl_dir=templates_dir)
    return parser.parse()


def convert(md_text: str) -> str:
    """兼容旧接口，等同于 render_wechat_html(md_text)。"""
    return render_wechat_html(md_text)


def main():
    parser = argparse.ArgumentParser(description='Markdown 转 微信公众号 HTML')
    parser.add_argument('input', help='输入 Markdown 文件路径')
    parser.add_argument('-o', '--output', help='输出 HTML 文件路径（默认同名 .html）')
    parser.add_argument('-t', '--templates', help='模板目录（默认使用项目 templates/）', default=None)
    args = parser.parse_args()

    in_path = os.path.abspath(args.input)
    if not os.path.exists(in_path):
        print(f'输入文件不存在：{in_path}', file=sys.stderr)
        sys.exit(1)

    out_path = args.output
    if not out_path:
        base, _ = os.path.splitext(in_path)
        out_path = base + '.html'
    out_path = os.path.abspath(out_path)

    md_text = read_file(in_path)
    html = render_wechat_html(md_text, templates_dir=args.templates)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'已生成：{out_path}')


if __name__ == '__main__':
    main()
