"""
HubContour – contouring/functions.py
Exact Python port of the web backend contourService.js contouring functions.
All formulas match 1-to-1; same input → same output.
"""

import math
import hashlib
import json


# ── Skewed-sine bump ──────────────────────────────────────────────────────────

def skewed_sine_bump(axial, le, te, amplitude, peak_pos):
    """
    Skewed sine bump between le..te.
    Matches JS: amplitude * Math.pow(Math.sin(Math.PI * Math.pow(t, s)), 2)
    """
    if not (0 < peak_pos < 1):
        raise ValueError("peak_pos must be strictly between 0 and 1")

    eps  = 1e-12
    s    = math.log(0.5) / math.log(peak_pos)
    bump = []
    for x in axial:
        if le <= x <= te:
            t = (x - le) / (te - le + eps)
            bump.append(amplitude * (math.sin(math.pi * (t ** s)) ** 2))
        else:
            bump.append(0.0)
    return bump


# ── Hicks-Henne bump ──────────────────────────────────────────────────────────

def hicks_henne_bump(axial, le, te, amplitude, peak_loc, width):
    """
    Classic Hicks-Henne bump.
    Matches JS: amplitude * Math.pow(Math.sin(Math.PI * Math.pow(t, p1)), width)
    """
    if not (0 < peak_loc < 1):
        raise ValueError("peak_loc must be strictly between 0 and 1")

    eps  = 1e-12
    p1   = math.log(0.5) / math.log(peak_loc)
    bump = []
    for x in axial:
        if le <= x <= te:
            t = (x - le) / (te - le + eps)
            bump.append(amplitude * (math.sin(math.pi * (t ** p1)) ** width))
        else:
            bump.append(0.0)
    return bump


# ── Cubic-spline contour ──────────────────────────────────────────────────────

def cubic_spline_contour(axial, radial, le, te, control_points):
    """
    Natural cubic spline interpolation through control_points.
    control_points: list of {'x': float, 'delta': float}
    Matches JS cubicSplineContour exactly.
    """
    pts = sorted(control_points, key=lambda p: p['x'])
    n   = len(pts)
    if n < 2:
        return list(radial)

    x_vals = [p['x']     for p in pts]
    y_vals = [p['delta'] for p in pts]

    h     = [x_vals[i+1] - x_vals[i] for i in range(n-1)]
    alpha = [0.0] * n
    for i in range(1, n-1):
        alpha[i] = ((3.0/h[i])   * (y_vals[i+1] - y_vals[i])
                  - (3.0/h[i-1]) * (y_vals[i]   - y_vals[i-1]))

    l  = [1.0] * n
    mu = [0.0] * n
    z  = [0.0] * n
    for i in range(1, n-1):
        l[i]  = 2.0*(x_vals[i+1] - x_vals[i-1]) - h[i-1]*mu[i-1]
        mu[i] = h[i] / l[i]
        z[i]  = (alpha[i] - h[i-1]*z[i-1]) / l[i]

    c = [0.0] * n
    b = [0.0] * (n-1)
    d = [0.0] * (n-1)
    for i in range(n-2, -1, -1):
        c[i] = z[i] - mu[i]*c[i+1]
        b[i] = ((y_vals[i+1] - y_vals[i]) / h[i]
                - h[i]*(c[i+1] + 2.0*c[i]) / 3.0)
        d[i] = (c[i+1] - c[i]) / (3.0*h[i])

    delta = [0.0] * len(axial)
    for i, x in enumerate(axial):
        if le <= x <= te:
            for j in range(n-1):
                if x_vals[j] <= x <= x_vals[j+1]:
                    dx       = x - x_vals[j]
                    delta[i] = (y_vals[j]
                                + b[j]*dx
                                + c[j]*dx*dx
                                + d[j]*dx*dx*dx)
                    break

    return [r + delta[i] for i, r in enumerate(radial)]


# ── Bezier contour ────────────────────────────────────────────────────────────

def _factorial(n):
    result = 1
    for i in range(2, n+1):
        result *= i
    return result


def _binom(n, k):
    return _factorial(n) // (_factorial(k) * _factorial(n-k))


