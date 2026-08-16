"""Live Earth Wallpaper - 多数据源卫星壁纸软件"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageTk
import pystray

from config import (
    load_config, save_config, load_metadata, save_metadata,
    IMAGE_CACHE_DIR, DEFAULT_API_KEY, CATEGORIES, ALL_CATEGORY,
    WALLPAPER_STYLES,
)
from nasa_api import fetch_apod_range, download_image, ApodImage
from categorizer import categorize_image, get_category_name, get_all_category_keys
from wallpaper import set_wallpaper, watermark_image
from scheduler import start_scheduler, stop_scheduler, is_scheduler_running, check_and_update
from providers import (
    GEOSTATIONARY_SATELLITES, SDO_BANDS,
    fetch_satellite_image, fetch_sdo_image,
    fetch_fy4_image, get_fy4_capture_time,
)
from autostart import is_autostart_enabled, set_autostart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ========== 颜色主题 (RealEarth UI Design System v5.0 "Cosmic Observatory") ==========
# 深空藏青色系，非纯黑，中性色带冷蓝色调微染
# 基础表面
BG_MAIN = "#080B14"            # --bg-app 应用最底层背景
BG_SURFACE = "#0D1220"         # --bg-surface 面板/控制区
BG_CARD = "#131A2B"            # --bg-card 卡片/预览容器
BG_CARD_HOVER = "#1A2238"      # --bg-card-hover
BG_ELEVATED = "#1E2740"        # --bg-elevated 浮层
BG_INPUT = "#0F1626"           # --bg-input 输入框
BG_SIDEBAR = "#0A0E1A"         # --bg-sidebar 侧边栏

# 文字色阶
FG_TEXT = "#E8ECF4"            # --text-primary
FG_SECONDARY = "#A8B0C8"       # --text-secondary
FG_DIM = "#6B7390"             # --text-tertiary
FG_DISABLED = "#3D4459"        # --text-disabled

# 边框色阶
BORDER = "#2A2A40"             # 保留兼容引用（对应 border-strong）
BORDER_SUBTLE = "#1A2238"      # 极淡分隔线
BORDER_DEFAULT = "#2A3A55"     # 默认边框 rgba(255,255,255,0.10) 近似

# 主操作色 (CTA)
ACCENT = "#E94560"             # --cta 「设为壁纸」主按钮
ACCENT_HOVER = "#FF6B81"       # --cta-hover

# 数据源主题色（色彩编码导航）
APOD_ACCENT = "#7C5CFC"        # 宇宙紫 — 天文图片
SAT_ACCENT = "#00B4D8"         # 海洋青 — 卫星影像
FY4_ACCENT = "#E8453C"         # 烬红 — 风云四号
SDO_ACCENT = "#FF8C00"         # 太阳橙 — 太阳观测
EARTH_ACCENT = "#00B4D8"       # 兼容旧引用 = SAT_ACCENT

# 次级操作/导航非激活底色
ACCENT2 = "#1E2740"            # 对应 --bg-elevated（替代旧深蓝 #0f3460）
NAV_ACTIVE = "#2563eb"         # 信息蓝（保留变量，导航已改用数据源色）

# 语义色
GREEN = "#4ECCA3"              # --success
YELLOW = "#F9D423"             # --warning
ERROR = "#EF4444"              # --error
BLUE = "#3B82F6"               # --info
BLUE_HOVER = "#4AA3F7"

# 侧边栏主题
SIDEBAR_BG = BG_SIDEBAR
SIDEBAR_HOVER = "#141A2E"      # --bg-sidebar-hover
NAV_ACTIVE_HOVER = "#3b82f6"

# 边框（对齐 HTML 原型 border 体系）
BORDER_SOFT = "rgba(255,255,255,0.08) 不可用"  # 占位（Tkinter 不支持 rgba，用近似色）
BORDER_SUBTLE_2 = "#1E2636"    # rgba(255,255,255,0.06) 近似 —— 预览容器极淡边框
BORDER_HOVER = "#3D4459"       # --border-strong

# 数据源亮色（原型 --apod-light / --sat-light 等，用于图标与激活文字）
APOD_LIGHT = "#A78BFA"         # 紫亮
SAT_LIGHT = "#33C9E8"          # 青亮
FY4_LIGHT = "#FF6B60"          # 红亮
SDO_LIGHT = "#FFAA33"          # 橙亮

# 字体系统（设计规范 §3：Windows 系统字体栈）
FONT_FAMILY = ("Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI", "Microsoft YaHei", "PingFang SC", "Arial")
FONT_MONO = ("Cascadia Code", "JetBrains Mono", "Consolas", "Consolas")

# 字号比例（1.2 模数，5 级）——规范 §3.2
FONT_TITLE = (FONT_FAMILY[0], 14, "bold")     # Panel Title
FONT_BODY = (FONT_FAMILY[0], 13)              # Body
FONT_SMALL = (FONT_FAMILY[0], 12, "normal")   # 按钮/控件标签（规范 Small 12px）
FONT_CAPTION = (FONT_FAMILY[0], 11, "normal") # Caption 辅助信息
FONT_MICRO = (FONT_MONO[0], 10, "bold")       # Micro（等宽，时间戳/分辨率标签）
FONT_BIG = (FONT_FAMILY[0], 16, "bold")
FONT_BRAND = (FONT_FAMILY[0], 16, "bold")     # 侧边栏品牌名


# ========== 圆角按钮 ==========
class ModernButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=100, height=32,
                 bg=ACCENT, fg="white", hover_bg=ACCENT_HOVER, font=FONT_BODY, **kw):
        super().__init__(parent, width=width, height=height, bg=BG_CARD,
                         highlightthickness=0, cursor="hand2", **kw)
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._font = font
        self._radius = 6
        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", self._on_click)

    def _draw(self, color):
        self.delete("all")
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self._round_rect(0, 0, w, h, self._radius, fill=color, outline="")
        self.create_text(w // 2, h // 2, text=self._text, fill=self._fg, font=self._font)

    def _on_click(self, event):
        if self._command:
            self._command()

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def set_text(self, text):
        self._text = text
        self._draw(self._bg)


# ========== 主应用 ==========
class NASAApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RealEarth v5.0 — Cosmic Observatory · 深空观测台")
        self.root.geometry("1300x850")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(1100, 700)

        self.config = load_config()
        self.metadata = load_metadata()
        self.data_source = self.config.get("data_source", "apod")
        self.sat_image_path = None
        self.sat_auto_refresh = self.config.get("satellite_auto_refresh", True)
        self.sat_refresh_interval = self.config.get("satellite_refresh_interval", 10)
        self._sat_timer_id = None
        self._sat_next_refresh = None

        self.sdo_image_path = None
        self.sdo_auto_refresh = self.config.get("sdo_auto_refresh", True)
        self.sdo_refresh_interval = self.config.get("sdo_refresh_interval", 60)
        self._sdo_timer_id = None
        self._sdo_next_refresh = None

        # 风云四号 FY-4B 状态
        self.fy4_image_path = None
        self.fy4_auto_refresh = self.config.get("fy4_auto_refresh", True)
        self.fy4_refresh_interval = self.config.get("fy4_refresh_interval", 15)
        self._fy4_timer_id = None
        self._fy4_next_refresh = None
        self.selected_fy4_size = tk.StringVar(value=str(self.config.get("fy4_size", 1080)))

        # satellite panel vars
        self.selected_satellite = tk.StringVar(value=self.config.get("satellite_id", "himawari"))
        self.selected_color = tk.StringVar(value=self.config.get("satellite_color", "natural_color"))
        self.selected_sdo_band = tk.StringVar(value=self.config.get("sdo_band", "0304"))

        # APOD 数据
        self.images_by_cat = {key: [] for key in get_all_category_keys()}
        self.current_cat = self.config.get("selected_category", ALL_CATEGORY)
        self.current_idx = 0
        self.current_image = None
        self.photo_ref = None

        # 拦截关闭按钮
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 系统托盘
        self.tray_icon = None

        self._build_ui()
        self._rebuild_category_data()
        self._refresh_ui()
        self._switch_panel(self.data_source)

        start_scheduler()
        self._check_auto_startup()


    # ========== UI 构建（v5.0 "Cosmic Observatory" 深空观测台 · 还原 HTML 原型三栏布局） ==========
    # ---- 辅助：圆角卡片/容器 ----
    def _rounded_rect(self, canvas, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return canvas.create_polygon(pts, smooth=True, **kw)

    def _build_ui(self):
        # =====================================================================
        #  整体纵向布局：底部状态栏 + 主区（侧边栏 + 内容）
        # =====================================================================
        self.main_frame = tk.Frame(self.root, bg=BG_MAIN)
        self.main_frame.pack(fill="both", expand=True)

        # ---- 状态栏（最底层底部，28px，规范 §6.1/§5.7） ----
        self._build_statusbar()

        # ---- 主内容区：左侧边栏 + 右侧内容 ----
        self._build_sidebar()

        # ---- 右侧内容：4 个面板（每面板 = 控制面板 + 预览区） ----
        self._build_panels()

    # ---------------------------------------------------------------------
    #  状态栏（底部 28px：左=模式文字+分隔线+缓存/磁盘，右=调度器脉冲灯）
    # ---------------------------------------------------------------------
    def _build_statusbar(self):
        status_frame = tk.Frame(self.main_frame, bg=BG_SURFACE, height=28)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        # 顶部细分隔线
        tk.Frame(status_frame, bg=BORDER_DEFAULT, height=1).pack(fill="x")

        # 左侧：模式状态（脉冲绿点 + 文字）
        left = tk.Frame(status_frame, bg=BG_SURFACE)
        left.pack(side="left", fill="y", padx=(16, 0))
        self.status_dot = tk.Canvas(left, width=6, height=6, bg=BG_SURFACE,
                                    highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_dot.create_oval(0, 0, 6, 6, fill=GREEN, outline="")
        self.status_bar = tk.Label(left, text="就绪", bg=BG_SURFACE, fg=FG_SECONDARY,
                                   font=FONT_CAPTION, anchor="w")
        self.status_bar.pack(side="left")

        # 分隔线 + 缓存/磁盘信息（占位，逻辑层可后续更新）
        tk.Frame(status_frame, bg=BORDER_DEFAULT, width=1, height=14).pack(
            side="left", padx=12)

        # 右侧：调度器运行中 + 脉冲灯
        right_bar = tk.Frame(status_frame, bg=BG_SURFACE)
        right_bar.pack(side="right", padx=16)
        self.sched_label = tk.Label(right_bar, text="调度器运行中", bg=BG_SURFACE,
                                    fg=FG_DIM, font=FONT_CAPTION)
        self.sched_label.pack(side="right", padx=(6, 0))
        self.sched_light = tk.Canvas(right_bar, width=10, height=10, bg=BG_SURFACE,
                                     highlightthickness=0)
        self.sched_light.pack(side="right")
        self.sched_light.create_oval(1, 1, 9, 9, fill=GREEN, outline="")

        # 启动调度器脉冲呼吸动画（纯视觉）
        self._sched_pulse_on = True
        self._sched_pulse_id = self.root.after(600, self._sched_pulse_tick)

    # ---------------------------------------------------------------------
    #  侧边栏（220px 固定：品牌区 + 数据源导航 + 底部区 + 版本号）
    # ---------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = tk.Frame(self.main_frame, bg=SIDEBAR_BG, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # ---- 品牌区（顶部：地球图标 + 名称 + 副标题） ----
        brand = tk.Frame(sidebar, bg=SIDEBAR_BG)
        brand.pack(fill="x", padx=20, pady=(18, 0))

        mark = tk.Frame(brand, bg=SIDEBAR_BG)
        mark.pack(anchor="w")
        # 地球图标（径向渐变模拟 —— 用三色圆）
        globe = tk.Canvas(mark, width=28, height=28, bg=SIDEBAR_BG, highlightthickness=0)
        globe.pack(side="left", padx=(0, 10))
        globe.create_oval(2, 2, 26, 26, fill="#1565C0", outline="#0D47A1", width=1)
        globe.create_oval(2, 2, 26, 26, fill="#2D8CF0", outline="")
        globe.create_arc(4, 4, 24, 24, start=20, extent=140, fill="#4FC3F7", outline="")
        # 大陆绿块
        globe.create_oval(10, 8, 18, 14, fill="#4ECCA3", outline="")
        globe.create_oval(12, 16, 21, 24, fill="#4ECCA3", outline="")
        tk.Label(mark, text="RealEarth", bg=SIDEBAR_BG, fg=FG_TEXT,
                 font=FONT_BRAND).pack(side="left")
        tk.Label(brand, text="真实地球壁纸", bg=SIDEBAR_BG, fg=FG_DIM,
                 font=FONT_MICRO).pack(anchor="w", padx=38, pady=(1, 0))

        # 星场装饰（顶部淡星点 —— 用 Canvas 轻绘）
        starfield = tk.Canvas(sidebar, width=220, height=70, bg=SIDEBAR_BG,
                              highlightthickness=0)
        starfield.pack(fill="x", pady=(4, 0))
        for sx, sy, sr, sa in [(20, 18, 1, 0.5), (60, 30, 1, 0.4), (100, 14, 1, 0.5),
                               (150, 40, 1, 0.4), (180, 20, 1, 0.5), (40, 50, 1, 0.3),
                               (200, 55, 1, 0.4)]:
            starfield.create_oval(sx, sy, sx + sr * 2, sy + sr * 2,
                                  fill=f"#{int(255*sa):02x}{int(255*sa):02x}{int(255*sa):02x}",
                                  outline="")
        starfield.create_oval(120, 26, 123, 29, fill=APOD_ACCENT, outline="")
        starfield.create_oval(70, 55, 72, 57, fill=SAT_ACCENT, outline="")

        # ---- 数据源区 ----
        tk.Label(sidebar, text="数据源", bg=SIDEBAR_BG, fg=FG_DISABLED,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", padx=20, pady=(6, 4))

        nav_list = tk.Frame(sidebar, bg=SIDEBAR_BG)
        nav_list.pack(fill="x", padx=8)

        # 4 个数据源导航项（图标 + 名称 + 右侧徽章 + 激活左侧 3px 主题色竖线）
        self.btn_apod = self._make_nav(nav_list, "🔭", "天文图片", "apod",
                                       APOD_ACCENT, "APOD", APOD_LIGHT)
        self.btn_sat = self._make_nav(nav_list, "🛰", "卫星影像", "satellite",
                                      SAT_ACCENT, "6 颗", SAT_LIGHT)
        self.btn_fy4 = self._make_nav(nav_list, "🇨🇳", "风云四号", "fy4",
                                      FY4_ACCENT, "FY-4B", FY4_LIGHT)
        self.btn_sdo = self._make_nav(nav_list, "☀", "太阳观测", "sdo",
                                      SDO_ACCENT, "11 波段", SDO_LIGHT)

        # ---- 底部区：分隔线 + 设置 / 使用说明 + 版本号 ----
        bottom = tk.Frame(sidebar, bg=SIDEBAR_BG)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(6, 10))
        tk.Frame(bottom, bg=BORDER_DEFAULT, height=1).pack(fill="x", padx=12, pady=(0, 6))

        self._make_bottom_nav(bottom, "⚙", "设置", self._show_settings, FG_DIM)
        self._make_bottom_nav(bottom, "📖", "使用说明", self._show_help, FG_DIM)

        tk.Label(sidebar, text="RealEarth v5.0 · Cosmic Observatory",
                 bg=SIDEBAR_BG, fg=FG_DISABLED, font=(FONT_FAMILY[0], 9)).pack(
                     side="bottom", pady=(0, 8))

    def _make_bottom_nav(self, parent, icon, text, command, fg):
        btn = tk.Button(parent, text=f"{icon}  {text}", command=command,
                        bg=SIDEBAR_BG, fg=fg, font=FONT_SMALL,
                        relief="flat", anchor="w", padx=12, pady=6,
                        activebackground=SIDEBAR_HOVER, activeforeground=FG_SECONDARY,
                        cursor="hand2", bd=0)
        btn.pack(fill="x", pady=1)
        return btn

    # ========== 侧边栏导航项（v5.0 色彩编码导航，还原 HTML 原型） ==========
    def _make_nav(self, parent, icon, text, source, accent, badge, light):
        """创建侧边栏导航项：左侧 3px 主题色指示条 + 图标 + 名称 + 右侧徽章。

        accent: 该数据源主色（激活指示条）
        badge:  徽章文字（APOD / 6 颗 / FY-4B / 11 波段）
        light:  图标亮色
        """
        row = tk.Frame(parent, bg=SIDEBAR_BG)
        row.pack(fill="x", pady=1)

        # 左侧 3px 主题色指示条（激活时显示 + 微光晕近似）
        indicator = tk.Frame(row, width=3, bg=SIDEBAR_BG)
        indicator.pack(side="left", fill="y", padx=(0, 6))

        # 主按钮（图标 + 文字 + 徽章）
        btn = tk.Button(row, text=f"{icon}  {text}", command=lambda s=source: self._switch_panel(s),
                        bg=SIDEBAR_BG, fg=FG_SECONDARY, font=FONT_BODY,
                        relief="flat", anchor="w", padx=8, pady=9,
                        activebackground=SIDEBAR_HOVER, activeforeground=FG_TEXT,
                        cursor="hand2", bd=0)
        btn.pack(side="left", fill="both", expand=True)

        # 右侧徽章
        badge_lbl = tk.Label(row, text=badge, bg=SIDEBAR_BG, fg=light,
                             font=(FONT_MONO[0], 8, "bold"), padx=6, pady=1)
        badge_lbl.pack(side="right", padx=(6, 4))

        # 保存供 _switch_panel 切换状态
        btn._indicator = indicator
        btn._accent = accent
        btn._badge = badge_lbl
        btn._badge_light = light
        btn._icon = icon
        btn._text = text
        return btn

    # ---------------------------------------------------------------------
    #  4 个面板（每面板 = 左侧控制面板 210px + 右侧预览区）
    # ---------------------------------------------------------------------
    def _build_panels(self):
        body = tk.Frame(self.main_frame, bg=BG_MAIN)
        body.pack(side="left", fill="both", expand=True)

        self.panel_apod = tk.Frame(body, bg=BG_MAIN)
        self.panel_sat = tk.Frame(body, bg=BG_MAIN)
        self.panel_fy4 = tk.Frame(body, bg=BG_MAIN)
        self.panel_sdo = tk.Frame(body, bg=BG_MAIN)

        self._build_apod_panel()
        self._build_sat_panel()
        self._build_fy4_panel()
        self._build_sdo_panel()

    # ---- 通用：面板头（主题色小图标块 + 标题 + 副标题） ----
    def _panel_header(self, parent, icon, accent, light, title, sub):
        hd = tk.Frame(parent, bg=BG_MAIN)
        hd.pack(fill="x", pady=(0, 12))
        icon_box = tk.Canvas(hd, width=20, height=20, bg=BG_MAIN, highlightthickness=0)
        icon_box.pack(side="left", padx=(0, 8))
        icon_box.create_oval(2, 2, 18, 18, fill=accent, outline="")
        # 简化图标：用主题色圆 + 白色符号
        icon_box.create_text(10, 10, text=icon, fill="white",
                             font=(FONT_FAMILY[0], 9, "bold"))
        tbox = tk.Frame(hd, bg=BG_MAIN)
        tbox.pack(side="left")
        tk.Label(tbox, text=title, bg=BG_MAIN, fg=FG_TEXT, font=FONT_TITLE,
                 anchor="w").pack(anchor="w")
        tk.Label(tbox, text=sub, bg=BG_MAIN, fg=FG_DIM, font=FONT_CAPTION,
                 anchor="w").pack(anchor="w")

    # ---- 通用：信息卡片（单 Label 多行，兼容逻辑层 info_label.config(text=...)） ----
    def _info_card(self, parent, rows, label_attr, accent=None):
        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER_DEFAULT,
                        highlightthickness=1)
        card.pack(fill="both", expand=True, pady=(4, 0))
        lines = [f"{label}  {value}" for label, value in rows]
        lbl = tk.Label(card, text="\n".join(lines), bg=BG_CARD, fg=FG_SECONDARY,
                       font=FONT_CAPTION, justify="left", anchor="nw",
                       padx=10, pady=4, wraplength=170)
        lbl.pack(fill="both", expand=True)
        setattr(self, label_attr, lbl)
        return lbl

    # ---- 通用：预览容器（空状态 + 水印 + 底部信息 + 加载） ----
    def _preview_container(self, parent, accent, light, empty_text,
                           preview_attr, status_attr):
        box = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER_SUBTLE_2,
                       highlightthickness=1)
        box.pack(fill="both", expand=True, pady=(0, 10))
        preview = tk.Label(box, bg=BG_CARD, text=empty_text, fg=accent,
                           font=(FONT_FAMILY[0], 16), justify="center")
        preview.pack(fill="both", expand=True)
        # 右下水印（来源 + 时间，等宽字体）
        watermark = tk.Label(box, bg=BG_CARD, fg=FG_DIM, font=FONT_MICRO,
                             justify="right")
        watermark.place(relx=0.98, rely=0.02, anchor="ne")
        # 底部信息条
        info_bar = tk.Frame(box, bg=BG_SURFACE)
        info_bar.place(relx=0, rely=1, relwidth=1, anchor="sw")
        info = tk.Label(info_bar, text="", bg=BG_SURFACE, fg=FG_SECONDARY,
                        font=FONT_CAPTION, anchor="w", padx=12, pady=5)
        info.pack(side="left", fill="x")
        setattr(self, preview_attr, preview)
        setattr(self, status_attr, watermark)
        return box, preview, watermark, info

    # ---- 通用：面板切换的 content 容器 ----
    def _content_root(self, parent):
        """每面板 = 控制面板(左 210px) + 预览区(右 flex)"""
        wrap = tk.Frame(parent, bg=BG_MAIN)
        wrap.pack(fill="both", expand=True)
        return wrap

    # ========== APOD 面板 ==========
    def _build_apod_panel(self):
        p = self.panel_apod
        # 内容容器
        inner = self._content_root(p)

        # 左侧控制面板（210px）
        left = tk.Frame(inner, bg=BG_SURFACE, width=210)
        left.pack(side="left", fill="y")
        tk.Frame(inner, bg=BORDER_DEFAULT, width=1).pack(side="left", fill="y")
        left.pack_propagate(False)

        self._panel_header(left, "★", APOD_ACCENT, APOD_LIGHT,
                           "天文图片", "NASA APOD 每日精选")

        tk.Label(left, text="图片分类", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))

        # 分类列表（用 Treeview，保留 cat_tree 属性供逻辑层使用）
        cat_frame = tk.Frame(left, bg=BG_INPUT, highlightbackground=BORDER_DEFAULT,
                             highlightthickness=1)
        cat_frame.pack(fill="both", expand=True)
        cols = ("category", "count")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols, show="headings", height=12)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG_INPUT, foreground=FG_SECONDARY,
                        fieldbackground=BG_INPUT, rowheight=26, font=FONT_CAPTION)
        style.configure("Treeview.Heading", background=BG_CARD, foreground=FG_DIM,
                        font=(FONT_FAMILY[0], 10, "bold"))
        style.map("Treeview", background=[("selected", BG_CARD_HOVER)],
                  foreground=[("selected", APOD_LIGHT)])
        style.configure("Vertical.TScrollbar", background=BG_CARD,
                        troughcolor=BG_MAIN, arrowcolor=FG_DIM)
        self.cat_tree.heading("category", text="分类")
        self.cat_tree.heading("count", text="数量")
        self.cat_tree.column("category", width=140, anchor="w")
        self.cat_tree.column("count", width=40, anchor="center")
        self.cat_tree.pack(side="left", fill="both", expand=True)
        cat_scroll = ttk.Scrollbar(cat_frame, orient="vertical",
                                   command=self.cat_tree.yview)
        cat_scroll.pack(side="right", fill="y")
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)

        # 获取历史按钮
        self.btn_fetch = ModernButton(left, text="↓ 获取历史图片",
                                      command=self._fetch_history,
                                      width=186, height=34, bg=BG_CARD,
                                      hover_bg=BG_CARD_HOVER, fg=FG_SECONDARY,
                                      font=FONT_SMALL)
        self.btn_fetch.pack(fill="x", pady=(8, 0))

        # 右侧预览区
        right = tk.Frame(inner, bg=BG_MAIN, padx=16, pady=16)
        right.pack(side="left", fill="both", expand=True)

        box, self.apod_preview, _wm, _info = self._preview_container(
            right, APOD_ACCENT, APOD_LIGHT,
            "★\n暂无图片，点击「获取历史」拉取 NASA 精选",
            "apod_preview", "_apod_wm")
        # 底部信息条：apod_info 显示日期/标题（逻辑层 _load_image 写入）
        self.apod_info = _info

        # 底部操作栏
        ctrl = tk.Frame(right, bg=BG_MAIN, height=40)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)

        # 分页
        nav = tk.Frame(ctrl, bg=BG_MAIN)
        nav.pack(side="left")
        self.btn_prev = ModernButton(nav, text="‹", command=self._prev_image,
                                     width=32, height=34, bg=BG_CARD,
                                     hover_bg=BG_CARD_HOVER, fg=FG_SECONDARY,
                                     font=(FONT_FAMILY[0], 16))
        self.btn_prev.pack(side="left", padx=(0, 4))
        self.page_label = tk.Label(nav, text="0 / 0", bg=BG_MAIN, fg=FG_SECONDARY,
                                   font=FONT_MICRO, width=8)
        self.page_label.pack(side="left", padx=6)
        self.btn_next = ModernButton(nav, text="›", command=self._next_image,
                                     width=32, height=34, bg=BG_CARD,
                                     hover_bg=BG_CARD_HOVER, fg=FG_SECONDARY,
                                     font=(FONT_FAMILY[0], 16))
        self.btn_next.pack(side="left", padx=(4, 0))

        # 更新（成功绿）
        self.btn_update = ModernButton(ctrl, text="↻ 更新", command=self._update_now,
                                       width=72, height=34, bg=GREEN,
                                       hover_bg="#6ee7c5", fg="#0A1A14",
                                       font=FONT_SMALL)
        self.btn_update.pack(side="left", padx=(24, 0))

        # 设为壁纸（CTA 粉，靠右）
        self.btn_wallpaper = ModernButton(ctrl, text="设为壁纸", command=self._set_wallpaper,
                                          width=104, height=34, bg=ACCENT,
                                          hover_bg=ACCENT_HOVER, font=FONT_SMALL)
        self.btn_wallpaper.pack(side="right")

    # ========== 卫星影像面板 ==========
    def _build_sat_panel(self):
        p = self.panel_sat
        inner = self._content_root(p)

        left = tk.Frame(inner, bg=BG_SURFACE, width=210)
        left.pack(side="left", fill="y")
        tk.Frame(inner, bg=BORDER_DEFAULT, width=1).pack(side="left", fill="y")
        left.pack_propagate(False)

        self._panel_header(left, "🛰", SAT_ACCENT, SAT_LIGHT,
                           "卫星影像", "地球静止卫星实时图")

        tk.Label(left, text="选择卫星", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))
        # 卫星下拉（保留 selected_satellite StringVar 与 Combobox 接口：values=key）
        sat_list = list(GEOSTATIONARY_SATELLITES.keys())
        sat_names = [GEOSTATIONARY_SATELLITES[s]["name"] for s in sat_list]
        self.sat_combo = ttk.Combobox(left, values=sat_names, state="readonly",
                                      font=(FONT_FAMILY[0], 10))
        self.sat_combo.pack(fill="x", pady=(0, 8))
        self._sat_name_to_key = dict(zip(sat_names, sat_list))
        self._sat_key_to_name = dict(zip(sat_list, sat_names))
        # 初始化显示当前卫星中文名
        cur_key = self.selected_satellite.get()
        self.sat_combo.set(self._sat_key_to_name.get(cur_key, cur_key))
        # 选择变化时同步 key 到 selected_satellite
        self.sat_combo.bind("<<ComboboxSelected>>", self._on_sat_combo_selected)

        tk.Label(left, text="颜色模式", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))
        seg1 = tk.Frame(left, bg=BG_INPUT, highlightbackground=BORDER_DEFAULT,
                        highlightthickness=1)
        seg1.pack(fill="x", pady=(0, 8))
        self._make_seg(seg1, "颜色", [("自然色", "natural_color"),
                                      ("地球色", "geocolor")],
                       self.selected_color, SAT_ACCENT)

        tk.Label(left, text="分辨率", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.sat_size_var = tk.StringVar(value="1080")
        seg2 = tk.Frame(left, bg=BG_INPUT, highlightbackground=BORDER_DEFAULT,
                        highlightthickness=1)
        seg2.pack(fill="x", pady=(0, 8))
        self._make_seg(seg2, "分辨率", [("标准", "688"), ("高清", "1100"),
                                      ("超清", "2200")],
                       self.sat_size_var, SAT_ACCENT)

        # 卫星信息卡片
        self._info_card(left, [
            ("机构", "-"), ("覆盖区域", "-"), ("更新频率", "每 10 分钟"),
            ("数据源", "CIRA Slider"),
        ], "sat_info_label")

        # 右侧预览区
        right = tk.Frame(inner, bg=BG_MAIN, padx=16, pady=16)
        right.pack(side="left", fill="both", expand=True)

        box, self.sat_preview, self.sat_status, _si = self._preview_container(
            right, SAT_ACCENT, SAT_LIGHT,
            "🛰\n选择卫星后点击获取最新影像",
            "sat_preview", "sat_status")
        # sat_status = 右上角水印（来源+时间+分辨率，逻辑层 _load_preview 写入）

        ctrl = tk.Frame(right, bg=BG_MAIN, height=40)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)

        self.btn_sat_fetch = ModernButton(ctrl, text="获取最新影像",
                                          command=self._fetch_satellite,
                                          width=112, height=34, bg=SAT_ACCENT,
                                          hover_bg=SAT_LIGHT, font=FONT_SMALL)
        self.btn_sat_fetch.pack(side="left", padx=(0, 6))

        self.btn_sat_auto = ModernButton(ctrl,
            text="自动刷新: 开" if self.sat_auto_refresh else "自动刷新: 关",
            command=self._toggle_sat_auto_refresh,
            width=104, height=34,
            bg="#123B35" if self.sat_auto_refresh else BG_CARD,
            hover_bg="#1a4a3f" if self.sat_auto_refresh else BG_CARD_HOVER,
            fg=GREEN if self.sat_auto_refresh else FG_DIM, font=FONT_SMALL)
        self.btn_sat_auto.pack(side="left", padx=(0, 6))

        self.sat_countdown = tk.Label(ctrl, text="", bg=BG_MAIN, fg=FG_DIM,
                                      font=FONT_MICRO)
        self.sat_countdown.pack(side="left", padx=4)

        self.btn_sat_wp = ModernButton(ctrl, text="设为壁纸",
                                       command=self._set_sat_wallpaper,
                                       width=104, height=34, bg=ACCENT,
                                       hover_bg=ACCENT_HOVER, font=FONT_SMALL)
        self.btn_sat_wp.pack(side="right")

    def _on_sat_combo_selected(self, event):
        name = self.sat_combo.get()
        key = self._sat_name_to_key.get(name)
        if key:
            self.selected_satellite.set(key)
            self._update_sat_info()

    def _make_seg(self, parent, label, options, var, accent):
        """分段控件（用按钮模拟 RadioButton 组，突出选中项）"""
        for text, val in options:
            b = tk.Radiobutton(parent, text=text, variable=var, value=val,
                               bg=BG_INPUT, fg=FG_SECONDARY, selectcolor=BG_INPUT,
                               activebackground=BG_INPUT, activeforeground=FG_TEXT,
                               indicatoron=False, relief="flat", bd=0,
                               highlightthickness=1, highlightbackground=BG_INPUT,
                               highlightcolor=accent, font=FONT_SMALL, cursor="hand2")
            b.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        # 初始高亮选中的
        self._refresh_seg(parent, var, accent)

    def _refresh_seg(self, parent, var, accent):
        pass  # Radiobutton 选中态由 ttk/indicator 管理，这里不强制刷新颜色

    # ========== 风云四号 FY-4B 面板 ==========
    def _build_fy4_panel(self):
        p = self.panel_fy4
        inner = self._content_root(p)

        left = tk.Frame(inner, bg=BG_SURFACE, width=210)
        left.pack(side="left", fill="y")
        tk.Frame(inner, bg=BORDER_DEFAULT, width=1).pack(side="left", fill="y")
        left.pack_propagate(False)

        self._panel_header(left, "🛰", FY4_ACCENT, FY4_LIGHT,
                           "风云四号", "FY-4B 真彩色全圆盘")

        # 固定真彩色提示（烬红信息卡）
        hint = tk.Frame(left, bg="#221010", highlightbackground=FY4_ACCENT,
                        highlightthickness=1)
        hint.pack(fill="x", pady=(0, 10))
        tk.Label(hint, text="⚠ 风云四号固定为真彩色，色彩模式不适用",
                 bg="#221010", fg=FY4_LIGHT, font=FONT_CAPTION, justify="left",
                 padx=10, pady=8, wraplength=180).pack(fill="x")

        tk.Label(left, text="分辨率", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))
        seg = tk.Frame(left, bg=BG_INPUT, highlightbackground=BORDER_DEFAULT,
                       highlightthickness=1)
        seg.pack(fill="x", pady=(0, 8))
        self._make_seg(seg, "分辨率", [("标准", "1080"), ("高清", "2200"),
                                     ("超清", "4000")],
                       self.selected_fy4_size, FY4_ACCENT)

        self._info_card(left, [
            ("卫星", "FY-4B"), ("国家", "中国"), ("机构", "NSMC"),
            ("影像类型", "真彩色全圆盘"), ("更新频率", "每 15 分钟"),
            ("时区", "UTC+8 北京时间"),
        ], "fy4_info_label")

        right = tk.Frame(inner, bg=BG_MAIN, padx=16, pady=16)
        right.pack(side="left", fill="both", expand=True)

        box, self.fy4_preview, self.fy4_status, _fi = self._preview_container(
            right, FY4_ACCENT, FY4_LIGHT,
            "🛰\n点击获取风云四号 FY-4B 真彩色影像",
            "fy4_preview", "fy4_status")
        # fy4_status = 右上角水印（逻辑层 _load_preview 写入）

        ctrl = tk.Frame(right, bg=BG_MAIN, height=40)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)

        self.btn_fy4_fetch = ModernButton(ctrl, text="获取最新影像",
                                          command=self._fetch_fy4,
                                          width=112, height=34, bg=FY4_ACCENT,
                                          hover_bg=FY4_LIGHT, font=FONT_SMALL)
        self.btn_fy4_fetch.pack(side="left", padx=(0, 6))

        self.btn_fy4_auto = ModernButton(ctrl,
            text="自动刷新: 开" if self.fy4_auto_refresh else "自动刷新: 关",
            command=self._toggle_fy4_auto_refresh,
            width=104, height=34,
            bg="#123B35" if self.fy4_auto_refresh else BG_CARD,
            hover_bg="#1a4a3f" if self.fy4_auto_refresh else BG_CARD_HOVER,
            fg=GREEN if self.fy4_auto_refresh else FG_DIM, font=FONT_SMALL)
        self.btn_fy4_auto.pack(side="left", padx=(0, 6))

        self.fy4_countdown = tk.Label(ctrl, text="", bg=BG_MAIN, fg=FG_DIM,
                                      font=FONT_MICRO)
        self.fy4_countdown.pack(side="left", padx=4)

        self.btn_fy4_wp = ModernButton(ctrl, text="设为壁纸",
                                       command=self._set_fy4_wallpaper,
                                       width=104, height=34, bg=ACCENT,
                                       hover_bg=ACCENT_HOVER, font=FONT_SMALL)
        self.btn_fy4_wp.pack(side="right")

    # ========== 太阳观测 SDO 面板 ==========
    def _build_sdo_panel(self):
        p = self.panel_sdo
        inner = self._content_root(p)

        left = tk.Frame(inner, bg=BG_SURFACE, width=210)
        left.pack(side="left", fill="y")
        tk.Frame(inner, bg=BORDER_DEFAULT, width=1).pack(side="left", fill="y")
        left.pack_propagate(False)

        self._panel_header(left, "☀", SDO_ACCENT, SDO_LIGHT,
                           "太阳观测", "NASA SDO 太阳动力学天文台")

        tk.Label(left, text="观测波段", bg=BG_SURFACE, fg=FG_DIM,
                 font=(FONT_FAMILY[0], 10, "bold")).pack(anchor="w", pady=(0, 4))

        band_frame = tk.Frame(left, bg=BG_SURFACE)
        band_frame.pack(fill="both", expand=True)
        for key, info in SDO_BANDS.items():
            b = tk.Radiobutton(band_frame, text=f"{info['name']}",
                               variable=self.selected_sdo_band, value=key,
                               bg=BG_SURFACE, fg=FG_SECONDARY, selectcolor=BG_SURFACE,
                               activebackground=BG_SURFACE, activeforeground=SDO_LIGHT,
                               font=FONT_SMALL, cursor="hand2", anchor="w")
            b.pack(fill="x", pady=1)

        self._info_card(left, [
            ("数据源", "NASA SDO"), ("当前波段", "304 Å 色球层"),
            ("更新频率", "15-60 分钟"), ("自动刷新", "每 60 分钟"),
        ], "sdo_info_label")

        right = tk.Frame(inner, bg=BG_MAIN, padx=16, pady=16)
        right.pack(side="left", fill="both", expand=True)

        box, self.sdo_preview, self.sdo_status, _di = self._preview_container(
            right, SDO_ACCENT, SDO_LIGHT,
            "☀\n选择波段后点击获取最新太阳图像",
            "sdo_preview", "sdo_status")
        # sdo_status = 右上角水印（逻辑层 _load_preview 写入）

        ctrl = tk.Frame(right, bg=BG_MAIN, height=40)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)

        self.btn_sdo_fetch = ModernButton(ctrl, text="获取最新太阳图",
                                          command=self._fetch_sdo,
                                          width=116, height=34, bg=SDO_ACCENT,
                                          hover_bg=SDO_LIGHT, font=FONT_SMALL)
        self.btn_sdo_fetch.pack(side="left", padx=(0, 6))

        self.btn_sdo_auto = ModernButton(ctrl,
            text="自动刷新: 开" if self.sdo_auto_refresh else "自动刷新: 关",
            command=self._toggle_sdo_auto_refresh,
            width=104, height=34,
            bg="#123B35" if self.sdo_auto_refresh else BG_CARD,
            hover_bg="#1a4a3f" if self.sdo_auto_refresh else BG_CARD_HOVER,
            fg=GREEN if self.sdo_auto_refresh else FG_DIM, font=FONT_SMALL)
        self.btn_sdo_auto.pack(side="left", padx=(0, 6))

        self.sdo_countdown = tk.Label(ctrl, text="", bg=BG_MAIN, fg=FG_DIM,
                                      font=FONT_MICRO)
        self.sdo_countdown.pack(side="left", padx=4)

        self.btn_sdo_wp = ModernButton(ctrl, text="设为壁纸",
                                       command=self._set_sdo_wallpaper,
                                       width=104, height=34, bg=ACCENT,
                                       hover_bg=ACCENT_HOVER, font=FONT_SMALL)
        self.btn_sdo_wp.pack(side="right")

    # ========== 面板切换 ==========
    def _switch_panel(self, source: str):
        self.data_source = source
        self.config["data_source"] = source
        save_config(self.config)

        # 隐藏所有面板
        for p in [self.panel_apod, self.panel_sat, self.panel_fy4, self.panel_sdo]:
            p.pack_forget()

        # 停止所有计时器
        self._stop_sat_refresh_timer()
        self._stop_fy4_refresh_timer()
        self._stop_sdo_refresh_timer()

        # 重置所有导航项（指示条透明 + 侧边栏底色 + 次要文字色）
        for btn in [self.btn_apod, self.btn_sat, self.btn_fy4, self.btn_sdo]:
            btn.configure(bg=SIDEBAR_BG, fg=FG_SECONDARY)
            btn._indicator.configure(bg=SIDEBAR_BG)

        if source == "apod":
            self.panel_apod.pack(fill="both", expand=True)
            self._activate_nav(self.btn_apod, "天文图片模式 · NASA APOD 每日精选")
        elif source == "satellite":
            self.panel_sat.pack(fill="both", expand=True)
            sat = self.config.get("satellite_id", "himawari")
            self._activate_nav(self.btn_sat,
                f"卫星影像模式 · {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}")
            self._update_sat_info()
            self._start_sat_refresh_timer()
        elif source == "fy4":
            self.panel_fy4.pack(fill="both", expand=True)
            self._activate_nav(self.btn_fy4, "风云四号 FY-4B 真彩色影像 · 中国 NSMC")
            self._update_fy4_info()
            self._start_fy4_refresh_timer()
        elif source == "sdo":
            self.panel_sdo.pack(fill="both", expand=True)
            band = self.config.get("sdo_band", "0304")
            self._activate_nav(self.btn_sdo,
                f"太阳观测模式 · {SDO_BANDS.get(band, {}).get('name', band)}")
            self._start_sdo_refresh_timer()

    def _activate_nav(self, btn, status_text: str):
        """激活指定导航项：左侧 3px 主题色指示条 + 背景高亮 + 图标亮色 + 更新状态栏"""
        btn.configure(bg=SIDEBAR_HOVER, fg=FG_TEXT)
        btn._indicator.configure(bg=btn._accent)
        btn._badge.configure(bg=SIDEBAR_HOVER)
        self._update_status(status_text)

    # ========== APOD 数据操作 ==========
    def _rebuild_category_data(self):
        self.images_by_cat = {key: [] for key in get_all_category_keys()}
        images = self.metadata.get("images", {})
        for date_str, data in images.items():
            img = ApodImage.from_dict(data)
            cat = categorize_image(img)
            self.images_by_cat[cat].append(img)
            self.images_by_cat[ALL_CATEGORY].append(img)
        for key in self.images_by_cat:
            self.images_by_cat[key].sort(key=lambda x: x.date, reverse=True)

    def _refresh_ui(self):
        self.cat_tree.delete(*self.cat_tree.get_children())
        cat_counts = {key: len(self.images_by_cat.get(key, [])) for key in get_all_category_keys()}
        for key in get_all_category_keys():
            name = get_category_name(key)
            count = cat_counts.get(key, 0)
            item = self.cat_tree.insert("", "end", values=(name, count))
            if key == self.current_cat:
                self.cat_tree.selection_set(item)
                self.cat_tree.see(item)
        self._show_current_image()

    def _show_current_image(self):
        images = self.images_by_cat.get(self.current_cat, [])
        total = len(images)
        if total == 0:
            self.apod_preview.config(text="📷 暂无图片\n\n点击「获取历史」拉取 NASA 图片", fg=FG_DIM)
            self.apod_info.config(text="")
            self.page_label.config(text="0 / 0")
            self.current_image = None
            self.photo_ref = None
            return

        self.current_idx = max(0, min(self.current_idx, total - 1))
        img = images[self.current_idx]
        self.current_image = img
        self.page_label.config(text=f"{self.current_idx + 1} / {total}")

        cache_path = IMAGE_CACHE_DIR / f"{img.date}.jpg"
        if not cache_path.exists() and img.hdurl:
            cache_path = IMAGE_CACHE_DIR / f"{img.date}_hd.jpg"

        if cache_path.exists():
            self._load_image(str(cache_path), self.apod_preview, self.apod_info)
        else:
            self.apod_preview.config(text=f"⬇ 正在下载...\n{img.title}", fg=FG_DIM)
            self.apod_info.config(text=f"{img.date} | {img.title}")
            threading.Thread(target=self._download_and_show, args=(img,), daemon=True).start()

    def _load_image(self, path: str, label: tk.Label, info_label: tk.Label = None):
        try:
            pil_img = Image.open(path)
            self.root.update_idletasks()
            pw = label.winfo_width() or 900
            ph = label.winfo_height() or 600
            iw, ih = pil_img.size
            ratio = min(pw / iw, ph / ih, 1.0)
            nw, nh = int(iw * ratio), int(ih * ratio)
            pil_img = pil_img.resize((nw, nh), Image.LANCZOS)
            self.photo_ref = ImageTk.PhotoImage(pil_img)
            label.config(image=self.photo_ref, text="")
            if info_label and self.current_image:
                img = self.current_image
                info = f"📅 {img.date}    📛 {img.title}"
                if img.copyright:
                    info += f"    © {img.copyright}"
                info_label.config(text=info)
        except Exception as e:
            logger.error(f"Load image error: {e}")
            label.config(text="❌ 图片加载失败", fg=ACCENT)

    # ====== 通用图片加载 ======
    def _load_preview(self, path: str, label: tk.Label, status_label: tk.Label = None,
                      source_text: str = "", extra: str = ""):
        """通用预览图加载"""
        try:
            pil_img = Image.open(path)
            self.root.update_idletasks()
            pw = label.winfo_width() or 900
            ph = label.winfo_height() or 600
            iw, ih = pil_img.size
            ratio = min(pw / iw, ph / ih, 1.0)
            nw, nh = int(iw * ratio), int(ih * ratio)
            pil_img = pil_img.resize((nw, nh), Image.LANCZOS)
            self._prev_photo = ImageTk.PhotoImage(pil_img)
            label.config(image=self._prev_photo, text="")
            if status_label:
                now = datetime.now()
                status_label.config(
                    text=f"{source_text} | {now.strftime('%Y-%m-%d %H:%M')} | "
                         f"{iw}x{ih} {extra}")
        except Exception as e:
            logger.error(f"Load preview error: {e}")
            label.config(text="❌ 加载失败", fg=ACCENT)

    def _download_and_show(self, img: ApodImage):
        path = download_image(img, hd=self.config.get("hd", True))
        if path:
            self.root.after(0, lambda: self._load_image(path, self.apod_preview, self.apod_info))
        else:
            self.root.after(0, lambda: self.apod_preview.config(
                text="❌ 下载失败，请检查网络", fg=ACCENT))

    # ========== APOD 事件 ==========
    def _on_cat_select(self, event):
        sel = self.cat_tree.selection()
        if not sel:
            return
        idx = self.cat_tree.index(sel[0])
        keys = get_all_category_keys()
        if idx < len(keys):
            self.current_cat = keys[idx]
            self.current_idx = 0
            self._show_current_image()
            self._update_status(f"已切换：{get_category_name(self.current_cat)}")

    def _prev_image(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._show_current_image()

    def _next_image(self):
        images = self.images_by_cat.get(self.current_cat, [])
        if self.current_idx < len(images) - 1:
            self.current_idx += 1
            self._show_current_image()

    def _set_wallpaper(self):
        if not self.current_image:
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        cache_path = IMAGE_CACHE_DIR / f"{self.current_image.date}.jpg"
        if not cache_path.exists() and self.current_image.hdurl:
            cache_path = IMAGE_CACHE_DIR / f"{self.current_image.date}_hd.jpg"
        if cache_path.exists():
            style = self.config.get("wallpaper_style", "fill")
            # 水印标注
            wp_path = watermark_image(
                str(cache_path),
                left_text="来源: NASA 每日天文图片 (APOD)",
                right_text=f"拍摄: {self.current_image.date} | {self.current_image.title}",
                output_key=f"apod_{self.current_image.date}",
            )
            if set_wallpaper(wp_path, self.current_image.date.replace("-", ""), style=style):
                self._update_status(f"壁纸已更换：{self.current_image.title}", color=GREEN)
            else:
                messagebox.showerror("错误", "壁纸设置失败")
        else:
            messagebox.showwarning("提示", "图片尚未下载完成")

    def _fetch_history(self):
        days = simpledialog.askinteger("获取历史图片", "获取最近多少天的 APOD 图片？",
                                       initialvalue=10, minvalue=1, maxvalue=365)
        if not days:
            return
        self._update_status(f"⏳ 正在获取最近 {days} 天的图片...")
        threading.Thread(target=self._do_fetch, args=(days,), daemon=True).start()

    def _do_fetch(self, days: int):
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            images = fetch_apod_range(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                api_key=self.config.get("api_key"),
            )
            metadata = load_metadata()
            for img in images:
                metadata["images"][img.date] = img.to_dict()
            save_metadata(metadata)
            self.metadata = metadata
            self.root.after(0, self._on_fetch_done, len(images))
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            self.root.after(0, lambda: self._update_status(f"❌ 获取失败: {e}", color=ACCENT))

    def _on_fetch_done(self, count: int):
        self._rebuild_category_data()
        self._refresh_ui()
        self._update_status(f"已获取 {count} 张图片", color=GREEN)

    def _update_now(self):
        self._update_status("⏳ 正在检查更新...")
        threading.Thread(target=self._do_update, daemon=True).start()

    def _do_update(self):
        try:
            result = check_and_update()
            self.root.after(0, self._rebuild_category_data)
            self.root.after(0, self._refresh_ui)
            self.root.after(0, lambda: self._update_status(
                "壁纸已更新" if result else "今日暂无匹配图片",
                color=GREEN if result else FG_DIM))
        except Exception as e:
            self.root.after(0, lambda: self._update_status(f"❌ 更新失败: {e}", color=ACCENT))

    # ========== 卫星影像事件 ==========
    def _update_sat_info(self):
        """更新卫星信息卡片"""
        sat = self.selected_satellite.get()
        info = GEOSTATIONARY_SATELLITES.get(sat, {})
        self.sat_info_label.config(
            text=f"卫星: {info.get('name', sat)}\n\n"
                 f"数据源\n━━━━━━━━━━\nCIRA RAMMB-Slider\n\n"
                 f"区域\n━━━━━━━━━━\n{info.get('region', '-')}\n\n"
                 f"更新频率\n━━━━━━━━━━\n约每 10 分钟\n\n"
                 f"颜色模式\n━━━━━━━━━━\n自然色/地球色"
        )

    def _fetch_satellite(self):
        sat = self.selected_satellite.get()
        color = self.selected_color.get()
        size = int(self.sat_size_var.get())
        name = GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)
        self.config["satellite_id"] = sat
        self.config["satellite_color"] = color
        save_config(self.config)
        self._update_status(f"⏳ 正在获取 {name} 卫星影像...", color=YELLOW)
        self.sat_preview.config(text="⏳\n正在获取卫星影像...", fg=FG_DIM)
        self._update_sat_info()
        threading.Thread(target=self._do_fetch_sat, args=(sat, color, size), daemon=True).start()

    def _do_fetch_sat(self, sat: str, color: str, size: int):
        try:
            path = fetch_satellite_image(satellite=sat, color=color, target_size=size)
            if path:
                self.sat_image_path = path
                self.root.after(0, lambda: self._load_preview(path, self.sat_preview, self.sat_status,
                    f"🛰 {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}"))
                self.root.after(0, lambda: self._update_status(
                    f"卫星影像已更新 | {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}",
                    color=GREEN))
            else:
                self.root.after(0, lambda: self.sat_preview.config(
                    text="❌ 获取失败\n数据暂时不可用，请稍后重试", fg=ACCENT))
                self.root.after(0, lambda: self._update_status("❌ 获取失败", color=ACCENT))
        except Exception as e:
            logger.error(f"Sat fetch error: {e}")
            self.root.after(0, lambda: self.sat_preview.config(text=f"❌ {str(e)[:60]}", fg=ACCENT))
            self.root.after(0, lambda: self._update_status(f"❌ {e}", color=ACCENT))

    def _set_sat_wallpaper(self):
        if not self.sat_image_path or not Path(self.sat_image_path).exists():
            messagebox.showwarning("提示", "请先获取卫星影像")
            return
        sat = self.config.get("satellite_id", "himawari")
        name = GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)
        style = self.config.get("wallpaper_style", "fill")
        now = datetime.now()
        wp_path = watermark_image(
            self.sat_image_path,
            left_text=f"来源: {name}",
            right_text=f"拍摄时间: {now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
            output_key=f"sat_{sat}",
        )
        if set_wallpaper(wp_path, f"sat_{sat}", style=style):
            self._update_status(f"壁纸已设置 | {name} | 后台持续自动更新", color=GREEN)
        else:
            messagebox.showerror("错误", "壁纸设置失败")

    # ========== SDO 太阳事件 ==========
    def _fetch_sdo(self):
        band = self.selected_sdo_band.get()
        name = SDO_BANDS.get(band, {}).get("name", band)
        self.config["sdo_band"] = band
        save_config(self.config)
        self._update_status(f"⏳ 正在获取 {name} 太阳图像...", color=YELLOW)
        self.sdo_preview.config(text="⏳\n正在获取太阳图像...", fg=FG_DIM)
        threading.Thread(target=self._do_fetch_sdo, args=(band,), daemon=True).start()

    def _do_fetch_sdo(self, band: str):
        try:
            path = fetch_sdo_image(band=band)
            if path:
                self.sdo_image_path = path
                name = SDO_BANDS.get(band, {}).get("name", band)
                self.root.after(0, lambda: self._load_preview(path, self.sdo_preview,
                    self.sdo_status, f"☀ {name}", "NASA SDO"))
                self.root.after(0, lambda: self._update_status(
                    f"太阳图像已更新 | {name}", color=GREEN))
            else:
                self.root.after(0, lambda: self.sdo_preview.config(
                    text="❌ 获取失败\nNASA SDO 数据暂时不可用", fg=ACCENT))
                self.root.after(0, lambda: self._update_status("❌ 获取失败", color=ACCENT))
        except Exception as e:
            logger.error(f"SDO fetch error: {e}")
            self.root.after(0, lambda: self.sdo_preview.config(text=f"❌ {str(e)[:60]}", fg=ACCENT))
            self.root.after(0, lambda: self._update_status(f"❌ {e}", color=ACCENT))

    def _set_sdo_wallpaper(self):
        if not self.sdo_image_path or not Path(self.sdo_image_path).exists():
            messagebox.showwarning("提示", "请先获取太阳图像")
            return
        band = self.config.get("sdo_band", "0304")
        name = SDO_BANDS.get(band, {}).get("name", band)
        style = self.config.get("wallpaper_style", "fill")
        now = datetime.now()
        wp_path = watermark_image(
            self.sdo_image_path,
            left_text=f"来源: NASA SDO 太阳观测",
            right_text=f"波段: {name} | {now.strftime('%Y-%m-%d %H:%M')}",
            output_key=f"sdo_{band}",
        )
        if set_wallpaper(wp_path, f"sdo_{band}", style=style):
            self._update_status(f"壁纸已设置 | {name}", color=GREEN)
        else:
            messagebox.showerror("错误", "壁纸设置失败")

    # ========== 卫星自动刷新 ==========
    def _toggle_sat_auto_refresh(self):
        self.sat_auto_refresh = not self.sat_auto_refresh
        self.config["satellite_auto_refresh"] = self.sat_auto_refresh
        save_config(self.config)
        if self.sat_auto_refresh:
            self.btn_sat_auto._bg = GREEN
            self.btn_sat_auto._hover_bg = "#6ee7c5"
            self.btn_sat_auto._text = "🔄 自动刷新: 开"
            self.btn_sat_auto._draw(GREEN)
            self._start_sat_refresh_timer()
            self._update_status("卫星自动刷新已开启", color=GREEN)
        else:
            self.btn_sat_auto._bg = ACCENT2
            self.btn_sat_auto._hover_bg = BG_CARD_HOVER
            self.btn_sat_auto._text = "🔄 自动刷新: 关"
            self.btn_sat_auto._draw(ACCENT2)
            self._stop_sat_refresh_timer()
            self._update_status("卫星自动刷新已关闭")

    def _start_sat_refresh_timer(self):
        if not self.sat_auto_refresh:
            return
        if self._sat_timer_id:
            self.root.after_cancel(self._sat_timer_id)
        self._sat_next_refresh = datetime.now() + timedelta(minutes=self.sat_refresh_interval)
        self._update_sat_countdown()
        self._sat_timer_id = self.root.after(1000, self._sat_tick)

    def _stop_sat_refresh_timer(self):
        if self._sat_timer_id:
            self.root.after_cancel(self._sat_timer_id)
            self._sat_timer_id = None
        self._sat_next_refresh = None
        self.sat_countdown.config(text="")

    def _sat_tick(self):
        if not self.sat_auto_refresh:
            return
        now = datetime.now()
        if self._sat_next_refresh and (self._sat_next_refresh - now).total_seconds() <= 0:
            self._sat_next_refresh = now + timedelta(minutes=self.sat_refresh_interval)
            self.sat_countdown.config(text="⏳ 刷新中...")
            sat = self.config.get("satellite_id", "himawari")
            color = self.config.get("satellite_color", "natural_color")
            size = self.config.get("satellite_size", 1080)
            threading.Thread(target=self._do_sat_auto_refresh, args=(sat, color, size), daemon=True).start()
        else:
            self._update_sat_countdown()
        self._sat_timer_id = self.root.after(1000, self._sat_tick)

    def _update_sat_countdown(self):
        if not self._sat_next_refresh:
            return
        remaining = max(0, (self._sat_next_refresh - datetime.now()).total_seconds())
        m, s = int(remaining // 60), int(remaining % 60)
        self.sat_countdown.config(text=f"⏱ {m:02d}:{s:02d}", fg=FG_DIM if m > 1 else YELLOW)

    def _do_sat_auto_refresh(self, sat: str, color: str, size: int):
        try:
            path = fetch_satellite_image(satellite=sat, color=color, target_size=size)
            if not path:
                return
            old = self.sat_image_path
            self.sat_image_path = path
            self.root.after(0, lambda: self._load_preview(path, self.sat_preview, self.sat_status,
                f"🛰 {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}"))
            if self.data_source == "satellite":
                style = self.config.get("wallpaper_style", "fill")
                now = datetime.now()
                name = GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)
                wp_path = watermark_image(path,
                    left_text=f"来源: {name}",
                    right_text=f"拍摄时间: {now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
                    output_key=f"sat_{sat}")
                set_wallpaper(wp_path, f"sat_{sat}", style=style)
                self.root.after(0, lambda: self._update_status(
                    f"🛰 自动刷新 | {now.strftime('%H:%M')} | 壁纸同步更新", color=GREEN))
            else:
                self.root.after(0, lambda: self._update_status("🛰 卫星影像已自动刷新", color=GREEN))
        except Exception as e:
            logger.error(f"Sat auto-refresh error: {e}")

    # ========== SDO 自动刷新 ==========
    def _toggle_sdo_auto_refresh(self):
        self.sdo_auto_refresh = not self.sdo_auto_refresh
        self.config["sdo_auto_refresh"] = self.sdo_auto_refresh
        save_config(self.config)
        if self.sdo_auto_refresh:
            self.btn_sdo_auto._bg = GREEN
            self.btn_sdo_auto._hover_bg = "#6ee7c5"
            self.btn_sdo_auto._text = "🔄 自动刷新: 开"
            self.btn_sdo_auto._draw(GREEN)
            self._start_sdo_refresh_timer()
            self._update_status("SDO 自动刷新已开启", color=GREEN)
        else:
            self.btn_sdo_auto._bg = ACCENT2
            self.btn_sdo_auto._hover_bg = BG_CARD_HOVER
            self.btn_sdo_auto._text = "🔄 自动刷新: 关"
            self.btn_sdo_auto._draw(ACCENT2)
            self._stop_sdo_refresh_timer()
            self._update_status("SDO 自动刷新已关闭")

    def _start_sdo_refresh_timer(self):
        if not self.sdo_auto_refresh:
            return
        if self._sdo_timer_id:
            self.root.after_cancel(self._sdo_timer_id)
        self._sdo_next_refresh = datetime.now() + timedelta(minutes=self.sdo_refresh_interval)
        self._update_sdo_countdown()
        self._sdo_timer_id = self.root.after(1000, self._sdo_tick)

    def _stop_sdo_refresh_timer(self):
        if self._sdo_timer_id:
            self.root.after_cancel(self._sdo_timer_id)
            self._sdo_timer_id = None
        self._sdo_next_refresh = None
        self.sdo_countdown.config(text="")

    def _sdo_tick(self):
        if not self.sdo_auto_refresh:
            return
        now = datetime.now()
        remaining = max(0, (self._sdo_next_refresh - now).total_seconds())
        if remaining <= 0:
            self._sdo_next_refresh = now + timedelta(minutes=self.sdo_refresh_interval)
            self.sdo_countdown.config(text="⏳ 刷新中...")
            band = self.config.get("sdo_band", "0304")
            threading.Thread(target=self._do_sdo_auto_refresh, args=(band,), daemon=True).start()
        else:
            self._update_sdo_countdown()
        self._sdo_timer_id = self.root.after(1000, self._sdo_tick)

    def _update_sdo_countdown(self):
        if not self._sdo_next_refresh:
            return
        remaining = max(0, (self._sdo_next_refresh - datetime.now()).total_seconds())
        m, s = int(remaining // 60), int(remaining % 60)
        self.sdo_countdown.config(text=f"⏱ {m:02d}:{s:02d}", fg=FG_DIM if m > 1 else YELLOW)

    def _do_sdo_auto_refresh(self, band: str):
        try:
            path = fetch_sdo_image(band=band)
            if not path:
                return
            self.sdo_image_path = path
            name = SDO_BANDS.get(band, {}).get("name", band)
            self.root.after(0, lambda: self._load_preview(path, self.sdo_preview,
                self.sdo_status, f"☀ {name}", "NASA SDO"))
            if self.data_source == "sdo":
                style = self.config.get("wallpaper_style", "fill")
                now = datetime.now()
                wp_path = watermark_image(path,
                    left_text="来源: NASA SDO 太阳观测",
                    right_text=f"波段: {name} | {now.strftime('%Y-%m-%d %H:%M')}",
                    output_key=f"sdo_{band}")
                set_wallpaper(wp_path, f"sdo_{band}", style=style)
                self.root.after(0, lambda: self._update_status(
                    f"☀ SDO 自动刷新 | {now.strftime('%H:%M')} | 壁纸同步更新", color=GREEN))
            else:
                self.root.after(0, lambda: self._update_status("☀ SDO 已自动刷新", color=GREEN))
        except Exception as e:
            logger.error(f"SDO auto-refresh error: {e}")

    # ========== 风云四号 FY-4B ==========
    def _update_fy4_info(self):
        """更新风云四号信息卡片"""
        size = self.selected_fy4_size.get()
        try:
            ct = get_fy4_capture_time()
            ct_str = ct.strftime("%Y-%m-%d %H:%M") + " (UTC+8)" if ct else "未知"
        except Exception:
            ct_str = "获取中..."
        self.fy4_info_label.config(
            text=f"卫星: 风云四号 FY-4B\n(FengYun-4B, 中国)\n\n"
                 f"数据源\n━━━━━━━━━━\n国家卫星气象中心\nNSMC FY-4\n\n"
                 f"分辨率\n━━━━━━━━━━\n{size} px\n\n"
                 f"色彩模式\n━━━━━━━━━━\n真彩色（固定）\n\n"
                 f"最近拍摄\n━━━━━━━━━━\n{ct_str}"
        )

    def _fetch_fy4(self):
        size = int(self.selected_fy4_size.get())
        self.config["fy4_size"] = size
        save_config(self.config)
        self._update_fy4_info()
        self._update_status("⏳ 正在获取风云四号 FY-4B 真彩色影像...", color=YELLOW)
        self.fy4_preview.config(text="⏳\n正在获取风云四号影像...", fg=FG_DIM)
        threading.Thread(target=self._do_fetch_fy4, args=(size,), daemon=True).start()

    def _do_fetch_fy4(self, size: int):
        try:
            path = fetch_fy4_image(target_size=size, force=True)
            if path:
                self.fy4_image_path = path
                try:
                    ct = get_fy4_capture_time()
                    ct_str = ct.strftime("%Y-%m-%d %H:%M") if ct else None
                except Exception:
                    ct_str = None
                self.root.after(0, lambda: self._load_preview(
                    path, self.fy4_preview, self.fy4_status,
                    "🇨🇳 风云四号 FY-4B", ct_str or ""))
                self.root.after(0, lambda: self._update_status(
                    "风云四号影像已更新 | 风云四号 FY-4B", color=GREEN))
                self.root.after(0, self._update_fy4_info)
            else:
                self.root.after(0, lambda: self.fy4_preview.config(
                    text="❌ 获取失败\n数据源暂时不可用，请稍后重试", fg=ACCENT))
                self.root.after(0, lambda: self._update_status("❌ 获取失败", color=ACCENT))
        except Exception as e:
            logger.error(f"FY4 fetch error: {e}")
            self.root.after(0, lambda: self.fy4_preview.config(text=f"❌ {str(e)[:60]}", fg=ACCENT))
            self.root.after(0, lambda: self._update_status(f"❌ {e}", color=ACCENT))

    def _set_fy4_wallpaper(self):
        if not self.fy4_image_path or not Path(self.fy4_image_path).exists():
            messagebox.showwarning("提示", "请先获取风云四号影像")
            return
        style = self.config.get("wallpaper_style", "fill")
        try:
            ct = get_fy4_capture_time()
            ct_str = ct.strftime("%Y-%m-%d %H:%M") if ct else None
        except Exception:
            ct_str = None
        now = datetime.now()
        wp_path = watermark_image(
            self.fy4_image_path,
            left_text="来源: 风云四号 FY-4B (中国)",
            right_text=f"拍摄时间: {ct_str or now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
            output_key="fy4_fy4b",
        )
        if set_wallpaper(wp_path, "fy4_fy4b", style=style):
            self._update_status("壁纸已设置 | 风云四号 FY-4B (中国) | 后台持续自动更新", color=GREEN)
        else:
            messagebox.showerror("错误", "壁纸设置失败")

    # ========== 风云四号自动刷新 ==========
    def _toggle_fy4_auto_refresh(self):
        self.fy4_auto_refresh = not self.fy4_auto_refresh
        self.config["fy4_auto_refresh"] = self.fy4_auto_refresh
        save_config(self.config)
        if self.fy4_auto_refresh:
            self.btn_fy4_auto.set_text("🔄 自动刷新: 开")
            self.btn_fy4_auto._bg = GREEN
            self.btn_fy4_auto._hover_bg = "#6ee7c5"
            self.btn_fy4_auto._draw(GREEN)
            self._start_fy4_refresh_timer()
            self._update_status("风云四号自动刷新已开启", color=GREEN)
        else:
            self.btn_fy4_auto.set_text("🔄 自动刷新: 关")
            self.btn_fy4_auto._bg = ACCENT2
            self.btn_fy4_auto._hover_bg = BG_CARD_HOVER
            self.btn_fy4_auto._draw(ACCENT2)
            self._stop_fy4_refresh_timer()
            self._update_status("风云四号自动刷新已关闭")

    def _start_fy4_refresh_timer(self):
        if not self.fy4_auto_refresh:
            return
        if self._fy4_timer_id:
            self.root.after_cancel(self._fy4_timer_id)
        self._fy4_next_refresh = datetime.now() + timedelta(minutes=self.fy4_refresh_interval)
        self._update_fy4_countdown()
        self._fy4_timer_id = self.root.after(1000, self._fy4_tick)

    def _stop_fy4_refresh_timer(self):
        if self._fy4_timer_id:
            self.root.after_cancel(self._fy4_timer_id)
            self._fy4_timer_id = None
        self._fy4_next_refresh = None
        self.fy4_countdown.config(text="")

    def _fy4_tick(self):
        if not self.fy4_auto_refresh:
            return
        now = datetime.now()
        remaining = max(0, (self._fy4_next_refresh - now).total_seconds())
        if remaining <= 0:
            self._fy4_next_refresh = now + timedelta(minutes=self.fy4_refresh_interval)
            self.fy4_countdown.config(text="⏳ 刷新中...")
            size = int(self.selected_fy4_size.get())
            threading.Thread(target=self._do_fy4_auto_refresh, args=(size,), daemon=True).start()
        else:
            self._update_fy4_countdown()
        self._fy4_timer_id = self.root.after(1000, self._fy4_tick)

    def _update_fy4_countdown(self):
        if not self._fy4_next_refresh:
            return
        remaining = max(0, (self._fy4_next_refresh - datetime.now()).total_seconds())
        m, s = int(remaining // 60), int(remaining % 60)
        self.fy4_countdown.config(text=f"⏱ {m:02d}:{s:02d}", fg=FG_DIM if m > 1 else YELLOW)

    def _do_fy4_auto_refresh(self, size: int):
        try:
            path = fetch_fy4_image(target_size=size, force=True)
            if not path:
                return
            self.fy4_image_path = path
            try:
                ct = get_fy4_capture_time()
                ct_str = ct.strftime("%Y-%m-%d %H:%M") if ct else None
            except Exception:
                ct_str = None
            self.root.after(0, lambda: self._load_preview(
                path, self.fy4_preview, self.fy4_status,
                "🇨🇳 风云四号 FY-4B", ct_str or ""))
            if self.data_source == "fy4":
                style = self.config.get("wallpaper_style", "fill")
                now = datetime.now()
                wp_path = watermark_image(path,
                    left_text="来源: 风云四号 FY-4B (中国)",
                    right_text=f"拍摄时间: {ct_str or now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
                    output_key="fy4_fy4b")
                set_wallpaper(wp_path, "fy4_fy4b", style=style)
                self.root.after(0, lambda: self._update_status(
                    f"🇨🇳 FY-4B 自动刷新 | {now.strftime('%H:%M')} | 壁纸同步更新", color=GREEN))
            else:
                self.root.after(0, lambda: self._update_status("🇨🇳 风云四号已自动刷新", color=GREEN))
            self.root.after(0, self._update_fy4_info)
        except Exception as e:
            logger.error(f"FY4 auto-refresh error: {e}")

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("420x480")
        win.configure(bg=BG_MAIN)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="⚙ 设置", bg=BG_MAIN, fg="white",
                 font=FONT_TITLE).pack(pady=12)

        # NASA API Key
        f1 = tk.Frame(win, bg=BG_MAIN)
        f1.pack(fill="x", padx=30, pady=4)
        tk.Label(f1, text="NASA API Key:", bg=BG_MAIN, fg=FG_TEXT, font=FONT_BODY).pack(anchor="w")
        api_entry = tk.Entry(f1, bg=BG_INPUT, fg=FG_TEXT, insertbackground=FG_TEXT,
                             font=FONT_BODY, relief="flat")
        api_entry.pack(fill="x", pady=2, ipady=3)
        api_entry.insert(0, self.config.get("api_key", DEFAULT_API_KEY))

        # 壁纸样式
        f_ws = tk.Frame(win, bg=BG_MAIN)
        f_ws.pack(fill="x", padx=30, pady=4)
        tk.Label(f_ws, text="壁纸样式:", bg=BG_MAIN, fg=FG_TEXT, font=FONT_BODY).pack(anchor="w")
        ws_frame = tk.Frame(f_ws, bg=BG_MAIN)
        ws_frame.pack(fill="x", pady=2)
        wp_style = tk.StringVar(value=self.config.get("wallpaper_style", "fill"))
        styles_cn = [("居中", "center"), ("平铺", "tile"), ("拉伸", "stretch"),
                     ("适应", "fit"), ("填充(推荐)", "fill")]
        for cn, val in styles_cn:
            tk.Radiobutton(ws_frame, text=cn, variable=wp_style, value=val,
                           bg=BG_MAIN, fg=FG_TEXT, selectcolor=BG_INPUT,
                           activebackground=BG_MAIN, activeforeground=FG_TEXT,
                           font=FONT_SMALL).pack(side="left", padx=5)

        # 自动更新
        f2 = tk.Frame(win, bg=BG_MAIN)
        f2.pack(fill="x", padx=30, pady=4)
        auto_var = tk.BooleanVar(value=self.config.get("auto_update", True))
        tk.Checkbutton(f2, text="启用自动更新壁纸", variable=auto_var,
                       bg=BG_MAIN, fg=FG_TEXT, selectcolor=BG_INPUT,
                       activebackground=BG_MAIN, activeforeground=FG_TEXT,
                       font=FONT_BODY).pack(anchor="w")

        # HD
        f4 = tk.Frame(win, bg=BG_MAIN)
        f4.pack(fill="x", padx=30, pady=4)
        hd_var = tk.BooleanVar(value=self.config.get("hd", True))
        tk.Checkbutton(f4, text="优先下载高清图片 (NASA APOD)", variable=hd_var,
                       bg=BG_MAIN, fg=FG_TEXT, selectcolor=BG_INPUT,
                       activebackground=BG_MAIN, activeforeground=FG_TEXT,
                       font=FONT_BODY).pack(anchor="w")

        # 开机自启动
        f5 = tk.Frame(win, bg=BG_MAIN)
        f5.pack(fill="x", padx=30, pady=4)
        autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(f5, text="开机自启动", variable=autostart_var,
                       bg=BG_MAIN, fg=FG_TEXT, selectcolor=BG_INPUT,
                       activebackground=BG_MAIN, activeforeground=FG_TEXT,
                       font=FONT_BODY).pack(anchor="w")
        tk.Label(f5, text="开机时自动启动软件并在后台运行",
                 bg=BG_MAIN, fg=FG_DIM, font=FONT_SMALL).pack(anchor="w", padx=22)

        def save():
            self.config["api_key"] = api_entry.get().strip() or DEFAULT_API_KEY
            self.config["wallpaper_style"] = wp_style.get()
            self.config["auto_update"] = auto_var.get()
            self.config["hd"] = hd_var.get()

            # 开机自启动
            want_autostart = autostart_var.get()
            if want_autostart != is_autostart_enabled():
                if set_autostart(want_autostart):
                    self.config["autostart"] = want_autostart
                    self._update_status(
                        "开机自启动已开启" if want_autostart else "开机自启动已关闭",
                        color=GREEN)
                else:
                    messagebox.showerror("错误", "开机自启动设置失败，请检查权限")
            else:
                self.config["autostart"] = want_autostart

            save_config(self.config)
            win.destroy()
            self._update_status("设置已保存", color=GREEN)

        ModernButton(win, text="💾 保存", command=save,
                     width=100, height=34, bg=ACCENT).pack(pady=15)

    # ========== 使用说明 ==========
    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("使用说明")
        win.geometry("540x520")
        win.configure(bg=BG_MAIN)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="📖 使用说明", bg=BG_MAIN, fg="white",
                 font=FONT_TITLE).pack(pady=12)

        help_text = """Live Earth Wallpaper - 卫星壁纸

