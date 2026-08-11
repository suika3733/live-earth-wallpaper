"""NASA Wallpaper + 实时地球 - 双数据源壁纸软件"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import logging
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ========== 颜色主题 ==========
BG_MAIN = "#0f0f1a"
BG_CARD = "#1a1a2e"
BG_INPUT = "#16213e"
FG_TEXT = "#e0e0e0"
FG_DIM = "#a0a0b0"
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
ACCENT2 = "#0f3460"
BORDER = "#2a2a40"
GREEN = "#4ecca3"
YELLOW = "#f9d423"
BLUE = "#2d8cf0"
BLUE_HOVER = "#4aa3f7"
EARTH_ACCENT = "#00b4d8"

FONT_FAMILY = ("Microsoft YaHei", "微软雅黑", "PingFang SC", "Arial")
FONT_TITLE = (FONT_FAMILY[0], 14, "bold")
FONT_BODY = (FONT_FAMILY[0], 11)
FONT_SMALL = (FONT_FAMILY[0], 9)
FONT_BIG = (FONT_FAMILY[0], 16, "bold")


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
        self.root.title("NASA 卫星壁纸")
        self.root.geometry("1300x850")
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(1100, 700)

        self.config = load_config()
        self.metadata = load_metadata()
        self.data_source = self.config.get("data_source", "apod")
        self.earth_image_path = None
        self.earth_auto_refresh = self.config.get("earth_auto_refresh", True)
        self.earth_refresh_interval = self.config.get("earth_refresh_interval", 10)  # 分钟
        self._earth_timer_id = None  # tkinter after ID
        self._earth_next_refresh = None  # datetime of next refresh

        # APOD 数据
        self.images_by_cat = {key: [] for key in get_all_category_keys()}
        self.current_cat = self.config.get("selected_category", ALL_CATEGORY)
        self.current_idx = 0
        self.current_image = None
        self.photo_ref = None

        # 拦截关闭按钮
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._rebuild_category_data()
        self._refresh_ui()
        self._switch_panel(self.data_source)

        start_scheduler()
        self._check_auto_startup()

    # ========== UI 构建 ==========
    def _build_ui(self):
        # ---- 顶部标题栏 ----
        header = tk.Frame(self.root, bg=BG_CARD, height=48)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(header, text="🚀 NASA 卫星壁纸", bg=BG_CARD, fg="white",
                 font=(FONT_FAMILY[0], 16, "bold")).pack(side="left", padx=18, pady=8)

        # 数据源切换标签
        ds_frame = tk.Frame(header, bg=BG_CARD)
        ds_frame.pack(side="left", padx=(20, 0))

        self.btn_apod = ModernButton(ds_frame, text="🔭 NASA APOD",
                                     command=lambda: self._switch_panel("apod"),
                                     width=110, height=30, bg=ACCENT2, hover_bg="#1a4a7a",
                                     font=(FONT_FAMILY[0], 9))
        self.btn_apod.pack(side="left", padx=3)

        self.btn_earth = ModernButton(ds_frame, text="🌍 实时地球",
                                      command=lambda: self._switch_panel("earth"),
                                      width=100, height=30, bg="#1a3a4a",
                                      hover_bg="#0f3460", font=(FONT_FAMILY[0], 9))
        self.btn_earth.pack(side="left", padx=3)

        # 右上角按钮
        menu_frame = tk.Frame(header, bg=BG_CARD)
        menu_frame.pack(side="right", padx=8)

        ModernButton(menu_frame, text="📖 说明", command=self._show_help,
                     width=60, height=28, bg=ACCENT2, hover_bg="#1a4a7a",
                     font=(FONT_FAMILY[0], 9)).pack(side="left", padx=3)
        ModernButton(menu_frame, text="⚙ 设置", command=self._show_settings,
                     width=60, height=28, bg=ACCENT2, hover_bg="#1a4a7a",
                     font=(FONT_FAMILY[0], 9)).pack(side="left", padx=3)

        # ---- 主体区域 ----
        body = tk.Frame(self.root, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=15, pady=10)

        # === APOD 面板 ===
        self.panel_apod = tk.Frame(body, bg=BG_MAIN)

        # 左侧分类列表
        left = tk.Frame(self.panel_apod, bg=BG_MAIN, width=150)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="📂 图片分类", bg=BG_MAIN, fg=FG_TEXT,
                 font=FONT_TITLE).pack(anchor="w", pady=(0, 8))

        cat_frame = tk.Frame(left, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
        cat_frame.pack(fill="both", expand=True)

        cols = ("category", "count")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols, show="headings", height=20)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=BG_INPUT, foreground=FG_TEXT,
                        fieldbackground=BG_INPUT, rowheight=28, font=FONT_BODY)
        style.configure("Treeview.Heading", background=BG_CARD, foreground=FG_TEXT,
                        font=(FONT_FAMILY[0], 10, "bold"))
        style.map("Treeview", background=[("selected", ACCENT2)],
                  foreground=[("selected", "white")])
        style.configure("Vertical.TScrollbar", background=BG_CARD,
                        troughcolor=BG_MAIN, arrowcolor=FG_DIM)

        self.cat_tree.heading("category", text="分类")
        self.cat_tree.heading("count", text="数量")
        self.cat_tree.column("category", width=140, anchor="w")
        self.cat_tree.column("count", width=50, anchor="center")
        self.cat_tree.pack(side="left", fill="both", expand=True)

        cat_scroll = ttk.Scrollbar(cat_frame, orient="vertical", command=self.cat_tree.yview)
        cat_scroll.pack(side="right", fill="y")
        self.cat_tree.configure(yscrollcommand=cat_scroll.set)
        self.cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)

        # 右侧预览区
        right = tk.Frame(self.panel_apod, bg=BG_MAIN)
        right.pack(side="left", fill="both", expand=True)

        preview = tk.Frame(right, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        preview.pack(fill="both", expand=True, pady=(0, 10))

        self.apod_preview = tk.Label(preview, bg=BG_CARD, text="📷 暂无图片", fg=FG_DIM,
                                     font=(FONT_FAMILY[0], 14))
        self.apod_preview.pack(fill="both", expand=True)

        self.apod_info = tk.Label(preview, bg=BG_CARD, fg=FG_DIM, font=FONT_SMALL,
                                  justify="left", wraplength=700)
        self.apod_info.place(relx=0.02, rely=0.97, anchor="sw")

        # 底部控制栏
        ctrl = tk.Frame(right, bg=BG_MAIN, height=45)
        ctrl.pack(fill="x", side="bottom")
        ctrl.pack_propagate(False)

        nav = tk.Frame(ctrl, bg=BG_MAIN)
        nav.pack(side="left")
        self.btn_prev = ModernButton(nav, text="◀", command=self._prev_image,
                                     width=40, height=32, bg=ACCENT2, hover_bg="#1a4a7a")
        self.btn_prev.pack(side="left", padx=2)
        self.page_label = tk.Label(nav, text="0 / 0", bg=BG_MAIN, fg=FG_TEXT,
                                   font=FONT_BODY, width=10)
        self.page_label.pack(side="left", padx=10)
        self.btn_next = ModernButton(nav, text="▶", command=self._next_image,
                                     width=40, height=32, bg=ACCENT2, hover_bg="#1a4a7a")
        self.btn_next.pack(side="left", padx=2)

        self.btn_fetch = ModernButton(ctrl, text="📥 获取历史", command=self._fetch_history,
                                      width=100, height=32, bg=BLUE, hover_bg=BLUE_HOVER)
        self.btn_fetch.pack(side="left", padx=(30, 2))

        rc = tk.Frame(ctrl, bg=BG_MAIN)
        rc.pack(side="right")
        self.btn_update = ModernButton(rc, text="🔄 更新", command=self._update_now,
                                       width=80, height=32, bg=GREEN, hover_bg="#6ee7c5",
                                       fg="#0f0f1a")
        self.btn_update.pack(side="left", padx=2)
        self.btn_wallpaper = ModernButton(rc, text="🖼 设为壁纸", command=self._set_wallpaper,
                                          width=100, height=32, bg=ACCENT, hover_bg=ACCENT_HOVER)
        self.btn_wallpaper.pack(side="left", padx=2)

        # === 实时地球面板 ===
        self.panel_earth = tk.Frame(body, bg=BG_MAIN)

        earth_left = tk.Frame(self.panel_earth, bg=BG_MAIN, width=150)
        earth_left.pack(side="left", fill="y", padx=(0, 10))
        earth_left.pack_propagate(False)

        tk.Label(earth_left, text="🌍 实时地球", bg=BG_MAIN, fg=FG_TEXT,
                 font=FONT_TITLE).pack(anchor="w", pady=(0, 8))

        info_card = tk.Frame(earth_left, bg=BG_CARD, highlightbackground=BORDER,
                             highlightthickness=1)
        info_card.pack(fill="both", expand=True)

        earth_info_text = (
            "数据来源\n"
            "━━━━━━━━━━━━\n"
            "日本 Himawari-8\n"
            "气象卫星\n\n"
            "更新频率\n"
            "━━━━━━━━━━━━\n"
            "每 10 分钟一张\n"
            "实时地球全盘图\n\n"
            "分辨率\n"
            "━━━━━━━━━━━━\n"
            "2200x2200 像素\n"
            "16 瓦片拼接\n\n"
            "延迟\n"
            "━━━━━━━━━━━━\n"
            "约 20-30 分钟\n\n"
            "自动刷新\n"
            "━━━━━━━━━━━━\n"
            "开启后每 10 分钟\n"
            "自动获取最新图\n"
            "设为壁纸同步更新"
        )
        earth_info_label = tk.Label(info_card, text=earth_info_text, bg=BG_CARD,
                                    fg=FG_DIM, font=FONT_SMALL, justify="left", padx=12, pady=10)
        earth_info_label.pack(fill="both", expand=True)

        # 地球预览区
        earth_right = tk.Frame(self.panel_earth, bg=BG_MAIN)
        earth_right.pack(side="left", fill="both", expand=True)

        earth_preview = tk.Frame(earth_right, bg=BG_CARD, highlightbackground=BORDER,
                                 highlightthickness=1)
        earth_preview.pack(fill="both", expand=True, pady=(0, 10))

        self.earth_preview = tk.Label(earth_preview, bg=BG_CARD,
                                      text="🌍\n点击下方按钮获取\n最新地球卫星图",
                                      fg=FG_DIM, font=(FONT_FAMILY[0], 14))
        self.earth_preview.pack(fill="both", expand=True)

        self.earth_status = tk.Label(earth_preview, bg=BG_CARD, fg=FG_DIM,
                                     font=FONT_SMALL)
        self.earth_status.place(relx=0.02, rely=0.97, anchor="sw")

        # 地球底部控制
        earth_ctrl = tk.Frame(earth_right, bg=BG_MAIN, height=45)
        earth_ctrl.pack(fill="x", side="bottom")
        earth_ctrl.pack_propagate(False)

        left_ec = tk.Frame(earth_ctrl, bg=BG_MAIN)
        left_ec.pack(side="left")

        self.btn_earth_fetch = ModernButton(earth_ctrl, text="📡 获取最新图片",
                                            command=self._fetch_earth,
                                            width=120, height=32, bg=EARTH_ACCENT,
                                            hover_bg="#00d4f4")
        self.btn_earth_fetch.pack(side="left", padx=(20, 2))

        # 自动刷新开关
        self.btn_auto_refresh = ModernButton(earth_ctrl,
                                             text="🔄 自动刷新: 开" if self.earth_auto_refresh else "🔄 自动刷新: 关",
                                             command=self._toggle_earth_auto_refresh,
                                             width=120, height=32,
                                             bg=GREEN if self.earth_auto_refresh else ACCENT2,
                                             hover_bg="#6ee7c5" if self.earth_auto_refresh else "#1a4a7a")
        self.btn_auto_refresh.pack(side="left", padx=5)

        # 倒计时标签
        self.earth_countdown = tk.Label(earth_ctrl, text="", bg=BG_MAIN, fg=FG_DIM,
                                        font=(FONT_FAMILY[0], 9))
        self.earth_countdown.pack(side="left", padx=8)

        right_ec = tk.Frame(earth_ctrl, bg=BG_MAIN)
        right_ec.pack(side="right")
        self.btn_earth_wp = ModernButton(right_ec, text="🖼 设为壁纸",
                                         command=self._set_earth_wallpaper,
                                         width=100, height=32, bg=ACCENT, hover_bg=ACCENT_HOVER)
        self.btn_earth_wp.pack(side="left", padx=2)

        # ---- 状态栏 ----
        self.status_bar = tk.Label(self.root, text="就绪", bg=BG_CARD, fg=FG_DIM,
                                   font=FONT_SMALL, anchor="w", padx=15)
        self.status_bar.pack(fill="x", side="bottom", ipady=4)

    # ========== 面板切换 ==========
    def _switch_panel(self, source: str):
        self.data_source = source
        self.config["data_source"] = source
        save_config(self.config)

        if source == "apod":
            self._stop_earth_refresh_timer()
            self.panel_earth.pack_forget()
            self.panel_apod.pack(fill="both", expand=True)
            self.btn_apod._bg = ACCENT2
            self.btn_apod._hover_bg = "#1a4a7a"
            self.btn_apod._draw(ACCENT2)
            self.btn_earth._bg = "#1a3a4a"
            self.btn_earth._hover_bg = "#0f3460"
            self.btn_earth._draw("#1a3a4a")
            self._update_status("已切换到 NASA APOD 模式", color=FG_DIM)
        else:
            self.panel_apod.pack_forget()
            self.panel_earth.pack(fill="both", expand=True)
            self.btn_earth._bg = EARTH_ACCENT
            self.btn_earth._hover_bg = "#00d4f4"
            self.btn_earth._draw(EARTH_ACCENT)
            self.btn_apod._bg = "#1a3a4a"
            self.btn_apod._hover_bg = "#0f3460"
            self.btn_apod._draw("#1a3a4a")
            self._update_status("已切换到实时地球模式 | 2200x2200 高清拼接", color=FG_DIM)

            # 自动加载 Earth 图片（如果已有缓存）
            from config import IMAGE_CACHE_DIR
            from earth_api import LATEST_IMAGE_FILE
            if LATEST_IMAGE_FILE.exists():
                self._load_earth_image(str(LATEST_IMAGE_FILE))
                self.earth_image_path = str(LATEST_IMAGE_FILE)
            else:
                # 没有缓存则自动获取
                self._fetch_earth()

            # 启动自动刷新计时器
            self._start_earth_refresh_timer()

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

    def _load_earth_image(self, path: str):
        """加载实时地球图片到预览区"""
        try:
            pil_img = Image.open(path)
            self.root.update_idletasks()
            pw = self.earth_preview.winfo_width() or 900
            ph = self.earth_preview.winfo_height() or 600
            iw, ih = pil_img.size
            ratio = min(pw / iw, ph / ih, 1.0)
            nw, nh = int(iw * ratio), int(ih * ratio)
            pil_img = pil_img.resize((nw, nh), Image.LANCZOS)
            self._earth_photo = ImageTk.PhotoImage(pil_img)
            self.earth_preview.config(image=self._earth_photo, text="")

            now = datetime.now()
            self.earth_status.config(
                text=f"🛰 Himawari-8 地球全盘图 | 获取时间: {now.strftime('%Y-%m-%d %H:%M')} | "
                     f"分辨率: {pil_img.width}x{pil_img.height}")
        except Exception as e:
            logger.error(f"Load earth image error: {e}")
            self.earth_preview.config(text="❌ 加载失败", fg=ACCENT)

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

    # ========== 实时地球事件 ==========
    def _fetch_earth(self):
        self._update_status("⏳ 正在获取最新地球卫星图...", color=YELLOW)
        self.earth_preview.config(text="⏳\n正在从 Himawari-8 卫星获取图片...", fg=FG_DIM)
        threading.Thread(target=self._do_fetch_earth, daemon=True).start()

    def _do_fetch_earth(self):
        try:
            from earth_api import fetch_earth_image
            path = fetch_earth_image(resolution=2200)
            if path:
                self.earth_image_path = path
                self.root.after(0, lambda: self._load_earth_image(path))
                self.root.after(0, lambda: self._update_status(
                    "地球卫星图已更新 2200x2200 | 可点击「设为壁纸」", color=GREEN))
            else:
                self.root.after(0, lambda: self.earth_preview.config(
                    text="❌ 获取失败\n\nHimawari-8 数据暂时不可用\n请稍后重试", fg=ACCENT))
                self.root.after(0, lambda: self._update_status(
                    "❌ 获取失败，请稍后重试", color=ACCENT))
        except Exception as e:
            logger.error(f"Earth fetch error: {e}")
            self.root.after(0, lambda: self.earth_preview.config(
                text=f"❌ 失败: {str(e)[:60]}", fg=ACCENT))
            self.root.after(0, lambda: self._update_status(f"❌ 获取失败: {e}", color=ACCENT))

    def _set_earth_wallpaper(self):
        if not self.earth_image_path or not Path(self.earth_image_path).exists():
            messagebox.showwarning("提示", "请先获取最新地球图片")
            return
        style = self.config.get("wallpaper_style", "fill")
        now = datetime.now()
        wp_path = watermark_image(
            self.earth_image_path,
            left_text="来源: Himawari-8 气象卫星",
            right_text=f"拍摄时间: {now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
            output_key="earth_live",
        )
        if set_wallpaper(wp_path, "earth_live", style=style):
            self._update_status(
                f"实时地球壁纸已设置 | {now.strftime('%H:%M')} | 后台持续自动更新",
                color=GREEN)
        else:
            messagebox.showerror("错误", "壁纸设置失败")
    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.geometry("420x420")
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

        def save():
            self.config["api_key"] = api_entry.get().strip() or DEFAULT_API_KEY
            self.config["wallpaper_style"] = wp_style.get()
            self.config["auto_update"] = auto_var.get()
            self.config["hd"] = hd_var.get()
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

        help_text = """欢迎使用 NASA 卫星壁纸！

