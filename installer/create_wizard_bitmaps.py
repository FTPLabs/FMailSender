"""
Generates Inno Setup wizard images with Aether Dark branding.
  wizard_sidebar.bmp  164x314 -- left image on Welcome/Finish pages
  wizard_header.bmp    55x58 -- top-right logo on inner pages
Usage: python installer/create_wizard_bitmaps.py [version]
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT     = Path(__file__).parent
VERSION = sys.argv[1] if len(sys.argv) > 1 else '2.0.0'

BG_BASE = (7,   7,  17)
ACCENT  = (139, 92, 246)
CTA     = (236, 72, 153)
TP      = (240, 240, 250)
TS      = (144, 144, 192)


def grad(draw, x0, y0, x1, y1, c1, c2, vert=True):
    n = (y1 - y0) if vert else (x1 - x0)
    for i in range(max(n, 1)):
        t = i / max(n - 1, 1)
        rgb = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
        if vert:
            draw.line([(x0, y0 + i), (x1, y0 + i)], fill=rgb)
        else:
            draw.line([(x0 + i, y0), (x0 + i, y1)], fill=rgb)


def get_font(size):
    for name in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def make_sidebar():
    W, H = 164, 314
    img  = Image.new('RGB', (W, H), BG_BASE)
    d    = ImageDraw.Draw(img)
    grad(d, 0, 0, W, H, ACCENT, CTA, vert=True)
    tint = Image.new('RGB', (W, H), BG_BASE)
    img  = Image.blend(img, tint, alpha=0.45)
    d    = ImageDraw.Draw(img)
    ex, ey, ew, eh = 52, 85, 60, 40
    d.rectangle([ex, ey, ex + ew, ey + eh], outline=TP, width=2)
    d.line([(ex, ey), (ex + ew // 2, ey + eh // 2), (ex + ew, ey)], fill=TP, width=2)
    fb, fs = get_font(15), get_font(10)
    d.text((W // 2, ey + eh + 18), 'Email Sender Pro', font=fb, fill=TP, anchor='mm')
    d.text((W // 2, ey + eh + 38), 'by FTPLabs',       font=fs, fill=TS, anchor='mm')
    d.text((W // 2, H - 16),       f'v{VERSION}',      font=fs, fill=TS, anchor='mm')
    img.save(OUT / 'wizard_sidebar.bmp', 'BMP')
    print('wizard_sidebar.bmp  164x314  OK')


def make_header():
    W, H = 55, 58
    img  = Image.new('RGB', (W, H), BG_BASE)
    d    = ImageDraw.Draw(img)
    grad(d, 0, 0, W, H, ACCENT, CTA, vert=False)
    ex, ey, ew, eh = 10, 17, 35, 23
    d.rectangle([ex, ey, ex + ew, ey + eh], outline=TP, width=1)
    d.line([(ex, ey), (ex + ew // 2, ey + eh // 2), (ex + ew, ey)], fill=TP, width=1)
    img.save(OUT / 'wizard_header.bmp', 'BMP')
    print('wizard_header.bmp   55x58   OK')


if __name__ == '__main__':
    make_sidebar()
    make_header()
