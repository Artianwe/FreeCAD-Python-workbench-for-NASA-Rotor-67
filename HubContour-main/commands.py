"""
HubContour – commands.py
FreeCAD command that extracts selected edges and opens the contouring tool.
Uses PySide6 (FreeCAD 0.21+).
"""

import FreeCAD
import FreeCADGui
from PySide6 import QtWidgets


def open_contour_tool():
    """Extract selected edges, convert to cylindrical (R, θ, Z) and open GUI."""
    sel = FreeCADGui.Selection.getSelectionEx()
    edges = []
    for s in sel:
        for i, sub in enumerate(s.SubObjects or []):
            if sub.ShapeType == 'Edge':
                edges.append((s.Object, s.SubElementNames[i], sub))

    if not edges:
        QtWidgets.QMessageBox.warning(
            None, "Hub Contour",
            "Please select at least one edge before opening the Contour Tool.\n\n"
            "Tip: Select the hub profile edge in the 3D view, then click Hub Contour → Hub Contour Tool."
        )
        return

    from HubContour.edge_utils import edge_to_cylindrical
    curves = []
    for obj, sub_name, edge in edges:
        label = f"{obj.Label}:{sub_name}"
        data  = edge_to_cylindrical(edge)
        data['label']   = label
        data['obj']     = obj
        data['subname'] = sub_name
        curves.append(data)

    from HubContour.gui.main_window import ContourWindow
    win = ContourWindow(curves, parent=FreeCADGui.getMainWindow())
    win.show()
    win.raise_()
    win.activateWindow()


class HubContourOpenCommand:
    """Toolbar / menu / context-menu command."""

    def GetResources(self):
        return {
            'MenuText': 'Hub Contour Tool',
            'ToolTip' : 'Open the Hub Contouring Overlay for selected edge(s)',
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        open_contour_tool()


FreeCADGui.addCommand('HubContour_Open', HubContourOpenCommand())
