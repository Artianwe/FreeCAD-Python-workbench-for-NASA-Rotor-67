# """
# HubContour – gui/manual_editor.py
# Manual Contour Editor with draggable control points.
# Features:
# - Adaptive grid (zoom-based)
# - Snap-to-grid precision
# - Smooth dragging with offset
# - Stable PCHIP interpolation (no oscillations)
# - LE->TE constraint preservation
# """

# import numpy as np
# from PySide6 import QtWidgets
# from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.figure import Figure
# import scipy.interpolate as si


# class ManualEditor(QtWidgets.QMainWindow):
#     """Manual Contour Editor - Direct control point editing with smooth spline."""

#     def __init__(self, curve, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Manual Contour Editor")
#         self.resize(1000, 700)
#         self.setMinimumSize(800, 600)

#         self._parent = parent
#         self._base_curve = curve

#         # Extract data
#         z = curve['axial']
#         r = curve['radial']
#         self._n_points = len(z)
#         self._z_min = min(z)
#         self._z_max = max(z)
#         self._z_range = self._z_max - self._z_min

#         # Initialize control points (6 points distributed along the curve)
#         indices = np.linspace(0, len(z) - 1, 6).astype(int)
#         self._control_points = [[z[i], r[i]] for i in indices]
        
#         # Fix endpoints (cannot be deleted)
#         self._fixed_endpoints = True
#         self._drag_idx = None
#         self._drag_offset = (0, 0)
#         self._grid_step = 1.0

#         # Minimum spacing between control points (2% of total range)
#         self._min_spacing = self._z_range * 0.02

#         # Setup UI
#         self._setup_ui()
#         self._update_curve()
#         self._refresh_plot()

#     def _setup_ui(self):
#         """Setup the main UI layout."""
#         central = QtWidgets.QWidget()
#         self.setCentralWidget(central)
        
#         main_layout = QtWidgets.QVBoxLayout(central)
#         main_layout.setContentsMargins(5, 5, 5, 5)
#         main_layout.setSpacing(5)

#         # Title bar
#         title_bar = QtWidgets.QHBoxLayout()
#         title = QtWidgets.QLabel("Manual Contour Editor - Drag points to adjust curve (Snap to Grid)")
#         title.setStyleSheet("color:#cccccc; font-size:11px; font-weight:bold;")
#         title_bar.addWidget(title)
#         title_bar.addStretch()
#         main_layout.addLayout(title_bar)

#         # Matplotlib figure
#         self._fig = Figure(facecolor='#1a1a1a', figsize=(10, 6))
#         self._canvas = FigureCanvas(self._fig)
#         self._ax = self._fig.add_subplot(111)
#         self._style_ax()
#         main_layout.addWidget(self._canvas, stretch=1)

#         # Control bar
#         control_bar = QtWidgets.QHBoxLayout()
        
#         # Info label
#         self._info_label = QtWidgets.QLabel("6 control points | Grid snap ON | Drag to edit")
#         self._info_label.setStyleSheet("color:#888; font-size:9px;")
#         control_bar.addWidget(self._info_label)
#         control_bar.addStretch()
        
#         # Snap toggle
#         self._snap_check = QtWidgets.QCheckBox("Snap to Grid")
#         self._snap_check.setChecked(True)
#         self._snap_check.setStyleSheet("color:#cccccc; font-size:9px;")
#         self._snap_check.stateChanged.connect(self._refresh_plot)
#         control_bar.addWidget(self._snap_check)
        
#         # Add point button
#         self._add_btn = QtWidgets.QPushButton("Add Point")
#         self._add_btn.setFixedWidth(100)
#         self._add_btn.clicked.connect(self._add_control_point)
#         control_bar.addWidget(self._add_btn)
        
#         # Delete point button
#         self._del_btn = QtWidgets.QPushButton("Delete Point")
#         self._del_btn.setFixedWidth(100)
#         self._del_btn.clicked.connect(self._delete_control_point)
#         control_bar.addWidget(self._del_btn)
        
#         # Reset button
#         self._reset_btn = QtWidgets.QPushButton("Reset")
#         self._reset_btn.setFixedWidth(80)
#         self._reset_btn.clicked.connect(self._reset_control_points)
#         control_bar.addWidget(self._reset_btn)
        
#         main_layout.addLayout(control_bar)

#         # Bottom buttons
#         button_bar = QtWidgets.QHBoxLayout()
#         button_bar.addStretch()
        
#         self._save_btn = QtWidgets.QPushButton("Save as New Contour")
#         self._save_btn.setStyleSheet("background:#ff6644; color:white; font-weight:bold; padding:8px 16px;")
#         self._save_btn.clicked.connect(self._on_save)
        
