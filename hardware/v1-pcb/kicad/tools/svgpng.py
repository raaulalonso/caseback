"""svgpng.py in.svg out.png [width_px] [x0,y0,x1,y1 in mm of the svg]

Render an SVG (optionally a window of it) to PNG with PyMuPDF (pip install pymupdf).
"""
import sys

import pymupdf as fitz

src, dst = sys.argv[1], sys.argv[2]
w = float(sys.argv[3]) if len(sys.argv) > 3 else 1400
doc = fitz.open(src)
page = doc[0]
clip = None
if len(sys.argv) > 4:
    k = 72 / 25.4
    x0, y0, x1, y1 = (float(v) * k for v in sys.argv[4].split(","))
    clip = fitz.Rect(x0, y0, x1, y1)
width = clip.width if clip else page.rect.width
z = w / width
pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, alpha=False)
pix.save(dst)