def bezier_contour(axial, radial, le, te, control_points):
    """
    Bernstein-polynomial Bezier curve.
    control_points: list of {'x': float, 'delta': float}
    Matches JS bezierContour exactly (including t-based sampling).
    """
    pts = [(p['x'], p['delta']) for p in control_points]
    n   = len(pts) - 1
    if n < 2:
        raise ValueError("Need at least 3 control points for Bezier")

    eps = 1e-12

    def bezier_at_t(t):
        rx = ry = 0.0
        for i, (px, py) in enumerate(pts):
            bern = _binom(n, i) * (t**i) * ((1-t)**(n-i))
            rx  += bern * px
            ry  += bern * py
        return rx, ry

    delta = []
    for x in axial:
        if le <= x <= te:
            t = (x - le) / (te - le + eps)
            _, dy = bezier_at_t(t)
            delta.append(dy)
        else:
            delta.append(0.0)

    return [r + delta[i] for i, r in enumerate(radial)]


# ── B-Spline contour ──────────────────────────────────────────────────────────

def _basis(i, k, t, knots):
    """Recursive Cox–de Boor basis function. Matches JS basis() exactly."""
    if k == 0:
        return 1.0 if (knots[i] <= t < knots[i+1]) else 0.0
    left = right = 0.0
    d1 = knots[i+k]   - knots[i]
    d2 = knots[i+k+1] - knots[i+1]
    if d1:
        left  = ((t - knots[i])        / d1) * _basis(i,   k-1, t, knots)
    if d2:
        right = ((knots[i+k+1] - t)    / d2) * _basis(i+1, k-1, t, knots)
    return left + right


def bspline_contour(axial, radial, le, te, control_points, degree=3):
    """
    Clamped uniform B-spline.
    control_points: list of {'x': float, 'delta': float}
    Matches JS bsplineContour exactly.
    """
    pts    = [p['delta'] for p in control_points]
    n_ctrl = len(pts)
    if n_ctrl < degree + 1:
        raise ValueError(f"Need at least {degree+1} control points for degree {degree} B-spline")

    n_knots = n_ctrl + degree + 1
    knots   = []
    for i in range(n_knots):
        if   i < degree:    knots.append(0.0)
        elif i > n_ctrl:    knots.append(1.0)
        else:               knots.append((i - degree) / (n_ctrl - degree))

    eps = 1e-12
    delta = []
    for x in axial:
        if le <= x <= te:
            u = max(0.0, min(1.0, (x - le) / (te - le + eps)))
            # Clamp just below 1 so the last basis segment triggers
            if u >= 1.0:
                u = 1.0 - eps
            val = sum(pts[j] * _basis(j, degree, u, knots) for j in range(n_ctrl))
            delta.append(val)
        else:
            delta.append(0.0)

    return [r + delta[i] for i, r in enumerate(radial)]


# ── Dispatcher ────────────────────────────────────────────────────────────────

def apply_contour(axial, radial, le, te, method, kwargs):
    """
    Apply the named contouring method and return a new radial array.

    method : 'sine' | 'hicks' | 'cubic' | 'bezier' | 'bspline'
    kwargs : dict matching each method's parameters (same keys as JS)
    """
    if method == 'sine':
        bump = skewed_sine_bump(axial, le, te,
                                kwargs['amplitude'], kwargs['peakPos'])
        return [r + bump[i] for i, r in enumerate(radial)]

    elif method == 'hicks':
        bump = hicks_henne_bump(axial, le, te,
                                kwargs['amplitude'],
                                kwargs['peakLoc'],
                                kwargs['width'])
        return [r + bump[i] for i, r in enumerate(radial)]

    elif method == 'cubic':
        return cubic_spline_contour(axial, radial, le, te, kwargs['controlPoints'])

    elif method == 'bezier':
        return bezier_contour(axial, radial, le, te, kwargs['controlPoints'])

    elif method == 'bspline':
        return bspline_contour(axial, radial, le, te,
                               kwargs['controlPoints'],
                               kwargs.get('degree', 3))

    else:
        raise ValueError(f"Unknown contouring method: '{method}'")


# ── Hash ──────────────────────────────────────────────────────────────────────

def generate_contour_hash(method, le, te, kwargs):
    """
    MD5 hash of (method, le, te, kwargs) — first 6 hex chars.
    Matches JS generateContourHash exactly.
    """
    param_str = f"{method}_{le:.2f}_{te:.2f}_{json.dumps(kwargs, sort_keys=True)}"
    return hashlib.md5(param_str.encode()).hexdigest()[:6]









