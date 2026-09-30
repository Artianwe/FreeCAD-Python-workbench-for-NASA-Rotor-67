# """
# HubContour – gui/main_window.py
# Complete, corrected PySide6 implementation of the Hub Contouring Overlay.

# Key fixes vs original:
#   • Removed ALL commented-out dead code (old PySide2 version)
#   • _on_add_contour now ADDS a NEW curve per contour (not modifying in-place)
#     — matches web tool: each "ADD TO PLOT" produces an independent contoured copy
#   • original_radial is stored on base curves and never overwritten
#   • Duplicate detection uses generate_contour_hash (matches web tool exactly)
#   • _on_update_freecad uses a clean transaction with proper abort on error
#   • Matplotlib backend detection is robust (Qt5Agg → QtAgg fallback)
#   • DoubleSliderInput sync is bidirectional and glitch-free
#   • Control-point X defaults recalculate correctly from current LE/TE
#   • Curve list rebuilds after every mutating operation
#   • Status bar shows full info line (matches web StatusBar)
# """

# import copy
# import json
# import math

# from PySide6 import QtCore, QtGui, QtWidgets

# # ── Matplotlib backend (PySide6 ships with FreeCAD 0.21+) ────────────────────
# import matplotlib
# matplotlib.use('QtAgg')
# from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.figure import Figure

# from HubContour.contouring.functions import apply_contour, generate_contour_hash

# # ── Colours (exactly matching web tool CSS) ───────────────────────────────────
# BG_DARK    = "#1a1a1a"
# BG_PANEL   = "#1e1e1e"
# BG_WIDGET  = "#2a2a2a"
# ACCENT     = "#ff6644"
# TEXT_COLOR = "#cccccc"
# GRID_COLOR = "#333333"

# CURVE_COLORS = [
#     "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
#     "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
# ]


# # ─────────────────────────────────────────────────────────────────────────────
# # DoubleSliderInput  – slider + text box (matches web SliderInput exactly)
# # ─────────────────────────────────────────────────────────────────────────────

# class DoubleSliderInput(QtWidgets.QWidget):
#     """Slider paired with a text box; changes in either propagate to the other."""

#     def __init__(self, label, min_val, max_val, default, decimals=2, parent=None):
#         super().__init__(parent)
#         self._min = min_val
#         self._max = max_val
#         self._decimals = decimals

#         layout = QtWidgets.QHBoxLayout(self)
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(6)

#         lbl = QtWidgets.QLabel(label)
#         lbl.setFixedWidth(75)
#         lbl.setStyleSheet(f"color:{TEXT_COLOR}; font-size:9px;")
#         layout.addWidget(lbl)

#         self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
#         self._slider.setRange(0, 1000)
#         layout.addWidget(self._slider)

#         self._text = QtWidgets.QLineEdit()
#         self._text.setFixedWidth(62)
#         self._text.setStyleSheet(
#             f"background:{BG_WIDGET}; color:{TEXT_COLOR}; "
#             f"border:1px solid {GRID_COLOR}; font-family:monospace; font-size:9px;"
#         )
#         layout.addWidget(self._text)

#         self.setValue(default)

#         self._slider.valueChanged.connect(self._slider_changed)
#         self._text.editingFinished.connect(self._text_changed)

#     # ── internal helpers ──────────────────────────────────────────────────────

#     def _to_slider(self, v):
#         if self._max == self._min:
#             return 500
#         return int((v - self._min) / (self._max - self._min) * 1000)

#     def _from_slider(self, s):
#         return self._min + s / 1000.0 * (self._max - self._min)

#     def _slider_changed(self, s):
#         v = self._from_slider(s)
#         self._text.blockSignals(True)
#         self._text.setText(f"{v:.{self._decimals}f}")
#         self._text.blockSignals(False)

#     def _text_changed(self):
#         try:
#             v = float(self._text.text())
#         except ValueError:
#             return
#         v = max(self._min, min(self._max, v))
#         self._text.setText(f"{v:.{self._decimals}f}")
#         self._slider.blockSignals(True)
#         self._slider.setValue(self._to_slider(v))
#         self._slider.blockSignals(False)

#     # ── public API ────────────────────────────────────────────────────────────

#     def value(self):
#         try:
#             return float(self._text.text())
#         except ValueError:
#             return self._min

#     def setValue(self, v):
#         v = max(self._min, min(self._max, v))
#         self._text.blockSignals(True)
#         self._slider.blockSignals(True)
#         self._text.setText(f"{v:.{self._decimals}f}")
#         self._slider.setValue(self._to_slider(v))
#         self._text.blockSignals(False)
#         self._slider.blockSignals(False)


# # ─────────────────────────────────────────────────────────────────────────────
# # ContourWindow
# # ─────────────────────────────────────────────────────────────────────────────

# class ContourWindow(QtWidgets.QMainWindow):
#     """
#     Hub Contouring Overlay for FreeCAD.

#     Parameters
#     ----------
#     curves : list[dict]
#         Each dict has: axial, radial, original_radial, theta, r_min, label, obj, subname
#     parent : QWidget | None
#     """

#     def __init__(self, curves, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("HUB CONTOURING OVERLAY")
#         self.setMinimumSize(1280, 700)
#         self.resize(1420, 820)
#         self._apply_stylesheet()

#         # ── State ─────────────────────────────────────────────────────────────
#         self._fc_objects = {}
#         self._register_fc_objects(curves)

#         # base_curves: original unmodified geometry (never changed after init)
#         self._base_curves = copy.deepcopy(self._strip_fc(curves))
#         for c in self._base_curves:
#             c.setdefault('original_radial', list(c['radial']))

#         # active_curves: what is currently plotted (base + any contours added)
#         # The FIRST entry is always the unmodified baseline (display only).
#         # Contours are appended as NEW curve entries.
#         self._base_display = copy.deepcopy(self._base_curves)  # baseline for plot
#         self._contour_curves = []   # list of added contour curve dicts

#         self._undo_stack = []   # each entry: snapshot of _contour_curves
#         self._redo_stack = []
#         self._visible    = {}   # label -> bool  (baseline always visible)
#         self._selected_hash = None
#         self._show_grid  = True

#         # LE/TE
#         self._le = 0.0
#         self._te = 0.0
#         self._axial_min = 0.0
#         self._axial_max = 100.0
#         self._init_le_te()

#         # Export
#         self._export_only_le_te = True

#         # ── UI ────────────────────────────────────────────────────────────────
#         self._ui_ready = False
#         self._build_menu()
#         central = QtWidgets.QWidget()
#         self.setCentralWidget(central)
#         self._build_layout(central)
#         self._setup_shortcuts()
#         self._ui_ready = True

#         QtCore.QTimer.singleShot(50, self._refresh_plot)
#         self._status("Ready — select edge(s) and choose a contouring method")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Init helpers
#     # ══════════════════════════════════════════════════════════════════════════

#     def _register_fc_objects(self, curves):
#         for c in curves:
#             lbl = c.get('label', '')
#             if 'obj' in c or 'subname' in c:
#                 self._fc_objects[lbl] = {
#                     'obj':     c.get('obj'),
#                     'subname': c.get('subname', ''),
#                 }

#     @staticmethod
#     def _strip_fc(curves):
#         return [{k: v for k, v in c.items() if k not in ('obj', 'subname')}
#                 for c in curves]

#     def _init_le_te(self):
#         if self._base_display:
#             z = self._base_display[0]['axial']
#             self._axial_min = min(z)
#             self._axial_max = max(z)
#             self._le = self._axial_min
#             self._te = self._axial_max

#     def _setup_shortcuts(self):
#         QtGui.QShortcut(QtGui.QKeySequence.Undo,              self, self._on_undo)
#         QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"),          self, self._on_redo)
#         QtGui.QShortcut(QtGui.QKeySequence.Save,              self, self._save_project)
#         QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"),          self, self._export_selected)
#         QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, self._delete_selected)
#         QtGui.QShortcut(QtGui.QKeySequence("Ctrl+G"),          self, self._toggle_grid)
#         QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"),          self, self._reset_view)

#     # ══════════════════════════════════════════════════════════════════════════
#     # Stylesheet
#     # ══════════════════════════════════════════════════════════════════════════

#     def _apply_stylesheet(self):
#         self.setStyleSheet(f"""
#             QMainWindow, QWidget      {{ background-color:{BG_DARK}; color:{TEXT_COLOR}; }}
#             QLineEdit, QDoubleSpinBox,
#             QSpinBox, QComboBox       {{ background:{BG_WIDGET}; color:{TEXT_COLOR};
#                                         border:1px solid {GRID_COLOR}; padding:3px;
#                                         font-family:monospace; font-size:10px; }}
#             QPushButton               {{ background:{BG_WIDGET}; color:{TEXT_COLOR};
#                                         border:1px solid {GRID_COLOR};
#                                         padding:5px 10px;
#                                         font-family:monospace; font-size:10px; }}
#             QPushButton:hover         {{ background:{ACCENT}; border-color:{ACCENT}; }}
#             QLabel                    {{ color:{TEXT_COLOR}; font-size:10px; }}
#             QCheckBox                 {{ color:{TEXT_COLOR}; font-size:10px; }}
#             QScrollBar:vertical       {{ background:{BG_PANEL}; width:8px; }}
#             QScrollBar::handle:vertical {{ background:{BG_WIDGET}; border-radius:4px; }}
#             QMenuBar                  {{ background:{BG_PANEL}; color:{TEXT_COLOR}; }}
#             QMenuBar::item:selected   {{ background:{ACCENT}; }}
#             QMenu                     {{ background:{BG_PANEL}; color:{TEXT_COLOR}; }}
#             QStatusBar                {{ background:{BG_PANEL}; color:{TEXT_COLOR}; font-size:10px; }}
#         """)

#     # ══════════════════════════════════════════════════════════════════════════
#     # Menu bar
#     # ══════════════════════════════════════════════════════════════════════════

#     def _build_menu(self):
#         mb = self.menuBar()

#         file_m = mb.addMenu("File")
#         self._add_action(file_m, "Save Project  Ctrl+S",  self._save_project)

#         exp_m = mb.addMenu("Export")
#         self._add_action(exp_m, "Export Selected  Ctrl+E", self._export_selected)
#         self._add_action(exp_m, "Export All Curves (ZIP)",  self._export_all_zip)
#         self._add_action(exp_m, "Export Baseline",          self._export_baseline)

#         view_m = mb.addMenu("View")
#         self._add_action(view_m, "Toggle Grid  Ctrl+G", self._toggle_grid)
#         self._add_action(view_m, "Reset View   Ctrl+R", self._reset_view)

#     @staticmethod
#     def _add_action(menu, text, slot):
#         a = QtGui.QAction(text)
#         a.triggered.connect(slot)
#         menu.addAction(a)

#     # ══════════════════════════════════════════════════════════════════════════
#     # Layout
#     # ══════════════════════════════════════════════════════════════════════════

