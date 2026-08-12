# Live Earth Wallpaper — 界面重设计方案

## 设计理念：Cosmic Observatory（宇宙观测台）

将原有的 tkinter 桌面界面重构为现代化 Web 交互界面，设计语言定位为「天文台控制室」——科学严谨、令人敬畏、以影像为核心。

## 设计系统

### 色彩体系
| 用途 | 色值 | 说明 |
|------|------|------|
| 背景层 | #080810 → #111122 | 深邃太空渐变，五层深度 |
| 表面层 | #12121f / #181830 | 卡片和面板层级 |
| APOD 强调色 | #c9a96e | 暖色星光金 — 呼应恒星 |
| 卫星强调色 | #4dab9a | 大地青蓝 — 呼应海洋 |
| SDO 强调色 | #e07040 | 太阳橙 — 呼应日冕 |
| 成功/警告/错误 | #5cb878 / #d4a843 / #d45252 | 语义色，低饱和度 |

### 排版
- 主字体：Microsoft YaHei / PingFang SC（中文优先）
- 等宽字体：Cascadia Code（技术数据）
- 字号阶梯：11px → 13px → 15px → 17px → 20px → 24px → 32px
- 无纯黑纯白，文字对比度 4.5:1+

### 间距
- 4px 基准网格（4/8/12/16/20/24/32/40/48）

## 架构改进

| 维度 | 旧版 (tkinter) | 新版 (HTML/CSS) |
|------|---------------|-----------------|
| 数据源切换 | 顶部独立按钮 | 分段式标签栏，带色彩编码 |
| 分类列表 | Treeview 表格 | 自定义列表，活跃态带左侧指示条 |
| 图片预览 | Label 组件 | 全幅预览区 + 叠加信息栏 |
| 卫星/SDO设置 | 传统 RadioButton | 自定义单选组 + 信息卡片 |
| 设置面板 | tkinter Toplevel | 毛玻璃模态弹窗 |
| 使用说明 | 新窗口 Text | 模态面板内嵌富文本 |
| 动画 | 无 | CSS transitions + 呼吸动效 |
| 响应式 | 固定 1300×850 | 自适应（860px 断点） |

## 交互亮点

1. **三面板无缝切换**：顶部分段控件切换 APOD/卫星/SDO，侧边栏同步变化
2. **分类导航**：左侧列表选中态带金色指示条和计数徽章
3. **键盘快捷键**：← → 浏览、1/2/3 切换数据源、Esc 关闭弹窗
4. **自动刷新状态**：卫星/SDO 模式显示倒计时和开关状态
5. **模态弹窗**：设置和帮助均以模态呈现，支持背景模糊和动画入场

## 可接入性

- 焦点可见指示（2px outline-offset）
- prefers-reduced-motion 尊重系统动效偏好
- 语义化 HTML 结构
- 鼠标和键盘双重操作路径

## 文件结构

```
ui-redesign/
├── index.html        # 完整单页应用（CSS + JS 内嵌，API 已对接）
├── server.py         # Flask REST API 后端
├── webview_app.py    # PyWebView 桌面应用入口
└── overview.md       # 本文件
```

## 集成架构（已完成）

```
┌──────────────────────────────────────────────┐
│  webview_app.py (桌面窗口)                    │
│  ↓ 加载                                      │
│  index.html (HTML/CSS/JS 前端)               │
│  ↓ fetch() API 调用                          │
│  server.py (Flask REST API)                  │
│  ↓ 调用                                      │
│  现有模块: nasa_api.py / providers /          │
│            wallpaper.py / scheduler.py /      │
│            config.py / categorizer.py         │
└──────────────────────────────────────────────┘
```

### 17 个 API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 静态页面 |
| `/api/status` | GET | 系统状态（调度器/任务） |
| `/api/config` | GET/POST | 配置读写 |
| `/api/apod/images` | GET | 图片列表（支持分类筛选） |
| `/api/apod/categories` | GET | 分类及计数 |
| `/api/apod/fetch` | POST | 拉取近 10 天 NASA 图片 |
| `/api/apod/download` | POST | 下载单张图片至缓存 |
| `/api/satellite/fetch` | POST | 获取卫星影像 |
| `/api/sdo/fetch` | POST | 获取 SDO 太阳图像 |
| `/api/wallpaper/set` | POST | 设置桌面壁纸 |
| `/api/wallpaper/watermark-and-set` | POST | 加水印+设壁纸 |
| `/api/scheduler/start\|stop\|status` | POST/GET | 调度器控制 |

## 启动方式

```bash
# 方式一：直接运行后端 + 浏览器
cd ui-redesign
python server.py
# 浏览器打开 http://127.0.0.1:51234

# 方式二：原生桌面窗口（需要 GUI 环境）
python webview_app.py
```
