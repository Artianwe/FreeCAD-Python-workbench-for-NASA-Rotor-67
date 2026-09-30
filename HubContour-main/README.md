# HubContour – FreeCAD Addon

A 2D hub contouring overlay for designing vortex-reduction bumps in jet engine
hub profiles.  Ported from the MERN-stack web tool; runs entirely inside FreeCAD
with no external server dependency.

---

## Installation

### Option A – Copy manually (recommended during development)

1. Find your FreeCAD user **Mod** folder:

   | Platform | Path |
   |----------|------|
   | Linux    | `~/.local/share/FreeCAD/Mod/` |
   | macOS    | `~/Library/Application Support/FreeCAD/Mod/` |
   | Windows  | `%APPDATA%\FreeCAD\Mod\` |

2. Copy the entire `HubContour/` folder into that `Mod/` directory:

   ```
   Mod/
   └── HubContour/
       ├── __init__.py
       ├── InitGui.py
       ├── commands.py
       ├── edge_utils.py
       ├── package.xml
       ├── contouring/
       │   ├── __init__.py
       │   └── functions.py
       └── gui/
           ├── __init__.py
           └── main_window.py
   ```

3. Restart FreeCAD.

### Option B – FreeCAD Addon Manager

*(Once hosted on GitHub)*  
Tools → Addon Manager → search "HubContour" → Install.

---

## Dependencies

All dependencies ship with FreeCAD ≥ 0.20:

| Library    | Used for |
|------------|----------|
| PySide2    | GUI widgets |
| matplotlib | Plot canvas |
| Part       | BSpline / edge geometry |

---

## Usage

### Method 1 – Right-click (fastest)

1. Select one or more edges in the 3D view or model tree.
2. Right-click → **Open in Contour Tool**.

### Method 2 – Toolbar / Menu

Switch to the **Hub Contour** workbench, then click the toolbar button or
use the *Hub Contour* menu.

---

## Workflow inside the tool

| Step | Action |
|------|--------|
| 1 | Curves from selected edges appear in the plot automatically |
| 2 | Set **LE / TE** axial bounds for the bump region |
| 3 | Choose a **method**: Hicks-Henne, Sine, Cubic, Bezier, or B-Spline |
| 4 | Tune parameters (amplitude, peak location, width, …) |
| 5 | Click **APPLY CONTOUR** – plot updates live |
| 6 | Use **UNDO / REDO** as needed |
| 7 | **Add to Plot** imports additional selected edges for comparison |
| 8 | Click **✦ Write to FreeCAD** to insert the contoured BSpline wire |

---

## Coordinate convention

```
FreeCAD XYZ  ──▶  cylindrical (R = √(X²+Y²), Θ = atan2(Y,X), Z)
                  plot axes: Z (axial) vs R (radial)
modified R   ──▶  back to XYZ via  X = R·cos(Θ),  Y = R·sin(Θ)
```

Theta is preserved exactly so the round-trip is lossless.

---

## Contouring methods

| Method | Parameters | Best for |
|--------|-----------|----------|
| **hicks** | amplitude, peak_loc, width | Classic Hicks-Henne aerodynamic bump |
| **sine**  | amplitude, peak_pos | Smooth symmetric bump |
| **cubic** | control points (x:Δ) | Free-form with cubic interpolation |
| **bezier**| control points (x:Δ) | Smooth free-form, designer control |
| **bspline**| control points (x:Δ), degree | Highest flexibility |

---

## Export

- **Export Selected Curve** → single `.csv`  (`X, Y, Z` = R_abs, Θ, Z)
- **Export All Curves (ZIP)** → one `.csv` per curve inside a `.zip`

The CSV format is identical to the original MERN-stack tool so existing
post-processing scripts work without modification.