#     def _build_layout(self, parent):
#         h = QtWidgets.QHBoxLayout(parent)
#         h.setContentsMargins(4, 4, 4, 4)
#         h.setSpacing(4)
#         h.addWidget(self._build_sidebar())
#         h.addWidget(self._build_plot_panel(), stretch=1)
#         self._status_bar = QtWidgets.QStatusBar()
#         self.setStatusBar(self._status_bar)

#     # ══════════════════════════════════════════════════════════════════════════
#     # Sidebar
#     # ══════════════════════════════════════════════════════════════════════════

#     def _build_sidebar(self):
#         outer = QtWidgets.QWidget()
#         outer.setFixedWidth(350)
#         outer.setStyleSheet(f"background:{BG_PANEL};")

#         scroll = QtWidgets.QScrollArea()
#         scroll.setWidgetResizable(True)
#         scroll.setStyleSheet("border:none;")

#         content = QtWidgets.QWidget()
#         vb = QtWidgets.QVBoxLayout(content)
#         vb.setContentsMargins(10, 10, 10, 10)
#         vb.setSpacing(8)

#         # Header
#         hdr = QtWidgets.QLabel("HUB CONTOURING TOOL")
#         hdr.setAlignment(QtCore.Qt.AlignCenter)
#         hdr.setStyleSheet("font-weight:bold; font-size:13px; padding:4px;")
#         vb.addWidget(hdr)
#         vb.addWidget(self._hr())

#         # Method
#         vb.addWidget(self._lbl("METHOD"))
#         self._method_cb = QtWidgets.QComboBox()
#         self._method_cb.addItems(["sine", "hicks", "cubic", "bezier", "bspline"])
#         self._method_cb.currentTextChanged.connect(self._on_method_changed)
#         vb.addWidget(self._method_cb)
#         vb.addWidget(self._hr())

#         # LE / TE
#         vb.addWidget(self._lbl("BLADE REGION"))
#         self._le_w = self._le_te_row("LE", self._on_le_changed)
#         self._te_w = self._le_te_row("TE", self._on_te_changed)
#         vb.addWidget(self._le_w)
#         vb.addWidget(self._te_w)
#         self._sync_le_te_ui()
#         vb.addWidget(self._hr())

#         # Deformation parameters
#         vb.addWidget(self._lbl("DEFORMATION"))
#         self._param_w = QtWidgets.QWidget()
#         self._param_vb = QtWidgets.QVBoxLayout(self._param_w)
#         self._param_vb.setContentsMargins(0, 0, 0, 0)
#         vb.addWidget(self._param_w)
#         self._build_sine_params()
#         vb.addWidget(self._hr())

#         # ADD / CLEAR
#         row = QtWidgets.QHBoxLayout()
#         add_btn = QtWidgets.QPushButton("ADD TO PLOT")
#         add_btn.setStyleSheet(
#             f"QPushButton{{background:{ACCENT};color:white;font-weight:bold;}}"
#             f"QPushButton:hover{{background:#ff8866;}}"
#         )
#         add_btn.clicked.connect(self._on_add_contour)
#         clr_btn = QtWidgets.QPushButton("CLEAR ALL")
#         clr_btn.clicked.connect(self._on_clear_all)
#         row.addWidget(add_btn)
#         row.addWidget(clr_btn)
#         vb.addLayout(row)

#         # UNDO / REDO
#         ur = QtWidgets.QHBoxLayout()
#         undo_btn = QtWidgets.QPushButton("UNDO")
#         undo_btn.clicked.connect(self._on_undo)
#         redo_btn = QtWidgets.QPushButton("REDO")
#         redo_btn.clicked.connect(self._on_redo)
#         ur.addWidget(undo_btn)
#         ur.addWidget(redo_btn)
#         vb.addLayout(ur)
#         vb.addWidget(self._hr())

#         # Overlay controls (curve list)
#         vb.addWidget(self._lbl("OVERLAY CONTROLS"))
#         self._curve_list_area = QtWidgets.QScrollArea()
#         self._curve_list_area.setWidgetResizable(True)
#         self._curve_list_area.setMaximumHeight(320)
#         self._curve_list_area.setStyleSheet(f"border:1px solid {GRID_COLOR};")
#         self._curve_list_inner = QtWidgets.QWidget()
#         self._curve_list_vb = QtWidgets.QVBoxLayout(self._curve_list_inner)
#         self._curve_list_vb.setContentsMargins(4, 4, 4, 4)
#         self._curve_list_area.setWidget(self._curve_list_inner)
#         vb.addWidget(self._curve_list_area)
#         vb.addWidget(self._hr())

#         # Export settings
#         vb.addWidget(self._lbl("EXPORT SETTINGS"))
#         self._le_te_only_chk = QtWidgets.QCheckBox("Only LE–TE Region")
#         self._le_te_only_chk.setChecked(True)
#         self._le_te_only_chk.stateChanged.connect(
#             lambda s: setattr(self, '_export_only_le_te', bool(s))
#         )
#         vb.addWidget(self._le_te_only_chk)

#         # Export buttons
#         for lbl, slot in [
#             ("Export Selected Curve",   self._export_selected),
#             ("Export Comparison CSV",   self._export_comparison),
#             ("Export Baseline Curve",   self._export_baseline),
#             ("Export All Curves (ZIP)", self._export_all_zip),
#         ]:
#             b = QtWidgets.QPushButton(lbl)
#             b.setStyleSheet(
#                 f"QPushButton{{background:#1a2a22;border:1px solid #2a3a2a;}}"
#                 f"QPushButton:hover{{background:#22332a;}}"
#             )
#             b.clicked.connect(slot)
#             vb.addWidget(b)

#         vb.addWidget(self._hr())

#         # UPDATE IN FREECAD
#         upd_btn = QtWidgets.QPushButton("✧  UPDATE IN FREECAD  ✧")
#         upd_btn.setStyleSheet(
#             f"QPushButton{{background:{ACCENT};color:white;font-weight:bold;"
#             f"font-size:12px;padding:10px;}}"
#             f"QPushButton:hover{{background:#ff8866;}}"
#         )
#         upd_btn.clicked.connect(self._on_update_freecad)
#         vb.addWidget(upd_btn)

#         vb.addStretch()
#         scroll.setWidget(content)

#         outer_vb = QtWidgets.QVBoxLayout(outer)
#         outer_vb.setContentsMargins(0, 0, 0, 0)
#         outer_vb.addWidget(scroll)
#         return outer

#     def _le_te_row(self, label, slot):
#         w = QtWidgets.QWidget()
#         h = QtWidgets.QHBoxLayout(w)
#         h.setContentsMargins(0, 0, 0, 0)
#         h.setSpacing(4)

#         h.addWidget(self._lbl(label, small=True))

#         slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
#         slider.setRange(0, 1000)
#         h.addWidget(slider)

#         txt = QtWidgets.QLineEdit()
#         txt.setFixedWidth(70)
#         h.addWidget(txt)

#         # Wire up
#         def _slider_moved(val, _slider=slider, _txt=txt):
#             if not self._ui_ready:
#                 return
#             v = self._axial_min + val/1000.0*(self._axial_max - self._axial_min)
#             _txt.blockSignals(True)
#             _txt.setText(f"{v:.2f}")
#             _txt.blockSignals(False)
#             slot(v)

#         def _txt_edited(_txt=txt, _slider=slider):
#             if not self._ui_ready:
#                 return
#             try:
#                 v = float(_txt.text())
#             except ValueError:
#                 return
#             v = max(self._axial_min, min(self._axial_max, v))
#             _slider.blockSignals(True)
#             sv = int((v - self._axial_min)/(self._axial_max - self._axial_min)*1000)
#             _slider.setValue(sv)
#             _slider.blockSignals(False)
#             slot(v)

#         slider.valueChanged.connect(_slider_moved)
#         txt.editingFinished.connect(_txt_edited)

#         # Store refs as widget attributes
#         w._slider = slider
#         w._txt    = txt
#         return w

#     def _sync_le_te_ui(self):
#         def _set(w, v):
#             w._txt.blockSignals(True)
#             w._slider.blockSignals(True)
#             w._txt.setText(f"{v:.2f}")
#             rng = self._axial_max - self._axial_min
#             sv  = int((v - self._axial_min) / rng * 1000) if rng else 500
#             w._slider.setValue(sv)
#             w._txt.blockSignals(False)
#             w._slider.blockSignals(False)

#         _set(self._le_w, self._le)
#         _set(self._te_w, self._te)

#     def _on_le_changed(self, v):
#         self._le = v
#         if self._te < self._le:
#             self._te = min(self._axial_max, self._le + (self._axial_max - self._axial_min)*0.05)
#             self._sync_le_te_ui()
#         self._refresh_plot()

#     def _on_te_changed(self, v):
#         self._te = max(v, self._le)
#         self._refresh_plot()

#     # ══════════════════════════════════════════════════════════════════════════
#     # Parameter panels
#     # ══════════════════════════════════════════════════════════════════════════

#     def _clear_params(self):
#         while self._param_vb.count():
#             item = self._param_vb.takeAt(0)
#             if item.widget():
#                 item.widget().deleteLater()

#     def _build_sine_params(self):
#         self._clear_params()
#         self._amp_w  = DoubleSliderInput("AMPLITUDE", -20.0, 20.0, -5.0, 2)
#         self._peak_w = DoubleSliderInput("PEAK POS",   0.2,   0.8,  0.5, 3)
#         self._param_vb.addWidget(self._amp_w)
#         self._param_vb.addWidget(self._peak_w)

#     def _build_hicks_params(self):
#         self._clear_params()
#         self._amp_w   = DoubleSliderInput("AMPLITUDE", -20.0, 20.0, -5.0, 2)
#         self._peak_w  = DoubleSliderInput("PEAK LOC",   0.1,   0.9,  0.3, 3)
#         self._width_w = DoubleSliderInput("WIDTH",      1.0,   4.0,  2.0, 2)
#         self._param_vb.addWidget(self._amp_w)
#         self._param_vb.addWidget(self._peak_w)
#         self._param_vb.addWidget(self._width_w)

#     def _build_cp_params(self, degree_selector=False):
#         """Shared UI for cubic / bezier / bspline."""
#         self._clear_params()

#         if degree_selector:
#             drow = QtWidgets.QHBoxLayout()
#             drow.addWidget(self._lbl("DEGREE", small=True))
#             self._deg_spin = QtWidgets.QSpinBox()
#             self._deg_spin.setRange(2, 5)
#             self._deg_spin.setValue(3)
#             drow.addWidget(self._deg_spin)
#             drow.addStretch()
#             self._param_vb.addLayout(drow)

#         crow = QtWidgets.QHBoxLayout()
#         crow.addWidget(self._lbl("CONTROL POINTS", small=True))
#         self._cp_count_spin = QtWidgets.QSpinBox()
#         self._cp_count_spin.setRange(2 if not degree_selector else 3, 8 if not degree_selector else 10)
#         self._cp_count_spin.setValue(4)
#         crow.addWidget(self._cp_count_spin)
#         crow.addStretch()
#         self._param_vb.addLayout(crow)

#         self._cp_container = QtWidgets.QWidget()
#         self._cp_vb = QtWidgets.QVBoxLayout(self._cp_container)
#         self._cp_vb.setContentsMargins(0, 0, 0, 0)
#         self._param_vb.addWidget(self._cp_container)

