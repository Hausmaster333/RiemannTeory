"""Desktop demonstration of the Riemann rearrangement theorem."""

import math
import os
import tempfile
import ctypes

if os.name == "nt":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass

import tkinter as tk
from tkinter import ttk, messagebox

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "RiemannDemo"))

from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from series import MAX_STEPS, Parameters, calculate, rough_steps


WHITE = "#FFFFFF"
INK = "#1F2933"
MUTED = "#68737D"
LINE = "#DEE3E6"
BLUE = "#346581"
BLUE_LIGHT = "#EAF2F6"
ORIGINAL = "#A9B3B9"
ERROR = "#A14A40"
PRESETS = (
    ("wave", "Параметрический", r"$\sum_{n=1}^{\infty}(-1)^{n+1}\frac{A+B\sin n}{n^p}$"),
    ("harmonic", "Гармонический", r"$\sum_{n=1}^{\infty}(-1)^{n+1}\frac{C}{n}$"),
    ("leibniz", "Ряд Лейбница", r"$\sum_{n=1}^{\infty}(-1)^{n+1}\frac{C}{2n-1}$"),
    ("sine", "Синусный", r"$\sum_{n=1}^{\infty}\frac{C\sin n}{n}$"),
)


def number(value: float, digits: int = 3) -> str:
    if abs(value) >= 1_000_000:
        return f"{value:.3g}"
    if value and abs(value) < 10 ** (-digits):
        return f"{value:.2e}"
    text = f"{value:.{digits}f}"
    return text.lstrip("-") if float(text) == 0 else text


def steps_text(value: float, approximate: bool = False) -> str:
    if not math.isfinite(value):
        return "очень много"
    prefix = "≈ " if approximate else ""
    if value >= 1_000_000_000:
        amount = f"{value / 1_000_000_000:.1f}".replace(".", ",")
        return f"{prefix}{amount} млрд"
    if value >= 1_000_000:
        amount = f"{value / 1_000_000:.1f}".replace(".", ",")
        return f"{prefix}{amount} млн"
    if approximate and value >= 10_000:
        amount = f"{value / 1_000:.1f}".replace(".", ",")
        return f"{prefix}{amount} тыс."
    return prefix + f"{round(value):,}".replace(",", " ")


def latex_formula(params: Parameters) -> str:
    def coefficient(value: float) -> str:
        text = f"{value:.5g}"
        if "e" not in text:
            return text
        mantissa, exponent = text.split("e")
        return rf"{mantissa}\cdot10^{{{int(exponent)}}}"

    amount = coefficient(params.a)
    if params.kind == "harmonic":
        return rf"$\sum_{{n=1}}^{{\infty}}(-1)^{{n+1}}\frac{{{amount}}}{{n}}$"
    if params.kind == "leibniz":
        return rf"$\sum_{{n=1}}^{{\infty}}(-1)^{{n+1}}\frac{{{amount}}}{{2n-1}}$"
    if params.kind == "sine":
        factor = "" if params.a == 1 else amount
        return rf"$\sum_{{n=1}}^{{\infty}}\frac{{{factor}\sin n}}{{n}}$"

    numerator = amount
    if params.b:
        sign = "+" if params.b > 0 else "-"
        numerator += rf"{sign}{coefficient(abs(params.b))}\sin n"
    return rf"$\sum_{{n=1}}^{{\infty}}(-1)^{{n+1}}\frac{{{numerator}}}{{n^{{{coefficient(params.p)}}}}}$"


class RiemannApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Теорема Римана")
        scale = root.winfo_fpixels("1i") / 96
        width = min(round(1060 * scale), root.winfo_screenwidth() - 80)
        height = min(round(720 * scale), root.winfo_screenheight() - 100)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(round(850 * scale), width), min(round(600 * scale), height))
        self.root.configure(bg=WHITE)
        self.scale = scale

        self.params: Parameters | None = None
        self.result = None
        self.step = 0
        self.playing = False
        self.timer: str | None = None
        self.recompute_timer: str | None = None
        self.syncing_scale = False
        self.switching_preset = False
        self.kind = "wave"
        self.preset_values = {
            "wave": ("1,5", "0,5", "0,6"),
            "harmonic": ("1", "0", "1"),
            "leibniz": ("1", "0", "1"),
            "sine": ("1", "0", "1"),
        }
        self.overlay: tk.Toplevel | None = None
        self.selector: tk.Toplevel | None = None

        rcParams["mathtext.fontset"] = "stix"
        rcParams["font.family"] = "Segoe UI"
        self._style()
        self._layout()
        self._recompute()
        self.root.bind("<Configure>", self._position_selector, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("R.TEntry", padding=7, fieldbackground=WHITE, foreground=INK,
                        bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("R.TCombobox", padding=6, fieldbackground=WHITE, background=WHITE,
                        foreground=INK, bordercolor=LINE)
        style.configure("Primary.TButton", padding=(14, 9), background=BLUE, foreground=WHITE,
                        borderwidth=0, font=("Segoe UI", 10))
        style.map("Primary.TButton", background=[("active", "#254E67")])
        style.configure("Quiet.TButton", padding=(12, 8), background=WHITE, foreground=INK,
                        bordercolor=LINE, borderwidth=1, font=("Segoe UI", 10))
        style.map("Quiet.TButton", background=[("active", "#F3F6F7")])
        style.configure("R.Horizontal.TScale", background=WHITE, troughcolor=LINE)
        style.configure("R.TCheckbutton", background=WHITE, foreground=MUTED,
                        font=("Segoe UI", 9))
        style.configure("Link.TButton", padding=(8, 4), background=WHITE,
                        foreground=BLUE, borderwidth=0, font=("Segoe UI", 9))
        style.map("Link.TButton", foreground=[("active", "#254E67")],
                  background=[("active", WHITE)])

    def _layout(self) -> None:
        formula_frame = tk.Frame(self.root, bg=WHITE, padx=27, pady=15)
        formula_frame.pack(fill="x")
        self.formula_figure = Figure(figsize=(8, 0.78), dpi=100, facecolor=WHITE)
        self.formula_figure.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self.formula_axis = self.formula_figure.add_axes((0, 0, 1, 1))
        self.formula_axis.axis("off")
        self.formula_text = self.formula_axis.text(0.01, 0.50, "", fontsize=22,
                                                   ha="left", va="center", color=INK)
        self.formula_canvas = FigureCanvasTkAgg(self.formula_figure, master=formula_frame)
        self.choose_button = ttk.Button(formula_frame, text="Выбрать ряд  ▾",
                                        command=self._open_selector, style="Link.TButton")
        self.choose_button.pack(side="right", padx=(0, 10))
        formula_widget = self.formula_canvas.get_tk_widget()
        formula_widget.configure(cursor="hand2")
        formula_widget.bind("<Button-1>", self._open_selector)
        formula_widget.pack(side="left", fill="x", expand=True)
        tk.Frame(self.root, bg=LINE, height=1).pack(fill="x")

        body = tk.Frame(self.root, bg=WHITE)
        body.pack(fill="both", expand=True)
        sidebar_view = tk.Frame(body, bg=WHITE, width=round(270 * self.scale))
        sidebar_view.pack(side="left", fill="y")
        sidebar_view.pack_propagate(False)
        sidebar_canvas = tk.Canvas(sidebar_view, bg=WHITE, highlightthickness=0, bd=0)
        sidebar_canvas.pack(side="left", fill="both", expand=True)
        sidebar_scroll = ttk.Scrollbar(sidebar_view, orient="vertical", command=sidebar_canvas.yview)
        sidebar_scroll.pack(side="right", fill="y")
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar = tk.Frame(sidebar_canvas, bg=WHITE, padx=26, pady=18)
        sidebar_window = sidebar_canvas.create_window(0, 0, window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda _event: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda event: sidebar_canvas.itemconfigure(sidebar_window, width=event.width))
        tk.Frame(body, bg=LINE, width=1).pack(side="left", fill="y")
        main = tk.Frame(body, bg=WHITE, padx=26, pady=23)
        main.pack(side="left", fill="both", expand=True)

        self.vars = {
            "target": tk.StringVar(value="2"),
            "epsilon": tk.StringVar(value="0,05"),
            "a": tk.StringVar(value="1,5"),
            "b": tk.StringVar(value="0,5"),
            "p": tk.StringVar(value="0,6"),
        }
        self._section(sidebar, "ЦЕЛЬ")
        self._field(sidebar, "Сумма L", "target")
        self._field(sidebar, "Точность ε", "epsilon")
        self._section(sidebar, "ШАГОВ ДО ТОЧНОСТИ ε")
        self.estimate = tk.Label(sidebar, text="—", bg=WHITE, fg=INK,
                                 font=("Segoe UI", 22, "bold"), anchor="w")
        self.estimate.pack(fill="x")
        self.estimate_note = tk.Label(sidebar, text="", bg=WHITE, fg=MUTED,
                                      font=("Segoe UI", 9), justify="left", anchor="nw",
                                      wraplength=210)
        self.estimate_note.pack(fill="x", pady=(4, 0))
        self._separator(sidebar)
        self._section(sidebar, "ПАРАМЕТРЫ РЯДА")
        self.a_field, self.a_label = self._field(sidebar, "Коэффициент A", "a")
        self.b_field, _ = self._field(sidebar, "Коэффициент B", "b")
        self.p_field, _ = self._field(sidebar, "Степень p", "p")
        self.validation = tk.Label(sidebar, text="A > |B|   ·   0 < p ≤ 1", bg=WHITE,
                                   fg=MUTED, font=("Segoe UI", 9), anchor="w",
                                   justify="left", wraplength=210)
        self.validation.pack(fill="x", pady=(2, 0))

        def bind_wheel(widget: tk.Widget) -> None:
            widget.bind("<MouseWheel>", lambda event: sidebar_canvas.yview_scroll(-int(event.delta / 120), "units"))
            for child in widget.winfo_children():
                bind_wheel(child)
        bind_wheel(sidebar)

        plot_header = tk.Frame(main, bg=WHITE)
        plot_header.pack(fill="x")
        tk.Label(plot_header, text="Частичные суммы", bg=WHITE, fg=INK,
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        self.zoom_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(plot_header, text="Вблизи L", variable=self.zoom_var,
                        command=self._toggle_zoom, style="R.TCheckbutton").pack(side="right")

        legend = tk.Frame(main, bg=WHITE)
        legend.pack(fill="x", pady=(10, 0))
        for swatch, title, color in (("━━", "Без перестановки", ORIGINAL),
                                      ("━━", "После перестановки", INK),
                                      ("┄┄", "Цель L", BLUE)):
            item = tk.Frame(legend, bg=WHITE)
            item.pack(side="left", padx=(0, 18))
            tk.Label(item, text=swatch, bg=WHITE, fg=color, font=("Segoe UI", 10)).pack(side="left")
            tk.Label(item, text=title, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 9)).pack(side="left", padx=(5, 0))

        self.figure = Figure(figsize=(7, 4), dpi=100, facecolor=WHITE)
        self.figure.subplots_adjust(left=0.10, right=0.99, bottom=0.18, top=0.97)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=main)
        footer = tk.Frame(main, bg=WHITE)
        footer.pack(side="bottom", fill="x")

        self.axis_caption = tk.Label(footer, text="Число членов k", bg=WHITE, fg=MUTED,
                                     font=("Segoe UI", 9))
        self.axis_caption.pack(fill="x", pady=(0, 5))
        tk.Frame(footer, bg=LINE, height=1).pack(fill="x", pady=(11, 0))
        metrics = tk.Frame(footer, bg=WHITE, pady=12)
        metrics.pack(fill="x")
        for label, key in (("Сумма Sₖ", "sum"), ("Ошибка |Sₖ−L|", "error"), ("Взято членов", "count")):
            cell = tk.Frame(metrics, bg=WHITE)
            cell.pack(side="left", fill="x", expand=True)
            tk.Label(cell, text=label, bg=WHITE, fg=MUTED,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")
            value = tk.Label(cell, text="—", bg=WHITE, fg=INK,
                             font=("Segoe UI", 16, "bold"), anchor="w")
            value.pack(fill="x", pady=(3, 0))
            setattr(self, f"metric_{key}", value)
        tk.Frame(footer, bg=LINE, height=1).pack(fill="x")

        self.position = ttk.Scale(footer, from_=0, to=1, orient="horizontal",
                                  command=self._scrub, style="R.Horizontal.TScale")
        self.position.pack(fill="x", pady=(18, 10))
        controls = tk.Frame(footer, bg=WHITE)
        controls.pack(fill="x")
        self.play_button = ttk.Button(controls, text="Воспроизвести", command=self._toggle_play,
                                      style="Primary.TButton")
        self.play_button.pack(side="left")
        ttk.Button(controls, text="Шаг", command=self._one_step,
                   style="Quiet.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Сначала", command=self._reset_position,
                   style="Quiet.TButton").pack(side="left", padx=(8, 0))
        self.speed = ttk.Combobox(controls, values=("1x", "5x", "20x"),
                                  state="readonly", width=5, style="R.TCombobox")
        self.speed.set("5x")
        self.speed.pack(side="right")
        tk.Label(controls, text="Скорость", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=(0, 9))
        plot_widget = self.canvas.get_tk_widget()
        plot_widget.pack(fill="both", expand=True, pady=(8, 0))
        plot_widget.bind("<Configure>", self._resize_plot, add="+")
        self._reset_plot()

        for var in self.vars.values():
            var.trace_add("write", self._schedule_recompute)

    def _section(self, parent: tk.Widget, title: str) -> None:
        tk.Label(parent, text=title, bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(0, 7))

    def _field(self, parent: tk.Widget, title: str, key: str) -> tuple[tk.Frame, tk.Label]:
        field = tk.Frame(parent, bg=WHITE)
        field.pack(fill="x")
        label = tk.Label(field, text=title, bg=WHITE, fg=INK,
                         font=("Segoe UI", 10), anchor="w")
        label.pack(fill="x", pady=(2, 3))
        ttk.Entry(field, textvariable=self.vars[key], style="R.TEntry").pack(fill="x", pady=(0, 7))
        return field, label

    def _separator(self, parent: tk.Widget) -> None:
        tk.Frame(parent, bg=LINE, height=1).pack(fill="x", pady=(10, 13))

    def _open_selector(self, _event: object = None) -> None:
        if self.selector is not None:
            self.selector.lift()
            return
        self._pause()
        self.root.update_idletasks()
        self.overlay = tk.Toplevel(self.root)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg="#192B36")
        self.overlay.attributes("-alpha", 0.38)
        self.overlay.transient(self.root)
        self.overlay.bind("<Button-1>", lambda _event: self._close_selector())

        self.selector = tk.Toplevel(self.overlay)
        self.selector.withdraw()
        self.selector.overrideredirect(True)
        self.selector.configure(bg=WHITE)
        self.selector.transient(self.overlay)
        self.selector.bind("<Escape>", lambda _event: self._close_selector())
        card = tk.Frame(self.selector, bg=WHITE, highlightbackground=LINE,
                        highlightthickness=1)
        card.pack(fill="both", expand=True)
        heading = tk.Frame(card, bg=WHITE, padx=22, pady=14)
        heading.pack(fill="x")
        tk.Label(heading, text="Выбрать ряд", bg=WHITE, fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        close_button = tk.Label(heading, text="×", bg=WHITE, fg=MUTED, cursor="hand2",
                                font=("Segoe UI", 17))
        close_button.pack(side="right")
        close_button.bind("<Button-1>", lambda _event: self._close_selector())
        tk.Frame(card, bg=LINE, height=1).pack(fill="x")

        self.selector_canvases = []
        selected_row = None
        for index, (kind, title, formula) in enumerate(PRESETS):
            row = tk.Frame(card, bg=WHITE, padx=22, pady=8, cursor="hand2", takefocus=1)
            row.pack(fill="x")
            marker = tk.Frame(row, bg=BLUE if kind == self.kind else WHITE, width=3)
            marker.pack(side="left", fill="y", padx=(0, 14))
            content = tk.Frame(row, bg=WHITE)
            content.pack(side="left", fill="x", expand=True)
            name = tk.Label(content, text=title, bg=WHITE,
                            fg=BLUE if kind == self.kind else INK,
                            font=("Segoe UI", 10, "bold"), anchor="w", cursor="hand2")
            name.pack(fill="x")
            figure = Figure(figsize=(4.6, 0.55), dpi=100, facecolor=WHITE)
            axis = figure.add_axes((0, 0, 1, 1))
            axis.axis("off")
            axis.text(0.01, 0.50, formula, fontsize=15, color=INK,
                      ha="left", va="center")
            canvas = FigureCanvasTkAgg(figure, master=content)
            self.selector_canvases.append(canvas)
            formula_widget = canvas.get_tk_widget()
            formula_widget.configure(cursor="hand2")
            formula_widget.pack(fill="x")
            canvas.draw_idle()
            choose = lambda _event, selected=kind: self._select_preset(selected)
            for widget in (row, marker, content, name, formula_widget):
                widget.bind("<Button-1>", choose)
            row.bind("<Return>", choose)
            row.bind("<space>", choose)
            if kind == self.kind:
                selected_row = row
            if index < len(PRESETS) - 1:
                tk.Frame(card, bg=LINE, height=1).pack(fill="x", padx=22)

        self.overlay.deiconify()
        self.selector.deiconify()
        self.overlay.update_idletasks()
        self.selector.update_idletasks()
        self._position_selector()
        self.selector.lift(self.overlay)
        if selected_row is not None:
            selected_row.focus_set()
        self.root.after_idle(self._position_selector)

    def _position_selector(self, event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not self.root:
            return
        if self.overlay is None or self.selector is None:
            return
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        width, height = self.root.winfo_width(), self.root.winfo_height()
        self.overlay.geometry(f"{width}x{height}+{x}+{y}")
        card_width = min(round(540 * self.scale), width - 40)
        card_height = min(round(430 * self.scale), height - 40)
        self.selector.geometry(f"{card_width}x{card_height}+{x + (width-card_width)//2}+{y + (height-card_height)//2}")

    def _close_selector(self) -> None:
        if self.selector is not None:
            self.selector.destroy()
            self.selector = None
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None
        self.selector_canvases = []
        self.choose_button.focus_set()

    def _select_preset(self, kind: str) -> None:
        self._close_selector()
        if kind == self.kind:
            return
        if self.recompute_timer:
            self.root.after_cancel(self.recompute_timer)
            self.recompute_timer = None
        self.preset_values[self.kind] = tuple(self.vars[key].get() for key in ("a", "b", "p"))
        self.kind = kind
        self.switching_preset = True
        for key, value in zip(("a", "b", "p"), self.preset_values[kind]):
            self.vars[key].set(value)
        self.switching_preset = False
        self.a_label.configure(text="Коэффициент A" if kind == "wave" else "Коэффициент C")
        for field in (self.b_field, self.p_field):
            if kind == "wave":
                field.pack(fill="x", before=self.validation)
            else:
                field.pack_forget()
        self._recompute()

    def _resize_plot(self, event: tk.Event) -> None:
        self.figure.subplots_adjust(bottom=min(0.45, max(0.13, 30 * self.scale / event.height)))
        self.canvas.draw_idle()

    def _schedule_recompute(self, *_args: object) -> None:
        if self.switching_preset:
            return
        if self.recompute_timer:
            self.root.after_cancel(self.recompute_timer)
        self.recompute_timer = self.root.after(350, self._recompute)

    def _parameters(self) -> Parameters:
        def read(key: str) -> float:
            return float(self.vars[key].get().strip().replace(",", "."))
        wave = self.kind == "wave"
        params = Parameters(read("target"), read("epsilon"), read("a"),
                            read("b") if wave else 0, read("p") if wave else 1,
                            self.kind)
        params.validate()
        return params

    def _recompute(self) -> None:
        self.recompute_timer = None
        self._pause()
        try:
            params = self._parameters()
        except (ValueError, OverflowError) as exc:
            self.params = None
            self.result = None
            self.validation.configure(text=str(exc) or "Проверьте значения.", fg=ERROR)
            self.estimate.configure(text="—")
            self.estimate_note.configure(text="")
            self.formula_text.set_text("")
            self.formula_canvas.draw_idle()
            self._clear_plot()
            return

        self.params = params
        self.validation.configure(text="A > |B|   ·   0 < p ≤ 1" if self.kind == "wave" else "C > 0", fg=MUTED)
        self.result = calculate(params)
        self.step = 0
        self.syncing_scale = True
        self.position.configure(to=max(1, len(self.result.rearranged) - 1))
        self.position.set(0)
        self.syncing_scale = False
        if self.result.stable_step is None:
            self.estimate.configure(text=steps_text(max(MAX_STEPS + 1, rough_steps(params)), approximate=True))
            self.estimate_note.configure(text=f"Оценка; показ до {steps_text(MAX_STEPS)} шагов.")
        else:
            self.estimate.configure(text=steps_text(self.result.stable_step))
            self.estimate_note.configure(text="До устойчивого приближения.")
        self._update_formula()
        self._reset_plot()
        self._update_plot()

    def _update_formula(self) -> None:
        assert self.params is not None
        self.formula_text.set_text(latex_formula(self.params))
        self.formula_canvas.draw_idle()

    def _clear_plot(self) -> None:
        self.ax.clear()
        self._style_axes()
        self.canvas.draw_idle()
        for widget in (self.metric_sum, self.metric_error, self.metric_count):
            widget.configure(text="—")

    def _style_axes(self) -> None:
        self.ax.set_facecolor(WHITE)
        self.ax.spines[["top", "right"]].set_visible(False)
        self.ax.spines[["left", "bottom"]].set_color(LINE)
        self.ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=7)
        self.ax.grid(axis="y", color="#EDF0F1", linewidth=0.8)
        self.ax.set_ylabel("Сумма", color=MUTED, fontsize=9, labelpad=9)

    def _reset_plot(self) -> None:
        self.ax.clear()
        self._style_axes()
        self.original_line, = self.ax.plot([], [], color=ORIGINAL, linewidth=1.4,
                                            label="Без перестановки")
        self.rearranged_line, = self.ax.plot([], [], color=INK, linewidth=1.8,
                                              label="После перестановки")
        self.current_dot, = self.ax.plot([], [], marker="o", markersize=5,
                                          markerfacecolor=BLUE, markeredgecolor=WHITE,
                                          markeredgewidth=1.2, linestyle="None")
        if self.params is not None:
            p = self.params
            self.target_band = self.ax.axhspan(p.target - p.epsilon, p.target + p.epsilon,
                                               color=BLUE_LIGHT, linewidth=0)
            self.target_line = self.ax.axhline(p.target, color=BLUE, linewidth=1.3,
                                               linestyle=(0, (4, 3)), label="Цель L")
        self.canvas.draw_idle()

    def _toggle_zoom(self) -> None:
        self._update_plot()

    def _update_plot(self) -> None:
        if self.result is None or self.params is None:
            return
        k = self.step
        start = max(0, k - 180) if self.zoom_var.get() else 0
        indices = list(range(start, k + 1, max(1, (k - start) // 900)))
        if indices[-1] != k:
            indices.append(k)
        self.rearranged_line.set_data(indices, [self.result.rearranged[i] for i in indices])
        self.original_line.set_data(indices, [self.result.original[i] for i in indices])
        self.original_line.set_visible(not self.zoom_var.get())
        self.current_dot.set_data([k], [self.result.rearranged[k]])

        self.ax.set_xlim(start, max(start + 20, k + 2))
        values = [self.result.rearranged[i] for i in indices] + [self.params.target]
        if not self.zoom_var.get():
            values.extend(self.result.original[i] for i in indices)
        low, high = min(values), max(values)
        pad = max(self.params.epsilon * 4, (high - low) * 0.12, 0.05)
        self.ax.set_ylim(low - pad, high + pad)
        self.canvas.draw_idle()

        digits = min(14, max(3, math.ceil(-math.log10(self.params.epsilon)) + 2))
        value = self.result.rearranged[k]
        error = abs(value - self.params.target)
        self.metric_sum.configure(text=number(value, digits))
        self.metric_error.configure(text=number(error, digits))
        self.metric_count.configure(text=steps_text(k))

    def _scrub(self, raw: str) -> None:
        if self.syncing_scale or self.result is None:
            return
        self._pause()
        self.step = min(len(self.result.rearranged) - 1, max(0, round(float(raw))))
        self._update_plot()

    def _move_to(self, step: int) -> None:
        if self.result is None:
            return
        self.step = min(len(self.result.rearranged) - 1, max(0, step))
        self.syncing_scale = True
        self.position.set(self.step)
        self.syncing_scale = False
        self._update_plot()

    def _tick(self) -> None:
        self.timer = None
        if not self.playing or self.result is None:
            return
        increment = {"1x": 1, "5x": 5, "20x": 20}[self.speed.get()]
        self._move_to(self.step + increment)
        if self.step >= len(self.result.rearranged) - 1:
            self._pause()
            self._update_plot()
        else:
            self.timer = self.root.after(55, self._tick)

    def _toggle_play(self) -> None:
        if self.result is None:
            return
        if self.playing:
            self._pause()
            self._update_plot()
            return
        if self.step >= len(self.result.rearranged) - 1:
            self._move_to(0)
        self.playing = True
        self.play_button.configure(text="Пауза")
        self._tick()

    def _pause(self) -> None:
        if self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.playing = False
        self.play_button.configure(text="Воспроизвести")

    def _one_step(self) -> None:
        self._pause()
        self._move_to(self.step + 1)

    def _reset_position(self) -> None:
        self._pause()
        self._move_to(0)

    def _close(self) -> None:
        self._pause()
        if self.recompute_timer:
            self.root.after_cancel(self.recompute_timer)
        self._close_selector()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    root.report_callback_exception = lambda _type, error, _trace: messagebox.showerror("Ошибка", str(error))
    RiemannApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
