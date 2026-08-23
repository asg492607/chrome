# Browser Engine

The Browser Engine module simulates a modern web browser's rendering pipeline.

## Pipeline
1. **Parsing**: `html_parser.py` builds the DOM, `css_parser.py` extracts rules.
2. **Styling**: `style_engine.py` manages defaults, `cascade_engine.py` resolves specific layers to compute styles.
3. **Layout**: `layout_engine.py` loops over the DOM to generate bounding boxes.
4. **Rendering**: `render_engine.py` translates boxes to primitives for drawing.