#         self._cp_rows = []
#         self._cp_count_spin.valueChanged.connect(self._rebuild_cp_rows)
#         self._rebuild_cp_rows(4)

#     def _rebuild_cp_rows(self, count):
#         while self._cp_vb.count():
#             item = self._cp_vb.takeAt(0)
#             if item.widget():
#                 item.widget().deleteLater()
#         self._cp_rows = []

#         # Preserve existing delta values if count shrinks/grows
#         old_deltas = [row[1].text() for row in self._cp_rows] if self._cp_rows else []

#         for i in range(count):
#             row_w = QtWidgets.QWidget()
#             row_h = QtWidgets.QHBoxLayout(row_w)
#             row_h.setContentsMargins(0, 1, 0, 1)

#             row_h.addWidget(self._lbl(f"P{i}", small=True))

#             x_in = QtWidgets.QLineEdit()
#             x_in.setFixedWidth(68)
#             x_in.setPlaceholderText("x pos")
#             t = i/(count-1) if count > 1 else 0.5
#             x_in.setText(f"{self._le + t*(self._te - self._le):.1f}")
#             row_h.addWidget(x_in)

#             row_h.addWidget(self._lbl("→", small=True))

#             d_in = QtWidgets.QLineEdit()
#             d_in.setFixedWidth(68)
#             d_in.setPlaceholderText("delta")
#             d_in.setText(old_deltas[i] if i < len(old_deltas) else "0")
#             row_h.addWidget(d_in)

#             self._cp_rows.append((x_in, d_in))
#             self._cp_vb.addWidget(row_w)

#     def _get_control_points(self):
#         pts = []
#         for x_in, d_in in self._cp_rows:
#             try:
#                 pts.append({'x': float(x_in.text()), 'delta': float(d_in.text())})
#             except ValueError:
#                 pass
#         return pts

#     def _build_cubic_params(self):
#         self._build_cp_params(degree_selector=False)

#     def _build_bezier_params(self):
#         self._build_cp_params(degree_selector=False)

#     def _build_bspline_params(self):
#         self._build_cp_params(degree_selector=True)

#     def _on_method_changed(self, method):
#         {
#             'sine':    self._build_sine_params,
#             'hicks':   self._build_hicks_params,
#             'cubic':   self._build_cubic_params,
#             'bezier':  self._build_bezier_params,
#             'bspline': self._build_bspline_params,
#         }.get(method, lambda: None)()

#     def _collect_kwargs(self, method):
#         if method == 'sine':
#             return {'amplitude': self._amp_w.value(), 'peakPos': self._peak_w.value()}
#         elif method == 'hicks':
#             return {'amplitude': self._amp_w.value(),
#                     'peakLoc':   self._peak_w.value(),
#                     'width':     self._width_w.value()}
#         elif method in ('cubic', 'bezier'):
#             return {'controlPoints': self._get_control_points()}
#         elif method == 'bspline':
#             return {'controlPoints': self._get_control_points(),
#                     'degree': self._deg_spin.value()}
#         return {}

#     # ══════════════════════════════════════════════════════════════════════════
#     # Plot panel
#     # ══════════════════════════════════════════════════════════════════════════

#     def _build_plot_panel(self):
#         panel = QtWidgets.QWidget()
#         vb    = QtWidgets.QVBoxLayout(panel)
#         vb.setContentsMargins(0, 0, 0, 0)

#         title = QtWidgets.QLabel("HUB CONTOURING OVERLAY")
#         title.setAlignment(QtCore.Qt.AlignCenter)
#         title.setStyleSheet("font-weight:bold; font-size:13px; padding:6px;")
#         vb.addWidget(title)

#         self._fig    = Figure(facecolor=BG_DARK, figsize=(9, 7))
#         self._canvas = FigureCanvas(self._fig)
#         self._ax     = self._fig.add_subplot(111)
#         self._style_ax()

#         # Mouse events
#         self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
#         self._canvas.mpl_connect('button_press_event',  self._on_plot_click)
#         self._canvas.mpl_connect('scroll_event',        self._on_scroll)

#         self._pan_data = None
#         self._canvas.mpl_connect('button_press_event',   self._on_pan_press)
#         self._canvas.mpl_connect('button_release_event', self._on_pan_release)
#         self._canvas.mpl_connect('motion_notify_event',  self._on_pan_drag)

#         vb.addWidget(self._canvas)
#         return panel

#     def _style_ax(self):
#         self._ax.set_facecolor(BG_DARK)
#         self._ax.tick_params(colors=TEXT_COLOR, labelsize=8)
#         for attr in ('xlabel', 'ylabel'):
#             getattr(self._ax, f'set_{attr}')(
#                 'AXIAL COORDINATE (Z)' if attr == 'xlabel' else 'RADIUS (R)',
#                 fontsize=9, color=TEXT_COLOR
#             )
#         for sp in self._ax.spines.values():
#             sp.set_edgecolor(GRID_COLOR)
#         self._ax.grid(self._show_grid, color=GRID_COLOR, linestyle='--', linewidth=0.5)
#         self._fig.tight_layout(pad=1.5)

#     def _refresh_plot(self):
#         if not hasattr(self, '_ax'):
#             return
#         self._ax.cla()
#         self._style_ax()

#         # Draw ORIGINAL baseline (solid white)
#         if self._base_display:
#             b = self._base_display[0]
#             self._ax.plot(b['axial'], b['original_radial'],
#                           color='white', lw=2.5, ls='-', label='ORIGINAL', zorder=1)

#         # Draw contour curves (dashed, coloured)
#         for idx, c in enumerate(self._contour_curves):
#             if not self._visible.get(c['hash'], True):
#                 continue
#             color = c.get('color', CURVE_COLORS[idx % len(CURVE_COLORS)])
#             lw    = 3.0 if c['hash'] == self._selected_hash else 1.5
#             self._ax.plot(c['axial'], c['radial'],
#                           color=color, lw=lw, ls='--',
#                           label=c['label'], zorder=2)

#         # LE / TE lines
#         for x, lbl in [(self._le, 'LE'), (self._te, 'TE')]:
#             self._ax.axvline(x, color='#ff8800', ls='--', lw=1.2, alpha=0.8, label=lbl, zorder=3)

#         self._ax.legend(loc='upper left', fontsize=7,
#                         facecolor=BG_PANEL, edgecolor=GRID_COLOR,
#                         labelcolor=TEXT_COLOR)
#         self._canvas.draw_idle()

#     # ══════════════════════════════════════════════════════════════════════════
#     # Curve list
#     # ══════════════════════════════════════════════════════════════════════════

#     def _rebuild_curve_list(self):
#         while self._curve_list_vb.count():
#             item = self._curve_list_vb.takeAt(0)
#             if item.widget():
#                 item.widget().deleteLater()

#         if not self._contour_curves:
#             lbl = QtWidgets.QLabel("No contours yet — click ADD TO PLOT")
#             lbl.setStyleSheet("color:#555; font-size:10px; padding:10px;")
#             self._curve_list_vb.addWidget(lbl)
#             return

#         for idx, c in enumerate(self._contour_curves):
#             item_w  = QtWidgets.QWidget()
#             item_h  = QtWidgets.QHBoxLayout(item_w)
#             item_h.setContentsMargins(4, 5, 4, 5)

#             color = c.get('color', CURVE_COLORS[idx % len(CURVE_COLORS)])

#             # Colour swatch
#             sw = QtWidgets.QLabel("■")
#             sw.setStyleSheet(f"color:{color}; font-size:14px;")
#             item_h.addWidget(sw)

#             # Editable name
#             name_ed = QtWidgets.QLineEdit(c['label'])
#             name_ed.setStyleSheet("background:transparent; border:none; font-size:9px;")
#             name_ed.textChanged.connect(lambda txt, curve=c: self._rename_curve(curve, txt))
#             item_h.addWidget(name_ed, stretch=1)

#             # Visibility
#             vis = QtWidgets.QCheckBox()
#             vis.setChecked(self._visible.get(c['hash'], True))
#             vis.stateChanged.connect(
#                 lambda st, h=c['hash']: self._set_visibility(h, bool(st))
#             )
#             item_h.addWidget(vis)

#             # Colour picker
#             cp_btn = QtWidgets.QPushButton("🎨")
#             cp_btn.setFixedSize(26, 22)
#             cp_btn.setStyleSheet("background:transparent; border:none;")
#             cp_btn.clicked.connect(lambda checked, curve=c: self._pick_color(curve))
#             item_h.addWidget(cp_btn)

#             # Delete
#             del_btn = QtWidgets.QPushButton("✕")
#             del_btn.setFixedSize(22, 22)
#             del_btn.setStyleSheet("background:transparent; border:none; color:#ff8888; font-size:14px;")
#             del_btn.clicked.connect(lambda checked, i=idx: self._remove_contour(i))
#             item_h.addWidget(del_btn)

#             # Click to select
#             item_w.setCursor(QtCore.Qt.PointingHandCursor)
#             item_w.mousePressEvent = (
#                 lambda e, h=c['hash']: self._select_curve(h)
#             )

#             border = f"border:1px solid {ACCENT};" if c['hash'] == self._selected_hash else ""
#             item_w.setStyleSheet(f"background:#252525; {border}")

#             self._curve_list_vb.addWidget(item_w)

#     def _rename_curve(self, curve, new_label):
#         curve['label'] = new_label
#         self._refresh_plot()

#     def _set_visibility(self, h, visible):
#         self._visible[h] = visible
#         self._refresh_plot()

#     def _select_curve(self, h):
#         self._selected_hash = None if h == self._selected_hash else h
#         self._rebuild_curve_list()
#         self._refresh_plot()

#     def _pick_color(self, curve):
#         color = QtWidgets.QColorDialog.getColor()
#         if color.isValid():
#             curve['color'] = color.name()
#             self._refresh_plot()
#             self._rebuild_curve_list()

#     def _remove_contour(self, idx):
#         self._push_undo()
#         removed = self._contour_curves.pop(idx)
#         if removed.get('hash') == self._selected_hash:
#             self._selected_hash = None
#         self._rebuild_curve_list()
#         self._refresh_plot()
#         self._status(f"Removed: {removed['label']}")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Add contour  (KEY FIX: each press appends a NEW independent curve)
#     # ══════════════════════════════════════════════════════════════════════════

#     def _on_add_contour(self):
#         method = self._method_cb.currentText()
#         le     = self._le
#         te     = self._te
#         kwargs = self._collect_kwargs(method)

#         h = generate_contour_hash(method, le, te, kwargs)

#         # Duplicate detection
#         for existing in self._contour_curves:
#             if existing.get('hash') == h:
#                 self._status("Identical configuration already exists")
#                 self._select_curve(h)
#                 return

#         # Compute new radial from the ORIGINAL baseline (not a previous contour)
#         base = self._base_display[0]
#         try:
#             new_radial = apply_contour(
#                 base['axial'], base['original_radial'], le, te, method, kwargs
#             )
#         except Exception as e:
#             QtWidgets.QMessageBox.critical(self, "Contour Error", str(e))
#             return

