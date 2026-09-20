"""AegisCode 工具包——按域拆分的工具执行器。

原 AegisCode tools.py 1770 行单文件 → 按工具域拆分:
- file.py:     文件操作（读/写/列/删/移动）
- command.py:  命令执行（沙箱约束）
- search.py:   代码搜索（grep/ripgrep/正则）
- __init__.py: 统一注册接口
"""