【三大数据源模式】
点击顶部的标签切换数据源：

🔭 天文图片 — NASA APOD 每日精选
• 首次启动自动获取近 10 天图片
• 左侧选择分类浏览：星云、星系、行星等 10 个类别
• 点击图片设为壁纸，支持导航浏览
• 每天在设定时间自动更新

🛰 卫星影像 — 多卫星实时影像
• 支持 6 颗地球静止卫星：
  GOES-16/18 (美洲)、Himawari-8 (亚太)、
  GK2A (韩国)、Meteosat (欧洲/非洲/印度洋)
• 颜色模式：自然色 / 地球色 (含夜景)
• 分辨率：标准 / 高清 / 超清
• 基于 CIRA RAMMB-Slider 数据
• 开启自动刷新，每 10 分钟自动更新

☀ 太阳观测 — NASA SDO 太阳图像
• 多个观测波段：
  304 Å (色球层)、171 Å (日冕)、
  连续光球 (太阳黑子)、带磁场线叠加
• 数据来源：NASA 太阳动力学天文台
• 约每 15-60 分钟更新一张

【壁纸样式】
在「设置」中选择：居中 / 平铺 / 拉伸 / 适应 / 填充

【NASA API Key】
默认使用 DEMO_KEY（每小时限流 30 次）。
建议访问 https://api.nasa.gov/ 申请免费 Key。