#         self._push_undo()

#         idx   = len(self._contour_curves)
#         label = f"{method.upper()}_{h}"
#         color = CURVE_COLORS[idx % len(CURVE_COLORS)]

#         new_curve = {
#             'label'          : label,
#             'axial'          : base['axial'],
#             'radial'         : new_radial,
#             'original_radial': list(base['original_radial']),
#             'theta'          : base['theta'],
#             'r_min'          : base['r_min'],
#             'method'         : method,
#             'le'             : le,
#             'te'             : te,
#             'params'         : kwargs,
#             'hash'           : h,
#             'color'          : color,
#         }

#         self._contour_curves.append(new_curve)
#         self._visible[h] = True
#         self._selected_hash = h
#         self._rebuild_curve_list()
#         self._refresh_plot()
#         self._status(f"Added: {label}")

#     def _on_clear_all(self):
#         self._push_undo()
#         self._contour_curves.clear()
#         self._visible.clear()
#         self._selected_hash = None
#         self._rebuild_curve_list()
#         self._refresh_plot()
#         self._status("All contours cleared")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Undo / Redo
#     # ══════════════════════════════════════════════════════════════════════════

#     def _push_undo(self):
#         self._undo_stack.append(copy.deepcopy(self._contour_curves))
#         self._redo_stack.clear()

#     def _on_undo(self):
#         if not self._undo_stack:
#             self._status("Nothing to undo")
#             return
#         self._redo_stack.append(copy.deepcopy(self._contour_curves))
#         self._contour_curves = self._undo_stack.pop()
#         self._rebuild_curve_list()
#         self._refresh_plot()
#         self._status("Undo successful")

#     def _on_redo(self):
#         if not self._redo_stack:
#             self._status("Nothing to redo")
#             return
#         self._undo_stack.append(copy.deepcopy(self._contour_curves))
#         self._contour_curves = self._redo_stack.pop()
#         self._rebuild_curve_list()
#         self._refresh_plot()
#         self._status("Redo successful")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Mouse / view
#     # ══════════════════════════════════════════════════════════════════════════

#     def _on_scroll(self, event):
#         if event.inaxes != self._ax:
#             return
#         factor = 1.1 if event.button == 'up' else 0.9
#         xl, xr = self._ax.get_xlim()
#         yb, yt = self._ax.get_ylim()
#         cx, cy = event.xdata, event.ydata
#         self._ax.set_xlim(cx - (cx-xl)*factor, cx + (xr-cx)*factor)
#         self._ax.set_ylim(cy - (cy-yb)*factor, cy + (yt-cy)*factor)
#         self._canvas.draw_idle()

#     def _on_pan_press(self, event):
#         if event.button == 3 and event.inaxes == self._ax:  # right-click pan
#             self._pan_data = (event.xdata, event.ydata,
#                               self._ax.get_xlim(), self._ax.get_ylim())

#     def _on_pan_release(self, event):
#         self._pan_data = None

#     def _on_pan_drag(self, event):
#         if self._pan_data is None or event.inaxes != self._ax:
#             return
#         ox, oy, (xl, xr), (yb, yt) = self._pan_data
#         dx = event.xdata - ox
#         dy = event.ydata - oy
#         self._ax.set_xlim(xl - dx, xr - dx)
#         self._ax.set_ylim(yb - dy, yt - dy)
#         self._canvas.draw_idle()

#     def _on_plot_click(self, event):
#         if event.xdata is None or event.inaxes != self._ax:
#             return
#         best_h, best_d = None, 5.0
#         for c in self._contour_curves:
#             if not self._visible.get(c['hash'], True):
#                 continue
#             for z, r in zip(c['axial'], c['radial']):
#                 d = math.hypot(event.xdata - z, event.ydata - r)
#                 if d < best_d:
#                     best_d, best_h = d, c['hash']
#         if best_h:
#             self._select_curve(best_h)

#     def _on_mouse_move(self, event):
#         if event.xdata is None:
#             return
#         self._status_bar.showMessage(
#             f"  X: {event.xdata:.2f}   R: {event.ydata:.3f}"
#             f"   LE: {self._le:.2f}   TE: {self._te:.2f}"
#             f"   CURVES: {len(self._contour_curves)}"
#             f"   UNDO: {len(self._undo_stack)}   REDO: {len(self._redo_stack)}"
#         )

#     def _reset_view(self):
#         if self._base_display:
#             z = self._base_display[0]['axial']
#             r = self._base_display[0]['original_radial']
#             zr, rr = max(z)-min(z), max(r)-min(r)
#             self._ax.set_xlim(min(z)-zr*.05, max(z)+zr*.05)
#             self._ax.set_ylim(min(r)-rr*.1,  max(r)+rr*.1)
#             self._canvas.draw_idle()
#         self._status("View reset")

#     def _toggle_grid(self):
#         self._show_grid = not self._show_grid
#         self._refresh_plot()
#         self._status(f"Grid {'ON' if self._show_grid else 'OFF'}")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Export helpers
#     # ══════════════════════════════════════════════════════════════════════════

#     def _curve_to_csv_lines(self, curve):
#         """Return list of CSV lines (R,Theta,Z) in absolute coordinates."""
#         lines = ["R,Theta,Z"]
#         le, te = curve.get('le', self._axial_min), curve.get('te', self._axial_max)
#         r_min  = curve.get('r_min', 0.0)
#         for r_n, th, z in zip(curve['radial'], curve['theta'], curve['axial']):
#             if self._export_only_le_te and not (le <= z <= te):
#                 continue
#             abs_r = r_n + r_min
#             lines.append(f"{abs_r:.6f},{th:.6f},{z:.6f}")
#         return lines

#     def _save_csv(self, lines, default_name):
#         path, _ = QtWidgets.QFileDialog.getSaveFileName(
#             self, "Save File", default_name, "CSV Files (*.csv)"
#         )
#         if path:
#             with open(path, 'w') as f:
#                 f.write("\n".join(lines))
#             self._status(f"Saved: {path}")

#     def _save_project(self):
#         data = {
#             'le': self._le, 'te': self._te,
#             'contours': [
#                 {'label': c['label'], 'method': c.get('method'),
#                  'le': c.get('le'), 'te': c.get('te'),
#                  'params': c.get('params'), 'color': c.get('color'),
#                  'visible': self._visible.get(c['hash'], True)}
#                 for c in self._contour_curves
#             ]
#         }
#         path, _ = QtWidgets.QFileDialog.getSaveFileName(
#             self, "Save Project", "", "JSON Files (*.json)"
#         )
#         if path:
#             with open(path, 'w') as f:
#                 json.dump(data, f, indent=2)
#             self._status("Project saved")

#     def _export_selected(self):
#         if not self._selected_hash:
#             self._status("No curve selected")
#             return
#         for c in self._contour_curves:
#             if c['hash'] == self._selected_hash:
#                 self._save_csv(self._curve_to_csv_lines(c), f"{c['label']}.csv")
#                 return

#     def _export_baseline(self):
#         if not self._base_display:
#             return
#         b = self._base_display[0]
#         lines = ["R,Theta,Z"]
#         r_min = b.get('r_min', 0.0)
#         for r_n, th, z in zip(b['original_radial'], b['theta'], b['axial']):
#             lines.append(f"{r_n + r_min:.6f},{th:.6f},{z:.6f}")
#         self._save_csv(lines, "baseline_hub.csv")

#     def _export_comparison(self):
#         if not self._selected_hash:
#             self._status("No curve selected for comparison")
#             return
#         for c in self._contour_curves:
#             if c['hash'] == self._selected_hash:
#                 lines = ["Z,R_baseline,R_contoured,Delta_R"]
#                 le, te = c.get('le', self._axial_min), c.get('te', self._axial_max)
#                 for z, r_base, r_cont in zip(c['axial'], c['original_radial'], c['radial']):
#                     if self._export_only_le_te and not (le <= z <= te):
#                         continue
#                     lines.append(f"{z:.6f},{r_base:.6f},{r_cont:.6f},{r_cont-r_base:.6f}")
#                 self._save_csv(lines, f"comparison_{c['label']}.csv")
#                 return

#     def _export_all_zip(self):
#         import zipfile
#         if not self._contour_curves:
#             self._status("No contours to export")
#             return
#         path, _ = QtWidgets.QFileDialog.getSaveFileName(
#             self, "Export All as ZIP", "hub_curves.zip", "ZIP Files (*.zip)"
#         )
#         if not path:
#             return
#         with zipfile.ZipFile(path, 'w') as zf:
#             for c in self._contour_curves:
#                 name = c['label'].replace('/', '_').replace('\\', '_')
#                 zf.writestr(f"{name}.csv", "\n".join(self._curve_to_csv_lines(c)))
#         self._status(f"Exported {len(self._contour_curves)} curves to ZIP")

#     # ══════════════════════════════════════════════════════════════════════════
#     # DELETE SELECTED
#     # ══════════════════════════════════════════════════════════════════════════

#     def _delete_selected(self):
#         if not self._selected_hash:
#             self._status("No curve selected")
#             return
#         for i, c in enumerate(self._contour_curves):
#             if c['hash'] == self._selected_hash:
#                 self._remove_contour(i)
#                 return

#     # ══════════════════════════════════════════════════════════════════════════
#     # UPDATE IN FREECAD  (the key action — closes the window on success)
#     # ══════════════════════════════════════════════════════════════════════════

#     def _on_update_freecad(self):
#         """
#         Write all VISIBLE contoured curves back into the FreeCAD document
#         as BSpline Part::Feature objects, then close this window so the user
#         can see the result directly in the 3D view.
#         """
#         try:
#             import FreeCAD
#             import FreeCADGui
#             from HubContour.edge_utils import cylindrical_to_bspline

#             doc = FreeCAD.ActiveDocument
#             if doc is None:
#                 raise RuntimeError("No active FreeCAD document")

#             visible_contours = [
#                 c for c in self._contour_curves
#                 if self._visible.get(c['hash'], True)
#             ]
#             if not visible_contours:
#                 raise RuntimeError("No visible contours to write back")

#             doc.openTransaction("Hub Contour Update")
#             written = []

#             for c in visible_contours:
#                 fc_ref  = self._fc_objects.get(
#                     # Try both the current label and the original base label
#                     c.get('label', ''),
#                     self._fc_objects.get(
#                         self._base_display[0].get('label', ''), {}
#                     )
#                 )
#                 obj     = fc_ref.get('obj')
#                 subname = fc_ref.get('subname', '')
#                 r_min   = c.get('r_min', 0.0)

#                 feat = cylindrical_to_bspline(
#                     c['axial'], c['radial'],
#                     c['theta'], r_min,
#                     obj, subname, doc
#                 )
#                 written.append(feat.Label)

#                 # Hide the source object to avoid visual clutter
#                 if obj is not None:
#                     try:
#                         obj.Visibility = False
#                     except Exception:
#                         pass

#             doc.commitTransaction()
#             doc.recompute()

#             try:
#                 FreeCADGui.SendMsgToActiveView("ViewFit")
#             except Exception:
#                 pass

