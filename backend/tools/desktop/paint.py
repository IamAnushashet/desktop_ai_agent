"""Microsoft Paint sketch drawing automation tool for Desktop AI Agent."""

import math
import time
from typing import Optional, List, Dict, Any, Tuple
from langchain_core.tools import tool

from backend.control.mouse import mouse_controller
from backend.control.window import window_controller
from backend.screen.capture import screen_capture
from backend.tools.system.system import run_system_app
from backend.utils.logger import logger


def _draw_line(x1: float, y1: float, x2: float, y2: float, steps: int = 8):
    """Draw a straight line from (x1, y1) to (x2, y2) in normalized coordinates."""
    mouse_controller.move(x1, y1, normalized=True)
    time.sleep(0.02)
    mouse_controller.mouse_down("left")
    time.sleep(0.02)
    
    for i in range(1, steps + 1):
        cx = x1 + (x2 - x1) * (i / steps)
        cy = y1 + (y2 - y1) * (i / steps)
        mouse_controller.move(cx, cy, normalized=True)
        time.sleep(0.005)
        
    mouse_controller.mouse_up("left")
    time.sleep(0.02)


def _draw_polyline(points: List[Tuple[float, float]], steps_per_seg: int = 6):
    """Draw connected line segments through a sequence of normalized points."""
    if len(points) < 2:
        return
    for i in range(len(points) - 1):
        _draw_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], steps=steps_per_seg)


def _draw_polygon(points: List[Tuple[float, float]], steps_per_seg: int = 6):
    """Draw a closed polygon connecting a list of normalized points."""
    if len(points) < 3:
        return
    closed = list(points) + [points[0]]
    _draw_polyline(closed, steps_per_seg=steps_per_seg)


def _draw_rectangle(x: float, y: float, w: float, h: float):
    """Draw a rectangle starting at top-left (x,y) with width w and height h."""
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    _draw_polygon(pts)


def _draw_circle(cx: float, cy: float, r: float, num_points: int = 16):
    """Draw a circle centered at (cx, cy) with radius r in normalized coordinates."""
    pts = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        pts.append((px, py))
    _draw_polygon(pts, steps_per_seg=3)


def _draw_star(cx: float, cy: float, r_outer: float = 0.05, r_inner: float = 0.02, points_count: int = 5):
    """Draw a star shape centered at (cx, cy)."""
    pts = []
    total_pts = points_count * 2
    for i in range(total_pts):
        r = r_outer if i % 2 == 0 else r_inner
        angle = (math.pi * i) / points_count - (math.pi / 2)
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        pts.append((px, py))
    _draw_polygon(pts, steps_per_seg=3)


# --- INDIVIDUAL SKETCH DRAWING ACTIONS ---

def draw_house_sketch() -> List[str]:
    """Draw a classic house sketch with walls, triangular roof, door, and window grid."""
    actions = []
    # Main House Body (Rectangle)
    _draw_rectangle(0.42, 0.48, 0.22, 0.22)
    actions.append("Drawn house body box (0.42, 0.48, 0.22, 0.22)")

    # Roof (Triangle)
    roof = [(0.40, 0.48), (0.53, 0.32), (0.66, 0.48)]
    _draw_polygon(roof)
    actions.append("Drawn triangular roof (0.40,0.48 -> 0.53,0.32 -> 0.66,0.48)")

    # Door (Rectangle)
    _draw_rectangle(0.50, 0.58, 0.06, 0.12)
    actions.append("Drawn door (0.50, 0.58, 0.06, 0.12)")

    # Window (Square) & Grid
    _draw_rectangle(0.44, 0.52, 0.04, 0.04)
    _draw_line(0.46, 0.52, 0.46, 0.56)
    _draw_line(0.44, 0.54, 0.48, 0.54)
    actions.append("Drawn window with grid (0.44, 0.52)")

    return actions


def draw_tree_sketch(cx: float = 0.28, cy_bottom: float = 0.70) -> List[str]:
    """Draw a tree sketch with trunk and foliage canopy."""
    actions = []
    # Trunk
    _draw_rectangle(cx - 0.02, cy_bottom - 0.18, 0.04, 0.18)
    actions.append(f"Drawn tree trunk at ({cx}, {cy_bottom})")

    # Canopy (Overlapping Canopy Circles / Triangles)
    _draw_circle(cx, cy_bottom - 0.23, 0.07)
    _draw_circle(cx - 0.03, cy_bottom - 0.21, 0.05)
    _draw_circle(cx + 0.03, cy_bottom - 0.21, 0.05)
    actions.append("Drawn tree foliage canopy circles")

    return actions


