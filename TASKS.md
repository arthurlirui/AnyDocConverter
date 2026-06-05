# 🖥️ AnyDocConverter — 任务队列 (Claude Code 执行)
# PM Agent 按顺序逐个调用 claude-task 执行

## ✅ 已完成

### 任务 1: utils — 格式工具函数 ⭐ 完成
- 创建 `algo/utils.py` 统一管理格式/扩展名/MIME 映射
- 更新 `workers/tasks.py` 引用共享模块
- 更新 `pipeline.py` 委派 get_supported_formats()

### 任务 2: 转换器 — PNG 支持 ⭐ 完成
- 创建 `algo/converters/to_png_converter.py`
- 注册到 `__init__.py` + `pipeline._FORMAT_MAP`
- 更新 `utils.CONVERTER_FORMATS`

### 任务 3: 集成测试 ⭐ 完成
- `tests/test_pipeline.py` — 6 个测试用例
  - 测试 PDF 生成
  - 6 种格式的参数化转换测试
  - 无效格式异常测试
  - 文件不存在异常测试

## ⬜ 待完成

### 任务 4: 参数校验 — 后端 schema 对齐
backend/schemas/task.py 中的 ConvertParams / OCRParams / LayoutParams / ImageParams / FontParams
与 algo/models/params.py 中的同名类字段不一致。同步两者字段定义。

### 任务 5: 本地可运行 — make run
创建 Makefile 实现一键安装依赖 + 启动开发服务器（不需要 Docker）。
支持 make install / make dev-backend / make dev-frontend / make run

### 任务 6: 文档补全 — README
更新 README.md，补充项目架构 + 快速开始 + API 文档 + Agent 团队说明。