#             QtWidgets.QMessageBox.information(
#                 self, "FreeCAD Update",
#                 "Written to FreeCAD:\n" + "\n".join(written)
#             )
#             self.close()

#         except Exception as e:
#             try:
#                 doc.abortTransaction()
#             except Exception:
#                 pass
#             QtWidgets.QMessageBox.critical(self, "Update Error", str(e))
#             self._status(f"Error: {e}")

#     # ══════════════════════════════════════════════════════════════════════════
#     # Utilities
#     # ══════════════════════════════════════════════════════════════════════════

#     def _hr(self):
#         line = QtWidgets.QFrame()
#         line.setFrameShape(QtWidgets.QFrame.HLine)
#         line.setStyleSheet(f"color:{GRID_COLOR};")
#         return line

#     def _lbl(self, text, small=False):
#         l = QtWidgets.QLabel(text)
#         l.setStyleSheet(f"color:{TEXT_COLOR}; font-size:{'8' if small else '10'}px;")
#         return l

#     def _status(self, msg):
#         self._status_bar.showMessage(msg, 4000)



















"""
HubContour – gui/main_window.py
Complete PySide6 implementation with:
- Persistent common parameters (Amplitude + Peak)
- Method-specific parameters (Width, Control Points, Degree)
- Point density control (50/100/200/Custom)
- Equal scaling (1:1 aspect ratio)
- Export dialog with location and format only
- 3D output modes (Wire/Surface/Extrude)
- Selected curve LE/TE shown in curve color (global LE/TE in white)
"""

import copy
import json
import math
import numpy as np

from PySide6 import QtCore, QtGui, QtWidgets

# ── Matplotlib backend ────────────────────────────────────────────────────────
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from HubContour.contouring.functions import apply_contour, generate_contour_hash

# ── Colours ───────────────────────────────────────────────────────────────────
BG_DARK    = "#1a1a1a"
BG_PANEL   = "#1e1e1e"
BG_WIDGET  = "#2a2a2a"
ACCENT     = "#ff6644"
TEXT_COLOR = "#cccccc"
GRID_COLOR = "#333333"

CURVE_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


# ─────────────────────────────────────────────────────────────────────────────
# ExportDialog Class
# ─────────────────────────────────────────────────────────────────────────────

