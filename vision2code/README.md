# Vision2Code v1.0.0

> 将 PDF 或图片转换为**可编辑的 HTML/CSS 代码**，使代码的渲染结果与原始文档高度一致。

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](./VERSION)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-green)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-59%20passed-brightgreen)](./tests)

用户上传 PDF 或图片后，系统自动解析版面、提取文本与图片，生成单文件 HTML 代码。支持**静态代码**和**动画代码**两种模式：

- **静态模式**：精确还原原始版式，绝对定位 + 内联 CSS
- **动画模式**（参考 Opus 5.5 社区实践）：元素按阅读顺序依次入场，带 CSS keyframes 动画 + 播放控制

用户可在内置代码编辑器中直接编辑代码并实时预览渲染效果。

---

## 目录

- [快速开始](#快速开始)
- [功能特性](#功能特性)
- [架构设计](#架构设计)
- [API 参考](#api-参考)
- [动画代码生成](#动画代码生成)
- [保真度检查](#保真度检查)
- [测试](#测试)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [设计理念](#设计理念)
- [版本历史](#版本历史)

---

## 快速开始

### 1. 创建 Conda 环境

```bash
conda create -n anydoc python=3.12 -y
conda activate anydoc

pip install fastapi==0.115.6 "uvicorn[standard]==0.34.0" python-multipart==0.0.18 \
  pydantic==2.10.3 pydantic-settings==2.7.0 PyMuPDF>=1.23.0 Pillow>=10.0.0 \
  python-docx>=1.0.0 python-pptx>=0.6.21 openpyxl>=3.1.0 jinja2>=3.1.0 pytest
```

### 2. 启动服务

```bash
cd vision2code/backend
PYTHONPATH="$(pwd):$(pwd)/../../algo" python -m app.main
```

服务启动后访问 http://localhost:8000

### 3. 使用

1. 点击或拖拽上传 PDF/图片文件
2. （可选）打开"生成动画代码"开关
3. 点击"转换为代码"按钮
4. 在左侧编辑器查看/编辑代码，右侧实时预览渲染效果
5. 复制或下载生成的 HTML 代码

---

## 功能特性

### 核心转换

| 功能 | 说明 |
|------|------|
| PDF 解析 | PyMuPDF 提取文本层（精确坐标、字体、颜色）+ 图片区域 |
| 图像解析 | PyMuPDF OCR 提取文本 + 整页图像保留为背景 |
| 标题检测 | 基于字号比例自动推断 H1-H3 标题层级 |
| 绝对定位 | `position: absolute` + 精确像素坐标还原版式 |
| 单文件输出 | CSS 内联 + 图片 base64 内嵌，生成独立 HTML |

### 动画代码生成

| 功能 | 说明 |
|------|------|
| 入场动画 | 标题缩放淡入、正文上滑淡入、图片缩放淡入 |
| 阅读顺序 | 元素按 y 坐标排序，错开 0.08s 依次入场 |
| 弹性缓动 | 标题使用 `cubic-bezier(0.34, 1.56, 0.64, 1)` 弹性效果 |
| 交互效果 | 鼠标悬停元素轻微放大 + 深色电影感背景 |
| 播放控制 | 重播动画 / 暂停继续按钮（JS） |
| 多页延迟 | 页间 0.3s 延迟，叙事节奏 |

### 保真度检查

| 维度 | 权重 | 说明 |
|------|------|------|
| 文本覆盖率 | 40% | 源文档文本在代码中出现的比例 |
| 图片覆盖率 | 30% | 源文档图片在代码中出现的比例 |
| 位置精度 | 30% | 坐标匹配精度（±2px 容差） |

---

## 架构设计

```
                    ┌─────────────────────────────────┐
                    │        用户上传 PDF/图片         │
                    └───────────────┬─────────────────┘
                                    ▼
                    ┌─────────────────────────────────┐
                    │   parse_to_layout()             │
                    │   PyMuPDF 解析 → DocumentLayout │
                    │   • TextElement (位置+字体+颜色) │
                    │   • ImageElement (裁剪+base64)  │
                    └───────────────┬─────────────────┘
                                    ▼
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌─────────────────┐
          │  generate_code()│             │generate_animated│
          │  静态 HTML/CSS  │             │  _code()        │
          │  绝对定位还原   │             │  CSS动画+JS控制 │
          └────────┬────────┘             └────────┬────────┘
                   └───────────────┬───────────────┘
                                   ▼
                   ┌─────────────────────────────────┐
                   │   refine_code()                 │
                   │   保真度检查 + 迭代优化          │
                   │   • 元素匹配度评分               │
                   │   • 自动修复缺失元素             │
                   └───────────────┬─────────────────┘
                                   ▼
                   ┌─────────────────────────────────┐
                   │   前端展示                       │
                   │   • 代码编辑器 (可编辑)          │
                   │   • 实时预览 (iframe)            │
                   │   • 保真度分数展示               │
                   └─────────────────────────────────┘
```

### 三阶段解耦架构

参考 ScreenCoder 的模块化管线和 screenshot-to-code 的 render-compare-refine 循环：

1. **解析阶段** (`parse_to_layout`)：从 PDF/图像提取结构化 `DocumentLayout`
2. **生成阶段** (`generate_code` / `generate_animated_code`)：将布局转换为 HTML/CSS 代码
3. **优化阶段** (`refine_code`)：保真度检查 + 自动修复

阶段之间通过 `DocumentLayout` 中间表示解耦，解析不关心输出格式，生成不关心源格式。

---

## API 参考

所有端点前缀为根路径（无 `/api/v1` 前缀）。

| Method | Path | Query Params | 说明 |
|--------|------|-------------|------|
| GET | `/` | — | 首页（上传界面） |
| POST | `/api/upload` | — | 上传文件 |
| POST | `/api/convert/{file_id}` | `animated` (bool) | 转换为代码 |
| GET | `/api/result/{task_id}` | — | 获取代码结果 |
| GET | `/api/preview/{task_id}` | — | 浏览器预览渲染 |
| GET | `/api/health` | — | 健康检查 |

### 上传示例

```bash
curl -F "file=@document.pdf" http://localhost:8000/api/upload
# → {"file_id": "uuid", "filename": "document.pdf", "size": 12345}
```

### 转换示例（静态）

```bash
curl -X POST "http://localhost:8000/api/convert/{file_id}?animated=false"
# → {"task_id": "uuid", "status": "completed", "fidelity_score": 1.0, ...}
```

### 转换示例（动画）

```bash
curl -X POST "http://localhost:8000/api/convert/{file_id}?animated=true"
# → {"task_id": "uuid", "status": "completed", "animated": true, ...}
```

### 获取结果

```bash
curl http://localhost:8000/api/result/{task_id}
# → {"code": "<!DOCTYPE html>...", "source_type": "pdf", ...}
```

---

## 动画代码生成

动画模式（参考 Opus 5.5 社区的"图像→动画代码"实践）在静态代码基础上添加：

### CSS 关键帧动画

```css
/* 标题：缩放 + 淡入（弹性缓动） */
@keyframes anim-title {
  from { opacity: 0; transform: scale(0.8) translateY(20px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

/* 正文：淡入 + 上滑 */
@keyframes anim-text {
  from { opacity: 0; transform: translateY(15px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 图片：淡入 + 缩放 */
@keyframes anim-image {
  from { opacity: 0; transform: scale(0.92); }
  to   { opacity: 1; transform: scale(1); }
}
```

### 阅读顺序入场

元素按 y 坐标排序，每个元素比前一个延迟 0.08s 入场：

```
标题   → delay: 0.15s  (最先)
正文1  → delay: 0.23s
正文2  → delay: 0.31s
图片   → delay: 0.39s
```

### JavaScript 控制

```javascript
replayAnimation()  // 重播所有动画
togglePause()      // 暂停/继续
```

---

## 保真度检查

系统自动计算保真度分数（0-100%），在结果页以彩色徽章展示：

- 🟢 **≥80%**：高质量还原
- 🟡 **50-80%**：部分元素缺失或位置偏差
- 🔴 **<50%**：需要检查

检查流程（参考 screenshot-to-code 的 render-compare-refine）：

1. 对比生成代码与源文档的每个元素
2. 计算文本覆盖率、图片覆盖率、位置精度
3. 如有缺失元素，自动重新生成代码
4. 最多迭代 2 轮，目标保真度 ≥ 95%

---

## 测试

### 运行测试

```bash
cd vision2code
conda activate anydoc
python -m pytest tests/ -v
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| `test_vision_to_code.py` | 25 | 解析器（PDF/图像）、代码生成器、端到端、辅助函数 |
| `test_animation.py` | 20 | 动画结构、延迟、静态vs动画对比、端到端 |
| HTTP 端到端 | 14 | 上传、转换（静态+动画）、结果、预览、错误处理 |
| **总计** | **59** | **全部通过** |

---

## 项目结构

```
vision2code/
├── algo/                          # 核心算法模块
│   ├── __init__.py                # 模块导出
│   ├── vision_to_code.py          # 图像/PDF → HTML/CSS 转换 (503行)
│   ├── animation.py               # 动画代码生成 (486行)
│   └── fidelity.py                # 保真度检查 + 迭代优化 (330行)
├── backend/                       # FastAPI 后端
│   └── app/
│       ├── main.py                # 应用入口
│       ├── api/routes.py          # REST API 端点
│       ├── core/config.py         # 配置管理
│       ├── services/converter.py  # 转换服务
│       └── templates/
│           └── index.html         # 前端 UI (Jinja2 模板, 601行)
├── tests/                         # 测试
│   ├── test_vision_to_code.py     # 25 个测试
│   └── test_animation.py          # 20 个测试
├── VERSION                        # 版本号: 1.0.0
├── CHANGELOG.md                   # 变更日志
└── README.md                      # 本文档
```

---

## 技术栈

| 层 | 技术 | 版本 | 用途 |
|---|---|---|---|
| 运行环境 | Conda (`anydoc`) | Python 3.12 | 隔离环境 |
| 后端 | FastAPI | 0.115.6 | REST API |
| 模板 | Jinja2 | 3.1.6 | 前端页面渲染 |
| PDF 解析 | PyMuPDF | ≥1.23.0 | 文本/图片/坐标提取 |
| 图像处理 | Pillow | ≥10.0.0 | 图像读取与合成 |
| 数据验证 | Pydantic | 2.10.3 | 配置与模型 |
| ASGI 服务器 | Uvicorn | 0.34.0 | 开发服务器 |
| 测试 | pytest | ≥9.0.0 | 单元测试 |

---

## 设计理念

### 研究基础

本项目设计参考了对当前 SOTA 工具的调研：

| 参考项目 | 借鉴点 |
|---------|--------|
| **screenshot-to-code** (80k★) | generate→render→compare→refine 循环 |
| **ScreenCoder** (3k★) | 模块化解耦管线 + 中间表示 |
| **Design2Code** (论文) | 文本增强提示 + 视觉保真度评估指标 |
| **Hyperframes** (HeyGen) | HTML→渲染 的确定性输出理念 |
| **Opus 5.5 社区实践** | 图像→动画代码 的 CSS keyframes 方法 |

### 核心决策

1. **解析 → IR → 生成** 三阶段解耦：解析不关心输出，生成不关心输入
2. **绝对定位保真**：`position: absolute` + 精确像素坐标，确保渲染与源一致
3. **纯 CSS 动画**：无 JS 框架依赖，用户可直接编辑 keyframes
4. **单文件输出**：CSS 内联 + base64 图片，便于分享和编辑
5. **确定性保真度**：用坐标/文本匹配代替 VLM 视觉对比，无需 GPU

---

## 版本历史

详见 [CHANGELOG.md](./CHANGELOG.md)。

- **v1.0.0** (2026-10-25)：首次发布，包含核心转换、动画生成、保真度检查、完整前后端