#         self._cancel_btn = QtWidgets.QPushButton("Cancel")
#         self._cancel_btn.clicked.connect(self.close)
        
#         button_bar.addWidget(self._save_btn)
#         button_bar.addWidget(self._cancel_btn)
#         main_layout.addLayout(button_bar)

#         # Connect mouse events
#         self._canvas.mpl_connect('button_press_event', self._on_press)
#         self._canvas.mpl_connect('motion_notify_event', self._on_drag)
#         self._canvas.mpl_connect('button_release_event', self._on_release)
#         self._canvas.mpl_connect('scroll_event', self._on_scroll)

#         # Create status bar
#         self._status_bar = QtWidgets.QStatusBar()
#         self.setStatusBar(self._status_bar)
#         self._status("Ready - Click and drag points to edit curve")

#     def _style_ax(self):
#         """Style the matplotlib axes."""
#         self._ax.set_facecolor('#1a1a1a')
#         self._ax.tick_params(colors='#cccccc', labelsize=8)
#         self._ax.set_xlabel('Axial Coordinate (Z)', fontsize=9, color='#cccccc')
#         self._ax.set_ylabel('Radius (R)', fontsize=9, color='#cccccc')
#         for sp in self._ax.spines.values():
#             sp.set_edgecolor('#333333')
#         self._fig.tight_layout(pad=1.0)

#     def _draw_adaptive_grid(self):
#         """Draw adaptive grid based on current zoom level."""
#         xlim = self._ax.get_xlim()
#         ylim = self._ax.get_ylim()

#         x_range = xlim[1] - xlim[0]
#         y_range = ylim[1] - ylim[0]

#         # Calculate adaptive step for X
#         base = 10 ** np.floor(np.log10(x_range))
#         step = base / 5
        
#         if x_range < 50:
#             step = base / 10
#         if x_range < 10:
#             step = base / 20

#         # Store step for snapping
#         self._grid_step = step

#         # Draw X grid lines
#         x_ticks = np.arange(xlim[0], xlim[1], step)
#         for x in x_ticks:
#             self._ax.axvline(x, color='#222222', linewidth=0.5, zorder=0)

#         # Calculate adaptive step for Y
#         base_y = 10 ** np.floor(np.log10(y_range))
#         step_y = base_y / 5
        
#         if y_range < 50:
#             step_y = base_y / 10
#         if y_range < 10:
#             step_y = base_y / 20

#         # Draw Y grid lines
#         y_ticks = np.arange(ylim[0], ylim[1], step_y)
#         for y in y_ticks:
#             self._ax.axhline(y, color='#222222', linewidth=0.5, zorder=0)

#         return step, step_y

#     def _snap(self, value, step):
#         """Snap value to nearest grid step."""
#         return round(value / step) * step

#     def _update_curve(self):
#         """
#         Update smooth curve from control points.
#         Uses PCHIP interpolator - NO oscillations, NO sharp edges.
#         """
#         if len(self._control_points) < 3:
#             return

#         # Sort control points by Z
#         pts = sorted(self._control_points, key=lambda p: p[0])
        
#         # Check minimum spacing constraint
#         for i in range(len(pts) - 1):
#             if abs(pts[i][0] - pts[i+1][0]) < self._min_spacing:
#                 # Invalid spacing - reject update
#                 return

#         z = np.array([p[0] for p in pts])
#         r = np.array([p[1] for p in pts])

#         try:
#             # PCHIP interpolator preserves monotonicity, no oscillations
#             spline = si.PchipInterpolator(z, r)
#             z_new = np.linspace(self._z_min, self._z_max, self._n_points)
#             r_new = spline(z_new)
#             self._current_curve = (z_new, r_new)
#         except Exception:
#             # Fallback to linear interpolation
#             z_new = np.linspace(self._z_min, self._z_max, self._n_points)
#             r_new = np.interp(z_new, z, r)
#             self._current_curve = (z_new, r_new)

#     def _refresh_plot(self):
#         """Refresh the plot with current curve and control points."""
#         if not hasattr(self, '_ax'):
#             return

#         self._ax.cla()
#         self._style_ax()

#         # Draw adaptive grid
#         step_x, step_y = self._draw_adaptive_grid()

#         # Original curve (reference - dashed gray)
#         self._ax.plot(
#             self._base_curve['axial'],
#             self._base_curve['radial'],
#             color='#888888', linestyle='--', linewidth=1.5,
#             label='Original Curve', alpha=0.7, zorder=1
#         )

