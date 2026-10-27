# 变更日志 (Changelog)

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [1.0.0] — 2026-10-25

### 首次发布

#### 新增功能

**核心转换引擎**
- `algo/vision_to_code.py`：图像/PDF → 可编辑 HTML/CSS 代码转换模块
  - 双路径解析：数字 PDF（PyMuPDF 文本层提取）+ 图像/扫描件（OCR）
  - 精确提取：文本元素（坐标、字体名、字号、粗体、颜色）、图片元素（裁剪 + base64）
  - 标题检测：基于字号比例自动推断 H1-H3 标题层级
  - 绝对定位代码生成：`position: absolute` + 精确像素坐标还原版式
  - 语义化标签：标题使用 `<h1>`-`<h3>`，正文使用 `<div>`/`<p>`
  - 单文件输出：CSS 内联 + 图片 base64 内嵌

**保真度检查模块**
- `algo/fidelity.py`：渲染对比与迭代优化（参考 screenshot-to-code 的 generate→render→compare→refine 循环）
  - 元素级匹配：文本覆盖率（40%权重）、图片覆盖率（30%）、位置精度（30%）
  - 自动修复：检测缺失元素并重新生成
  - 迭代优化：最多 2 轮自动优化，目标保真度 ≥ 0.95

**动画代码生成模块**
- `algo/animation.py`：静态代码 → 带 CSS 动画的交互式代码（参考 Opus 5.5 社区动画实践）
  - CSS `@keyframes` 动画：标题缩放淡入、正文上滑淡入、图片缩放淡入
  - 阅读顺序入场：元素按 y 坐标排序，错开 0.08s 延迟依次入场
  - 弹性缓动：标题使用 `cubic-bezier(0.34, 1.56, 0.64, 1)` 弹性动画
  - 交互效果：鼠标悬停元素轻微放大 + 深色电影感背景
  - JS 控制：重播动画 / 暂停继续按钮
  - 多页延迟：页间 0.3s 延迟

**后端 API (FastAPI)**
- `POST /api/upload`：文件上传（PDF/PNG/JPG/BMP/TIFF/WEBP，最大 50MB）
- `POST /api/convert/{file_id}?animated=true|false`：代码转换（支持静态/动画模式）
- `GET /api/result/{task_id}`：获取转换结果代码
- `GET /api/preview/{task_id}`：浏览器中预览渲染结果
- `GET /api/health`：健康检查

**前端界面 (Jinja2 模板)**
- 拖拽上传区（支持点击和拖放）
- 动画代码开关（toggle switch）
- 转换进度显示
- 分屏布局：左侧代码编辑器 + 右侧 iframe 实时预览
- 保真度分数徽章（绿/黄/红色编码）
- 动画模式徽章（🎬 标识）
- 代码操作：复制、下载 HTML、新窗口预览
- 防抖自动预览更新（500ms）

**测试**
- `tests/test_vision_to_code.py`：25 个测试（解析器、代码生成器、端到端、辅助函数）
- `tests/test_animation.py`：20 个测试（动画结构、延迟、静态vs动画对比、端到端）
- HTTP 端到端测试：14 个测试（上传、转换、结果、预览、错误处理）

#### 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 运行环境 | Conda (anydoc) | Python 3.12 |
| 后端 | FastAPI | 0.115.6 |
| 模板 | Jinja2 | 3.1.6 |
| PDF 解析 | PyMuPDF | ≥1.23.0 |
| 图像处理 | Pillow | ≥10.0.0 |
| 数据验证 | Pydantic | 2.10.3 |
| 测试 | pytest | ≥9.0.0 |

#### 项目结构

```
vision2code/
├── algo/
│   ├── __init__.py            # 模块导出
│   ├── vision_to_code.py      # 核心转换：图像/PDF → HTML/CSS (503行)
│   ├── animation.py           # 动画代码生成 (486行)
│   └── fidelity.py            # 保真度检查 + 迭代优化 (330行)
├── backend/
│   └── app/
│       ├── main.py            # FastAPI 入口
│       ├── api/routes.py      # REST 端点
│       ├── core/config.py     # 配置
│       ├── services/converter.py  # 转换服务
│       └── templates/index.html   # 前端 UI (601行)
├── tests/
│   ├── test_vision_to_code.py # 25 个测试
│   └── test_animation.py      # 20 个测试
├── VERSION                    # 1.0.0
├── CHANGELOG.md               # 本文件
└── README.md                  # 项目文档
```

#### 测试结果

- 单元测试：45/45 通过
- HTTP 端到端测试：14/14 通过
- 总计：59 个测试全部通过