【双数据源模式】
点击顶部的标签切换数据源：

🔭 NASA APOD — 天文每日图片
• 首次启动自动获取近 10 天图片
• 左侧选择分类浏览：星云、星系、行星等 10 个类别
• 点击图片设为壁纸，支持导航浏览
• 每天在设定时间自动更新

🌍 实时地球 — Himawari-8 卫星
• 日本气象卫星 Himawari-8 每 10 分钟拍摄一张
  地球全盘图
• 默认 2200x2200 高清分辨率（16瓦片拼接）
• 点击「获取最新图片」下载当前卫星图
• 开启「自动刷新」每 10 分钟自动获取 + 更新
• 设为壁纸后，自动刷新同步跟新壁纸
• 数据延迟约 20-30 分钟

【壁纸样式】
在「设置」中选择：居中 / 平铺 / 拉伸 / 适应 / 填充

【NASA API Key】
默认使用 DEMO_KEY（每小时限流 30 次）。
建议访问 https://api.nasa.gov/ 申请免费 Key，
在「设置」中填入，获得每小时 1000 次额度。

【数据存储】
配置和缓存在 %USERPROFILE%\\.nasa_wallpaper\\ 目录

【关闭与后台运行】
• 点击右上角 X 关闭窗口时，可选择：
  -「最小化到任务栏」：隐藏到任务栏，后台持续更新壁纸
  -「退出程序」：停止所有更新并退出