# """
# HubContour – contouring/functions.py
# Exact Python port of the web backend contourService.js contouring functions.
# All formulas match 1-to-1; same input → same output.
# ADDED: Absolute mode for Bezier and B-spline (control points define actual curve)
# """

# import math
# import hashlib
# import json


# # ── Skewed-sine bump ──────────────────────────────────────────────────────────

# def skewed_sine_bump(axial, le, te, amplitude, peak_pos):
#     """
#     Skewed sine bump between le..te.
#     Matches JS: amplitude * Math.pow(Math.sin(Math.PI * Math.pow(t, s)), 2)
#     """
#     if not (0 < peak_pos < 1):
#         raise ValueError("peak_pos must be strictly between 0 and 1")

#     eps  = 1e-12
#     s    = math.log(0.5) / math.log(peak_pos)
#     bump = []
#     for x in axial:
#         if le <= x <= te:
#             t = (x - le) / (te - le + eps)
#             bump.append(amplitude * (math.sin(math.pi * (t ** s)) ** 2))
#         else:
#             bump.append(0.0)
#     return bump


# # ── Hicks-Henne bump ──────────────────────────────────────────────────────────

# def hicks_henne_bump(axial, le, te, amplitude, peak_loc, width):
#     """
#     Classic Hicks-Henne bump.
#     Matches JS: amplitude * Math.pow(Math.sin(Math.PI * Math.pow(t, p1)), width)
#     """
#     if not (0 < peak_loc < 1):
#         raise ValueError("peak_loc must be strictly between 0 and 1")

#     eps  = 1e-12
#     p1   = math.log(0.5) / math.log(peak_loc)
#     bump = []
#     for x in axial:
#         if le <= x <= te:
#             t = (x - le) / (te - le + eps)
#             bump.append(amplitude * (math.sin(math.pi * (t ** p1)) ** width))
#         else:
#             bump.append(0.0)
#     return bump


# # ── Cubic-spline contour ──────────────────────────────────────────────────────

# def cubic_spline_contour(axial, radial, le, te, control_points):
#     """
#     Natural cubic spline interpolation through control_points.
#     control_points: list of {'x': float, 'delta': float}
#     Matches JS cubicSplineContour exactly.
#     """
#     pts = sorted(control_points, key=lambda p: p['x'])
#     n   = len(pts)
#     if n < 2:
#         return list(radial)

#     x_vals = [p['x']     for p in pts]
#     y_vals = [p['delta'] for p in pts]

#     h     = [x_vals[i+1] - x_vals[i] for i in range(n-1)]
#     alpha = [0.0] * n
#     for i in range(1, n-1):
#         alpha[i] = ((3.0/h[i])   * (y_vals[i+1] - y_vals[i])
#                   - (3.0/h[i-1]) * (y_vals[i]   - y_vals[i-1]))

#     l  = [1.0] * n
#     mu = [0.0] * n
#     z  = [0.0] * n
#     for i in range(1, n-1):
#         l[i]  = 2.0*(x_vals[i+1] - x_vals[i-1]) - h[i-1]*mu[i-1]
#         mu[i] = h[i] / l[i]
#         z[i]  = (alpha[i] - h[i-1]*z[i-1]) / l[i]

#     c = [0.0] * n
#     b = [0.0] * (n-1)
#     d = [0.0] * (n-1)
#     for i in range(n-2, -1, -1):
#         c[i] = z[i] - mu[i]*c[i+1]
#         b[i] = ((y_vals[i+1] - y_vals[i]) / h[i]
#                 - h[i]*(c[i+1] + 2.0*c[i]) / 3.0)
#         d[i] = (c[i+1] - c[i]) / (3.0*h[i])

#     delta = [0.0] * len(axial)
#     for i, x in enumerate(axial):
#         if le <= x <= te:
#             for j in range(n-1):
#                 if x_vals[j] <= x <= x_vals[j+1]:
#                     dx       = x - x_vals[j]
#                     delta[i] = (y_vals[j]
#                                 + b[j]*dx
#                                 + c[j]*dx*dx
#                                 + d[j]*dx*dx*dx)
#                     break

#     return [r + delta[i] for i, r in enumerate(radial)]


# # ── Bezier contour ────────────────────────────────────────────────────────────

# def _factorial(n):
#     result = 1
#     for i in range(2, n+1):
#         result *= i
#     return result


# def _binom(n, k):
#     return _factorial(n) // (_factorial(k) * _factorial(n-k))