#         # Edited curve (smooth - cyan)
#         if hasattr(self, '_current_curve'):
#             z, r = self._current_curve
#             self._ax.plot(z, r, color='#00ffff', linewidth=2.5,
#                          label='Edited Curve', zorder=2)

#         # Control points
#         cp = np.array(self._control_points)
        
#         if self._fixed_endpoints and len(cp) >= 2:
#             # Fixed endpoints (red squares)
#             self._ax.scatter(cp[0, 0], cp[0, 1], color='#ff6644', marker='s', s=120,
#                            edgecolors='white', linewidth=1.5, label='Fixed Endpoints', zorder=3)
#             self._ax.scatter(cp[-1, 0], cp[-1, 1], color='#ff6644', marker='s', s=120,
#                            edgecolors='white', linewidth=1.5, zorder=3)
#             # Movable points (yellow circles)
#             if len(cp) > 2:
#                 self._ax.scatter(cp[1:-1, 0], cp[1:-1, 1], color='#ffff00', marker='o', s=100,
#                                edgecolors='white', linewidth=1.5, label='Control Points', zorder=3)
#         else:
#             self._ax.scatter(cp[:, 0], cp[:, 1], color='#ffff00', marker='o', s=100,
#                            edgecolors='white', linewidth=1.5, label='Control Points', zorder=3)

#         # Highlight currently dragging point
#         if self._drag_idx is not None:
#             p = self._control_points[self._drag_idx]
#             self._ax.scatter(p[0], p[1], color='#00ff88', marker='o', s=80,
#                            edgecolors='white', linewidth=2, zorder=5)

#         self._ax.legend(loc='upper left', fontsize=8, facecolor='#1e1e1e', edgecolor='#333')
        
#         # Add some padding to view
#         x_padding = self._z_range * 0.05
#         self._ax.set_xlim(self._z_min - x_padding, self._z_max + x_padding)
        
#         self._canvas.draw_idle()
        
#         snap_status = "ON" if self._snap_check.isChecked() else "OFF"
#         self._info_label.setText(f"{len(self._control_points)} control points | Grid snap {snap_status} | Grid step: {step_x:.3f}")

#     def _find_nearest_point(self, x, y):
#         """Find nearest control point with scale-aware threshold."""
#         # Scale-aware threshold (2% of total Z range)
#         threshold = 0.02 * self._z_range
        
#         min_dist = float('inf')
#         idx = None
        
#         for i, (px, py) in enumerate(self._control_points):
#             dist = np.sqrt((px - x)**2 + (py - y)**2)
#             if dist < min_dist and dist < threshold:
#                 min_dist = dist
#                 idx = i
        
#         return idx

#     def _on_scroll(self, event):
#         """Handle scroll for zooming."""
#         if event.inaxes != self._ax:
#             return
        
#         factor = 1.1 if event.button == 'up' else 0.9
#         xlim = self._ax.get_xlim()
#         ylim = self._ax.get_ylim()
#         cx, cy = event.xdata, event.ydata
        
#         if cx is not None and cy is not None:
#             new_xlim = (cx - (cx - xlim[0]) * factor, cx + (xlim[1] - cx) * factor)
#             new_ylim = (cy - (cy - ylim[0]) * factor, cy + (ylim[1] - cy) * factor)
#             self._ax.set_xlim(new_xlim)
#             self._ax.set_ylim(new_ylim)
#             self._refresh_plot()

#     def _on_press(self, event):
#         """Handle mouse press - start dragging."""
#         if event.xdata is None or event.ydata is None:
#             return
        
#         if event.button == 1:  # Left click
#             self._drag_idx = self._find_nearest_point(event.xdata, event.ydata)
#             if self._drag_idx is not None:
#                 # Store drag offset for smooth dragging
#                 px, py = self._control_points[self._drag_idx]
#                 self._drag_offset = (event.xdata - px, event.ydata - py)
#                 self._status(f"Dragging point {self._drag_idx}")
#                 self._refresh_plot()  # Show highlight
                
#         elif event.button == 3:  # Right click - delete
#             idx = self._find_nearest_point(event.xdata, event.ydata)
#             if idx is not None:
#                 self._delete_point_at_index(idx)

#     def _on_drag(self, event):
#         """Handle mouse drag - move control point with smoothing and snap."""
#         if self._drag_idx is None or event.xdata is None or event.ydata is None:
#             return
        
#         # Calculate new position with offset
#         new_z = event.xdata - self._drag_offset[0]
#         new_r = event.ydata - self._drag_offset[1]
        
