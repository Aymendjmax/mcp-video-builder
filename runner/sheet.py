#!/usr/bin/env python3
"""Contact sheet: sheet.py OUT.jpg COLS CELL_W  FRAME.jpg[:label] ...  -> one JPEG grid with a timestamp label on every cell."""
import sys
from PIL import Image, ImageDraw, ImageFont

def font(sz):
    for p in ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

def make(out, cols, cell_w, items, quality=78):
    ims = []
    for it in items:
        path, _, label = it.partition("|")
        im = Image.open(path).convert("RGB"); r = cell_w / im.width
        ims.append((im.resize((cell_w, max(1, int(im.height * r)))), label))
    if not ims: raise SystemExit("no frames")
    ch = max(i.height for i, _ in ims); rows = (len(ims) + cols - 1) // cols; gap = 4
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * gap, rows * ch + (rows + 1) * gap), (24, 24, 28))
    d = ImageDraw.Draw(sheet); f = font(max(12, cell_w // 22))
    for n, (im, label) in enumerate(ims):
        x = gap + (n % cols) * (cell_w + gap); y = gap + (n // cols) * (ch + gap)
        sheet.paste(im, (x, y))
        if label:
            w = d.textlength(label, font=f) + 10; d.rectangle([x, y, x + w, y + f.size + 8], fill=(0, 0, 0)); d.text((x + 5, y + 3), label, fill=(255, 255, 255), font=f)
    sheet.save(out, "JPEG", quality=quality)

if __name__ == "__main__":
    out, cols, w = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    make(out, cols, w, sys.argv[4:]); print(out)