# def bezier_contour(axial, radial, le, te, control_points):
#     """
#     Bernstein-polynomial Bezier curve (DELTA mode).
#     control_points: list of {'x': float, 'delta': float}
#     Matches JS bezierContour exactly.
#     """
#     pts = [(p['x'], p['delta']) for p in control_points]
#     n   = len(pts) - 1
#     if n < 2:
#         raise ValueError("Need at least 3 control points for Bezier")

#     eps = 1e-12

#     def bezier_at_t(t):
#         rx = ry = 0.0
#         for i, (px, py) in enumerate(pts):
#             bern = _binom(n, i) * (t**i) * ((1-t)**(n-i))
#             rx  += bern * px
#             ry  += bern * py
#         return rx, ry

#     delta = []
#     for x in axial:
#         if le <= x <= te:
#             t = (x - le) / (te - le + eps)
#             _, dy = bezier_at_t(t)
#             delta.append(dy)
#         else:
#             delta.append(0.0)

#     return [r + delta[i] for i, r in enumerate(radial)]


# # ── Absolute Bezier contour (uses actual Z,R control points) ─────────────────

# def bezier_contour_absolute(axial, le, te, control_points):
#     """
#     Bezier curve using absolute control points (Z, R).
#     control_points: list of {'Z': float, 'R': float}
#     """
#     pts = sorted(control_points, key=lambda p: p['Z'])
#     n = len(pts) - 1
#     if n < 2:
#         raise ValueError("Need at least 3 control points for Bezier")
    
#     # Get min/max Z from control points
#     z_min = pts[0]['Z']
#     z_max = pts[-1]['Z']
    
#     # Normalize control point Z to t (0-1 range)
#     t_vals = [(p['Z'] - z_min) / (z_max - z_min) for p in pts]
#     r_vals = [p['R'] for p in pts]
    
#     def bezier_at_t(t):
#         rx = ry = 0.0
#         for i in range(n + 1):
#             bern = _binom(n, i) * (t**i) * ((1-t)**(n-i))
#             rx += bern * t_vals[i]
#             ry += bern * r_vals[i]
#         return rx, ry
    
#     result = []
#     eps = 1e-12
#     for x in axial:
#         if le <= x <= te:
#             # Map x to t within LE-TE range
#             t = (x - le) / (te - le + eps)
#             # Find corresponding R on Bezier
#             _, r_val = bezier_at_t(t)
#             result.append(r_val)
#         else:
#             result.append(0)
    
#     return result


# # ── B-Spline contour ──────────────────────────────────────────────────────────

# def _basis(i, k, t, knots):
#     """Recursive Cox–de Boor basis function. Matches JS basis() exactly."""
#     if k == 0:
#         return 1.0 if (knots[i] <= t < knots[i+1]) else 0.0
#     left = right = 0.0
#     d1 = knots[i+k]   - knots[i]
#     d2 = knots[i+k+1] - knots[i+1]
#     if d1:
#         left  = ((t - knots[i])        / d1) * _basis(i,   k-1, t, knots)
#     if d2:
#         right = ((knots[i+k+1] - t)    / d2) * _basis(i+1, k-1, t, knots)
#     return left + right


# def bspline_contour(axial, radial, le, te, control_points, degree=3):
#     """
#     Clamped uniform B-spline (DELTA mode).
#     control_points: list of {'x': float, 'delta': float}
#     Matches JS bsplineContour exactly.
#     """
#     pts    = [p['delta'] for p in control_points]
#     n_ctrl = len(pts)
#     if n_ctrl < degree + 1:
#         raise ValueError(f"Need at least {degree+1} control points for degree {degree} B-spline")

#     n_knots = n_ctrl + degree + 1
#     knots   = []
#     for i in range(n_knots):
#         if   i < degree:    knots.append(0.0)
#         elif i > n_ctrl:    knots.append(1.0)
#         else:               knots.append((i - degree) / (n_ctrl - degree))

#     eps = 1e-12
#     delta = []
#     for x in axial:
#         if le <= x <= te:
#             u = max(0.0, min(1.0, (x - le) / (te - le + eps)))
#             if u >= 1.0:
#                 u = 1.0 - eps
#             val = sum(pts[j] * _basis(j, degree, u, knots) for j in range(n_ctrl))
#             delta.append(val)
#         else:
#             delta.append(0.0)