【数据存储】
配置和缓存在 %USERPROFILE%\\.nasa_wallpaper\\ 目录

【关闭与后台运行】
• 点击右上角 X 可选择「最小化到任务栏」或「退出」
• 最小化后后台持续更新壁纸
• 壁纸右上角标注来源和拍摄时间
"""

        text = tk.Text(win, bg=BG_INPUT, fg=FG_TEXT, font=FONT_BODY,
                       relief="flat", wrap="word", padx=15, pady=10, height=22, width=55)
        text.pack(fill="both", expand=True, padx=20, pady=5)
        text.insert("1.0", help_text)
        text.config(state="disabled")

        ModernButton(win, text="知道了", command=win.destroy,
                     width=80, height=32, bg=ACCENT2, hover_bg=BG_CARD_HOVER).pack(pady=8)

    # ========== 状态/自动启动 ==========
    def _update_status(self, text: str, color: str = FG_SECONDARY):
        self.status_bar.config(text=text, fg=color)

    def _sched_pulse_tick(self):
        """调度器指示灯呼吸动画（规范 §8.10）：深浅绿交替模拟 opacity 脉冲，纯视觉。"""
        try:
            self._sched_pulse_on = not self._sched_pulse_on
            fill = "#2A6E56" if self._sched_pulse_on else GREEN
            self.sched_light.delete("all")
            self.sched_light.create_oval(1, 1, 9, 9, fill=fill, outline="")
            self._sched_pulse_id = self.root.after(900, self._sched_pulse_tick)
        except tk.TclError:
            pass  # 窗口已销毁

    def _auto_fetch_on_startup(self):
        self._update_status("⏳ 首次启动，正在自动获取 NASA 图片...", color=YELLOW)
        self.apod_preview.config(text="⏳ 首次启动\n\n正在从 NASA 获取卫星图片...\n请稍候", fg=FG_DIM)
        self.apod_info.config(text="数据来源: NASA APOD API | 首次运行自动拉取近 10 天图片")
        threading.Thread(target=self._do_auto_fetch, daemon=True).start()

    def _do_auto_fetch(self):
        try:
            end = datetime.now()
            start = end - timedelta(days=10)
            api_key = self.config.get("api_key") or DEFAULT_API_KEY
            self.root.after(0, lambda: self._update_status("⏳ 正在连接 NASA API...", color=YELLOW))
            images = fetch_apod_range(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                api_key=api_key,
            )
            if images:
                metadata = load_metadata()
                for img in images:
                    metadata["images"][img.date] = img.to_dict()
                save_metadata(metadata)
                self.metadata = metadata
                self.root.after(0, lambda: self._on_auto_fetch_done(len(images)))
            else:
                self.root.after(0, lambda: self._update_status(
                    "⚠ NASA API 暂时不可用，请稍后手动获取", color=ACCENT))
                self.root.after(0, lambda: self.apod_preview.config(
                    text="⚠ 首次拉取失败\n\nNASA API 暂时不可用\n请稍后点击「获取历史」重试", fg=YELLOW))
        except Exception as e:
            logger.error(f"Auto-fetch error: {e}")
            self.root.after(0, lambda: self._update_status(f"⚠ 自动获取失败: {e}", color=ACCENT))

    def _on_auto_fetch_done(self, count: int):
        self._rebuild_category_data()
        self._refresh_ui()
        self._update_status(f"已自动获取 {count} 张 NASA 图片，选一个分类设为壁纸吧", color=GREEN)

    def _check_auto_startup(self):
        if not self.metadata.get("images"):
            self._auto_fetch_on_startup()
        else:
            self._update_status("就绪")

    # ========== 关闭行为 ==========
    # ========== 关闭 / 托盘 ==========
    def _on_close(self):
        """点击 X 按钮时弹出选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("退出选项")
        dialog.geometry("380x200")
        dialog.configure(bg=BG_MAIN)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        dw, dh = dialog.winfo_width(), dialog.winfo_height()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dialog.geometry(f"+{rx + (rw - dw) // 2}+{ry + (rh - dh) // 2}")

        tk.Label(dialog, text="Live Earth Wallpaper", bg=BG_MAIN, fg="white",
                 font=FONT_TITLE).pack(pady=(18, 4))
        tk.Label(dialog, text="请选择关闭方式", bg=BG_MAIN, fg=FG_DIM,
                 font=FONT_BODY).pack(pady=(0, 12))

        btn_frame = tk.Frame(dialog, bg=BG_MAIN)
        btn_frame.pack(pady=4)

        def do_minimize():
            dialog.destroy()
            self._minimize_to_tray()

        def do_quit():
            dialog.destroy()
            self._quit_app()

        ModernButton(btn_frame, text="— 最小化到状态栏 —",
                     command=do_minimize,
                     width=150, height=38, bg=BLUE, hover_bg=BLUE_HOVER,
                     font=(FONT_FAMILY[0], 10)).pack(side="left", padx=8)

        ModernButton(btn_frame, text="✕ 退出程序",
                     command=do_quit,
                     width=120, height=38, bg=ACCENT, hover_bg=ACCENT_HOVER,
                     font=(FONT_FAMILY[0], 10)).pack(side="left", padx=8)

        tk.Label(dialog, text="最小化后后台持续更新 | 在状态栏右键恢复窗口",
                 bg=BG_MAIN, fg=FG_DIM, font=FONT_SMALL).pack(pady=(8, 0))

    def _minimize_to_tray(self):
        """最小化到系统托盘"""
        if self.tray_icon is not None:
            self.root.withdraw()
            return

        # 创建托盘图标（简单的 64x64 地球图标）
        icon_img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(icon_img)
        # 画一个简单的圆形地球
        draw.ellipse([4, 4, 60, 60], fill="#2d8cf0", outline="#1a6fd4", width=2)
        # 画一个简化的大陆轮廓
        draw.ellipse([14, 12, 40, 36], fill="#4ecca3")
        draw.ellipse([22, 42, 50, 58], fill="#4ecca3")

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._restore_from_tray, default=True),
            pystray.MenuItem("退出程序", self._quit_from_tray),
        )

        self.tray_icon = pystray.Icon(
            "LivingEarthWallpaper",
            icon_img,
            "Live Earth Wallpaper",
            menu,
        )

        self.root.withdraw()
        self._update_status("已最小化到状态栏，后台持续更新壁纸", color=GREEN)

        # 在后台线程运行托盘图标
        import threading
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _restore_from_tray(self):
        """从状态栏恢复窗口"""
        self.root.after(0, self._do_restore)

    def _do_restore(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._update_status("窗口已恢复", color=GREEN)

    def _quit_from_tray(self):
        """从状态栏退出"""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self._quit_app()

    def _quit_app(self):
        """完全退出程序"""
        if getattr(self, "_sched_pulse_id", None):
            try:
                self.root.after_cancel(self._sched_pulse_id)
            except Exception:
                pass
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        stop_scheduler()
        self.root.destroy()


def main():
    root = tk.Tk()
    NASAApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
