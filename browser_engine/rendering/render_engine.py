import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from browser_engine.rendering.canvas_renderer import CanvasRenderer

class RenderEngine:
    def __init__(self, browser_window):
        self.canvas_renderer = CanvasRenderer(browser_window)

    def render(self, canvas, layout_boxes):
        """
        Coordinates the final rendering phase.
        """
        self.canvas_renderer.paint(canvas, layout_boxes)