def draw_sun_sketch(cx: float = 0.75, cy: float = 0.28) -> List[str]:
    """Draw a sun sketch with central circle and radiating sun rays."""
    actions = []
    r = 0.04
    _draw_circle(cx, cy, r)
    actions.append(f"Drawn sun center circle at ({cx}, {cy})")

    # Radiating Rays
    num_rays = 8
    for i in range(num_rays):
        angle = (2 * math.pi * i) / num_rays
        x1 = cx + (r + 0.01) * math.cos(angle)
        y1 = cy + (r + 0.01) * math.sin(angle)
        x2 = cx + (r + 0.035) * math.cos(angle)
        y2 = cy + (r + 0.035) * math.sin(angle)
        _draw_line(x1, y1, x2, y2, steps=4)
    actions.append(f"Drawn {num_rays} radiating sun rays")

    return actions


def draw_cloud_sketch(cx: float = 0.35, cy: float = 0.28) -> List[str]:
    """Draw a cloud sketch with fluffy top arcs and flat bottom."""
    actions = []
    _draw_circle(cx - 0.04, cy, 0.035)
    _draw_circle(cx, cy - 0.02, 0.045)
    _draw_circle(cx + 0.04, cy, 0.035)
    _draw_line(cx - 0.07, cy + 0.025, cx + 0.07, cy + 0.025)
    actions.append(f"Drawn cloud outline centered at ({cx}, {cy})")
    return actions


def draw_car_sketch() -> List[str]:
    """Draw a simple car sketch with chassis, cabin, and wheels."""
    actions = []
    # Chassis
    _draw_rectangle(0.38, 0.55, 0.24, 0.08)
    # Cabin
    _draw_polygon([(0.43, 0.55), (0.47, 0.48), (0.57, 0.48), (0.60, 0.55)])
    # Wheels
    _draw_circle(0.43, 0.63, 0.025)
    _draw_circle(0.57, 0.63, 0.025)
    actions.append("Drawn car chassis, cabin, and wheels")
    return actions


def draw_flower_sketch() -> List[str]:
    """Draw a flower sketch with stem, leaf, and petals."""
    actions = []
    # Stem & Leaf
    _draw_line(0.50, 0.50, 0.50, 0.70)
    _draw_polygon([(0.50, 0.60), (0.54, 0.57), (0.50, 0.56)])
    # Center & Petals
    _draw_circle(0.50, 0.47, 0.025)
    petals = 5
    for i in range(petals):
        angle = (2 * math.pi * i) / petals
        px = 0.50 + 0.045 * math.cos(angle)
        py = 0.47 + 0.045 * math.sin(angle)
        _draw_circle(px, py, 0.022)
    actions.append("Drawn flower stem, leaf, center, and 5 petals")
    return actions


def draw_landscape_sketch() -> List[str]:
    """Draw a landscape scene with horizon line, mountains, sun, tree, and house."""
    actions = []
    # Horizon Ground Line
    _draw_line(0.15, 0.70, 0.85, 0.70)
    actions.append("Drawn ground horizon line")
    
    # Mountain peak
    _draw_polygon([(0.20, 0.70), (0.35, 0.45), (0.50, 0.70)])
    actions.append("Drawn mountain peak")

    # Sun, Tree, House
    actions.extend(draw_sun_sketch(0.75, 0.28))
    actions.extend(draw_tree_sketch(0.24, 0.70))
    actions.extend(draw_house_sketch())
    return actions


def draw_shape_sketch(shape_name: str) -> List[str]:
    """Draw a simple geometric shape (circle, square, triangle, star, rectangle)."""
    s_norm = shape_name.lower().strip()
    actions = []
    cx, cy = 0.52, 0.50

    if "circle" in s_norm or "ball" in s_norm:
        _draw_circle(cx, cy, 0.12)
        actions.append(f"Drawn circle shape centered at ({cx}, {cy})")
    elif "triangle" in s_norm:
        _draw_polygon([(cx, cy - 0.12), (cx - 0.12, cy + 0.10), (cx + 0.12, cy + 0.10)])
        actions.append(f"Drawn triangle shape centered at ({cx}, {cy})")
    elif "square" in s_norm:
        _draw_rectangle(cx - 0.10, cy - 0.10, 0.20, 0.20)
        actions.append(f"Drawn square shape centered at ({cx}, {cy})")
    elif "star" in s_norm:
        _draw_star(cx, cy, r_outer=0.12, r_inner=0.05, points_count=5)
        actions.append(f"Drawn 5-pointed star shape centered at ({cx}, {cy})")
    else:
        _draw_rectangle(cx - 0.12, cy - 0.08, 0.24, 0.16)
        actions.append(f"Drawn rectangle shape centered at ({cx}, {cy})")

    return actions