#         # Apply snap to grid if enabled
#         if self._snap_check.isChecked():
#             new_z = self._snap(new_z, self._grid_step)
#             new_r = self._snap(new_r, self._grid_step)
        
#         # Constrain to bounds
#         new_z = max(self._z_min, min(self._z_max, new_z))
        
#         # Apply smoothing (low-pass filter for smooth dragging)
#         alpha = 0.25  # Smoothing factor
#         prev_z, prev_r = self._control_points[self._drag_idx]
#         new_z = prev_z * (1 - alpha) + new_z * alpha
#         new_r = prev_r * (1 - alpha) + new_r * alpha
        
#         # Fixed endpoints: keep Z fixed
#         if self._fixed_endpoints and (self._drag_idx == 0 or self._drag_idx == len(self._control_points) - 1):
#             new_z = self._control_points[self._drag_idx][0]
        
#         self._control_points[self._drag_idx] = [new_z, new_r]
        
#         # Sort control points by Z
#         self._control_points.sort(key=lambda p: p[0])
        
#         # Update drag index after sort
#         for i, pt in enumerate(self._control_points):
#             if abs(pt[0] - new_z) < 0.01 and abs(pt[1] - new_r) < 0.01:
#                 self._drag_idx = i
#                 break
        
#         self._update_curve()
#         self._refresh_plot()

#     def _on_release(self, event):
#         """Handle mouse release - stop dragging."""
#         if self._drag_idx is not None:
#             self._status(f"Point {self._drag_idx} moved")
#         self._drag_idx = None
#         self._refresh_plot()

#     def _add_control_point(self):
#         """Add a new control point."""
#         if len(self._control_points) >= 12:
#             self._status("Maximum 12 control points reached")
#             return
        
#         if hasattr(self, '_current_curve'):
#             z, r = self._current_curve
#             mid_idx = len(z) // 2
#             new_point = [z[mid_idx], r[mid_idx]]
#         else:
#             new_point = [(self._z_min + self._z_max) / 2, 0]
        
#         self._control_points.append(new_point)
#         self._control_points.sort(key=lambda p: p[0])
#         self._update_curve()
#         self._refresh_plot()
#         self._status(f"Added control point at Z={new_point[0]:.2f}")

#     def _delete_point_at_index(self, idx):
#         """Delete control point at index."""
#         if self._fixed_endpoints and (idx == 0 or idx == len(self._control_points) - 1):
#             self._status("Cannot delete fixed endpoints (LE/TE)")
#             return
        
#         if len(self._control_points) <= 3:
#             self._status("Minimum 3 control points required")
#             return
        
#         deleted = self._control_points.pop(idx)
#         self._update_curve()
#         self._refresh_plot()
#         self._status(f"Deleted control point at Z={deleted[0]:.2f}")

#     def _delete_control_point(self):
#         """Delete last movable point."""
#         if len(self._control_points) <= 3:
#             self._status("Minimum 3 control points required")
#             return
        
#         if self._fixed_endpoints and len(self._control_points) > 2:
#             idx = len(self._control_points) - 2
#             self._delete_point_at_index(idx)
#         elif len(self._control_points) > 1:
#             idx = len(self._control_points) - 1
#             self._delete_point_at_index(idx)

#     def _reset_control_points(self):
#         """Reset to original curve."""
#         z = self._base_curve['axial']
#         r = self._base_curve['radial']
#         indices = np.linspace(0, len(z) - 1, 6).astype(int)
#         self._control_points = [[z[i], r[i]] for i in indices]
#         self._update_curve()
#         self._refresh_plot()
#         self._status("Reset to original curve")

#     def _on_save(self):
#         """Save and add to main window."""
#         if not hasattr(self, '_current_curve'):
#             return
        
#         z, r = self._current_curve
        
#         import hashlib
#         import time
#         contour_hash = hashlib.md5(f"manual_{time.time()}".encode()).hexdigest()[:6]
        
#         new_curve = {
#             'label': f"MANUAL_{contour_hash}",
#             'axial': z.tolist(),
#             'radial': r.tolist(),
#             'original_radial': self._base_curve.get('original_radial', self._base_curve['radial']),
#             'theta': self._base_curve.get('theta', []),
#             'r_min': self._base_curve.get('r_min', 0.0),
#             'method': 'manual',
#             'le': self._base_curve.get('le', self._z_min),
#             'te': self._base_curve.get('te', self._z_max),
#             'params': {'control_points': self._control_points},
#             'hash': contour_hash,
#         }
        
#         if self._parent and hasattr(self._parent, '_add_manual_curve'):
#             self._parent._add_manual_curve(new_curve)
#             self._status("Manual contour saved")
        
