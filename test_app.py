"""Small runnable checks for the series and the displayed formula."""

import os
import tempfile
import math

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "RiemannDemo"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import tkinter as tk

from app import RiemannApp, latex_formula
from series import Parameters, bound, calculate, next_index, rough_steps, term


for params in (
    Parameters(2, 0.05, 1.5, 0.5, 0.6),
    Parameters(-1, 0.08, 1.2, -0.3, 0.75),
    Parameters(2, 0.05, 1, kind="harmonic"),
    Parameters(2, 0.05, 1, kind="leibniz"),
    Parameters(2, 0.05, 1, kind="sine"),
    Parameters(-1, 0.08, 1, kind="sine"),
):
    result = calculate(params)
    assert result.stable_step is not None
    assert len(result.rearranged) == len(result.original)

    positive = next_index(1, 1, params)
    negative = next_index(1, -1, params)
    for k in range(1, len(result.rearranged)):
        assert math.isclose(result.original[k] - result.original[k - 1],
                            term(k, params), abs_tol=1e-10)
        if result.rearranged[k - 1] <= params.target:
            expected = term(positive, params)
            positive = next_index(positive + 1, 1, params)
        else:
            expected = term(negative, params)
            negative = next_index(negative + 1, -1, params)
        assert math.isclose(result.rearranged[k] - result.rearranged[k - 1],
                            expected, abs_tol=1e-10)

    assert abs(result.rearranged[-1] - params.target) <= params.epsilon
    assert bound(positive, params) <= params.epsilon
    assert bound(negative, params) <= params.epsilon
    current = result.rearranged[-1]
    for _ in range(1000):
        if current <= params.target:
            current += term(positive, params)
            positive = next_index(positive + 1, 1, params)
        else:
            current += term(negative, params)
            negative = next_index(negative + 1, -1, params)
        assert abs(current - params.target) <= params.epsilon + 1e-12

    figure = Figure(figsize=(7, 1))
    figure.text(0.02, 0.5, latex_formula(params), fontsize=18)
    FigureCanvasAgg(figure).draw()

slow = Parameters(10, 0.001, 3, 0, 0.4)
assert calculate(slow, limit=1000).stable_step is None
assert rough_steps(slow) > 100_000_000
assert term(2, Parameters(0, 0.1, 1, kind="harmonic")) == -0.5
assert math.isclose(term(2, Parameters(0, 0.1, 1, kind="leibniz")), -1 / 3)
assert math.isclose(term(1, Parameters(0, 0.1, 1, kind="sine")), math.sin(1))

root = tk.Tk()
app = RiemannApp(root)
minimum_width, minimum_height = root.minsize()
root.geometry(f"{minimum_width}x{minimum_height}")
root.update()
sidebar_canvas = app.estimate.master.master
assert app.estimate.winfo_rooty() >= sidebar_canvas.winfo_rooty()
assert app.estimate.winfo_rooty() + app.estimate.winfo_height() <= sidebar_canvas.winfo_rooty() + sidebar_canvas.winfo_height()
for widget in (app.canvas.get_tk_widget(), app.axis_caption, app.metric_count,
               app.position, app.play_button, app.speed):
    assert widget.winfo_width() > 1 and widget.winfo_height() > 1
    assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width()
    assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
assert app.canvas.get_tk_widget().winfo_height() >= 120
app.canvas.draw()
renderer = app.canvas.get_renderer()
assert all(tick.label1.get_window_extent(renderer).y0 >= 0
           for tick in app.ax.xaxis.get_major_ticks() if tick.label1.get_visible())
app.speed.set("20x")
app._toggle_play()
assert app.step == 20
app._pause()
app._open_selector()
root.update()
assert app.selector is not None and app.overlay is not None
assert len(app.selector_canvases) == 4
assert app.selector.winfo_height() < root.winfo_height()
assert (app.overlay.winfo_rootx(), app.overlay.winfo_rooty()) == (root.winfo_rootx(), root.winfo_rooty())
assert (app.overlay.winfo_width(), app.overlay.winfo_height()) == (root.winfo_width(), root.winfo_height())
for canvas in app.selector_canvases:
    canvas.draw()
    text = canvas.figure.axes[0].texts[0]
    box = text.get_window_extent(canvas.get_renderer())
    assert 0 <= box.x0 < box.x1 <= canvas.figure.bbox.width
    assert 0 <= box.y0 < box.y1 <= canvas.figure.bbox.height
app._select_preset("harmonic")
assert app.kind == "harmonic" and not app.b_field.winfo_manager()
assert app.vars["target"].get() == "2"
assert app.result.stable_step is not None
app.vars["a"].set("2")
app._select_preset("leibniz")
assert app.kind == "leibniz" and app.result.stable_step is not None
app._select_preset("sine")
assert app.kind == "sine" and app.result.stable_step is not None
app._select_preset("harmonic")
assert app.vars["a"].get() == "2"
app._select_preset("wave")
assert app.b_field.winfo_manager() == "pack" and app.p_field.winfo_manager() == "pack"
root.update()
sidebar_canvas.yview_moveto(1)
root.update()
assert app.validation.winfo_rooty() + app.validation.winfo_height() <= sidebar_canvas.winfo_rooty() + sidebar_canvas.winfo_height()
root.destroy()

print("Series, formula and minimum-window layout checks passed.")
