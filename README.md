# RealEarth 真实地球壁纸

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**RealEarth 4.0.0** — 多数据源 Windows 桌面壁纸软件，支持 **NASA 天文图片 (APOD)**、**地球静止卫星实时影像**、**中国风云四号 FY-4B 真彩色影像** 和 **NASA SDO 太阳观测** 四大数据源。

> 4.0.0 重新设计为 **现代深色侧边栏界面**，并回归 **Tkinter 单进程架构**（不再依赖 Web UI / Edge WebView2）。
> 单进程模型让应用直接掌控主循环、后台调度器与关闭流程，彻底解决了旧版 Web UI「无法关闭」「自动刷新失效」的问题。

## 功能特性

### 🔭 NASA APOD 模式
- 自动获取 NASA 天文每日图片 (Astronomy Picture of the Day)
- **多个智能分类**：星云、星系、行星、地球、太阳、月球、极光、彗星、恒星、空间站
- 基于关键词匹配自动分类，切换类别即可浏览对应图片

### 🛰 卫星影像模式
- 支持 **6 颗地球静止卫星**：
  - GOES-19 / GOES-18 / GOES-16（美洲，NOAA 数据源）
  - Himawari-8（亚太）、GK2A（韩国）
  - 风云四号 FY-4B（中国，NSMC 数据源，真彩色全圆盘）
- 颜色模式：自然色 / 地球色（含夜景）
- 分辨率可选：标准 / 高清 / 超清
- 每 10 分钟自动刷新

### 🇨🇳 风云四号 FY-4B 模式（4.0.0 新增）
- 数据来源：**国家卫星气象中心 (NSMC)**
- **真彩色全圆盘影像**，固定真彩色（色彩模式不适用）
- 分辨率可选：标准 1080 / 高清 2200 / 超清 4000
- 每 15 分钟自动刷新（与 NSMC 更新频率一致）

### ☀ 太阳观测模式
- 数据来源：**NASA SDO** (Solar Dynamics Observatory)
- **11 个波段**：304 Å、171 Å、193 Å、211 Å、335 Å、94 Å、131 Å、1600 Å、1700 Å、4500 Å、连续光球等
- 约每 15-60 分钟更新一张

### 🖼 壁纸设置
- 支持多种壁纸样式：居中、平铺、拉伸、适应、填充
- 壁纸自动标注来源和拍摄时间（风云四号标注北京时间 UTC+8）
- Windows 注册表控制壁纸样式

### ⚡ 后台运行
- 点击关闭按钮弹出选择对话框："最小化到任务栏" 或 "退出程序"
- 最小化后调度器在后台持续运行，自动更新壁纸
- **干净退出**：单进程架构，退出时统一停止调度器与主窗口，无残留子进程

## 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.10+
- **依赖**: `requests`, `Pillow (PIL)`, `pystray`

## 安装 & 运行

### 方式一：源码运行

```bash
git clone https://github.com/suika3733/realearth.git
cd realearth

# 安装依赖
pip install -r requirements.txt

# 运行
python launcher.py
```

### 方式二：打包为 EXE

```bash
pip install pyinstaller
pyinstaller RealEarth.spec
```

### 方式三：直接下载

从 [Releases](https://github.com/suika3733/realearth/releases) 页面下载压缩包，解压双击运行。

> 首次启动会自动获取近 10 天的 NASA APOD 图片到本地缓存。

## 项目结构

```
├── launcher.py          # 入口（单进程 Tkinter 启动 + 单实例锁）
├── main.py              # 主程序 - Tkinter GUI（侧边栏 + 4 面板）
├── providers/           # 数据源提供商
│   ├── geostationary.py # 地球静止卫星 (RAMMB-Slider / NOAA GOES)
│   ├── sdo.py           # NASA SDO 太阳图像（11 波段）
│   ├── fy4.py           # 风云四号 FY-4B 真彩色（NSMC）
│   └── noaa_goes.py     # NOAA GOES 影像
├── nasa_api.py          # NASA APOD API
├── categorizer.py       # 图片关键词分类器
├── wallpaper.py         # Windows 壁纸设置 + 水印
├── scheduler.py         # 后台调度器（短轮询，切换数据源即时生效）
├── config.py            # 配置管理
├── autostart.py         # 开机自启动
└── RealEarth.spec       # PyInstaller 打包配置
```

### 数据存储

所有运行数据存储在 `%USERPROFILE%\.nasa_wallpaper\` 目录：

| 路径 | 说明 |
|------|------|
| `config.json` | 用户配置 |
| `metadata.json` | NASA APOD 元数据 |
| `cache/` | 图片缓存 |
| `cache/fy4/` | 风云四号影像缓存 |
| `cache/satellite/` | 卫星影像缓存 |
| `cache/sdo/` | SDO 太阳图像缓存 |
| `wallpaper/` | 当前壁纸副本 |
| `watermarked/` | 带水印壁纸 |

## 数据来源

| 数据 | 来源 |
|------|------|
| 天文图片 | [NASA APOD API](https://api.nasa.gov/) |
| 卫星影像 | [CIRA RAMMB-Slider](https://rammb-slider.cira.colostate.edu) / [NOAA GOES](https://www.star.nesdis.noaa.gov/) |
| 风云四号 | [国家卫星气象中心 NSMC](https://img.nsmc.org.cn/) |
| 太阳图像 | [NASA SDO](https://sdo.gsfc.nasa.gov) |

## 致谢

本项目卫星数据源架构基于 [lennart-rth/Live-Earth-Wallpapers](https://github.com/lennart-rth/Live-Earth-Wallpapers) (GPL v3)。

## License

MIT License — 详见 [LICENSE](LICENSE) 文件。