#         self.close()

#     def _status(self, msg):
#         """Show status message."""
#         if hasattr(self, '_status_bar'):
#             self._status_bar.showMessage(msg, 2000)






"""
HubContour – gui/manual_editor.py
Manual Contour Editor with draggable control points.
Features:
- Adaptive grid (zoom-based)
- Snap-to-grid precision
- Smooth dragging with offset
- Stable PCHIP interpolation (no oscillations)
- LE->TE constraint preservation
- Control points: 3-10 (smooth curve only)
"""

import numpy as np
from PySide6 import QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import scipy.interpolate as si


class ManualEditor(QtWidgets.QMainWindow):
    """Manual Contour Editor - Direct control point editing with smooth spline."""

    # Control point limits
    MIN_POINTS = 3  # Minimum for smooth curve
    MAX_POINTS = 10  # Maximum for smooth curve

    def __init__(self, curve, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Contour Editor")
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)

        self._parent = parent
        self._base_curve = curve

        # Extract data
        z = curve['axial']
        r = curve['radial']
        self._n_points = len(z)
        self._z_min = min(z)
        self._z_max = max(z)
        self._z_range = self._z_max - self._z_min

        # Initialize control points (6 points distributed along the curve)
        num_initial = min(6, self.MAX_POINTS)
        indices = np.linspace(0, len(z) - 1, num_initial).astype(int)
        self._control_points = [[z[i], r[i]] for i in indices]
        
        # Fix endpoints (cannot be deleted)
        self._fixed_endpoints = True
        self._drag_idx = None
        self._drag_offset = (0, 0)
        self._grid_step = 1.0

        # Minimum spacing between control points (2% of total range)
        self._min_spacing = self._z_range * 0.02

        # Setup UI
        self._setup_ui()
        self._update_curve()
        self._refresh_plot()

    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Title bar
        title_bar = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Manual Contour Editor - Drag points to adjust curve (Snap to Grid)")
        title.setStyleSheet("color:#cccccc; font-size:11px; font-weight:bold;")
        title_bar.addWidget(title)
        title_bar.addStretch()
        main_layout.addLayout(title_bar)

        # Matplotlib figure
        self._fig = Figure(facecolor='#1a1a1a', figsize=(10, 6))
        self._canvas = FigureCanvas(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._style_ax()
        main_layout.addWidget(self._canvas, stretch=1)

        # Control bar
        control_bar = QtWidgets.QHBoxLayout()
        
        # Info label
        self._info_label = QtWidgets.QLabel(f"{len(self._control_points)} control points | Grid snap ON | Drag to edit")
        self._info_label.setStyleSheet("color:#888; font-size:9px;")
        control_bar.addWidget(self._info_label)
        control_bar.addStretch()
        
        # Snap toggle
        self._snap_check = QtWidgets.QCheckBox("Snap to Grid")
        self._snap_check.setChecked(True)
        self._snap_check.setStyleSheet("color:#cccccc; font-size:9px;")
        self._snap_check.stateChanged.connect(self._refresh_plot)
        control_bar.addWidget(self._snap_check)
        
        # Add point button
        self._add_btn = QtWidgets.QPushButton("Add Point")
        self._add_btn.setFixedWidth(100)
        self._add_btn.clicked.connect(self._add_control_point)
        control_bar.addWidget(self._add_btn)
        
        # Delete point button
        self._del_btn = QtWidgets.QPushButton("Delete Point")
        self._del_btn.setFixedWidth(100)
        self._del_btn.clicked.connect(self._delete_control_point)
        control_bar.addWidget(self._del_btn)
        
        # Reset button
        self._reset_btn = QtWidgets.QPushButton("Reset")
        self._reset_btn.setFixedWidth(80)
        self._reset_btn.clicked.connect(self._reset_control_points)
        control_bar.addWidget(self._reset_btn)
        
        main_layout.addLayout(control_bar)

        # Bottom buttons
        button_bar = QtWidgets.QHBoxLayout()
        button_bar.addStretch()
        
        self._save_btn = QtWidgets.QPushButton("Save as New Contour")
        self._save_btn.setStyleSheet("background:#ff6644; color:white; font-weight:bold; padding:8px 16px;")
        self._save_btn.clicked.connect(self._on_save)
        
        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.close)
        
        button_bar.addWidget(self._save_btn)
        button_bar.addWidget(self._cancel_btn)
        main_layout.addLayout(button_bar)

        # Connect mouse events
        self._canvas.mpl_connect('button_press_event', self._on_press)
        self._canvas.mpl_connect('motion_notify_event', self._on_drag)
        self._canvas.mpl_connect('button_release_event', self._on_release)
        self._canvas.mpl_connect('scroll_event', self._on_scroll)

        # Create status bar
        self._status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status("Ready - Click and drag points to edit curve")

    def _style_ax(self):
        """Style the matplotlib axes."""
        self._ax.set_facecolor('#1a1a1a')
        self._ax.tick_params(colors='#cccccc', labelsize=8)
        self._ax.set_xlabel('Axial Coordinate (Z)', fontsize=9, color='#cccccc')
        self._ax.set_ylabel('Radius (R)', fontsize=9, color='#cccccc')
        for sp in self._ax.spines.values():
            sp.set_edgecolor('#333333')
        self._fig.tight_layout(pad=1.0)

    def _draw_adaptive_grid(self):
        """Draw adaptive grid based on current zoom level."""
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()

        x_range = xlim[1] - xlim[0]
        y_range = ylim[1] - ylim[0]

        # Calculate adaptive step for X
        base = 10 ** np.floor(np.log10(x_range))
        step = base / 5
        
        if x_range < 50:
            step = base / 10
        if x_range < 10:
            step = base / 20

        # Store step for snapping
        self._grid_step = step

        # Draw X grid lines
        x_ticks = np.arange(xlim[0], xlim[1], step)
        for x in x_ticks:
            self._ax.axvline(x, color='#222222', linewidth=0.5, zorder=0)

        # Calculate adaptive step for Y
        base_y = 10 ** np.floor(np.log10(y_range))
        step_y = base_y / 5
        
        if y_range < 50:
            step_y = base_y / 10
        if y_range < 10:
            step_y = base_y / 20

        # Draw Y grid lines
        y_ticks = np.arange(ylim[0], ylim[1], step_y)
        for y in y_ticks:
            self._ax.axhline(y, color='#222222', linewidth=0.5, zorder=0)

        return step, step_y

    def _snap(self, value, step):
        """Snap value to nearest grid step."""
        return round(value / step) * step

    def _update_curve(self):
        """
        Update smooth curve from control points.
        Uses PCHIP interpolator - NO oscillations, NO sharp edges.
        """
        if len(self._control_points) < self.MIN_POINTS:
            self._status(f"Need at least {self.MIN_POINTS} control points for smooth curve")
            return

        # Sort control points by Z
        pts = sorted(self._control_points, key=lambda p: p[0])
        
        # Check minimum spacing constraint
        for i in range(len(pts) - 1):
            if abs(pts[i][0] - pts[i+1][0]) < self._min_spacing:
                self._status("Points too close — adjust spacing")
                return

        z = np.array([p[0] for p in pts])
        r = np.array([p[1] for p in pts])

        try:
            # PCHIP interpolator preserves monotonicity, no oscillations
            spline = si.PchipInterpolator(z, r)
            z_new = np.linspace(self._z_min, self._z_max, self._n_points)
            r_new = spline(z_new)
            self._current_curve = (z_new, r_new)
            self._status("Curve updated (smooth PCHIP)")
        except Exception as e:
            self._status(f"Error: {e}")
            # Fallback to linear interpolation
            z_new = np.linspace(self._z_min, self._z_max, self._n_points)
            r_new = np.interp(z_new, z, r)
            self._current_curve = (z_new, r_new)

    def _refresh_plot(self):
        """Refresh the plot with current curve and control points."""
        if not hasattr(self, '_ax'):
            return

        self._ax.cla()
        self._style_ax()

        # Draw adaptive grid
        step_x, step_y = self._draw_adaptive_grid()

        # Original curve (reference - dashed gray)
        self._ax.plot(
            self._base_curve['axial'],
            self._base_curve['radial'],
            color='#888888', linestyle='--', linewidth=1.5,
            label='Original Curve', alpha=0.7, zorder=1
        )

        # Edited curve (smooth - cyan)
        if hasattr(self, '_current_curve'):
            z, r = self._current_curve
            self._ax.plot(z, r, color='#00ffff', linewidth=2.5,
                         label='Edited Curve', zorder=2)

        # Control points
        cp = np.array(self._control_points)
        
        if self._fixed_endpoints and len(cp) >= 2:
            # Fixed endpoints (red squares)
            self._ax.scatter(cp[0, 0], cp[0, 1], color='#ff6644', marker='s', s=120,
                           edgecolors='white', linewidth=1.5, label='Fixed Endpoints', zorder=3)
            self._ax.scatter(cp[-1, 0], cp[-1, 1], color='#ff6644', marker='s', s=120,
                           edgecolors='white', linewidth=1.5, zorder=3)
            # Movable points (yellow circles)
            if len(cp) > 2:
                self._ax.scatter(cp[1:-1, 0], cp[1:-1, 1], color='#ffff00', marker='o', s=100,
                               edgecolors='white', linewidth=1.5, label='Control Points', zorder=3)
        else:
            self._ax.scatter(cp[:, 0], cp[:, 1], color='#ffff00', marker='o', s=100,
                           edgecolors='white', linewidth=1.5, label='Control Points', zorder=3)

        # Highlight currently dragging point
        if self._drag_idx is not None:
            p = self._control_points[self._drag_idx]
            self._ax.scatter(p[0], p[1], color='#00ff88', marker='o', s=80,
                           edgecolors='white', linewidth=2, zorder=5)

        self._ax.legend(loc='upper left', fontsize=8, facecolor='#1e1e1e', edgecolor='#333')
        
        # Set proper x and y limits
        x_padding = self._z_range * 0.05
        self._ax.set_xlim(self._z_min - x_padding, self._z_max + x_padding)
        
        # Calculate y limits from control points and curve
        r_values = [p[1] for p in self._control_points]
        if hasattr(self, '_current_curve'):
            r_values += list(self._current_curve[1])
        
        if r_values:
            r_min = min(r_values)
            r_max = max(r_values)
            if r_max != r_min:
                y_padding = (r_max - r_min) * 0.1
            else:
                y_padding = 1.0
            self._ax.set_ylim(r_min - y_padding, r_max + y_padding)
        
        self._canvas.draw_idle()
        
        snap_status = "ON" if self._snap_check.isChecked() else "OFF"
        self._info_label.setText(f"{len(self._control_points)}/{self.MAX_POINTS} control points | Grid snap {snap_status} | Step: {step_x:.3f}")

    def _find_nearest_point(self, x, y):
        """Find nearest control point with scale-aware threshold."""
        threshold = 0.02 * self._z_range
        
        min_dist = float('inf')
        idx = None
        
        for i, (px, py) in enumerate(self._control_points):
            dist = np.sqrt((px - x)**2 + (py - y)**2)
            if dist < min_dist and dist < threshold:
                min_dist = dist
                idx = i
        
        return idx

    def _on_scroll(self, event):
        """Handle scroll for zooming."""
        if event.inaxes != self._ax:
            return
        
        factor = 1.1 if event.button == 'up' else 0.9
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()
        cx, cy = event.xdata, event.ydata
        
        if cx is not None and cy is not None:
            new_xlim = (cx - (cx - xlim[0]) * factor, cx + (xlim[1] - cx) * factor)
            new_ylim = (cy - (cy - ylim[0]) * factor, cy + (ylim[1] - cy) * factor)
            self._ax.set_xlim(new_xlim)
            self._ax.set_ylim(new_ylim)
            self._refresh_plot()

    def _on_press(self, event):
        """Handle mouse press - start dragging."""
        if event.xdata is None or event.ydata is None:
            return
        
        if event.button == 1:  # Left click
            self._drag_idx = self._find_nearest_point(event.xdata, event.ydata)
            if self._drag_idx is not None:
                px, py = self._control_points[self._drag_idx]
                self._drag_offset = (event.xdata - px, event.ydata - py)
                self._status(f"Dragging point {self._drag_idx}")
                self._refresh_plot()
                
        elif event.button == 3:  # Right click - delete
            idx = self._find_nearest_point(event.xdata, event.ydata)
            if idx is not None:
                self._delete_point_at_index(idx)

    def _on_drag(self, event):
        """Handle mouse drag - move control point with smoothing and snap."""
        if self._drag_idx is None or event.xdata is None or event.ydata is None:
            return
        
        new_z = event.xdata - self._drag_offset[0]
        new_r = event.ydata - self._drag_offset[1]
        
        if self._snap_check.isChecked():
            new_z = self._snap(new_z, self._grid_step)
            new_r = self._snap(new_r, self._grid_step)
        
        new_z = max(self._z_min, min(self._z_max, new_z))
        
        # Apply smoothing (low-pass filter for smooth dragging)
        alpha = 0.25
        prev_z, prev_r = self._control_points[self._drag_idx]
        new_z = prev_z * (1 - alpha) + new_z * alpha
        new_r = prev_r * (1 - alpha) + new_r * alpha
        
        # Fixed endpoints: keep Z fixed
        if self._fixed_endpoints and (self._drag_idx == 0 or self._drag_idx == len(self._control_points) - 1):
            new_z = self._control_points[self._drag_idx][0]
        
        self._control_points[self._drag_idx] = [new_z, new_r]
        self._control_points.sort(key=lambda p: p[0])
        
        # Update drag index after sort
        for i, pt in enumerate(self._control_points):
            if abs(pt[0] - new_z) < 0.01 and abs(pt[1] - new_r) < 0.01:
                self._drag_idx = i
                break
        
        self._update_curve()
        self._refresh_plot()

    def _on_release(self, event):
        """Handle mouse release - stop dragging."""
        if self._drag_idx is not None:
            self._status(f"Point {self._drag_idx} moved")
        self._drag_idx = None
        self._refresh_plot()

    def _add_control_point(self):
        """Add a new control point at the largest gap."""
        if len(self._control_points) >= self.MAX_POINTS:
            self._status(f"Maximum {self.MAX_POINTS} control points reached")
            return
        
        # Find largest gap between existing points
        pts = sorted(self._control_points, key=lambda p: p[0])
        
        max_gap = 0
        insert_z = None
        insert_idx = 0
        
        for i in range(len(pts) - 1):
            gap = pts[i+1][0] - pts[i][0]
            if gap > max_gap:
                max_gap = gap
                insert_z = (pts[i+1][0] + pts[i][0]) / 2
                insert_idx = i + 1
        
        if insert_z is None:
            self._status("Cannot add point - no valid position found")
            return
        
        # Interpolate R at that Z from current curve
        if hasattr(self, '_current_curve'):
            z_curve, r_curve = self._current_curve
            insert_r = np.interp(insert_z, z_curve, r_curve)
        else:
            insert_r = 0
        
        new_point = [insert_z, insert_r]
        self._control_points.append(new_point)
        self._control_points.sort(key=lambda p: p[0])
        
        self._update_curve()
        self._refresh_plot()
        self._status(f"Added control point at Z={insert_z:.2f} (gap={max_gap:.3f})")

    def _delete_point_at_index(self, idx):
        """Delete control point at index."""
        if self._fixed_endpoints and (idx == 0 or idx == len(self._control_points) - 1):
            self._status("Cannot delete fixed endpoints (LE/TE)")
            return
        
        if len(self._control_points) <= self.MIN_POINTS:
            self._status(f"Minimum {self.MIN_POINTS} control points required")
            return
        
        deleted = self._control_points.pop(idx)
        self._update_curve()
        self._refresh_plot()
        self._status(f"Deleted control point at Z={deleted[0]:.2f}")

    def _delete_control_point(self):
        """Delete last movable point."""
        if len(self._control_points) <= self.MIN_POINTS:
            self._status(f"Minimum {self.MIN_POINTS} control points required")
            return
        
        if self._fixed_endpoints and len(self._control_points) > 2:
            idx = len(self._control_points) - 2
            self._delete_point_at_index(idx)
        elif len(self._control_points) > 1:
            idx = len(self._control_points) - 1
            self._delete_point_at_index(idx)

    def _reset_control_points(self):
        """Reset to original curve."""
        z = self._base_curve['axial']
        r = self._base_curve['radial']
        num_initial = min(6, self.MAX_POINTS)
        indices = np.linspace(0, len(z) - 1, num_initial).astype(int)
        self._control_points = [[z[i], r[i]] for i in indices]
        self._update_curve()
        self._refresh_plot()
        self._status("Reset to original curve")

    def _on_save(self):
        """Save as new contour in main window."""
        if not hasattr(self, '_current_curve'):
            self._status("No valid curve to save")
            return
        
        z, r = self._current_curve
        
        import hashlib
        import time
        contour_hash = hashlib.md5(f"manual_{time.time()}".encode()).hexdigest()[:6]
        
        new_curve = {
            'label': f"MANUAL_{contour_hash}",
            'axial': z.tolist(),
            'radial': r.tolist(),
            'original_radial': self._base_curve.get('original_radial', self._base_curve['radial']),
            'theta': self._base_curve.get('theta', []),
            'r_min': self._base_curve.get('r_min', 0.0),
            'method': 'manual',
            'le': self._base_curve.get('le', self._z_min),
            'te': self._base_curve.get('te', self._z_max),
            'params': {'control_points': self._control_points},
            'hash': contour_hash,
        }
        
        if self._parent and hasattr(self._parent, '_add_manual_curve'):
            self._parent._add_manual_curve(new_curve)
            self._status("Manual contour saved as new curve")
        else:
            self._status("Error: Parent window doesn't support adding curves")
        
        self.close()

    def _status(self, msg):
        """Show status message."""
        if hasattr(self, '_status_bar'):
            self._status_bar.showMessage(msg, 2000)
        print(f"ManualEditor: {msg}")