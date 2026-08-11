# NASA 卫星壁纸 (NASA Satellite Wallpaper)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

双数据源 Windows 桌面壁纸软件，支持 **NASA 每日天文图片 (APOD)** 和 **Himawari-8 实时地球卫星图**。

## 功能特性

### 🔭 NASA APOD 模式
- 自动获取 NASA 天文每日图片 (Astronomy Picture of the Day)
- **10 个智能分类**：星云、星系、行星、地球、太阳、月球、极光、彗星、恒星、空间站
- 基于关键词匹配自动分类，切换类别即可浏览对应图片
- 每天在设定时间自动检查更新，匹配选中分类时自动更换壁纸

### 🌍 实时地球模式
- 数据来源：日本气象卫星 **Himawari-8**（数据产品 D531106）
- 每 10 分钟拍摄一张地球全盘图，约 20-30 分钟延迟
- **2200x2200 高清分辨率**（4x4=16 瓦片并行下载拼接）
- 支持自动刷新：每 10 分钟获取最新图并同步更新壁纸

### 🖼 壁纸设置
- 支持多种壁纸样式：居中、平铺、拉伸、适应、填充
- 壁纸右上角自动标注来源和拍摄时间（半透圆角角标）
- 通过 Windows 注册表控制壁纸样式

### ⚡ 后台运行
- 点击关闭按钮弹出选择对话框："最小化到任务栏" 或 "退出程序"
- 最小化后调度器在后台持续运行，自动按周期更新壁纸
- 从任务栏点击图标即可恢复窗口

## 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.10+
- **依赖**: `requests>=2.31.0`, `Pillow>=10.0.0`

## 安装 & 运行

### 方式一：源码运行

```bash
# 克隆仓库
git clone https://github.com/yourusername/nasa-wallpaper.git
cd nasa-wallpaper

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

### 方式二：打包为 EXE（无需 Python 环境）

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "NASA_Wallpaper" --collect-all PIL main.py
# EXE 生成在 dist/NASA_Wallpaper.exe
```

### 方式三：直接下载

从 [Releases](https://github.com/yourusername/nasa-wallpaper/releases) 页面下载 `NASA_Wallpaper_v*.zip`，解压双击运行。

> 首次启动会自动获取近 10 天的 NASA APOD 图片到本地缓存。

## 项目结构

```
nasa_wallpaper/
├── main.py           # 主程序 - tkinter GUI 界面
├── nasa_api.py       # NASA APOD API 客户端
├── earth_api.py      # Himawari-8 卫星数据获取与拼接
├── categorizer.py    # 图片关键词分类器
├── wallpaper.py      # Windows 壁纸设置 + 水印
├── scheduler.py      # 后台调度器 (APOD 每天 / Earth 每10分钟)
├── config.py         # 配置管理与数据持久化
├── requirements.txt  # Python 依赖
└── LICENSE           # MIT 协议
```

### 数据存储

所有运行数据存储在 `%USERPROFILE%\.nasa_wallpaper\` 目录：

| 路径 | 说明 |
|------|------|
| `config.json` | 用户配置 (API Key、分类、样式等) |
| `metadata.json` | 获取过的图片元数据 |
| `cache/` | 图片缓存 |
| `wallpaper/` | 当前壁纸副本 |
| `watermarked/` | 带水印的壁纸图片 |

## NASA API Key

默认使用 `DEMO_KEY`（每小时限流 30 次，每天 100 次）。

建议访问 [https://api.nasa.gov/](https://api.nasa.gov/) 申请免费 API Key，在软件「设置」中填入，可获得每小时 1000 次额度。

## 技术栈

- **GUI**: tkinter (深色太空主题)
- **图像处理**: Pillow (PIL) — JPEG 水印、瓦片拼接
- **网络请求**: requests — NASA API + Himawari-8 NICT
- **打包**: PyInstaller (--onefile --windowed)
- **多线程**: threading.Thread + ThreadPoolExecutor (并行下载瓦片)
- **壁纸设置**: ctypes → SystemParametersInfoW + winreg 注册表

## 数据来源

- [NASA APOD API](https://api.nasa.gov/) — Astronomy Picture of the Day
- [NICT Himawari-8](https://himawari8.nict.go.jp/) — 日本气象卫星实时地球影像

## License

MIT License — 详见 [LICENSE](LICENSE) 文件。
