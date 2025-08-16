# -*- coding: utf-8 -*-
"""
依赖加载助手：在导入第三方包失败时，自动通过 pip 安装并重试导入。
注：此做法适用于本地开发/测试环境，生产环境仍建议使用 requirements.txt 进行依赖管理。
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Any


def install_and_import(module: str, package: str | None = None) -> Any:
    """
    尝试导入指定模块；如失败则安装对应 pip 包后重试导入。

    参数：
    - module: Python 模块路径（例如 "streamlit"、"googleapiclient.discovery"）
    - package: pip 包名（例如 "streamlit"、"google-api-python-client"）。
               若不提供，则默认与 module 顶级名相同。
    返回：
    - 已导入的模块对象
    """
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError:
        pkg = package or module.split(".")[0]
        # 执行安装
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        # 重新导入
        return importlib.import_module(module)
