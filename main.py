"""Live Earth Wallpaper - 多数据源卫星壁纸软件
UI 美化版本 — "Cosmic Observatory" 深空暗色设计系统 v5.0
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageTk

from config import (
    load_config, save_config, load_metadata, save_metadata,
    IMAGE_CACHE_DIR, DEFAULT_API_KEY, CATEGORIES, ALL_CATEGORY,
    WALLPAPER_STYLES,
)
from nasa_api import fetch_apod_range, download_image, ApodImage
from categorizer import categorize_image, get_category_name, get_all_category_keys
from wallpaper import set_wallpaper, watermark_image
from scheduler import start_scheduler, stop_scheduler, is_scheduler_running, check_and_update
from providers import GEOSTATIONARY_SATELLITES, SDO_BANDS, fetch_satellite_image, fetch_sdo_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# =====================================================================
# 设计令牌 (Design Tokens) — "Cosmic Observatory" v5.0
# =====================================================================
# 基础表面 — 深空藏蓝
BG_APP = "#080B14"
BG_SURFACE = "#0D1220"
BG_CARD = "#131A2B"
BG_CARD_HOVER = "#1A2238"
BG_ELEVATED = "#1E2740"
BG_INPUT = "#0F1626"

# 侧边栏
BG_SIDEBAR = "#0A0E1A"
BG_SIDEBAR_HOVER = "#141A2E"

# 文字层级
TEXT_PRIMARY = "#E8ECF4"
TEXT_SECONDARY = "#A8B0C8"
TEXT_TERTIARY = "#6B7390"
TEXT_DISABLED = "#3D4459"

# 边框 (rgba via 8-digit hex, Tk 8.6+)
BORDER_SUBTLE = "#1E2740"   # was #FFFFFF10, Tk on Windows rejects 8-digit hex
BORDER_DEFAULT = "#2C3A5A"   # was #FFFFFF1A
BORDER_STRONG = "#3D4459"    # was #FFFFFF29

# 数据源强调色 (Data Source Accents)
APOD_PRIMARY = "#7C5CFC"; APOD_LIGHT = "#9D7FFF"; APOD_GLOW = "#2D1E50"  # was #7C5CFC40
SAT_PRIMARY = "#00B4D8";  SAT_LIGHT = "#33C9E8";  SAT_GLOW = "#0A2E3A"   # was #00B4D840
FY4_PRIMARY = "#E8453C";  FY4_LIGHT = "#FF6B60";  FY4_GLOW = "#3D1518"   # was #E8453C40
SDO_PRIMARY = "#FF8C00";  SDO_LIGHT = "#FFAA33";  SDO_GLOW = "#3A2A10"   # was #FF8C0040

ACCENTS = {
    "apod":     {"primary": APOD_PRIMARY, "light": APOD_LIGHT, "glow": APOD_GLOW},
    "satellite":{"primary": SAT_PRIMARY,  "light": SAT_LIGHT,  "glow": SAT_GLOW},
    "sdo":      {"primary": SDO_PRIMARY,  "light": SDO_LIGHT,  "glow": SDO_GLOW},
}

# 语义色
SUCCESS = "#4ECCA3"; SUCCESS_BG = "#0F2E24"  # was #4ECCA320
WARNING = "#F9D423"
ERROR = "#EF4444"
INFO = "#3B82F6"

# 主行动按钮 CTA
CTA = "#E94560"; CTA_HOVER = "#FF6B81"; CTA_GLOW = "#3D1518"  # was #E9456040

# 字体
FONT_SANS = ("Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Arial")
FONT_MONO = ("Cascadia Code", "JetBrains Mono", "Consolas", "Courier New")


def F(size, weight="normal"):
    return (FONT_SANS[0], size, weight)


FONT_BRAND = F(16, "bold")
FONT_SUBTITLE = F(10)
FONT_PANEL_TITLE = F(14, "bold")
FONT_MODAL_TITLE = F(15, "bold")
FONT_BODY = F(13)
FONT_SECONDARY = F(12)
FONT_LABEL = F(11)
FONT_SMALL = F(11)
FONT_TINY = F(10)
FONT_TINY_BOLD = F(10, "bold")

# 兼容旧业务逻辑使用的别名
ACCENT = CTA
ACCENT_HOVER = CTA_HOVER
ACCENT2 = "#0F3460"
BLUE = "#2D8CF0"
BLUE_HOVER = "#4AA3F7"
GREEN = SUCCESS
YELLOW = WARNING
FG_DIM = TEXT_TERTIARY

PLACEHOLDER = {
    "apod": "📷\n暂无图片\n\n点击「获取历史」拉取 NASA 图片",
    "satellite": "🛰\n选择卫星后点击「获取最新影像」",
    "sdo": "☀\n选择波段后点击「获取最新太阳图」",
}

APP_VERSION = "v2.0.1"


# =====================================================================
# 通用绘图工具
# =====================================================================
def _round_rect(c, x1, y1, x2, y2, r, **kw):
    """在画布上绘制圆角矩形 (tkinter 无原生圆角)"""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


# =====================================================================
# 现代按钮 (Canvas 圆角按钮)
# =====================================================================
class ModernButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=100, height=32,
                 bg=CTA, fg="white", hover_bg=CTA_HOVER, font=FONT_BODY,
                 glow=None, **kw):
        super().__init__(parent, width=width, height=height, bg=BG_CARD,
                         highlightthickness=0, cursor="hand2", **kw)
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._font = font
        self._glow = glow
        self._radius = 6
        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._draw(self._hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self._bg))
        self.bind("<Button-1>", self._on_click)

    def _draw(self, color):
        self.delete("all")
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        if self._glow and color == self._hover_bg:
            _round_rect(self, 0, 2, w, h + 2, self._radius,
                        fill=self._glow, outline="")
        _round_rect(self, 0, 0, w, h, self._radius, fill=color, outline="")
        self.create_text(w // 2, h // 2, text=self._text, fill=self._fg, font=self._font)

    def _on_click(self, event):
        if self._command:
            self._command()

    def set_text(self, text):
        self._text = text
        self._draw(self._bg)

    def restyle(self, bg, hover_bg, fg="white", redraw=True):
        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        if redraw:
            self._draw(bg)

    def current_bg(self):
        return self._bg


# =====================================================================
# 分段控件 (Segmented Control)
# =====================================================================
class SegmentedControl(tk.Canvas):
    def __init__(self, parent, options, variable, accent=APOD_PRIMARY,
                 command=None, height=30, font=FONT_SECONDARY):
        self._opts = options
        self._var = variable
        self._accent = accent
        self._command = command
        self._font = font
        self._h = height
        pad = 6
        self._seg_w = {}
        total = 6
        for val, lab in options:
            w = int(len(lab) * 7) + pad * 2 + 4
            self._seg_w[val] = w
            total += w
        self._total_w = total
        super().__init__(parent, width=total, height=height,
                         bg=BG_INPUT, highlightthickness=0, bd=0)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _draw(self):
        self.delete("all")
        W = self.winfo_width() or self._total_w
        _round_rect(self, 0, 0, W, self._h, 6, fill=BG_INPUT, outline="")
        n = len(self._opts)
        if n == 0:
            return
        seg_w = (W - 6) / n
        x = 3
        for val, lab in self._opts:
            sel = (self._var.get() == val)
            if sel:
                _round_rect(self, x, 3, x + seg_w, self._h - 3, 4, fill=self._accent, outline="")
            col = "white" if sel else TEXT_TERTIARY
            self.create_text(x + seg_w / 2, self._h / 2, text=lab, fill=col,
                             font=self._font, anchor="center")
            x += seg_w

    def _on_click(self, e):
        W = self.winfo_width() or self._total_w
        n = len(self._opts)
        if n == 0:
            return
        seg_w = (W - 6) / n
        idx = int((e.x - 3) / seg_w)
        if 0 <= idx < n:
            val = self._opts[idx][0]
            if self._var.get() != val:
                self._var.set(val)
                self._draw()
                if self._command:
                    self._command(val)

    def set_accent(self, color):
        self._accent = color
        self._draw()

    def set_value(self, val):
        self._var.set(val)
        self._draw()


# =====================================================================
# 开关 (Toggle Switch)
# =====================================================================
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable=None, command=None, width=36, height=20):
        super().__init__(parent, width=width, height=height,
                         bg=BG_APP, highlightthickness=0, bd=0)
        self._var = variable or tk.BooleanVar()
        self._command = command
        self._w = width
        self._h = height
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self, on=None):
        if on is None:
            on = self._var.get()
        self.delete("all")
        r = self._h / 2
        track = SUCCESS if on else BG_INPUT
        _round_rect(self, 0, 0, self._w, self._h, r,
                    fill=track, outline=BORDER_DEFAULT if not on else "")
        knob = self._h - 4
        kx = 2 if not on else (self._w - knob - 2)
        ky = 2
        self.create_oval(kx, ky, kx + knob, ky + knob, fill="white", outline="")

    def _toggle(self, e):
        self._var.set(not self._var.get())
        self._draw()
        if self._command:
            self._command(self._var.get())

    def set_state(self, v):
        self._var.set(v)
        self._draw()

    def get(self):
        return self._var.get()


# =====================================================================
# 加载遮罩 (Loading Overlay + 旋转 Spinner)
# =====================================================================
class LoadingOverlay(tk.Frame):
    def __init__(self, parent, accent=APOD_PRIMARY):
        super().__init__(parent, bg="#080B14")
        self._accent = accent
        self._spin = tk.Canvas(self, width=34, height=34, bg="#080B14", highlightthickness=0)
        self._spin.pack(expand=True)
        self._label = tk.Label(self, text="加载中…", bg="#080B14",
                               fg=TEXT_SECONDARY, font=FONT_SMALL)
        self._label.place(relx=0.5, rely=0.64, anchor="center")
        self._angle = 0
        self._running = False
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self._anim()

    def set_accent(self, c):
        self._accent = c

    def show(self):
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self._running = True

    def hide(self):
        self.place_forget()
        self._running = False

    def _anim(self):
        if not self.winfo_exists():
            return
        self._spin.delete("all")
        if self._running:
            self._spin.create_arc(2, 2, 32, 32, start=self._angle, extent=300,
                                  style="arc", outline=self._accent, width=3)
            self._angle = (self._angle + 30) % 360
        self.after(60, self._anim)


# =====================================================================
# 脉动指示灯 (Pulse Dot)
# =====================================================================
class PulseDot(tk.Canvas):
    def __init__(self, parent, color=SUCCESS, size=10, bg=BG_APP):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._color = color
        self._size = size
        self._t = 0
        self._on = True
        self._draw()

    def _draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        if self._on:
            r = self._size / 2
            rr = r * (0.65 + 0.35 * abs(math.sin(self._t)))
            cx = cy = self._size / 2
            self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                             fill=self._color, outline="")
        self._t += 0.18
        self.after(120, self._draw)

    def set_color(self, c):
        self._color = c

    def set_on(self, v):
        self._on = v


# =====================================================================
# 自定义下拉菜单 (Dropdown)
# =====================================================================
class Dropdown(tk.Frame):
    def __init__(self, parent, options, variable, on_change=None,
                 width=180, accent=SAT_PRIMARY):
        super().__init__(parent, bg=BG_INPUT, highlightbackground=BORDER_DEFAULT,
                         highlightthickness=1)
        self._opts = options
        self._var = variable
        self._on_change = on_change
        self._accent = accent
        self._open = False
        self._pop = None
        self._btn = tk.Label(self, bg=BG_INPUT, fg=TEXT_PRIMARY, font=FONT_BODY,
                             anchor="w", padx=10, cursor="hand2")
        self._btn.pack(side="left", fill="both", expand=True)
        self._arrow = tk.Label(self, text="▾", bg=BG_INPUT, fg=TEXT_TERTIARY,
                               font=FONT_BODY, padx=8, cursor="hand2")
        self._arrow.pack(side="right")
        for w in (self, self._btn, self._arrow):
            w.bind("<Button-1>", self._toggle)
        self._sync_text()

    def _sync_text(self):
        key = self._var.get()
        name = dict(self._opts).get(key, key)
        self._btn.config(text=name)

    def _toggle(self, e=None):
        if self._open:
            self._close()
        else:
            self._open_pop()

    def _open_pop(self):
        self._open = True
        self._arrow.config(text="▴")
        self.config(highlightbackground=self._accent)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        pop = tk.Toplevel(self)
        pop.wm_overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.geometry(f"+{x}+{y}")
        pop.config(bg=BG_ELEVATED, highlightbackground=BORDER_DEFAULT, highlightthickness=1)
        self._pop = pop
        for key, name in self._opts:
            row = tk.Frame(pop, bg=BG_ELEVATED)
            row.pack(fill="x")
            dot = tk.Label(row, text="●", fg=self._accent, bg=BG_ELEVATED,
                           font=FONT_TINY, width=2)
            dot.pack(side="left", padx=(10, 6))
            lbl = tk.Label(row, text=name, bg=BG_ELEVATED, fg=TEXT_SECONDARY,
                           font=FONT_BODY, anchor="w")
            lbl.pack(side="left", fill="x", expand=True, pady=7)
            row.bind("<Enter>", lambda e, r=row: r.config(bg=BG_CARD_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.config(bg=BG_ELEVATED))
            row.bind("<Button-1>", lambda e, k=key: self._select(k))
        pop.bind("<FocusOut>", lambda e: self._close())
        pop.focus_set()

    def _select(self, key):
        self._var.set(key)
        self._sync_text()
        self._close()
        if self._on_change:
            self._on_change(key)

    def _close(self):
        self._open = False
        self._arrow.config(text="▾")
        self.config(highlightbackground=BORDER_DEFAULT)
        if self._pop:
            self._pop.destroy()
            self._pop = None


# =====================================================================
# 侧边栏导航项 (Nav Item)
# =====================================================================
class NavItem(tk.Frame):
    def __init__(self, parent, icon, label, badge, badge_bg, accent, command):
        super().__init__(parent, bg=BG_SIDEBAR, height=40)
        self.pack_propagate(False)
        self._accent = accent
        self._command = command
        self._active = False
        self._badge = badge
        self._badge_bg = badge_bg

        self._bar = tk.Canvas(self, width=3, height=40, bg=BG_SIDEBAR,
                              highlightthickness=0, bd=0)
        self._bar.pack(side="left")
        self._icon = tk.Label(self, text=icon, bg=BG_SIDEBAR, fg=TEXT_SECONDARY,
                              font=F(14))
        self._icon.pack(side="left", padx=(10, 10))
        self._label = tk.Label(self, text=label, bg=BG_SIDEBAR, fg=TEXT_SECONDARY,
                               font=FONT_BODY, anchor="w")
        self._label.pack(side="left", fill="x", expand=True)
        self._badge_lbl = tk.Label(self, text=badge, bg=badge_bg, fg=accent,
                                   font=FONT_TINY_BOLD, padx=6, pady=1)
        self._badge_lbl.pack(side="right", padx=(0, 12))

        for w in (self, self._icon, self._label, self._badge_lbl):
            w.bind("<Enter>", self._hover_on)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", lambda e: self._command())

    def _set_bg(self, c):
        self.config(bg=c)
        self._bar.config(bg=c)
        self._icon.config(bg=c)
        self._label.config(bg=c)
        self._badge_lbl.config(bg=c)

    def _hover_on(self, e):
        if not self._active:
            self._set_bg(BG_SIDEBAR_HOVER)
            self._icon.config(fg=TEXT_PRIMARY)
            self._label.config(fg=TEXT_PRIMARY)

    def _leave(self, e):
        if not self._active:
            self._set_bg(BG_SIDEBAR)
            self._icon.config(fg=TEXT_SECONDARY)
            self._label.config(fg=TEXT_SECONDARY)

    def set_active(self, v, accent=None):
        self._active = v
        if accent:
            self._accent = accent
            self._badge_lbl.config(fg=accent)
        if v:
            self._set_bg(BG_SIDEBAR_HOVER)
            self._icon.config(fg=TEXT_PRIMARY)
            self._label.config(fg=TEXT_PRIMARY)
            self._bar.delete("all")
            self._bar.create_rectangle(0, 8, 3, 32, fill=self._accent, outline="")
        else:
            self._set_bg(BG_SIDEBAR)
            self._icon.config(fg=TEXT_SECONDARY)
            self._label.config(fg=TEXT_TERTIARY)
            self._bar.delete("all")


# =====================================================================
# 主应用
# =====================================================================
class NASAApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RealEarth - 真实地球壁纸")
        self.root.geometry("1200x780")
        self.root.configure(bg=BG_APP)
        self.root.minsize(1000, 680)
        self.root.resizable(True, True)
        self.root.overrideredirect(True)

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

        self._build_title_bar()
        self._build_ui()
        self._rebuild_category_data()
        self._refresh_ui()
        self._switch_panel(self.data_source)

        start_scheduler()
        self._check_auto_startup()

    # ========== 标题栏 ==========
    def _build_title_bar(self):
        tb = tk.Frame(self.root, bg=BG_SIDEBAR, height=36)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        # 品牌图标 (环形地球)
        brand_icon = tk.Canvas(tb, width=18, height=18, bg=BG_SIDEBAR,
                               highlightthickness=0, bd=0)
        brand_icon.pack(side="left", padx=(14, 8))
        brand_icon.create_oval(1, 1, 17, 17, fill="#1E2740", outline="")
        brand_icon.create_oval(4, 4, 14, 14, fill="#0A0E1A", outline="")
        brand_icon.create_arc(3, 3, 15, 15, start=30, extent=300,
                              style="arc", outline="#4ECCA3", width=2)
        brand_icon.create_arc(3, 3, 15, 15, start=210, extent=300,
                              style="arc", outline="#2D8CF0", width=2)

        brand_txt = tk.Label(tb, text="RealEarth", bg=BG_SIDEBAR, fg=TEXT_PRIMARY,
                             font=FONT_BRAND)
        brand_txt.pack(side="left")
        sub = tk.Label(tb, text="真实地球壁纸", bg=BG_SIDEBAR, fg=TEXT_TERTIARY,
                       font=FONT_SUBTITLE)
        sub.pack(side="left", padx=(6, 0))

        # 窗口控制按钮
        ctrl = tk.Frame(tb, bg=BG_SIDEBAR)
        ctrl.pack(side="right")
        self._title_controls = []

        def make_btn(sym, cmd, hover):
            b = tk.Label(ctrl, text=sym, bg=BG_SIDEBAR, fg=TEXT_SECONDARY,
                         font=("Segoe UI", 10), width=4, cursor="hand2")
            b.pack(side="right", padx=0)
            b.bind("<Enter>", lambda e, w=b, h=hover: w.config(bg=h, fg="white"))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=BG_SIDEBAR, fg=TEXT_SECONDARY))
            b.bind("<Button-1>", lambda e: cmd())
            self._title_controls.append(b)
            return b

        make_btn("✕", self._on_close, "#E8453C")
        make_btn("▢", self._toggle_maximize, "#1E2740")
        make_btn("—", self.root.iconify, "#1E2740")

        # 拖拽
        tb.bind("<Button-1>", self._on_title_drag_start)
        tb.bind("<B1-Motion>", self._on_title_drag)
        brand_txt.bind("<Button-1>", self._on_title_drag_start)
        brand_txt.bind("<B1-Motion>", self._on_title_drag)
        sub.bind("<Button-1>", self._on_title_drag_start)
        sub.bind("<B1-Motion>", self._on_title_drag)
        brand_icon.bind("<Button-1>", self._on_title_drag_start)
        brand_icon.bind("<B1-Motion>", self._on_title_drag)
        self._drag_x = 0
        self._drag_y = 0

    def _on_title_drag_start(self, e):
        if e.widget in self._title_controls:
            return
        self._drag_x = e.x
        self._drag_y = e.y

    def _on_title_drag(self, e):
        if e.widget in self._title_controls:
            return
        x = self.root.winfo_x() + (e.x - self._drag_x)
        y = self.root.winfo_y() + (e.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _toggle_maximize(self):
        try:
            if self.root.state() == "zoomed":
                self.root.state("normal")
            else:
                self.root.state("zoomed")
        except tk.TclError:
            pass

    # ========== UI 构建 ==========
    def _build_ui(self):
        # 主区域
        self.main = tk.Frame(self.root, bg=BG_APP)
        self.main.pack(fill="both", expand=True)

        self._build_sidebar(self.main)
        self.content = tk.Frame(self.main, bg=BG_APP)
        self.content.pack(side="left", fill="both", expand=True)

        self._build_apod_panel()
        self._build_sat_panel()
        self._build_sdo_panel()

        self._build_status_bar()

    # ========== 侧边栏 ==========
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG_SIDEBAR, width=220)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        # 星点装饰
        stars = tk.Canvas(sb, width=220, height=180, bg=BG_SIDEBAR,
                          highlightthickness=0, bd=0)
        stars.pack(fill="x")
        import random
        random.seed(7)
        for _ in range(60):
            x = random.randint(0, 219)
            y = random.randint(0, 179)
            r = random.choice([0.7, 1.0, 1.3])
            a = random.choice(["#6B7390", "#A8B0C8", "#9D7FFF", "#33C9E8"])
            stars.create_oval(x, y, x + r, y + r, fill=a, outline="")

        # 品牌区
        brand = tk.Frame(sb, bg=BG_SIDEBAR)
        brand.pack(fill="x", padx=16, pady=(6, 14))
        earth = tk.Canvas(brand, width=28, height=28, bg=BG_SIDEBAR,
                          highlightthickness=0, bd=0)
        earth.pack(side="left", padx=(0, 10))
        earth.create_oval(1, 1, 27, 27, fill="#0A1A2E", outline="")
        earth.create_arc(2, 2, 26, 26, start=0, extent=360,
                         style="arc", outline="#2D8CF0", width=3)
        earth.create_arc(4, 6, 24, 24, start=200, extent=140,
                         style="arc", outline="#4ECCA3", width=2)
        earth.create_oval(9, 9, 19, 19, fill="#0F3460", outline="")
        btxt = tk.Frame(brand, bg=BG_SIDEBAR)
        btxt.pack(side="left", fill="x")
        tk.Label(btxt, text="RealEarth", bg=BG_SIDEBAR, fg=TEXT_PRIMARY,
                 font=FONT_BRAND).pack(anchor="w")
        tk.Label(btxt, text="真实地球壁纸", bg=BG_SIDEBAR, fg=TEXT_TERTIARY,
                 font=FONT_SUBTITLE).pack(anchor="w")

        # 分节标题
        tk.Label(sb, text="数据源", bg=BG_SIDEBAR, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", padx=16, pady=(4, 6))

        # 导航项
        self.nav_items = {}
        nav_list = [
            ("apod", "🔭", "天文图片", "APOD", APOD_GLOW, APOD_PRIMARY),
            ("satellite", "🛰", "卫星影像", "6 颗", SAT_GLOW, SAT_PRIMARY),
            ("sdo", "☀", "太阳观测", f"{len(SDO_BANDS)} 波段", SDO_GLOW, SDO_PRIMARY),
        ]
        for src, icon, label, badge, bglow, bprim in nav_list:
            item = NavItem(sb, icon, label, badge, bglow, bprim,
                           command=lambda s=src: self._switch_panel(s))
            item.pack(fill="x", padx=10, pady=1)
            self.nav_items[src] = item

        # 底部功能区
        bottom = tk.Frame(sb, bg=BG_SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=10, pady=10)

        def nav_btn(icon, text, cmd):
            b = tk.Frame(bottom, bg=BG_SIDEBAR, cursor="hand2")
            b.pack(fill="x", pady=1)
            tk.Label(b, text=icon, bg=BG_SIDEBAR, fg=TEXT_TERTIARY,
                     font=F(13)).pack(side="left", padx=(6, 10))
            tk.Label(b, text=text, bg=BG_SIDEBAR, fg=TEXT_SECONDARY,
                     font=FONT_BODY).pack(side="left")
            for w in (b, b.winfo_children()[0], b.winfo_children()[1]):
                w.bind("<Enter>", lambda e, f=b: f.config(bg=BG_SIDEBAR_HOVER))
                w.bind("<Leave>", lambda e, f=b: f.config(bg=BG_SIDEBAR))
                w.bind("<Button-1>", lambda e, c=cmd: c())
            return b

        nav_btn("⚙", "设置", self._show_settings)
        nav_btn("📖", "使用说明", self._show_help)
        tk.Label(bottom, text=f"RealEarth {APP_VERSION}", bg=BG_SIDEBAR,
                 fg=TEXT_TERTIARY, font=FONT_TINY).pack(anchor="w", padx=6, pady=(8, 0))

    # ========== 面板脚手架 ==========
    def _panel_scaffold(self, source, title, subtitle, icon):
        accent = ACCENTS[source]
        panel = tk.Frame(self.content, bg=BG_APP)

        # 控制面板
        ctrl = tk.Frame(panel, bg=BG_SURFACE, width=210)
        ctrl.pack(side="left", fill="y")
        ctrl.pack_propagate(False)
        inner = tk.Frame(ctrl, bg=BG_SURFACE)
        inner.pack(fill="both", expand=True, padx=14, pady=16)

        header = tk.Frame(inner, bg=BG_SURFACE)
        header.pack(fill="x", pady=(0, 16))
        ic = tk.Canvas(header, width=22, height=22, bg=BG_SURFACE,
                       highlightthickness=0, bd=0)
        ic.pack(side="left", padx=(0, 8))
        ic.create_oval(1, 1, 21, 21, fill=accent["glow"], outline="")
        ic.create_text(11, 11, text=icon, fill=accent["light"], font=F(12))
        titles = tk.Frame(header, bg=BG_SURFACE)
        titles.pack(side="left", fill="x")
        tk.Label(titles, text=title, bg=BG_SURFACE, fg=TEXT_PRIMARY,
                 font=FONT_PANEL_TITLE).pack(anchor="w")
        tk.Label(titles, text=subtitle, bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_LABEL).pack(anchor="w")

        # 预览列
        prev_col = tk.Frame(panel, bg=BG_APP)
        prev_col.pack(side="left", fill="both", expand=True)

        prev_container = tk.Frame(prev_col, bg=BG_CARD,
                                  highlightbackground=BORDER_DEFAULT,
                                  highlightthickness=1)
        prev_container.pack(fill="both", expand=True, padx=16, pady=16)

        prev_label = tk.Label(prev_container, bg=BG_CARD, text=PLACEHOLDER[source],
                              fg=TEXT_TERTIARY, font=FONT_SECONDARY,
                              justify="center", wraplength=480)
        prev_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 底部信息条
        overlay = tk.Frame(prev_container, bg="#0B0F1A")
        overlay.place(relx=0, rely=1, relwidth=1, height=58, anchor="sw")
        otitle = tk.Label(overlay, text="", bg="#0B0F1A", fg="white",
                          font=F(13, "bold"), anchor="w", padx=16)
        otitle.pack(fill="x", padx=0, pady=(6, 0))
        ometa = tk.Label(overlay, text="", bg="#0B0F1A",
                         fg="#A8B0C8", font=FONT_SMALL, anchor="w", padx=16)
        ometa.pack(fill="x")

        # 水印
        watermark = tk.Label(prev_container, text=f"RealEarth · {source.upper()}",
                             bg=BG_CARD, fg="#A8B0C8",
                             font=(FONT_MONO[0], 10))
        watermark.place(relx=1.0, rely=0.0, x=-16, y=12, anchor="ne")

        # 加载遮罩
        loading = LoadingOverlay(prev_container, accent=accent["primary"])
        loading.hide()

        # 操作栏
        action = tk.Frame(prev_col, bg=BG_APP, height=44)
        action.pack(fill="x", side="bottom")
        action.pack_propagate(False)

        return {
            "panel": panel, "ctrl": ctrl, "inner": inner,
            "prev_col": prev_col, "prev_container": prev_container,
            "prev_label": prev_label, "overlay": overlay,
            "otitle": otitle, "ometa": ometa, "watermark": watermark,
            "loading": loading, "action": action, "accent": accent,
        }

    # ========== APOD 面板 ==========
    def _build_apod_panel(self):
        s = self._panel_scaffold("apod", "天文图片", "NASA APOD 每日精选", "🔭")
        self.panel_apod = s["panel"]

        # 分类列表
        tk.Label(s["inner"], text="图片分类", bg=BG_SURFACE, fg=TEXT_SECONDARY,
                 font=FONT_LABEL).pack(anchor="w", pady=(0, 6))

        # 获取历史按钮 (控制面板底部预留)
        ModernButton(s["inner"], text="📥 获取历史图片", command=self._fetch_history,
                     width=182, height=34, bg=APOD_PRIMARY, hover_bg=APOD_LIGHT,
                     glow=APOD_GLOW).pack(side="bottom", fill="x", pady=(12, 0))

        cat_frame = tk.Frame(s["inner"], bg=BG_INPUT,
                             highlightbackground=BORDER_DEFAULT, highlightthickness=1)
        cat_frame.pack(side="top", fill="both", expand=True)

        cols = ("category", "count")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols, show="headings", height=18)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG_INPUT, foreground=TEXT_SECONDARY,
                        fieldbackground=BG_INPUT, rowheight=28, font=FONT_BODY)
        style.configure("Treeview.Heading", background=BG_CARD, foreground=TEXT_SECONDARY,
                        font=FONT_TINY_BOLD)
        style.map("Treeview",
                  background=[("selected", APOD_GLOW)],
                  foreground=[("selected", APOD_LIGHT)])
        style.configure("Vertical.TScrollbar", background=BG_CARD,
                        troughcolor=BG_APP, arrowcolor=TEXT_TERTIARY,
                        bordercolor=BG_APP, lightcolor=BG_APP, darkcolor=BG_APP)

        self.cat_tree.heading("category", text="分类")
        self.cat_tree.heading("count", text="数量")
        self.cat_tree.column("category", width=150, anchor="w")
        self.cat_tree.column("count", width=44, anchor="center")
        self.cat_tree.pack(side="left", fill="both", expand=True)

        cat_scroll = ttk.Scrollbar(cat_frame, orient="vertical", command=self.cat_tree.yview)
        cat_scroll.pack(side="right", fill="y")
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)

        # 预览
        self.apod_preview = s["prev_label"]
        self.apod_info = s["ometa"]
        self.apod_title = s["otitle"]
        self.apod_loading = s["loading"]

        # 操作栏
        a = s["action"]
        nav = tk.Frame(a, bg=BG_APP)
        nav.pack(side="left")
        self.btn_prev = ModernButton(nav, text="◀", command=self._prev_image,
                                     width=36, height=32, bg=BG_ELEVATED,
                                     hover_bg=BG_CARD_HOVER, fg=TEXT_SECONDARY)
        self.btn_prev.pack(side="left", padx=2)
        self.page_label = tk.Label(nav, text="0 / 0", bg=BG_APP, fg=TEXT_PRIMARY,
                                   font=FONT_BODY, width=10, anchor="center")
        self.page_label.pack(side="left", padx=8)
        self.btn_next = ModernButton(nav, text="▶", command=self._next_image,
                                     width=36, height=32, bg=BG_ELEVATED,
                                     hover_bg=BG_CARD_HOVER, fg=TEXT_SECONDARY)
        self.btn_next.pack(side="left", padx=2)

        rc = tk.Frame(a, bg=BG_APP)
        rc.pack(side="right")
        self.btn_update = ModernButton(rc, text="🔄 更新", command=self._update_now,
                                       width=84, height=32, bg=SUCCESS, hover_bg="#6EE7C5",
                                       fg="#0A1A14", glow=SUCCESS_BG)
        self.btn_update.pack(side="left", padx=2)
        self.btn_wallpaper = ModernButton(rc, text="🖼 设为壁纸", command=self._set_wallpaper,
                                          width=104, height=32, bg=CTA, hover_bg=CTA_HOVER,
                                          glow=CTA_GLOW)
        self.btn_wallpaper.pack(side="left", padx=2)

    # ========== 卫星影像面板 ==========
    def _build_sat_panel(self):
        s = self._panel_scaffold("satellite", "卫星影像", "地球静止卫星实时图", "🛰")
        self.panel_sat = s["panel"]

        # 卫星选择
        tk.Label(s["inner"], text="卫星", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", pady=(0, 5))
        sat_opts = [(k, v["name"]) for k, v in GEOSTATIONARY_SATELLITES.items()]
        self.sat_combo = Dropdown(s["inner"], sat_opts, self.selected_satellite,
                                  on_change=lambda k: self._update_sat_info(),
                                  width=182, accent=SAT_PRIMARY)
        self.sat_combo.pack(fill="x", pady=(0, 14))

        # 颜色模式
        tk.Label(s["inner"], text="颜色模式", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", pady=(0, 5))
        self.sat_color_seg = SegmentedControl(
            s["inner"],
            [("natural_color", "自然色"), ("geocolor", "地球色")],
            self.selected_color, accent=SAT_PRIMARY, command=lambda v: None)
        self.sat_color_seg.pack(fill="x", pady=(0, 14))

        # 分辨率
        tk.Label(s["inner"], text="分辨率", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", pady=(0, 5))
        self.sat_size_var = tk.StringVar(value=str(self.config.get("satellite_size", 1080)))
        self.sat_size_seg = SegmentedControl(
            s["inner"],
            [("688", "标准"), ("1100", "高清"), ("2200", "超清")],
            self.sat_size_var, accent=SAT_PRIMARY)
        self.sat_size_seg.pack(fill="x", pady=(0, 14))

        # 卫星信息卡
        info_card = tk.Frame(s["inner"], bg=BG_CARD,
                             highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        info_card.pack(fill="both", expand=True)
        self.sat_info_label = tk.Label(info_card, text="", bg=BG_CARD,
                                        fg=TEXT_TERTIARY, font=FONT_SMALL, justify="left",
                                        padx=10, pady=10, wraplength=180)
        self.sat_info_label.pack(fill="both", expand=True)

        # 预览
        self.sat_preview = s["prev_label"]
        self.sat_status = s["ometa"]
        self.sat_title = s["otitle"]
        self.sat_loading = s["loading"]

        # 操作栏
        a = s["action"]
        self.btn_sat_fetch = ModernButton(a, text="📡 获取最新影像",
                                          command=self._fetch_satellite,
                                          width=130, height=32, bg=SAT_PRIMARY,
                                          hover_bg=SAT_LIGHT, glow=SAT_GLOW)
        self.btn_sat_fetch.pack(side="left", padx=(16, 2))

        self.btn_sat_auto = ModernButton(a,
                                         text="🔄 自动刷新: 开" if self.sat_auto_refresh else "🔄 自动刷新: 关",
                                         command=self._toggle_sat_auto_refresh,
                                         width=124, height=32,
                                         bg=SUCCESS if self.sat_auto_refresh else ACCENT2,
                                         hover_bg="#6EE7C5" if self.sat_auto_refresh else "#1A4A7A",
                                         glow=SUCCESS_BG if self.sat_auto_refresh else None)
        self.btn_sat_auto.pack(side="left", padx=5)

        self.sat_countdown = tk.Label(a, text="", bg=BG_APP, fg=TEXT_TERTIARY,
                                      font=FONT_SMALL)
        self.sat_countdown.pack(side="left", padx=8)

        right_sc = tk.Frame(a, bg=BG_APP)
        right_sc.pack(side="right", padx=(0, 16))
        self.btn_sat_wp = ModernButton(right_sc, text="🖼 设为壁纸",
                                       command=self._set_sat_wallpaper,
                                       width=104, height=32, bg=CTA, hover_bg=CTA_HOVER,
                                       glow=CTA_GLOW)
        self.btn_sat_wp.pack(side="left", padx=2)

    # ========== SDO 太阳观测面板 ==========
    def _build_sdo_panel(self):
        s = self._panel_scaffold("sdo", "太阳观测", "NASA SDO 太阳动力学天文台", "☀")
        self.panel_sdo = s["panel"]

        tk.Label(s["inner"], text="数据来源", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", pady=(0, 5))
        tk.Label(s["inner"], text="NASA SDO · 太阳动力学天文台", bg=BG_SURFACE,
                 fg=TEXT_SECONDARY, font=FONT_LABEL).pack(anchor="w", pady=(0, 12))

        tk.Label(s["inner"], text="观测波段", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_TINY_BOLD).pack(anchor="w", pady=(0, 5))
        # 波段列表
        band_frame = tk.Frame(s["inner"], bg=BG_SURFACE)
        band_frame.pack(fill="x", pady=(0, 12))
        self.sdo_band_rows = {}
        for key, info in SDO_BANDS.items():
            row = tk.Frame(band_frame, bg=BG_SURFACE, cursor="hand2")
            row.pack(fill="x", pady=1)
            wl = info["name"].split(" ")[0]
            dot = tk.Label(row, text="●", bg=BG_SURFACE, fg=SDO_PRIMARY,
                           font=FONT_TINY, width=2)
            dot.pack(side="left", padx=(2, 6))
            lbl = tk.Label(row, text=info["name"], bg=BG_SURFACE, fg=TEXT_SECONDARY,
                           font=FONT_SMALL, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            wtag = tk.Label(row, text=wl, bg="#3A2A10", fg=SDO_LIGHT,
                            font=(FONT_MONO[0], 9), padx=5, pady=1)
            wtag.pack(side="right", padx=(4, 2))
            for w in (row, dot, lbl, wtag):
                w.bind("<Enter>", lambda e, r=row: r.config(bg=BG_CARD_HOVER))
                w.bind("<Leave>", lambda e, r=row, k=key: self._sdo_band_leave(r, k))
                w.bind("<Button-1>", lambda e, k=key: self._sdo_select_band(k))
            self.sdo_band_rows[key] = (row, lbl, dot)

        # 观测信息卡
        sdo_info_card = tk.Frame(s["inner"], bg=BG_CARD,
                                 highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        sdo_info_card.pack(fill="both", expand=True)
        tk.Label(sdo_info_card, text="拍摄频率\n约每 15-60 分钟\n自动刷新每 60 分钟",
                 bg=BG_CARD, fg=TEXT_TERTIARY, font=FONT_SMALL, justify="left",
                 padx=10, pady=10).pack(fill="both")

        # 预览
        self.sdo_preview = s["prev_label"]
        self.sdo_status = s["ometa"]
        self.sdo_title = s["otitle"]
        self.sdo_loading = s["loading"]

        # 操作栏
        a = s["action"]
        self.btn_sdo_fetch = ModernButton(a, text="📡 获取最新太阳图",
                                          command=self._fetch_sdo,
                                          width=130, height=32, bg=SDO_PRIMARY,
                                          hover_bg=SDO_LIGHT, glow=SDO_GLOW)
        self.btn_sdo_fetch.pack(side="left", padx=(16, 2))

        self.btn_sdo_auto = ModernButton(a,
                                         text="🔄 自动刷新: 开" if self.sdo_auto_refresh else "🔄 自动刷新: 关",
                                         command=self._toggle_sdo_auto_refresh,
                                         width=124, height=32,
                                         bg=SUCCESS if self.sdo_auto_refresh else ACCENT2,
                                         hover_bg="#6EE7C5" if self.sdo_auto_refresh else "#1A4A7A",
                                         glow=SUCCESS_BG if self.sdo_auto_refresh else None)
        self.btn_sdo_auto.pack(side="left", padx=5)

        self.sdo_countdown = tk.Label(a, text="", bg=BG_APP, fg=TEXT_TERTIARY,
                                      font=FONT_SMALL)
        self.sdo_countdown.pack(side="left", padx=8)

        right_sdo = tk.Frame(a, bg=BG_APP)
        right_sdo.pack(side="right", padx=(0, 16))
        self.btn_sdo_wp = ModernButton(right_sdo, text="🖼 设为壁纸",
                                       command=self._set_sdo_wallpaper,
                                       width=104, height=32, bg=CTA, hover_bg=CTA_HOVER,
                                       glow=CTA_GLOW)
        self.btn_sdo_wp.pack(side="left", padx=2)

        self._sdo_select_band(self.selected_sdo_band.get(), redraw_only=True)

    def _sdo_band_leave(self, row, key):
        if self.selected_sdo_band.get() == key:
            row.config(bg=SDO_GLOW)
        else:
            row.config(bg=BG_SURFACE)

    def _sdo_select_band(self, key, redraw_only=False):
        self.selected_sdo_band.set(key)
        for k, (row, lbl, dot) in self.sdo_band_rows.items():
            if k == key:
                row.config(bg=SDO_GLOW)
                lbl.config(fg=SDO_LIGHT)
                dot.config(fg=SDO_LIGHT)
            else:
                row.config(bg=BG_SURFACE)
                lbl.config(fg=TEXT_SECONDARY)
                dot.config(fg=SDO_PRIMARY)
        if not redraw_only:
            self.config["sdo_band"] = key
            save_config(self.config)

    # ========== 状态栏 ==========
    def _build_status_bar(self):
        sb = tk.Frame(self.root, bg=BG_SURFACE, height=28)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        sb.config(highlightbackground=BORDER_SUBTLE, highlightthickness=1)

        left = tk.Frame(sb, bg=BG_SURFACE)
        left.pack(side="left", padx=16)
        self.status_dot = PulseDot(left, color=SUCCESS, size=8, bg=BG_SURFACE)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_bar = tk.Label(left, text="就绪", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                                   font=FONT_SMALL, anchor="w")
        self.status_bar.pack(side="left")

        mid = tk.Frame(sb, bg=BG_SURFACE)
        mid.pack(side="left", padx=16)
        self._cache_label = tk.Label(mid, text="缓存: 0 张", bg=BG_SURFACE,
                                      fg=TEXT_TERTIARY, font=FONT_SMALL)
        self._cache_label.pack(side="left")
        sep = tk.Frame(mid, bg=BORDER_DEFAULT, width=1, height=14)
        sep.pack(side="left", padx=12)
        tk.Label(mid, text="磁盘占用: — MB", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_SMALL).pack(side="left")

        right = tk.Frame(sb, bg=BG_SURFACE)
        right.pack(side="right", padx=16)
        tk.Label(right, text="调度器运行中", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_SMALL).pack(side="left", padx=(0, 6))
        PulseDot(right, color=SUCCESS, size=8, bg=BG_SURFACE).pack(side="left")

    # ========== 面板切换 (主题注入) ==========
    def _switch_panel(self, source: str):
        self.data_source = source
        self.config["data_source"] = source
        save_config(self.config)

        for p in [self.panel_apod, self.panel_sat, self.panel_sdo]:
            p.pack_forget()

        self._stop_sat_refresh_timer()
        self._stop_sdo_refresh_timer()

        for src, item in self.nav_items.items():
            item.set_active(src == source)

        if source == "apod":
            self.panel_apod.pack(fill="both", expand=True)
            self._update_status("天文图片模式 · NASA APOD 每日精选")
        elif source == "satellite":
            self.panel_sat.pack(fill="both", expand=True)
            self._update_sat_info()
            sat = self.config.get("satellite_id", "himawari")
            sat_name = GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)
            self._update_status(f"卫星影像模式 · {sat_name}")
            self._start_sat_refresh_timer()
        elif source == "sdo":
            self.panel_sdo.pack(fill="both", expand=True)
            band = self.config.get("sdo_band", "0304")
            band_name = SDO_BANDS.get(band, {}).get("name", band)
            self._update_status(f"太阳观测模式 · NASA SDO {band_name}")
            self._start_sdo_refresh_timer()

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
        self._refresh_status_stats()

    def _show_current_image(self):
        images = self.images_by_cat.get(self.current_cat, [])
        total = len(images)
        if total == 0:
            self.apod_preview.config(text="📷 暂无图片\n\n点击「获取历史」拉取 NASA 图片", fg=TEXT_TERTIARY)
            self.apod_info.config(text="")
            self.apod_title.config(text="")
            self.page_label.config(text="0 / 0")
            self.current_image = None
            self.photo_ref = None
            return

        self.current_idx = max(0, min(self.current_idx, total - 1))
        img = images[self.current_idx]
        self.current_image = img
        self.page_label.config(text=f"{self.current_idx + 1} / {total}")
        self.apod_title.config(text=img.title)

        cache_path = IMAGE_CACHE_DIR / f"{img.date}.jpg"
        if not cache_path.exists() and img.hdurl:
            cache_path = IMAGE_CACHE_DIR / f"{img.date}_hd.jpg"

        if cache_path.exists():
            self._load_image(str(cache_path), self.apod_preview, self.apod_info)
        else:
            self.apod_preview.config(text=f"⬇ 正在下载...\n{img.title}", fg=TEXT_TERTIARY)
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
            label.config(text="❌ 图片加载失败", fg=ERROR)

    # ====== 通用图片加载 ======
    def _load_preview(self, path: str, label: tk.Label, status_label: tk.Label = None,
                      source_text: str = "", extra: str = "", title_text: str = ""):
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
            if title_text:
                self._set_title(label, title_text)
        except Exception as e:
            logger.error(f"Load preview error: {e}")
            label.config(text="❌ 加载失败", fg=ERROR)

    def _set_title(self, label, title):
        # 将标题写入对应面板的 overlay 标题
        if label is self.sat_preview:
            self.sat_title.config(text=title)
        elif label is self.sdo_preview:
            self.sdo_title.config(text=title)

    def _download_and_show(self, img: ApodImage):
        path = download_image(img, hd=self.config.get("hd", True))
        if path:
            self.root.after(0, lambda: self._load_image(path, self.apod_preview, self.apod_info))
        else:
            self.root.after(0, lambda: self.apod_preview.config(
                text="❌ 下载失败，请检查网络", fg=ERROR))

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
        self.apod_loading.show()
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
            self.root.after(0, lambda: self._update_status(f"❌ 获取失败: {e}", color=ERROR))
            self.root.after(0, self.apod_loading.hide)

    def _on_fetch_done(self, count: int):
        self._rebuild_category_data()
        self._refresh_ui()
        self.apod_loading.hide()
        self._update_status(f"已获取 {count} 张图片", color=GREEN)

    def _update_now(self):
        self.apod_loading.show()
        self._update_status("⏳ 正在检查更新...")
        threading.Thread(target=self._do_update, daemon=True).start()

    def _do_update(self):
        try:
            result = check_and_update()
            self.root.after(0, self._rebuild_category_data)
            self.root.after(0, self._refresh_ui)
            self.root.after(0, self.apod_loading.hide)
            self.root.after(0, lambda: self._update_status(
                "壁纸已更新" if result else "今日暂无匹配图片",
                color=GREEN if result else FG_DIM))
        except Exception as e:
            self.root.after(0, self.apod_loading.hide)
            self.root.after(0, lambda: self._update_status(f"❌ 更新失败: {e}", color=ERROR))

    # ========== 卫星影像事件 ==========
    def _update_sat_info(self):
        """更新卫星信息卡片"""
        sat = self.selected_satellite.get()
        self.config["satellite_id"] = sat
        save_config(self.config)
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
        try:
            size = int(self.sat_size_var.get())
        except ValueError:
            size = 1080
        name = GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)
        self.config["satellite_id"] = sat
        self.config["satellite_color"] = color
        self.config["satellite_size"] = size
        save_config(self.config)
        self.sat_loading.show()
        self._update_status(f"⏳ 正在获取 {name} 卫星影像...", color=YELLOW)
        self.sat_preview.config(text="⏳\n正在获取卫星影像...", fg=TEXT_TERTIARY)
        self._update_sat_info()
        threading.Thread(target=self._do_fetch_sat, args=(sat, color, size), daemon=True).start()

    def _do_fetch_sat(self, sat: str, color: str, size: int):
        try:
            path = fetch_satellite_image(satellite=sat, color=color, target_size=size)
            if path:
                self.sat_image_path = path
                self.root.after(0, lambda: (
                    self._load_preview(path, self.sat_preview, self.sat_status,
                        f"🛰 {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}", "",
                        GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)),
                    self.sat_loading.hide(),
                ))
                self.root.after(0, lambda: self._update_status(
                    f"卫星影像已更新 | {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}",
                    color=GREEN))
            else:
                self.root.after(0, lambda: self.sat_preview.config(
                    text="❌ 获取失败\n数据暂时不可用，请稍后重试", fg=ERROR))
                self.root.after(0, self.sat_loading.hide)
                self.root.after(0, lambda: self._update_status("❌ 获取失败", color=ERROR))
        except Exception as e:
            logger.error(f"Sat fetch error: {e}")
            self.root.after(0, lambda: self.sat_preview.config(text=f"❌ {str(e)[:60]}", fg=ERROR))
            self.root.after(0, self.sat_loading.hide)
            self.root.after(0, lambda: self._update_status(f"❌ {e}", color=ERROR))

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
        self.sdo_loading.show()
        self._update_status(f"⏳ 正在获取 {name} 太阳图像...", color=YELLOW)
        self.sdo_preview.config(text="⏳\n正在获取太阳图像...", fg=TEXT_TERTIARY)
        threading.Thread(target=self._do_fetch_sdo, args=(band,), daemon=True).start()

    def _do_fetch_sdo(self, band: str):
        try:
            path = fetch_sdo_image(band=band)
            if path:
                self.sdo_image_path = path
                name = SDO_BANDS.get(band, {}).get("name", band)
                self.root.after(0, lambda: (
                    self._load_preview(path, self.sdo_preview,
                        self.sdo_status, f"☀ {name}", "NASA SDO", name),
                    self.sdo_loading.hide(),
                ))
                self.root.after(0, lambda: self._update_status(
                    f"太阳图像已更新 | {name}", color=GREEN))
            else:
                self.root.after(0, lambda: self.sdo_preview.config(
                    text="❌ 获取失败\nNASA SDO 数据暂时不可用", fg=ERROR))
                self.root.after(0, self.sdo_loading.hide)
                self.root.after(0, lambda: self._update_status("❌ 获取失败", color=ERROR))
        except Exception as e:
            logger.error(f"SDO fetch error: {e}")
            self.root.after(0, lambda: self.sdo_preview.config(text=f"❌ {str(e)[:60]}", fg=ERROR))
            self.root.after(0, self.sdo_loading.hide)
            self.root.after(0, lambda: self._update_status(f"❌ {e}", color=ERROR))

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
            self.btn_sat_auto._bg = SUCCESS
            self.btn_sat_auto._hover_bg = "#6EE7C5"
            self.btn_sat_auto._glow = SUCCESS_BG
            self.btn_sat_auto._text = "🔄 自动刷新: 开"
            self.btn_sat_auto._draw(SUCCESS)
            self._start_sat_refresh_timer()
            self._update_status("卫星自动刷新已开启", color=GREEN)
        else:
            self.btn_sat_auto._bg = ACCENT2
            self.btn_sat_auto._hover_bg = "#1A4A7A"
            self.btn_sat_auto._glow = None
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
        self.sat_countdown.config(text=f"⏱ {m:02d}:{s:02d}", fg=TEXT_TERTIARY if m > 1 else WARNING)

    def _do_sat_auto_refresh(self, sat: str, color: str, size: int):
        try:
            path = fetch_satellite_image(satellite=sat, color=color, target_size=size)
            if not path:
                return
            old = self.sat_image_path
            self.sat_image_path = path
            self.root.after(0, lambda: self._load_preview(path, self.sat_preview, self.sat_status,
                f"🛰 {GEOSTATIONARY_SATELLITES.get(sat, {}).get('name', sat)}", "",
                GEOSTATIONARY_SATELLITES.get(sat, {}).get("name", sat)))
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
            self.btn_sdo_auto._bg = SUCCESS
            self.btn_sdo_auto._hover_bg = "#6EE7C5"
            self.btn_sdo_auto._glow = SUCCESS_BG
            self.btn_sdo_auto._text = "🔄 自动刷新: 开"
            self.btn_sdo_auto._draw(SUCCESS)
            self._start_sdo_refresh_timer()
            self._update_status("SDO 自动刷新已开启", color=GREEN)
        else:
            self.btn_sdo_auto._bg = ACCENT2
            self.btn_sdo_auto._hover_bg = "#1A4A7A"
            self.btn_sdo_auto._glow = None
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
        self.sdo_countdown.config(text=f"⏱ {m:02d}:{s:02d}", fg=TEXT_TERTIARY if m > 1 else WARNING)

    def _do_sdo_auto_refresh(self, band: str):
        try:
            path = fetch_sdo_image(band=band)
            if not path:
                return
            self.sdo_image_path = path
            name = SDO_BANDS.get(band, {}).get("name", band)
            self.root.after(0, lambda: self._load_preview(path, self.sdo_preview,
                self.sdo_status, f"☀ {name}", "NASA SDO", name))
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

    # ========== 设置 ==========
    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("440x500")
        win.configure(bg=BG_APP)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.attributes("-alpha", 0.0)
        self._fade_in(win)

        # 标题
        th = tk.Frame(win, bg=BG_APP)
        th.pack(fill="x", padx=24, pady=(22, 8))
        tk.Label(th, text="⚙", bg=BG_APP, fg=APOD_LIGHT, font=F(18)).pack(side="left", padx=(0, 8))
        tk.Label(th, text="设置", bg=BG_APP, fg=TEXT_PRIMARY, font=FONT_MODAL_TITLE).pack(side="left")
        tk.Frame(win, bg=BORDER_SUBTLE, height=1).pack(fill="x", padx=24, pady=(0, 4))

        # NASA API Key
        f1 = tk.Frame(win, bg=BG_APP)
        f1.pack(fill="x", padx=24, pady=(12, 4))
        tk.Label(f1, text="NASA API Key", bg=BG_APP, fg=TEXT_SECONDARY,
                 font=FONT_LABEL).pack(anchor="w")
        api_entry = tk.Entry(f1, bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                             font=(FONT_MONO[0], 12), relief="flat",
                             highlightbackground=BORDER_DEFAULT, highlightthickness=1)
        api_entry.pack(fill="x", pady=4, ipady=5)
        api_entry.insert(0, self.config.get("api_key", DEFAULT_API_KEY))
        tk.Label(f1, text="默认使用 DEMO_KEY（每小时限流 30 次），建议申请免费 Key",
                 bg=BG_APP, fg=TEXT_TERTIARY, font=FONT_TINY).pack(anchor="w")

        # 壁纸样式
        f_ws = tk.Frame(win, bg=BG_APP)
        f_ws.pack(fill="x", padx=24, pady=(10, 4))
        tk.Label(f_ws, text="壁纸样式", bg=BG_APP, fg=TEXT_SECONDARY,
                 font=FONT_LABEL).pack(anchor="w")
        wp_style = tk.StringVar(value=self.config.get("wallpaper_style", "fill"))
        styles = [("center", "居中"), ("tile", "平铺"), ("stretch", "拉伸"),
                  ("fit", "适应"), ("fill", "填充")]
        seg = SegmentedControl(f_ws, styles, wp_style, accent=APOD_PRIMARY,
                               command=lambda v: None)
        seg.pack(fill="x", pady=4)

        # 开关组
        def toggle_row(parent, label, default_key):
            row = tk.Frame(parent, bg=BG_APP)
            row.pack(fill="x", padx=24, pady=8)
            tk.Label(row, text=label, bg=BG_APP, fg=TEXT_SECONDARY,
                     font=FONT_BODY).pack(side="left")
            var = tk.BooleanVar(value=self.config.get(default_key, True))
            tg = ToggleSwitch(row, variable=var)
            tg.pack(side="right")
            return var

        auto_var = toggle_row(win, "自动更新壁纸", "auto_update")
        hd_var = toggle_row(win, "优先下载高清图片 (NASA APOD)", "hd")
        startup_var = toggle_row(win, "开机自启动", "auto_start")

        def save():
            self.config["api_key"] = api_entry.get().strip() or DEFAULT_API_KEY
            self.config["wallpaper_style"] = wp_style.get()
            self.config["auto_update"] = auto_var.get()
            self.config["hd"] = hd_var.get()
            self.config["auto_start"] = startup_var.get()
            save_config(self.config)
            win.destroy()
            self._update_status("设置已保存", color=GREEN)

        ModernButton(win, text="💾 保存", command=save,
                     width=120, height=36, bg=CTA, hover_bg=CTA_HOVER,
                     glow=CTA_GLOW).pack(pady=(16, 0))

    def _fade_in(self, win, alpha=0.0):
        alpha += 0.08
        if alpha >= 1.0:
            win.attributes("-alpha", 1.0)
            return
        try:
            win.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        win.after(16, lambda: self._fade_in(win, alpha))

    # ========== 使用说明 ==========
    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("使用说明")
        win.geometry("560x560")
        win.configure(bg=BG_APP)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.attributes("-alpha", 0.0)
        self._fade_in(win)

        th = tk.Frame(win, bg=BG_APP)
        th.pack(fill="x", padx=24, pady=(22, 8))
        tk.Label(th, text="📖", bg=BG_APP, fg=SAT_LIGHT, font=F(18)).pack(side="left", padx=(0, 8))
        tk.Label(th, text="使用说明", bg=BG_APP, fg=TEXT_PRIMARY, font=FONT_MODAL_TITLE).pack(side="left")
        tk.Frame(win, bg=BORDER_SUBTLE, height=1).pack(fill="x", padx=24, pady=(0, 8))

        sections = [
            ("🔭 天文图片 — NASA APOD", APOD_LIGHT,
             "• 首次启动自动获取近 10 天图片\n"
             "• 左侧选择分类浏览：星云、星系、行星等\n"
             "• 点击图片设为壁纸，支持导航浏览\n"
             "• 每天在设定时间自动更新"),
            ("🛰 卫星影像 — 多卫星实时影像", SAT_LIGHT,
             "• 支持 6 颗地球静止卫星（Himawari-8 / GOES / GK2A / Meteosat）\n"
             "• 颜色模式：自然色 / 地球色\n"
             "• 分辨率：标准 / 高清 / 超清\n"
             "• 开启自动刷新，每 10 分钟自动更新"),
            ("☀ 太阳观测 — NASA SDO", SDO_LIGHT,
             "• 多个观测波段（304 Å 色球层 / 171 Å 日冕 / 连续光球 / 磁场线）\n"
             "• 数据来源：NASA 太阳动力学天文台\n"
             "• 约每 15-60 分钟更新一张"),
        ]
        body = tk.Frame(win, bg=BG_APP)
        body.pack(fill="both", expand=True, padx=24, pady=4)
        for title, color, text in sections:
            sec = tk.Frame(body, bg=BG_CARD, highlightbackground=BORDER_SUBTLE,
                           highlightthickness=1)
            sec.pack(fill="x", pady=6)
            tk.Label(sec, text=title, bg=BG_CARD, fg=color, font=FONT_BODY).pack(
                anchor="w", padx=12, pady=(8, 2))
            tk.Label(sec, text=text, bg=BG_CARD, fg=TEXT_SECONDARY, font=FONT_SMALL,
                     justify="left", anchor="w").pack(anchor="w", padx=12, pady=(0, 8))

        ModernButton(win, text="知道了", command=win.destroy,
                     width=100, height=34, bg=ACCENT2, hover_bg="#1A4A7A").pack(pady=(8, 16))

    # ========== 状态/自动启动 ==========
    def _update_status(self, text: str, color: str = FG_DIM):
        self.status_bar.config(text=text, fg=color)

    def _refresh_status_stats(self):
        n = len(self.metadata.get("images", {}))
        self._cache_label.config(text=f"缓存: {n} 张")

    def _auto_fetch_on_startup(self):
        self.apod_loading.show()
        self._update_status("⏳ 首次启动，正在自动获取 NASA 图片...", color=YELLOW)
        self.apod_preview.config(text="⏳ 首次启动\n\n正在从 NASA 获取卫星图片...\n请稍候", fg=TEXT_TERTIARY)
        self.apod_info.config(text="数据来源: NASA APOD API | 首次运行自动拉取近 10 天图片")
        self.apod_title.config(text="")
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
                    "⚠ NASA API 暂时不可用，请稍后手动获取", color=ERROR))
                self.root.after(0, lambda: self.apod_preview.config(
                    text="⚠ 首次拉取失败\n\nNASA API 暂时不可用\n请稍后点击「获取历史」重试", fg=YELLOW))
                self.root.after(0, self.apod_loading.hide)
        except Exception as e:
            logger.error(f"Auto-fetch error: {e}")
            self.root.after(0, lambda: self._update_status(f"⚠ 自动获取失败: {e}", color=ERROR))
            self.root.after(0, self.apod_loading.hide)

    def _on_auto_fetch_done(self, count: int):
        self._rebuild_category_data()
        self._refresh_ui()
        self.apod_loading.hide()
        self._update_status(f"已自动获取 {count} 张 NASA 图片，选一个分类设为壁纸吧", color=GREEN)

    def _check_auto_startup(self):
        if not self.metadata.get("images"):
            self._auto_fetch_on_startup()
        else:
            self._update_status("就绪")

    # ========== 关闭行为 ==========
    def _on_close(self):
        """点击 X 按钮时弹出选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("退出选项")
        dialog.geometry("380x210")
        dialog.configure(bg=BG_SURFACE)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.attributes("-alpha", 0.0)
        self._fade_in(dialog)

        # 居中显示
        dialog.update_idletasks()
        dw, dh = dialog.winfo_width(), dialog.winfo_height()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        dialog.geometry(f"+{rx + (rw - dw) // 2}+{ry + (rh - dh) // 2}")

        tk.Label(dialog, text="RealEarth", bg=BG_SURFACE, fg=TEXT_PRIMARY,
                 font=FONT_PANEL_TITLE).pack(pady=(20, 2))
        tk.Label(dialog, text="请选择关闭方式", bg=BG_SURFACE, fg=TEXT_TERTIARY,
                 font=FONT_BODY).pack(pady=(0, 14))

        btn_frame = tk.Frame(dialog, bg=BG_SURFACE)
        btn_frame.pack(pady=4)

        def do_minimize():
            dialog.destroy()
            self.root.iconify()
            self._update_status("已最小化到任务栏，后台持续更新壁纸", color=GREEN)

        def do_quit():
            dialog.destroy()
            stop_scheduler()
            self.root.destroy()

        ModernButton(btn_frame, text="— 最小化到任务栏 —",
                     command=do_minimize,
                     width=150, height=38, bg=BLUE, hover_bg=BLUE_HOVER,
                     font=FONT_BODY).pack(side="left", padx=8)

        ModernButton(btn_frame, text="✕ 退出程序",
                     command=do_quit,
                     width=120, height=38, bg=CTA, hover_bg=CTA_HOVER,
                     glow=CTA_GLOW, font=FONT_BODY).pack(side="left", padx=8)

        tk.Label(dialog, text="最小化后后台将持续更新 | 从任务栏点击恢复窗口",
                 bg=BG_SURFACE, fg=TEXT_TERTIARY, font=FONT_SMALL).pack(pady=(10, 0))


def main():
    root = tk.Tk()
    NASAApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
