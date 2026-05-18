# AGENT 工作指南（student）

本文件用于指导在 `student_optimization` 项目中执行开发、重构、调试与数据处理任务的智能体行为。

## 1. 项目目标

基于 Langgraph 的学生画像生成与模拟后端系统

## 2. Python 编码规范

遵循 Google Python 风格并结合本项目约束：

1. 格式
   - 4 空格缩进，禁用 Tab。
   - 行宽不超过 120。
   - 顶层定义间 2 空行；类方法间 1 空行。

2. 导入
   - 顺序：标准库 → 第三方 → 本地模块，各组之间空一行。
   - 禁止 `from x import *`，禁止相对导入。
   - 禁止在函数/方法内部 import（除非有明确的延迟加载需求）。

3. 命名
   - 模块/函数/变量：`snake_case`
   - 类：`PascalCase`
   - 常量：`UPPER_SNAKE_CASE`
   - 私有模块级符号：`_leading_underscore`

4. 类型与文档
   - 所有函数必须有参数和返回值类型注解。
   - 使用内置泛型语法（如 `list[str]`、`str | None`）。
   - 公共模块/函数/类必须写中文文档字符串（Google 风格）。

5. 异常与函数设计
   - 捕获具体异常，避免裸 `except`。
   - 禁止可变默认参数。

6. I/O 与路径
   - 使用 `pathlib.Path` 处理文件路径。
   - 文件读写显式 `encoding="utf-8"`。
