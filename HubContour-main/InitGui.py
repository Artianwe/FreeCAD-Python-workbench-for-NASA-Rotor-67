"""
HubContour FreeCAD Addon
Initializes the workbench and registers commands/context menu entries.
"""

import FreeCADGui


class HubContourWorkbench(FreeCADGui.Workbench):
    MenuText = "Hub Contour"
    ToolTip  = "2D hub contouring tool for secondary flow reduction"
    Icon     = ""

    def Initialize(self):
        import HubContour.commands  # registers HubContour_Open as side-effect
        self.appendToolbar("Hub Contour", ["HubContour_Open"])
        self.appendMenu("Hub Contour", ["HubContour_Open"])

    def ContextMenu(self, recipient):
        try:
            sel      = FreeCADGui.Selection.getSelectionEx()
            has_edge = any(
                any(getattr(so, 'ShapeType', '') == 'Edge'
                    for so in (s.SubObjects or []))
                for s in sel
            )
            if has_edge:
                self.appendContextMenu("Hub Contour", ["HubContour_Open"])
        except Exception:
            pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(HubContourWorkbench())