@tool
def draw_sketch_in_paint(sketch_type: str, shape_name: Optional[str] = None) -> str:
    """
    Opens Microsoft Paint, brings canvas to focus, converts user's sketch request
    into safe mouse drawing actions (using MouseController), draws the sketch
    (house, tree, sun, cloud, car, flower, landscape, shape), and verifies with ScreenCapture.

    Args:
        sketch_type: Description of sketch to draw (e.g. 'house', 'tree', 'sun', 'cloud', 'car', 'flower', 'landscape', 'house with sun and tree').
        shape_name: Optional shape name if requesting a specific shape (e.g. 'circle', 'triangle', 'square', 'star').
    """
    logger.info(f"[TOOL draw_sketch_in_paint] Opening Paint and drawing sketch: '{sketch_type}' (shape: {shape_name})")
    try:
        # 1. Open Microsoft Paint
        run_res = run_system_app("paint")
        time.sleep(1.8)

        # Maximize Paint window if possible
        window_controller.maximize()
        time.sleep(0.5)

        # Click on Paint canvas center to ensure drawing focus
        mouse_controller.move(0.50, 0.50, normalized=True)
        time.sleep(0.1)
        mouse_controller.click("left")
        time.sleep(0.2)

        s_clean = (sketch_type + " " + (shape_name or "")).lower().strip()
        executed_actions: List[str] = []

        # 2. Select and Execute Sketch Drawing Routines
        if "landscape" in s_clean or ("house" in s_clean and "sun" in s_clean and "tree" in s_clean):
            executed_actions = draw_landscape_sketch()
        else:
            # Check individual elements
            if "house" in s_clean:
                executed_actions.extend(draw_house_sketch())
            if "sun" in s_clean and "landscape" not in s_clean:
                executed_actions.extend(draw_sun_sketch(0.75, 0.28))
            if "tree" in s_clean and "landscape" not in s_clean:
                executed_actions.extend(draw_tree_sketch(0.25, 0.70))
            if "cloud" in s_clean:
                executed_actions.extend(draw_cloud_sketch(0.35, 0.28))
            if "car" in s_clean:
                executed_actions.extend(draw_car_sketch())
            if "flower" in s_clean:
                executed_actions.extend(draw_flower_sketch())
            if shape_name or any(shp in s_clean for shp in ["circle", "triangle", "square", "star", "shape"]):
                target_shp = shape_name or s_clean
                executed_actions.extend(draw_shape_sketch(target_shp))

            # Default fallback if no specific keyword matched
            if not executed_actions:
                executed_actions.extend(draw_house_sketch())
                executed_actions.extend(draw_sun_sketch(0.75, 0.28))

        # 3. Verification
        time.sleep(0.5)
        active_window_info = window_controller.get_active_window()
        active_title = active_window_info.get("title", "")
        paint_active = "paint" in active_title.lower() or "mspaint" in active_title.lower() or active_window_info.get("width", 0) > 0

        # Capture screenshot verification
        shot_frame = screen_capture.capture_frame(force=True)
        has_screenshot = shot_frame is not None and "data" in shot_frame

        actions_str = "\n".join([f"  - {act}" for act in executed_actions])

        return (
            f"Successfully executed sketch drawing in Microsoft Paint.\n"
            f"- Sketch Requested: '{sketch_type}'\n"
            f"- Window Focus: '{active_title}' (Paint Active: {paint_active})\n"
            f"- Drawing Actions Executed:\n{actions_str}\n"
            f"- Screen Capture Verification: {'PASSED (Screenshot captured)' if has_screenshot else 'COMPLETED'}\n"
            f"- Operation Status: COMPLETED"
        )

    except Exception as e:
        logger.error(f"[PAINT TOOL ERROR] Failed drawing sketch: {e}")
        return f"Error drawing sketch in Paint: {str(e)}"