• 最小化后从任务栏点击图标即可恢复窗口
• 壁纸来源和拍摄时间会标注在壁纸右下角
"""

        text = tk.Text(win, bg=BG_INPUT, fg=FG_TEXT, font=FONT_BODY,
                       relief="flat", wrap="word", padx=15, pady=10, height=22, width=55)
        text.pack(fill="both", expand=True, padx=20, pady=5)
        text.insert("1.0", help_text)
        text.config(state="disabled")

        ModernButton(win, text="知道了", command=win.destroy,
                     width=80, height=32, bg=ACCENT2, hover_bg="#1a4a7a").pack(pady=8)

    # ========== 状态/自动启动 ==========
    def _update_status(self, text: str, color: str = FG_DIM):
        self.status_bar.config(text=text, fg=color)

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

    # ========== 地球自动刷新 ==========
    def _toggle_earth_auto_refresh(self):
        """切换自动刷新开关"""
        self.earth_auto_refresh = not self.earth_auto_refresh
        self.config["earth_auto_refresh"] = self.earth_auto_refresh
        save_config(self.config)

        if self.earth_auto_refresh:
            self.btn_auto_refresh._bg = GREEN
            self.btn_auto_refresh._hover_bg = "#6ee7c5"
            self.btn_auto_refresh._text = "🔄 自动刷新: 开"
            self.btn_auto_refresh._draw(GREEN)
            self._start_earth_refresh_timer()
            self._update_status("自动刷新已开启 | 每10分钟获取最新地球图", color=GREEN)
        else:
            self.btn_auto_refresh._bg = ACCENT2
            self.btn_auto_refresh._hover_bg = "#1a4a7a"
            self.btn_auto_refresh._text = "🔄 自动刷新: 关"
            self.btn_auto_refresh._draw(ACCENT2)
            self._stop_earth_refresh_timer()
            self._update_status("自动刷新已关闭")

    def _start_earth_refresh_timer(self):
        """启动地球自动刷新计时器"""
        if not self.earth_auto_refresh:
            return
        if self._earth_timer_id:
            self.root.after_cancel(self._earth_timer_id)

        # 设置下次刷新时间
        from datetime import datetime, timedelta
        self._earth_next_refresh = datetime.now() + timedelta(minutes=self.earth_refresh_interval)
        self._update_earth_countdown()

        # 定时秒级更新倒计时显示
        self._earth_timer_id = self.root.after(1000, self._earth_tick)

    def _stop_earth_refresh_timer(self):
        """停止地球自动刷新计时器"""
        if self._earth_timer_id:
            self.root.after_cancel(self._earth_timer_id)
            self._earth_timer_id = None
        self._earth_next_refresh = None
        self.earth_countdown.config(text="")

    def _earth_tick(self):
        """计时器每秒触发"""
        if not self.earth_auto_refresh:
            return

        now = datetime.now()
        if self._earth_next_refresh:
            remaining = (self._earth_next_refresh - now).total_seconds()
            if remaining <= 0:
                # 时间到，执行刷新
                self._earth_next_refresh = now + timedelta(minutes=self.earth_refresh_interval)
                self.earth_countdown.config(text="⏳ 刷新中...")
                threading.Thread(target=self._do_earth_auto_refresh, daemon=True).start()
            else:
                self._update_earth_countdown()

        # 每秒更新倒计时
        self._earth_timer_id = self.root.after(1000, self._earth_tick)

    def _update_earth_countdown(self):
        """更新倒计时显示"""
        if not self._earth_next_refresh:
            return
        remaining = max(0, (self._earth_next_refresh - datetime.now()).total_seconds())
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.earth_countdown.config(
            text=f"⏱ 下次更新: {minutes:02d}:{seconds:02d}",
            fg=FG_DIM if minutes > 1 else YELLOW,
        )

    def _do_earth_auto_refresh(self):
        """后台自动刷新地球图"""
        try:
            from earth_api import fetch_earth_image
            path = fetch_earth_image(resolution=2200)
            if path:
                old_path = self.earth_image_path
                self.earth_image_path = path
                self.root.after(0, lambda: self._load_earth_image(path))

                # 如果当前数据源是 earth 且设了壁纸，同步更新壁纸
                if self.data_source == "earth":
                    style = self.config.get("wallpaper_style", "fill")
                    now = datetime.now()
                    wp_path = watermark_image(
                        path,
                        left_text="来源: Himawari-8 气象卫星",
                        right_text=f"拍摄时间: {now.strftime('%Y-%m-%d %H:%M')} (UTC+8)",
                        output_key="earth_live",
                    )
                    set_wallpaper(wp_path, "earth_live", style=style)
                    self.root.after(0, lambda: self._update_status(
                        f"🛰 已自动刷新 | {now.strftime('%H:%M')} | 壁纸同步更新",
                        color=GREEN))
                else:
                    self.root.after(0, lambda: self._update_status(
                        "🛰 地球图已自动刷新", color=GREEN))
            else:
                self.root.after(0, lambda: self._update_status(
                    "⚠ 自动刷新失败，下次重试", color=ACCENT))
        except Exception as e:
            logger.error(f"Earth auto-refresh error: {e}")

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

        tk.Label(dialog, text="NASA 卫星壁纸", bg=BG_MAIN, fg="white",
                 font=FONT_TITLE).pack(pady=(18, 4))
        tk.Label(dialog, text="请选择关闭方式", bg=BG_MAIN, fg=FG_DIM,
                 font=FONT_BODY).pack(pady=(0, 12))

        btn_frame = tk.Frame(dialog, bg=BG_MAIN)
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
                     font=(FONT_FAMILY[0], 10)).pack(side="left", padx=8)

        ModernButton(btn_frame, text="✕ 退出程序",
                     command=do_quit,
                     width=120, height=38, bg=ACCENT, hover_bg=ACCENT_HOVER,
                     font=(FONT_FAMILY[0], 10)).pack(side="left", padx=8)

        tk.Label(dialog, text="最小化后后台将持续更新 | 从任务栏点击恢复窗口",
                 bg=BG_MAIN, fg=FG_DIM, font=FONT_SMALL).pack(pady=(8, 0))


def main():
    root = tk.Tk()
    NASAApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
