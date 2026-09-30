# HubContour - FreeCAD Hub Contouring Workbench

A Python-based FreeCAD workbench for extracting hub-profile edges, transforming them into cylindrical coordinates, applying configurable contour modifications, and writing the resulting geometry back into FreeCAD.

The project is aimed at rapid, interactive hub-profile exploration for turbomachinery and aerodynamic geometry studies. It combines a FreeCAD-native GUI with several parametric contouring methods and CSV/ZIP export workflows.

> **Project status:** Experimental / development-stage workbench.

## What it does

HubContour takes a selected FreeCAD edge and converts its geometry into an axial–radial representation:

```
FreeCAD XYZ
   │
   ├── R = √(X² + Y²)
   ├── Θ = atan2(Y, X)
   └── Z = axial coordinate
        │
        ▼
   2D contour workspace
        │
        ├── Sine bump
        ├── Hicks–Henne bump
        ├── Cubic spline
        ├── Bézier curve
        └── B-spline
        │
        ▼
   Modified R(Z)
        │
        ▼
   Back to XYZ → FreeCAD geometry
```

The angular coordinate is preserved so the modified profile can be reconstructed in the original 3D coordinate system.

## Key features

- **FreeCAD-native workbench** with toolbar, menu, and edge-selection context-menu integration.
- **Parametric contour generation** using five methods: Sine, Hicks–Henne, Cubic spline, Bézier, and B-spline.
- **Interactive overlay workflow** for comparing multiple generated contours against the baseline.
- **Manual contour editor** with draggable control points, grid snapping, point insertion/deletion, and reset controls.
- **Point-density control** for resampling profiles before contour generation.
- **Undo / redo** and duplicate-configuration detection.
- **FreeCAD geometry write-back** as a B-spline-based feature, with Wire, Surface, and Extrude modes.
- **Export tools** for baseline curves, selected curves, comparison CSVs, and ZIP bundles.
- **Project persistence** through JSON project export.

## Contouring methods

| Method | Main controls | Use |
|---|---|---|
| **Sine** | Amplitude, peak position | Smooth parametric bump |
| **Hicks–Henne** | Amplitude, peak location, width | Classic aerodynamic bump parameterization |
| **Cubic spline** | Control-point position and radial offset | Smooth free-form shaping |
| **Bézier** | Control points | Designer-controlled smooth shaping |
| **B-spline** | Control points, degree | Flexible higher-order shaping |

## Coordinate transformation

For a selected edge, the workbench samples the 3D geometry and computes:

```
R = √(X² + Y²)
Θ = atan2(Y, X)
Z = Z
```

The radial profile is normalized by subtracting its minimum radius during the contouring stage. When geometry is written back, the absolute radius is restored and converted to Cartesian coordinates:

```
X = R · cos(Θ)
Y = R · sin(Θ)
Z = Z
```

## Installation

The workbench is currently structured under `HubContour-main/`.

### Manual installation

1. Locate the FreeCAD user `Mod` directory.

| Platform | User Mod directory |
|---|---|
| Windows | `%APPDATA%\\FreeCAD\\Mod\\` |
| Linux | `~/.local/share/FreeCAD/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/Mod/` |

2. Copy the **contents of `HubContour-main/`** into a folder named `HubContour` inside the `Mod` directory:

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
        ├── main_window.py
        └── manual_editor.py
```

3. Restart FreeCAD.

The code uses **PySide6**, so it is intended for FreeCAD distributions that provide the PySide6-based GUI stack.

## Usage

1. Open a FreeCAD document containing the hub/profile geometry.
2. Select one or more edges representing the profile.
3. Open **Hub Contour → Hub Contour Tool** from the workbench toolbar/menu, or use the context menu when an edge is selected.
4. Choose the contouring method and define the LE/TE region.
5. Adjust the method parameters.
6. Click **ADD TO PLOT** to create an independent contour.
7. Compare, rename, hide/show, recolor, or remove generated curves from the overlay list.
8. Use the manual editor when direct control-point editing is required.
9. Export the curve data or click **UPDATE IN FREECAD** to create the modified geometry in the active document.

## Export formats

### Curve CSV

```text
R,Theta,Z
...

```

### Comparison CSV

```text
Z,R_baseline,R_contoured,Delta_R
...

```

### ZIP export

**Export All Curves (ZIP)** packages one CSV file per generated contour.

## Repository structure

```text
FreeCAD-Python-workbench-for-NASA-Rotor-67/
└── HubContour-main/
    ├── InitGui.py                 # FreeCAD workbench registration
    ├── commands.py                # Toolbar/menu/context command
    ├── edge_utils.py              # Edge sampling + XYZ/RθZ conversion
    ├── package.xml                # FreeCAD addon metadata
    ├── contouring/
    │   └── functions.py           # Parametric contour algorithms
    └── gui/
        ├── main_window.py         # Main contouring interface
        └── manual_editor.py       # Interactive control-point editor
```

## Technical implementation

The contour engine is implemented in pure Python and includes:

- Skewed-sine and Hicks–Henne parameterizations.
- Natural cubic-spline interpolation.
- Bernstein-polynomial Bézier evaluation.
- Cox–de Boor B-spline basis evaluation.
- Deterministic contour configuration hashing.
- FreeCAD `Part.BSplineCurve` geometry generation.
- Transaction-based write-back into the active FreeCAD document.

## Design workflow

The intended workflow is:

```
Select hub edge
      ↓
Sample 3D geometry
      ↓
Convert XYZ → (R, Θ, Z)
      ↓
Set LE / TE region
      ↓
Generate one or more contour variants
      ↓
Overlay + compare
      ↓
Export data / write geometry to FreeCAD
```

## Development notes

This repository is a portfolio/development implementation rather than an official FreeCAD project. API behavior and dependency availability can vary across FreeCAD releases and operating-system distributions.

Before distributing the workbench through the FreeCAD Addon Manager, the package metadata, installation layout, dependency handling, versioning, and automated tests should be reviewed against the current FreeCAD addon requirements.

## Developers

**Anwesh Dash (@Artianwe)**  
**AryaJeet1364 (@AryaJeet1364)**

Developed collaboratively.

## License

MIT License — see [LICENSE](LICENSE).

## Acknowledgements

- [FreeCAD](https://www.freecad.org/) for the open-source parametric CAD platform and Python API.
- The original HubContour concept/workflow that this FreeCAD implementation was developed from.
