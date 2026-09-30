# """
# HubContour – edge_utils.py
# Converts a FreeCAD edge to cylindrical (R, θ, Z) arrays
# and writes modified geometry back as a BSpline feature.
# """

# import math
# import FreeCAD
# import Part


# N_SAMPLES = 50


# def edge_to_cylindrical(edge, n=N_SAMPLES):
#     """
#     Discretise *edge* into *n* evenly-spaced points.
#     Returns dict:
#         axial           – Z coordinates (sorted ascending)
#         radial          – R = sqrt(X²+Y²), normalised so min(R) = 0
#         theta           – atan2(Y, X) in radians (preserved for round-trip)
#         r_min           – the subtracted minimum (needed to reconstruct absolute R)
#         original_radial – copy of radial before any contouring (same as radial at load time)
#     """
#     first  = edge.FirstParameter
#     last   = edge.LastParameter

#     params = [first + (last - first) * i / (n - 1) for i in range(n)]
#     points = [edge.valueAt(p) for p in params]

#     X = [p.x for p in points]
#     Y = [p.y for p in points]
#     Z = [p.z for p in points]

#     R     = [math.sqrt(x**2 + y**2) for x, y in zip(X, Y)]
#     Theta = [math.atan2(y, x)        for x, y in zip(X, Y)]

#     # Sort by axial (Z) — matches JS sort in contourService.js
#     order  = sorted(range(n), key=lambda i: Z[i])
#     Z_s    = [Z[i]     for i in order]
#     R_s    = [R[i]     for i in order]
#     Th_s   = [Theta[i] for i in order]

#     # Normalise radial (subtract minimum) — matches JS normalizedRadial
#     r_min  = min(R_s)
#     R_norm = [r - r_min for r in R_s]

#     return {
#         'axial'          : Z_s,
#         'radial'         : R_norm,
#         'original_radial': list(R_norm),   # snapshot before contouring
#         'theta'          : Th_s,
#         'r_min'          : r_min,
#     }


# def cylindrical_to_bspline(axial, radial, theta, r_min, obj, subname, doc):
#     """
#     Convert (axial=Z, radial=R_norm, theta) back to XYZ and create a
#     BSpline Part::Feature in *doc*.  Returns the new feature.
#     """
#     R_abs = [r + r_min for r in radial]

#     pts = [
#         FreeCAD.Vector(
#             R_abs[i] * math.cos(theta[i]),
#             R_abs[i] * math.sin(theta[i]),
#             axial[i]
#         )
#         for i in range(len(axial))
#     ]

#     bspline = Part.BSplineCurve()
#     bspline.interpolate(pts)
#     shape = bspline.toShape()

#     base_label = f"Contoured_{subname}" if subname else "Contoured_Hub"
#     feat        = doc.addObject("Part::Feature", base_label)
#     feat.Shape  = shape
#     feat.Label  = base_label
#     doc.recompute()
#     return feat




"""
HubContour – edge_utils.py
Converts a FreeCAD edge to cylindrical (R, θ, Z) arrays with dynamic point density.
"""

import math
import FreeCAD
import Part

# Default - will be overridden by UI
DEFAULT_SAMPLES = 50


def edge_to_cylindrical(edge, n=DEFAULT_SAMPLES):
    """
    Discretise *edge* into *n* evenly-spaced points.
    n can be changed by user (50, 100, 200, or custom).
    """
    first = edge.FirstParameter
    last = edge.LastParameter
    
    params = [first + (last - first) * i / (n - 1) for i in range(n)]
    points = [edge.valueAt(p) for p in params]
    
    X = [p.x for p in points]
    Y = [p.y for p in points]
    Z = [p.z for p in points]
    
    R = [math.sqrt(x**2 + y**2) for x, y in zip(X, Y)]
    Theta = [math.atan2(y, x) for x, y in zip(X, Y)]
    
    # Sort by axial (Z)
    order = sorted(range(n), key=lambda i: Z[i])
    Z_s = [Z[i] for i in order]
    R_s = [R[i] for i in order]
    Th_s = [Theta[i] for i in order]
    
    # Normalise radial (subtract minimum)
    r_min = min(R_s)
    R_norm = [r - r_min for r in R_s]
    
    return {
        'axial': Z_s,
        'radial': R_norm,
        'original_radial': list(R_norm),
        'theta': Th_s,
        'r_min': r_min,
    }


def cylindrical_to_bspline(axial, radial, theta, r_min, obj, subname, doc, mode="Wire"):
    """
    Convert back to XYZ and create a BSpline in FreeCAD.
    mode: "Wire", "Surface", or "Extrude"
    """
    R_abs = [r + r_min for r in radial]
    
    pts = [
        FreeCAD.Vector(
            R_abs[i] * math.cos(theta[i]),
            R_abs[i] * math.sin(theta[i]),
            axial[i]
        )
        for i in range(len(axial))
    ]
    
    bspline = Part.BSplineCurve()
    bspline.interpolate(pts)
    shape = bspline.toShape()
    
    # Apply 3D mode
    if mode == "Surface":
        # Revolve around Z-axis to create surface
        shape = shape.revolve(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1), 360)
    elif mode == "Extrude":
        # Extrude along Z direction
        shape = shape.extrude(FreeCAD.Vector(0, 0, 10))
    # else "Wire" - keep as wire
    
    base_label = f"Contoured_{subname}" if subname else "Contoured_Hub"
    feat = doc.addObject("Part::Feature", base_label)
    feat.Shape = shape
    feat.Label = base_label
    doc.recompute()
    
    return feat