class ExportDialog(QtWidgets.QDialog):
    """Simple export dialog with location and format only."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Curve")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Save location
        layout.addWidget(QtWidgets.QLabel("Save Location:"))
        path_layout = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Select save location...")
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # Format selection
        layout.addWidget(QtWidgets.QLabel("Save Format:"))
        self.format_cb = QtWidgets.QComboBox()
        self.format_cb.addItems(["CSV (.csv)", "TXT (.txt)"])
        layout.addWidget(self.format_cb)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("Export")
        export_btn.setStyleSheet(f"background:{ACCENT}; color:white; padding:8px; font-weight:bold;")
        export_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def _browse(self):
        fmt_text = self.format_cb.currentText()
        ext = ".csv" if "CSV" in fmt_text else ".txt"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save File", "", f"*{ext}")
        if path:
            self.path_edit.setText(path)
    
    def get_values(self):
        path = self.path_edit.text()
        fmt_text = self.format_cb.currentText()
        ext = ".csv" if "CSV" in fmt_text else ".txt"
        if not path.endswith(ext):
            path += ext
        return path, ext


# ─────────────────────────────────────────────────────────────────────────────
# DoubleSliderInput Class
# ─────────────────────────────────────────────────────────────────────────────

class DoubleSliderInput(QtWidgets.QWidget):
    """Slider paired with a text box; changes in either propagate to the other."""

    def __init__(self, label, min_val, max_val, default, decimals=2, parent=None):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self._decimals = decimals

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(75)
        lbl.setStyleSheet(f"color:{TEXT_COLOR}; font-size:9px;")
        layout.addWidget(lbl)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._slider.setRange(0, 1000)
        layout.addWidget(self._slider)

        self._text = QtWidgets.QLineEdit()
        self._text.setFixedWidth(62)
        self._text.setStyleSheet(
            f"background:{BG_WIDGET}; color:{TEXT_COLOR}; "
            f"border:1px solid {GRID_COLOR}; font-family:monospace; font-size:9px;"
        )
        layout.addWidget(self._text)

        self.setValue(default)

        self._slider.valueChanged.connect(self._slider_changed)
        self._text.editingFinished.connect(self._text_changed)

    def _to_slider(self, v):
        if self._max == self._min:
            return 500
        return int((v - self._min) / (self._max - self._min) * 1000)

    def _from_slider(self, s):
        return self._min + s / 1000.0 * (self._max - self._min)

    def _slider_changed(self, s):
        v = self._from_slider(s)
        self._text.blockSignals(True)
        self._text.setText(f"{v:.{self._decimals}f}")
        self._text.blockSignals(False)

    def _text_changed(self):
        try:
            v = float(self._text.text())
        except ValueError:
            return
        v = max(self._min, min(self._max, v))
        self._text.setText(f"{v:.{self._decimals}f}")
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_slider(v))
        self._slider.blockSignals(False)

    def value(self):
        try:
            return float(self._text.text())
        except ValueError:
            return self._min

    def setValue(self, v):
        v = max(self._min, min(self._max, v))
        self._text.blockSignals(True)
        self._slider.blockSignals(True)
        self._text.setText(f"{v:.{self._decimals}f}")
        self._slider.setValue(self._to_slider(v))
        self._text.blockSignals(False)
        self._slider.blockSignals(False)


# ─────────────────────────────────────────────────────────────────────────────
# ContourWindow Class
# ─────────────────────────────────────────────────────────────────────────────

class ContourWindow(QtWidgets.QMainWindow):
    """Hub Contouring Overlay for FreeCAD."""

    def __init__(self, curves, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HUB CONTOURING OVERLAY")
        self.setMinimumSize(1280, 700)
        self.resize(1420, 820)
        self._apply_stylesheet()

        # ── State ─────────────────────────────────────────────────────────────
        self._fc_objects = {}
        self._register_fc_objects(curves)

        self._base_curves = copy.deepcopy(self._strip_fc(curves))
        for c in self._base_curves:
            c.setdefault('original_radial', list(c['radial']))

        self._base_display = copy.deepcopy(self._base_curves)
        self._contour_curves = []

        self._undo_stack = []
        self._redo_stack = []
        self._visible = {}
        self._selected_hash = None
        self._show_grid = True

        # LE/TE
        self._le = 0.0
        self._te = 0.0
        self._axial_min = 0.0
        self._axial_max = 100.0
        self._init_le_te()

        # Export
        self._export_only_le_te = True

        # ── UI ────────────────────────────────────────────────────────────────
        self._ui_ready = False
        self._build_menu()
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        self._build_layout(central)
        self._setup_shortcuts()
        
        # Create status bar
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        
        self._ui_ready = True

        QtCore.QTimer.singleShot(50, self._refresh_plot)
        self._status("Ready — select edge(s) and choose a contouring method")

    # ══════════════════════════════════════════════════════════════════════════
    # Init helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _register_fc_objects(self, curves):
        for c in curves:
            lbl = c.get('label', '')
            if 'obj' in c or 'subname' in c:
                self._fc_objects[lbl] = {
                    'obj': c.get('obj'),
                    'subname': c.get('subname', ''),
                }

    @staticmethod
    def _strip_fc(curves):
        return [{k: v for k, v in c.items() if k not in ('obj', 'subname')}
                for c in curves]

    def _init_le_te(self):
        if self._base_display:
            z = self._base_display[0]['axial']
            self._axial_min = min(z)
            self._axial_max = max(z)
            self._le = self._axial_min
            self._te = self._axial_max

    def _setup_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence.Undo, self, self._on_undo)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self, self._on_redo)
        QtGui.QShortcut(QtGui.QKeySequence.Save, self, self._save_project)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, self._export_selected)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, self._delete_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+G"), self, self._toggle_grid)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self._reset_view)

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget      {{ background-color:{BG_DARK}; color:{TEXT_COLOR}; }}
            QLineEdit, QDoubleSpinBox,
            QSpinBox, QComboBox       {{ background:{BG_WIDGET}; color:{TEXT_COLOR};
                                        border:1px solid {GRID_COLOR}; padding:3px;
                                        font-family:monospace; font-size:10px; }}
            QPushButton               {{ background:{BG_WIDGET}; color:{TEXT_COLOR};
                                        border:1px solid {GRID_COLOR};
                                        padding:5px 10px;
                                        font-family:monospace; font-size:10px; }}
            QPushButton:hover         {{ background:{ACCENT}; border-color:{ACCENT}; }}
            QLabel                    {{ color:{TEXT_COLOR}; font-size:10px; }}
            QCheckBox                 {{ color:{TEXT_COLOR}; font-size:10px; }}
            QScrollBar:vertical       {{ background:{BG_PANEL}; width:8px; }}
            QScrollBar::handle:vertical {{ background:{BG_WIDGET}; min-height:20px; }}
            QMenuBar                  {{ background:{BG_PANEL}; color:{TEXT_COLOR}; }}
            QMenuBar::item:selected   {{ background:{ACCENT}; }}
            QMenu                     {{ background:{BG_PANEL}; color:{TEXT_COLOR}; }}
            QStatusBar                {{ background:{BG_PANEL}; color:{TEXT_COLOR}; font-size:10px; }}
        """)

    def _build_menu(self):
        mb = self.menuBar()
        file_m = mb.addMenu("File")
        self._add_action(file_m, "Save Project  Ctrl+S", self._save_project)
        exp_m = mb.addMenu("Export")
        self._add_action(exp_m, "Export Selected  Ctrl+E", self._export_selected)
        self._add_action(exp_m, "Export All Curves (ZIP)", self._export_all_zip)
        self._add_action(exp_m, "Export Baseline", self._export_baseline)
        view_m = mb.addMenu("View")
        self._add_action(view_m, "Toggle Grid  Ctrl+G", self._toggle_grid)
        self._add_action(view_m, "Reset View   Ctrl+R", self._reset_view)

    @staticmethod
    def _add_action(menu, text, slot):
        a = QtGui.QAction(text)
        a.triggered.connect(slot)
        menu.addAction(a)

    def _build_layout(self, parent):
        h = QtWidgets.QHBoxLayout(parent)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(4)
        h.addWidget(self._build_sidebar())
        h.addWidget(self._build_plot_panel(), stretch=1)

    def _build_sidebar(self):
        outer = QtWidgets.QWidget()
        outer.setFixedWidth(350)
        outer.setStyleSheet(f"background:{BG_PANEL};")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")

        content = QtWidgets.QWidget()
        vb = QtWidgets.QVBoxLayout(content)
        vb.setContentsMargins(10, 10, 10, 10)
        vb.setSpacing(8)

        # Header
        hdr = QtWidgets.QLabel("HUB CONTOURING TOOL")
        hdr.setAlignment(QtCore.Qt.AlignCenter)
        hdr.setStyleSheet("font-weight:bold; font-size:13px; padding:4px;")
        vb.addWidget(hdr)
        vb.addWidget(self._hr())

        # Method
        vb.addWidget(self._lbl("METHOD"))
        self._method_cb = QtWidgets.QComboBox()
        self._method_cb.addItems(["sine", "hicks", "cubic", "bezier", "bspline"])
        self._method_cb.currentTextChanged.connect(self._on_method_changed)
        vb.addWidget(self._method_cb)
        vb.addWidget(self._hr())

        # LE / TE
        vb.addWidget(self._lbl("BLADE REGION"))
        self._le_w = self._le_te_row("LE", self._on_le_changed)
        self._te_w = self._le_te_row("TE", self._on_te_changed)
        vb.addWidget(self._le_w)
        vb.addWidget(self._te_w)
        self._sync_le_te_ui()
        vb.addWidget(self._hr())

        # ── COMMON PARAMETERS (Always visible) ───────────────────────────────
        vb.addWidget(self._lbl("COMMON PARAMETERS"))
        self._common_param_w = QtWidgets.QWidget()
        self._common_vb = QtWidgets.QVBoxLayout(self._common_param_w)
        self._common_vb.setContentsMargins(0, 0, 0, 0)
        vb.addWidget(self._common_param_w)
        
        # Build common params once (never deleted)
        self._build_common_params()
        vb.addWidget(self._hr())

        # ── METHOD PARAMETERS (Changes based on method) ──────────────────────
        vb.addWidget(self._lbl("METHOD PARAMETERS"))
        self._method_param_w = QtWidgets.QWidget()
        self._method_vb = QtWidgets.QVBoxLayout(self._method_param_w)
        self._method_vb.setContentsMargins(0, 0, 0, 0)
        vb.addWidget(self._method_param_w)
        vb.addWidget(self._hr())

        # ── POINT DENSITY ──
        vb.addWidget(self._lbl("POINT DENSITY"))
        self._density_cb = QtWidgets.QComboBox()
        self._density_cb.addItems(["50", "100", "200", "Custom"])
        self._density_cb.currentTextChanged.connect(self._on_density_change)
        vb.addWidget(self._density_cb)

        self._density_input = QtWidgets.QLineEdit()
        self._density_input.setPlaceholderText("Enter custom points")
        self._density_input.setVisible(False)
        vb.addWidget(self._density_input)
        vb.addWidget(self._hr())

        # ── 3D OUTPUT MODE ──
        vb.addWidget(self._lbl("3D OUTPUT MODE"))
        self._mode_cb = QtWidgets.QComboBox()
        self._mode_cb.addItems(["Wire", "Surface", "Extrude"])
        vb.addWidget(self._mode_cb)
        vb.addWidget(self._hr())

        # ADD / CLEAR
        row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("ADD TO PLOT")
        add_btn.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:white;font-weight:bold;}}"
            f"QPushButton:hover{{background:#ff8866;}}"
        )
        add_btn.clicked.connect(self._on_add_contour)
        clr_btn = QtWidgets.QPushButton("CLEAR ALL")
        clr_btn.clicked.connect(self._on_clear_all)
        row.addWidget(add_btn)
        row.addWidget(clr_btn)
        vb.addLayout(row)

        # UNDO / REDO
        ur = QtWidgets.QHBoxLayout()
        undo_btn = QtWidgets.QPushButton("UNDO")
        undo_btn.clicked.connect(self._on_undo)
        redo_btn = QtWidgets.QPushButton("REDO")
        redo_btn.clicked.connect(self._on_redo)
        ur.addWidget(undo_btn)
        ur.addWidget(redo_btn)
        vb.addLayout(ur)
        vb.addWidget(self._hr())

        # Manual Contouring button
        manual_btn = QtWidgets.QPushButton("Manual Contouring")
        manual_btn.setStyleSheet(
            f"QPushButton{{background:#2a2a2a;border:1px solid #ff6644;padding:8px;}}"
            f"QPushButton:hover{{background:#3a3a3a;border-color:#ff8866;}}"
        )
        manual_btn.clicked.connect(self._open_manual_editor)
        vb.addWidget(manual_btn)
        vb.addWidget(self._hr())

        # Overlay controls - compact size, no horizontal scroll
        vb.addWidget(self._lbl("OVERLAY CONTROLS"))
        self._curve_list_area = QtWidgets.QScrollArea()
        self._curve_list_area.setWidgetResizable(True)
        self._curve_list_area.setMaximumHeight(250)
        self._curve_list_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._curve_list_area.setStyleSheet(f"border:1px solid {GRID_COLOR}; background:{BG_DARK};")
        self._curve_list_inner = QtWidgets.QWidget()
        self._curve_list_vb = QtWidgets.QVBoxLayout(self._curve_list_inner)
        self._curve_list_vb.setContentsMargins(4, 4, 4, 4)
        self._curve_list_vb.setSpacing(4)
        self._curve_list_area.setWidget(self._curve_list_inner)
        vb.addWidget(self._curve_list_area)
        vb.addWidget(self._hr())

        # Export settings
        vb.addWidget(self._lbl("EXPORT SETTINGS"))
        self._le_te_only_chk = QtWidgets.QCheckBox("Only LE–TE Region")
        self._le_te_only_chk.setChecked(True)
        self._le_te_only_chk.stateChanged.connect(
            lambda s: setattr(self, '_export_only_le_te', bool(s))
        )
        vb.addWidget(self._le_te_only_chk)

        # Export buttons
        export_buttons = [
            ("Export Selected Curve", self._export_selected),
            ("Export Comparison CSV", self._export_comparison),
            ("Export Baseline Curve", self._export_baseline),
            ("Export All Curves (ZIP)", self._export_all_zip),
        ]
        for lbl, slot in export_buttons:
            b = QtWidgets.QPushButton(lbl)
            b.setStyleSheet(
                f"QPushButton{{background:#1a2a22;border:1px solid #2a3a2a;}}"
                f"QPushButton:hover{{background:#22332a;}}"
            )
            b.clicked.connect(slot)
            vb.addWidget(b)

        vb.addWidget(self._hr())

        # UPDATE IN FREECAD
        upd_btn = QtWidgets.QPushButton("UPDATE IN FREECAD")
        upd_btn.setStyleSheet(
            f"QPushButton{{background:{ACCENT};color:white;font-weight:bold;"
            f"font-size:12px;padding:10px;}}"
            f"QPushButton:hover{{background:#ff8866;}}"
        )
        upd_btn.clicked.connect(self._on_update_freecad)
        vb.addWidget(upd_btn)

        vb.addStretch()
        scroll.setWidget(content)

        outer_vb = QtWidgets.QVBoxLayout(outer)
        outer_vb.setContentsMargins(0, 0, 0, 0)
        outer_vb.addWidget(scroll)
        
        # Initialize default method params (sine has no extra params)
        self._clear_method_params()
        
        return outer

    def _build_common_params(self):
        """Build common parameters once - NEVER deleted."""
        self._amp_w = DoubleSliderInput("AMPLITUDE", -20.0, 20.0, -5.0, 2)
        self._peak_w = DoubleSliderInput("PEAK", 0.0, 1.0, 0.5, 3)
        self._common_vb.addWidget(self._amp_w)
        self._common_vb.addWidget(self._peak_w)

    def _clear_method_params(self):
        """Clear ONLY method-specific parameters."""
        while self._method_vb.count():
            item = self._method_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _build_sine_params(self):
        """Sine uses only common params - nothing extra."""
        self._clear_method_params()

    def _build_hicks_params(self):
        """Hicks-Henne adds Width parameter."""
        self._clear_method_params()
        self._width_w = DoubleSliderInput("WIDTH", 1.0, 4.0, 2.0, 2)
        self._method_vb.addWidget(self._width_w)

    def _build_cp_params(self, degree_selector=False):
        """Build control points UI for spline methods."""
        self._clear_method_params()
        
        if degree_selector:
            drow = QtWidgets.QHBoxLayout()
            drow.addWidget(self._lbl("DEGREE", small=True))
            self._deg_spin = QtWidgets.QSpinBox()
            self._deg_spin.setRange(2, 5)
            self._deg_spin.setValue(3)
            drow.addWidget(self._deg_spin)
            drow.addStretch()
            self._method_vb.addLayout(drow)

        crow = QtWidgets.QHBoxLayout()
        crow.addWidget(self._lbl("CONTROL POINTS", small=True))
        self._cp_count_spin = QtWidgets.QSpinBox()
        self._cp_count_spin.setRange(2 if not degree_selector else 3, 8 if not degree_selector else 10)
        self._cp_count_spin.setValue(4)
        crow.addWidget(self._cp_count_spin)
        crow.addStretch()
        self._method_vb.addLayout(crow)

        self._cp_container = QtWidgets.QWidget()
        self._cp_vb = QtWidgets.QVBoxLayout(self._cp_container)
        self._cp_vb.setContentsMargins(0, 0, 0, 0)
        self._method_vb.addWidget(self._cp_container)

        self._cp_rows = []
        self._cp_count_spin.valueChanged.connect(self._rebuild_cp_rows)
        self._rebuild_cp_rows(4)

    def _rebuild_cp_rows(self, count):
        while self._cp_vb.count():
            item = self._cp_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cp_rows = []

        old_deltas = [row[1].text() for row in self._cp_rows] if self._cp_rows else []

        for i in range(count):
            row_w = QtWidgets.QWidget()
            row_h = QtWidgets.QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 1, 0, 1)
            row_h.addWidget(self._lbl(f"P{i}", small=True))
            x_in = QtWidgets.QLineEdit()
            x_in.setFixedWidth(68)
            x_in.setPlaceholderText("x pos")
            t = i/(count-1) if count > 1 else 0.5
            x_in.setText(f"{self._le + t*(self._te - self._le):.1f}")
            row_h.addWidget(x_in)
            row_h.addWidget(self._lbl("→", small=True))
            d_in = QtWidgets.QLineEdit()
            d_in.setFixedWidth(68)
            d_in.setPlaceholderText("delta")
            d_in.setText(old_deltas[i] if i < len(old_deltas) else "0")
            row_h.addWidget(d_in)
            self._cp_rows.append((x_in, d_in))
            self._cp_vb.addWidget(row_w)

    def _get_control_points(self):
        pts = []
        for x_in, d_in in self._cp_rows:
            try:
                pts.append({'x': float(x_in.text()), 'delta': float(d_in.text())})
            except ValueError:
                pass
        return pts

    def _build_cubic_params(self):
        self._build_cp_params(degree_selector=False)

    def _build_bezier_params(self):
        self._build_cp_params(degree_selector=False)

    def _build_bspline_params(self):
        self._build_cp_params(degree_selector=True)

    def _on_method_changed(self, method):
        """Switch method parameters while preserving common params."""
        {
            'sine': self._build_sine_params,
            'hicks': self._build_hicks_params,
            'cubic': self._build_cubic_params,
            'bezier': self._build_bezier_params,
            'bspline': self._build_bspline_params,
        }.get(method, lambda: None)()

    def _collect_kwargs(self, method):
        """Collect ALL parameters (common + method-specific)."""
        if method == 'sine':
            return {
                'amplitude': self._amp_w.value(),
                'peakPos': self._peak_w.value()
            }
        elif method == 'hicks':
            return {
                'amplitude': self._amp_w.value(),
                'peakLoc': self._peak_w.value(),
                'width': self._width_w.value()
            }
        elif method in ('cubic', 'bezier'):
            return {'controlPoints': self._get_control_points()}
        elif method == 'bspline':
            return {
                'controlPoints': self._get_control_points(),
                'degree': self._deg_spin.value()
            }
        return {}

    # ── Point Density Methods ────────────────────────────────────────────────

    def _on_density_change(self, val):
        self._density_input.setVisible(val == "Custom")

    def _get_point_density(self):
        val = self._density_cb.currentText()
        if val == "Custom":
            try:
                return int(self._density_input.text())
            except ValueError:
                return 100
        return int(val)

    def _le_te_row(self, label, slot):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        h.addWidget(self._lbl(label, small=True))

        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 1000)
        h.addWidget(slider)

        txt = QtWidgets.QLineEdit()
        txt.setFixedWidth(70)
        h.addWidget(txt)

        def _slider_moved(val, _slider=slider, _txt=txt):
            if not self._ui_ready:
                return
            v = self._axial_min + val/1000.0*(self._axial_max - self._axial_min)
            _txt.blockSignals(True)
            _txt.setText(f"{v:.2f}")
            _txt.blockSignals(False)
            slot(v)

        def _txt_edited(_txt=txt, _slider=slider):
            if not self._ui_ready:
                return
            try:
                v = float(_txt.text())
            except ValueError:
                return
            v = max(self._axial_min, min(self._axial_max, v))
            _slider.blockSignals(True)
            sv = int((v - self._axial_min)/(self._axial_max - self._axial_min)*1000)
            _slider.setValue(sv)
            _slider.blockSignals(False)
            slot(v)

        slider.valueChanged.connect(_slider_moved)
        txt.editingFinished.connect(_txt_edited)

        w._slider = slider
        w._txt = txt
        return w

    def _sync_le_te_ui(self):
        def _set(w, v):
            w._txt.blockSignals(True)
            w._slider.blockSignals(True)
            w._txt.setText(f"{v:.2f}")
            rng = self._axial_max - self._axial_min
            sv = int((v - self._axial_min) / rng * 1000) if rng else 500
            w._slider.setValue(sv)
            w._txt.blockSignals(False)
            w._slider.blockSignals(False)

        _set(self._le_w, self._le)
        _set(self._te_w, self._te)

    def _on_le_changed(self, v):
        self._le = v
        if self._te < self._le:
            self._te = min(self._axial_max, self._le + (self._axial_max - self._axial_min)*0.05)
            self._sync_le_te_ui()
        self._refresh_plot()

    def _on_te_changed(self, v):
        self._te = max(v, self._le)
        self._refresh_plot()

    # ── Plot panel ───────────────────────────────────────────────────────────

    def _build_plot_panel(self):
        panel = QtWidgets.QWidget()
        vb = QtWidgets.QVBoxLayout(panel)
        vb.setContentsMargins(0, 0, 0, 0)

        title = QtWidgets.QLabel("HUB CONTOURING OVERLAY")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight:bold; font-size:13px; padding:6px;")
        vb.addWidget(title)

        self._fig = Figure(facecolor=BG_DARK, figsize=(9, 7))
        self._canvas = FigureCanvas(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._style_ax()

        self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self._canvas.mpl_connect('button_press_event', self._on_plot_click)
        self._canvas.mpl_connect('scroll_event', self._on_scroll)

        self._pan_data = None
        self._canvas.mpl_connect('button_press_event', self._on_pan_press)
        self._canvas.mpl_connect('button_release_event', self._on_pan_release)
        self._canvas.mpl_connect('motion_notify_event', self._on_pan_drag)

        vb.addWidget(self._canvas)
        return panel

    def _style_ax(self):
        self._ax.set_facecolor(BG_DARK)
        self._ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        self._ax.set_xlabel('AXIAL COORDINATE (Z)', fontsize=9, color=TEXT_COLOR)
        self._ax.set_ylabel('RADIUS (R)', fontsize=9, color=TEXT_COLOR)
        for sp in self._ax.spines.values():
            sp.set_edgecolor(GRID_COLOR)
        self._ax.grid(self._show_grid, color=GRID_COLOR, linestyle='--', linewidth=0.5)
        self._fig.tight_layout(pad=1.5)

    def _refresh_plot(self):
        if not hasattr(self, '_ax'):
            return
        self._ax.cla()
        self._style_ax()

        # Draw ORIGINAL baseline (solid white)
        if self._base_display:
            b = self._base_display[0]
            self._ax.plot(b['axial'], b['original_radial'],
                          color='white', lw=2.5, ls='-', label='ORIGINAL', zorder=1)

        # Draw contour curves (dashed, coloured)
        for idx, c in enumerate(self._contour_curves):
            if not self._visible.get(c['hash'], True):
                continue
            color = c.get('color', CURVE_COLORS[idx % len(CURVE_COLORS)])
            lw = 3.0 if c['hash'] == self._selected_hash else 1.5
            self._ax.plot(c['axial'], c['radial'],
                          color=color, lw=lw, ls='--',
                          label=c['label'], zorder=2)

        # Draw LE/TE lines
        # Global LE/TE (white)
        self._ax.axvline(self._le, color='white', ls='--', lw=1.5, alpha=0.9, label='LE (global)', zorder=3)
        self._ax.axvline(self._te, color='white', ls='--', lw=1.5, alpha=0.9, label='TE (global)', zorder=3)
        
        # Selected curve's LE/TE (in curve color)
        if self._selected_hash:
            for c in self._contour_curves:
                if c['hash'] == self._selected_hash:
                    color = c.get('color', '#ff8800')
                    le_curve = c.get('le', self._le)
                    te_curve = c.get('te', self._te)
                    self._ax.axvline(le_curve, color=color, ls=':', lw=2.0, alpha=0.8, label=f'LE ({c["label"]})', zorder=4)
                    self._ax.axvline(te_curve, color=color, ls=':', lw=2.0, alpha=0.8, label=f'TE ({c["label"]})', zorder=4)
                    break

        self._ax.legend(loc='upper left', fontsize=7,
                        facecolor=BG_PANEL, edgecolor=GRID_COLOR,
                        labelcolor=TEXT_COLOR)

        # Equal aspect ratio (1:1 scaling)
        self._ax.set_aspect('equal', adjustable='datalim')
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()
        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]
        max_range = max(x_range, y_range)
        x_mid = (xlim[0] + xlim[1]) / 2
        y_mid = (ylim[0] + ylim[1]) / 2
        self._ax.set_xlim(x_mid - max_range/2, x_mid + max_range/2)
        self._ax.set_ylim(y_mid - max_range/2, y_mid + max_range/2)

        self._canvas.draw_idle()

    # ── Add Contour ──────────────────────────────────────────────────────────

    def _on_add_contour(self):
        method = self._method_cb.currentText()
        le = self._le
        te = self._te
        kwargs = self._collect_kwargs(method)

        h = generate_contour_hash(method, le, te, kwargs)

        for existing in self._contour_curves:
            if existing.get('hash') == h:
                self._status("Identical configuration already exists")
                self._select_curve(h)
                return

        n_points = self._get_point_density()
        base = self._base_display[0]

        # Resample to selected density
        z_original = base['axial']
        r_original = base['original_radial']
        theta_original = base['theta']

        z_uniform = np.linspace(min(z_original), max(z_original), n_points)
        r_interp = np.interp(z_uniform, z_original, r_original)
        theta_interp = np.interp(z_uniform, z_original, theta_original)

        try:
            new_radial = apply_contour(
                z_uniform.tolist(), r_interp.tolist(), le, te, method, kwargs
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Contour Error", str(e))
            return

        self._push_undo()

        idx = len(self._contour_curves)
        label = f"{method.upper()}_{h}"
        color = CURVE_COLORS[idx % len(CURVE_COLORS)]

        new_curve = {
            'label': label,
            'axial': z_uniform.tolist(),
            'radial': new_radial,
            'original_radial': r_interp.tolist(),
            'theta': theta_interp.tolist(),
            'r_min': base['r_min'],
            'method': method,
            'le': le,
            'te': te,
            'params': kwargs,
            'hash': h,
            'color': color,
        }

        self._contour_curves.append(new_curve)
        self._visible[h] = True
        self._selected_hash = h
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status(f"Added: {label} ({n_points} points)")

    def _on_clear_all(self):
        self._push_undo()
        self._contour_curves.clear()
        self._visible.clear()
        self._selected_hash = None
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status("All contours cleared")

    def _open_manual_editor(self):
        """Open the manual contour editor."""
        # Find curve to edit (selected or latest)
        curve_to_edit = None
        if self._selected_hash:
            for c in self._contour_curves:
                if c['hash'] == self._selected_hash:
                    curve_to_edit = c
                    break
        if curve_to_edit is None and self._contour_curves:
            curve_to_edit = self._contour_curves[-1]
        if curve_to_edit is None:
            curve_to_edit = self._base_display[0]
        
        from HubContour.gui.manual_editor import ManualEditor
        self._manual_editor = ManualEditor(curve_to_edit, parent=self)
        self._manual_editor.show()
        self._status("Manual contour editor opened")

    def _add_manual_curve(self, curve):
        """Add manually created curve to contour list."""
        color = CURVE_COLORS[len(self._contour_curves) % len(CURVE_COLORS)]
        curve['color'] = color
        self._push_undo()
        self._contour_curves.append(curve)
        self._visible[curve['hash']] = True
        self._selected_hash = curve['hash']
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status(f"Added manual contour: {curve['label']}")

    # ── Undo / Redo ──────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append(copy.deepcopy(self._contour_curves))
        self._redo_stack.clear()

    def _on_undo(self):
        if not self._undo_stack:
            self._status("Nothing to undo")
            return
        self._redo_stack.append(copy.deepcopy(self._contour_curves))
        self._contour_curves = self._undo_stack.pop()
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status("Undo successful")

    def _on_redo(self):
        if not self._redo_stack:
            self._status("Nothing to redo")
            return
        self._undo_stack.append(copy.deepcopy(self._contour_curves))
        self._contour_curves = self._redo_stack.pop()
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status("Redo successful")

    # ── Curve List ───────────────────────────────────────────────────────────

    def _rebuild_curve_list(self):
        while self._curve_list_vb.count():
            item = self._curve_list_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._contour_curves:
            lbl = QtWidgets.QLabel("No contours yet — click ADD TO PLOT")
            lbl.setStyleSheet("color:#666; font-size:10px; padding:10px; text-align:center;")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            self._curve_list_vb.addWidget(lbl)
            return

        for idx, c in enumerate(self._contour_curves):
            item_w = QtWidgets.QWidget()
            item_w.setStyleSheet("background:#252525; margin:2px;")
            item_h = QtWidgets.QHBoxLayout(item_w)
            item_h.setContentsMargins(6, 4, 6, 4)
            item_h.setSpacing(6)

            color = c.get('color', CURVE_COLORS[idx % len(CURVE_COLORS)])

            # Colour swatch
            sw = QtWidgets.QLabel("●")
            sw.setStyleSheet(f"color:{color}; font-size:14px;")
            sw.setFixedSize(20, 20)
            sw.setAlignment(QtCore.Qt.AlignCenter)
            item_h.addWidget(sw)

            # Editable name
            name_ed = QtWidgets.QLineEdit(c['label'])
            name_ed.setStyleSheet("background:#333; border:1px solid #444; padding:3px; font-size:9px;")
            name_ed.textChanged.connect(lambda txt, curve=c: self._rename_curve(curve, txt))
            item_h.addWidget(name_ed, stretch=2)

            # Visibility toggle
            vis = QtWidgets.QCheckBox()
            vis.setChecked(self._visible.get(c['hash'], True))
            vis.stateChanged.connect(lambda st, h=c['hash']: self._set_visibility(h, bool(st)))
            item_h.addWidget(vis)

            # Colour picker
            cp_btn = QtWidgets.QPushButton("Color")
            cp_btn.setFixedSize(45, 22)
            cp_btn.setStyleSheet("background:#444; border:1px solid #555; font-size:8px;")
            cp_btn.clicked.connect(lambda checked, curve=c: self._pick_color(curve))
            item_h.addWidget(cp_btn)

            # Delete button
            del_btn = QtWidgets.QPushButton("Del")
            del_btn.setFixedSize(35, 22)
            del_btn.setStyleSheet("background:#442222; border:1px solid #662222; font-size:8px;")
            del_btn.clicked.connect(lambda checked, i=idx: self._remove_contour(i))
            item_h.addWidget(del_btn)

            # Click to select
            item_w.setCursor(QtCore.Qt.PointingHandCursor)
            item_w.mousePressEvent = lambda e, h=c['hash']: self._select_curve(h)

            border_style = f"border:1px solid {ACCENT};" if c['hash'] == self._selected_hash else "border:1px solid #444;"
            item_w.setStyleSheet(f"background:#2a2a2a; {border_style} margin:2px;")

            self._curve_list_vb.addWidget(item_w)

    def _rename_curve(self, curve, new_label):
        curve['label'] = new_label
        self._refresh_plot()

    def _set_visibility(self, h, visible):
        self._visible[h] = visible
        self._refresh_plot()

    def _select_curve(self, h):
        self._selected_hash = None if h == self._selected_hash else h
        self._rebuild_curve_list()
        self._refresh_plot()

    def _pick_color(self, curve):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            curve['color'] = color.name()
            self._refresh_plot()
            self._rebuild_curve_list()

    def _remove_contour(self, idx):
        self._push_undo()
        removed = self._contour_curves.pop(idx)
        if removed.get('hash') == self._selected_hash:
            self._selected_hash = None
        self._rebuild_curve_list()
        self._refresh_plot()
        self._status(f"Removed: {removed['label']}")

    # ── Mouse / view ─────────────────────────────────────────────────────────

    def _on_scroll(self, event):
        if event.inaxes != self._ax:
            return
        factor = 1.1 if event.button == 'up' else 0.9
        xl, xr = self._ax.get_xlim()
        yb, yt = self._ax.get_ylim()
        cx, cy = event.xdata, event.ydata
        self._ax.set_xlim(cx - (cx-xl)*factor, cx + (xr-cx)*factor)
        self._ax.set_ylim(cy - (cy-yb)*factor, cy + (yt-cy)*factor)
        self._canvas.draw_idle()

    def _on_pan_press(self, event):
        if event.button == 3 and event.inaxes == self._ax:
            self._pan_data = (event.xdata, event.ydata,
                              self._ax.get_xlim(), self._ax.get_ylim())

    def _on_pan_release(self, event):
        self._pan_data = None

    def _on_pan_drag(self, event):
        if self._pan_data is None or event.inaxes != self._ax:
            return
        ox, oy, (xl, xr), (yb, yt) = self._pan_data
        dx = event.xdata - ox
        dy = event.ydata - oy
        self._ax.set_xlim(xl - dx, xr - dx)
        self._ax.set_ylim(yb - dy, yt - dy)
        self._canvas.draw_idle()

    def _on_plot_click(self, event):
        if event.xdata is None or event.inaxes != self._ax:
            return
        best_h, best_d = None, 5.0
        for c in self._contour_curves:
            if not self._visible.get(c['hash'], True):
                continue
            for z, r in zip(c['axial'], c['radial']):
                d = math.hypot(event.xdata - z, event.ydata - r)
                if d < best_d:
                    best_d, best_h = d, c['hash']
        if best_h:
            self._select_curve(best_h)

    def _on_mouse_move(self, event):
        if event.xdata is None:
            return
        self._status(f"X: {event.xdata:.2f}   R: {event.ydata:.3f}"
                     f"   LE: {self._le:.2f}   TE: {self._te:.2f}"
                     f"   CURVES: {len(self._contour_curves)}"
                     f"   UNDO: {len(self._undo_stack)}   REDO: {len(self._redo_stack)}")

    def _reset_view(self):
        if self._base_display:
            z = self._base_display[0]['axial']
            r = self._base_display[0]['original_radial']
            zr, rr = max(z)-min(z), max(r)-min(r)
            self._ax.set_xlim(min(z)-zr*.05, max(z)+zr*.05)
            self._ax.set_ylim(min(r)-rr*.1, max(r)+rr*.1)
            self._canvas.draw_idle()
        self._status("View reset")

    def _toggle_grid(self):
        self._show_grid = not self._show_grid
        self._refresh_plot()
        self._status(f"Grid {'ON' if self._show_grid else 'OFF'}")

    # ── Export ───────────────────────────────────────────────────────────────

    def _curve_to_csv_lines(self, curve):
        """Return list of CSV lines (R,Theta,Z) in absolute coordinates."""
        le, te = curve.get('le', self._axial_min), curve.get('te', self._axial_max)
        r_min = curve.get('r_min', 0.0)
        
        lines = ["R,Theta,Z"]
        for r_n, th, z in zip(curve['radial'], curve['theta'], curve['axial']):
            if self._export_only_le_te and not (le <= z <= te):
                continue
            abs_r = r_n + r_min
            lines.append(f"{abs_r:.6f},{th:.6f},{z:.6f}")
        return lines

    def _save_csv(self, lines, default_name):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save File", default_name, "CSV Files (*.csv)"
        )
        if path:
            with open(path, 'w') as f:
                f.write("\n".join(lines))
            self._status(f"Saved: {path}")

    def _save_project(self):
        data = {
            'le': self._le, 'te': self._te,
            'contours': [
                {'label': c['label'], 'method': c.get('method'),
                 'le': c.get('le'), 'te': c.get('te'),
                 'params': c.get('params'), 'color': c.get('color'),
                 'visible': self._visible.get(c['hash'], True)}
                for c in self._contour_curves
            ]
        }
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Project", "", "JSON Files (*.json)"
        )
        if path:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            self._status("Project saved")

    def _export_selected(self):
        if not self._selected_hash:
            self._status("No curve selected")
            return

        for c in self._contour_curves:
            if c['hash'] == self._selected_hash:
                dlg = ExportDialog(self)
                if dlg.exec():
                    path, fmt = dlg.get_values()
                    lines = self._curve_to_csv_lines(c)
                    with open(path, 'w') as f:
                        f.write("\n".join(lines))
                    self._status(f"Exported to {path}")
                return

    def _export_baseline(self):
        if not self._base_display:
            return
        b = self._base_display[0]
        lines = self._curve_to_csv_lines(b)
        self._save_csv(lines, "baseline_hub.csv")

    def _export_comparison(self):
        if not self._selected_hash:
            self._status("No curve selected for comparison")
            return
        for c in self._contour_curves:
            if c['hash'] == self._selected_hash:
                lines = ["Z,R_baseline,R_contoured,Delta_R"]
                le, te = c.get('le', self._axial_min), c.get('te', self._axial_max)
                for z, r_base, r_cont in zip(c['axial'], c['original_radial'], c['radial']):
                    if self._export_only_le_te and not (le <= z <= te):
                        continue
                    lines.append(f"{z:.6f},{r_base:.6f},{r_cont:.6f},{r_cont-r_base:.6f}")
                self._save_csv(lines, f"comparison_{c['label']}.csv")
                return

    def _export_all_zip(self):
        import zipfile
        if not self._contour_curves:
            self._status("No contours to export")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export All as ZIP", "hub_curves.zip", "ZIP Files (*.zip)"
        )
        if not path:
            return
        with zipfile.ZipFile(path, 'w') as zf:
            for c in self._contour_curves:
                name = c['label'].replace('/', '_').replace('\\', '_')
                lines = self._curve_to_csv_lines(c)
                zf.writestr(f"{name}.csv", "\n".join(lines))
        self._status(f"Exported {len(self._contour_curves)} curves to ZIP")

    def _delete_selected(self):
        if not self._selected_hash:
            self._status("No curve selected")
            return
        for i, c in enumerate(self._contour_curves):
            if c['hash'] == self._selected_hash:
                self._remove_contour(i)
                return

    # ── Update FreeCAD ───────────────────────────────────────────────────────

    def _on_update_freecad(self):
        try:
            import FreeCAD
            import FreeCADGui
            from HubContour.edge_utils import cylindrical_to_bspline

            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise RuntimeError("No active FreeCAD document")

            visible_contours = [
                c for c in self._contour_curves
                if self._visible.get(c['hash'], True)
            ]
            if not visible_contours:
                raise RuntimeError("No visible contours to write back")

            mode = self._mode_cb.currentText()

            doc.openTransaction("Hub Contour Update")
            written = []

            for c in visible_contours:
                fc_ref = self._fc_objects.get(
                    c.get('label', ''),
                    self._fc_objects.get(
                        self._base_display[0].get('label', ''), {}
                    )
                )
                obj = fc_ref.get('obj')
                subname = fc_ref.get('subname', '')
                r_min = c.get('r_min', 0.0)

                feat = cylindrical_to_bspline(
                    c['axial'], c['radial'],
                    c['theta'], r_min,
                    obj, subname, doc, mode
                )
                written.append(feat.Label)

                if obj is not None:
                    try:
                        obj.Visibility = False
                    except Exception:
                        pass

            doc.commitTransaction()
            doc.recompute()

            try:
                FreeCADGui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass

            QtWidgets.QMessageBox.information(
                self, "FreeCAD Update",
                f"Written to FreeCAD:\n" + "\n".join(written) + f"\n\nMode: {mode}"
            )
            self.close()

        except Exception as e:
            try:
                doc.abortTransaction()
            except Exception:
                pass
            QtWidgets.QMessageBox.critical(self, "Update Error", str(e))
            self._status(f"Error: {e}")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _hr(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet(f"color:{GRID_COLOR};")
        return line

    def _lbl(self, text, small=False):
        l = QtWidgets.QLabel(text)
        l.setStyleSheet(f"color:{TEXT_COLOR}; font-size:{'8' if small else '10'}px;")
        return l

    def _status(self, msg):
        if hasattr(self, '_status_bar') and self._status_bar is not None:
            self._status_bar.showMessage(msg, 4000)
        else:
            print(f"STATUS: {msg}")

