#     return [r + delta[i] for i, r in enumerate(radial)]


# # ── Absolute B-Spline contour (uses actual Z,R control points) ───────────────

# def bspline_contour_absolute(axial, le, te, control_points, degree=3):
#     """
#     B-Spline curve using absolute control points (Z, R).
#     control_points: list of {'Z': float, 'R': float}
#     """
#     pts = sorted(control_points, key=lambda p: p['Z'])
#     n_ctrl = len(pts)
#     if n_ctrl < degree + 1:
#         raise ValueError(f"Need at least {degree+1} control points for degree {degree} B-spline")
    
#     # Get min/max Z from control points
#     z_min = pts[0]['Z']
#     z_max = pts[-1]['Z']
    
#     # Normalize control point Z to u (0-1 range)
#     u_vals = [(p['Z'] - z_min) / (z_max - z_min) for p in pts]
#     r_vals = [p['R'] for p in pts]
    
#     # Create knot vector (clamped)
#     n_knots = n_ctrl + degree + 1
#     knots = []
#     for i in range(n_knots):
#         if i < degree:
#             knots.append(0.0)
#         elif i > n_ctrl:
#             knots.append(1.0)
#         else:
#             knots.append((i - degree) / (n_ctrl - degree))
    
#     def bspline_at_u(u):
#         val = 0.0
#         for j in range(n_ctrl):
#             b = _basis(j, degree, u, knots)
#             val += r_vals[j] * b
#         return val
    
#     result = []
#     eps = 1e-12
#     for x in axial:
#         if le <= x <= te:
#             u = max(0.0, min(1.0, (x - le) / (te - le + eps)))
#             if u >= 1.0:
#                 u = 1.0 - eps
#             r_val = bspline_at_u(u)
#             result.append(r_val)
#         else:
#             result.append(0)
    
#     return result


# # ── Dispatcher ────────────────────────────────────────────────────────────────

# def apply_contour(axial, radial, le, te, method, kwargs, mode='delta'):
#     """
#     Apply the named contouring method and return a new radial array.
    
#     method : 'sine' | 'hicks' | 'cubic' | 'bezier' | 'bspline'
#     kwargs : dict matching each method's parameters
#     mode : 'delta' (deformation relative to baseline) or 'absolute' (direct curve)
#     """
#     # Safety check
#     if abs(te - le) < 1e-12:
#         return list(radial)
    
#     if method == 'sine':
#         bump = skewed_sine_bump(axial, le, te,
#                                 kwargs['amplitude'], kwargs['peakPos'])
#         return [r + bump[i] for i, r in enumerate(radial)]
    
#     elif method == 'hicks':
#         bump = hicks_henne_bump(axial, le, te,
#                                 kwargs['amplitude'],
#                                 kwargs['peakLoc'],
#                                 kwargs['width'])
#         return [r + bump[i] for i, r in enumerate(radial)]
    
#     elif method == 'cubic':
#         # Cubic spline always uses delta mode
#         return cubic_spline_contour(axial, radial, le, te, kwargs['controlPoints'])
    
#     elif method == 'bezier':
#         if mode == 'absolute':
#             delta_vals = bezier_contour_absolute(axial, le, te, kwargs['controlPoints'])
#             return [r + delta_vals[i] for i, r in enumerate(radial)]
#         else:
#             return bezier_contour(axial, radial, le, te, kwargs['controlPoints'])
    
#     elif method == 'bspline':
#         if mode == 'absolute':
#             delta_vals = bspline_contour_absolute(axial, le, te, kwargs['controlPoints'],
#                                                    kwargs.get('degree', 3))
#             return [r + delta_vals[i] for i, r in enumerate(radial)]
#         else:
#             return bspline_contour(axial, radial, le, te,
#                                    kwargs['controlPoints'],
#                                    kwargs.get('degree', 3))
    
#     else:
#         raise ValueError(f"Unknown contouring method: '{method}'")


# # ── Hash ──────────────────────────────────────────────────────────────────────

# def generate_contour_hash(method, le, te, kwargs):
#     """
#     MD5 hash of (method, le, te, kwargs) — first 6 hex chars.
#     Matches JS generateContourHash exactly.
#     """
#     param_str = f"{method}_{le:.2f}_{te:.2f}_{json.dumps(kwargs, sort_keys=True)}"
#     return hashlib.md5(param_str.encode()).hexdigest()[:6]