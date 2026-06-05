# 🖥️ AnyDocConverter — 任务队列 (Claude Code 执行)
# PM Agent 按顺序逐个调用 claude-task.sh 执行

## 任务 1: utils — 格式工具函数
修复 workers/tasks.py 中 `_format_to_extension()` 未在任务上下文被调用的缺失，
将格式映射抽取到 algo 层共享，确保 workers 和 API 统一使用同一映射表。
→ 产出: algo/utils.py + 更新引用

## 任务 2: 转换器 — PNG 支持
formats.py 中声明了 `markdown/txt/png/pdf-edit` 格式，但 algo 层只有 5 个转换器。
添加 png 转换器（类似 jpg 转换器但输出 png 格式）。
→ 产出: algo/converters/to_png_converter.py + 注册到 __init__ + pipeline

## 任务 3: 集成测试 — PDF 管线
编写 pytest 集成测试：
1. 用 PyMuPDF 生成一个简易测试 PDF（含文字+图片）
2. 调用 pipeline.convert() 分别测试 5 种格式
3. 验证输出文件存在且非空
→ 产出: tests/test_pipeline.py

## 任务 4: 参数校验 — 后端 schema 对齐
backend/schemas/task.py 中的 ConvertParams / OCRParams / LayoutParams / ImageParams / FontParams 与 algo/models/params.py 中的同名类字段不一致。
同步两者字段定义，同时保持各自格式的兼容性。
→ 产出: 同步后的 schema 定义

## 任务 5: 本地可运行 — make run
创建 Makefile 实现一键安装依赖 + 启动开发服务器（不需要 Docker）。
支持 make install / make dev-backend / make dev-frontend / make run
→ 产出: Makefile

## 任务 6: 文档补全 — README
更新 README.md，补充：
1. 项目架构说明
2. 快速开始（Docker + 本地两种方式）
3. API 文档索引
4. 开发团队架构（Agent 团队说明）
→ 产出: 更新后的 README.md
