"""Builder preview and overflow lint.

Draws every slide of the PPTX from its own geometry with real Arial metrics (Pillow), and reports text that
would not fit its frame. This is NOT a PowerPoint or Keynote render: no renderer was available to this lane
(see qa/visual-qa.txt). Use it to catch overflow and collisions, then confirm with a real render.

Run: uv run --no-project --with python-pptx python build/preview.py [outdir]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Emu

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "outputs" / "Tsenta-Pitch-2026-10-14.pptx"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs" / "preview"
DPI = 144
FONTS = {
    (False, False): "/System/Library/Fonts/Supplemental/Arial.ttf",
    (True, False): "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    (False, True): "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
    (True, True): "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
}
_font_cache = {}


def px(emu):
    return int(round(Emu(emu).inches * DPI))


def font(size_pt, bold, italic):
    key = (round(size_pt * 4), bold, italic)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONTS[(bool(bold), bool(italic))], max(1, int(round(size_pt * DPI / 72))))
    return _font_cache[key]


def rgb(colorfmt, default=(0x25, 0x1F, 0x21)):
    try:
        if colorfmt and colorfmt.type is not None and colorfmt.rgb is not None:
            v = colorfmt.rgb
            return (v[0], v[1], v[2])
    except Exception:
        pass
    return default


def runs_of(para):
    out = []
    for r in para.runs:
        f = r.font
        size = f.size.pt if f.size else 18
        spc = r._r.find(qn("a:rPr"))
        spc = int(spc.get("spc", "0")) / 100 if spc is not None else 0
        out.append((r.text, size, bool(f.bold), bool(f.italic), rgb(f.color), spc))
    return out


def layout_para(para, width_px):
    """Greedy word wrap across runs. Returns list of lines; each line = list of (text, font, color, spc_px), height."""
    runs = runs_of(para)
    if not runs:
        return [([], 18)], 18
    max_size = max(r[1] for r in runs)
    words = []  # (word_with_trailing_space, run)
    for text, size, b, it, col, spc in runs:
        parts = text.split(" ")
        for i, w in enumerate(parts):
            token = w + (" " if i < len(parts) - 1 else "")
            if token:
                words.append((token, (size, b, it, col, spc)))
    lines, cur, cur_w = [], [], 0
    for token, st in words:
        f = font(st[0], st[1], st[2])
        spc_px = st[4] * DPI / 72
        w = f.getlength(token) + spc_px * len(token)
        if cur and cur_w + w - (f.getlength(" ") if token.endswith(" ") else 0) > width_px:
            lines.append(cur)
            cur, cur_w = [], 0
            token = token.lstrip()
            w = f.getlength(token) + spc_px * len(token)
        cur.append((token, f, st[3], spc_px))
        cur_w += w
    if cur:
        lines.append(cur)
    return lines, max_size


def draw_text_frame(d, tf, x, y, w, h, issues, label, anchor_mid=False):
    ml = px(tf.margin_left) if tf.margin_left is not None else px(91440)
    mr = px(tf.margin_right) if tf.margin_right is not None else px(91440)
    mt = px(tf.margin_top) if tf.margin_top is not None else px(45720)
    mb = px(tf.margin_bottom) if tf.margin_bottom is not None else px(45720)
    inner_w = w - ml - mr
    blocks, total = [], 0
    for para in tf.paragraphs:
        lines, size = layout_para(para, inner_w)
        ls = para.line_spacing if isinstance(para.line_spacing, float) else 1.0
        lh = size * 1.2 * ls * DPI / 72
        sb = para.space_before.pt * DPI / 72 if para.space_before is not None else 0
        sa = para.space_after.pt * DPI / 72 if para.space_after is not None else 0
        blocks.append((para, lines, lh, sb, sa))
        total += sb + lh * len(lines) + sa
    total -= blocks[-1][4] if blocks else 0
    avail = h - mt - mb
    if total > avail + 2:
        issues.append(f"{label}: text needs {total / DPI:.2f} in, frame has {avail / DPI:.2f} in")
    widest = 0
    cy = y + mt + (max(0, (avail - total) / 2) if anchor_mid else 0)
    for para, lines, lh, sb, sa in blocks:
        cy += sb
        align = para.alignment
        for line in lines:
            lw = sum(f.getlength(t) + sp * len(t) for t, f, c, sp in line)
            if len(line) == 1:
                widest = max(widest, line[0][1].getlength(line[0][0].rstrip()))
            if align is not None and int(align) == 2:  # center
                cx = x + ml + (inner_w - lw) / 2
            elif align is not None and int(align) == 3:  # right
                cx = x + ml + inner_w - lw
            else:
                cx = x + ml
            base = cy + lh * 0.8
            for t, f, c, sp in line:
                if sp:
                    for ch in t:
                        d.text((cx, base), ch, font=f, fill=c, anchor="ls")
                        cx += f.getlength(ch) + sp
                else:
                    d.text((cx, base), t, font=f, fill=c, anchor="ls")
                    cx += f.getlength(t)
            cy += lh
        cy += sa
    if widest > inner_w + 2:
        issues.append(f"{label}: a single word is wider than the frame")


def line_props(shape):
    try:
        ln = shape.line
        if ln.fill.type is None or ln.fill.type == 5:  # background / none
            return None
        col = rgb(ln.color)
        wid = max(1, int(round((ln.width.pt if ln.width else 0.75) * DPI / 72)))
        return col, wid
    except Exception:
        return None


def draw_slide(slide, size, issues, n):
    W, H = size
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    boxes = []
    for shp in slide.shapes:
        x, y, w, h = px(shp.left), px(shp.top), px(shp.width), px(shp.height)
        label = f"slide {n} '{shp.name}'"
        if x < 0 or y < 0 or x + w > W + 1 or y + h > H + 1:
            issues.append(f"{label}: outside the slide")
        if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
            from io import BytesIO
            im = Image.open(BytesIO(shp.image.blob)).convert("RGB").resize((w, h))
            img.paste(im, (x, y))
            lp = line_props(shp)
            if lp:
                d.rectangle([x, y, x + w, y + h], outline=lp[0], width=lp[1])
            continue
        if shp.shape_type == MSO_SHAPE_TYPE.LINE or shp.__class__.__name__ == "Connector":
            col, wid = line_props(shp) or ((0x58, 0x52, 0x54), 2)
            bx, by, ex, ey = px(shp.begin_x), px(shp.begin_y), px(shp.end_x), px(shp.end_y)
            d.line([bx, by, ex, ey], fill=col, width=wid)
            ln = shp.line._get_or_add_ln()
            for tag, (tx, ty, fx, fy) in (("a:tailEnd", (ex, ey, bx, by)), ("a:headEnd", (bx, by, ex, ey))):
                if ln.find(qn(tag)) is not None:
                    import math
                    ang = math.atan2(ty - fy, tx - fx)
                    s_ = 9
                    pts = [(tx, ty), (tx - s_ * math.cos(ang - 0.45), ty - s_ * math.sin(ang - 0.45)),
                           (tx - s_ * math.cos(ang + 0.45), ty - s_ * math.sin(ang + 0.45))]
                    d.polygon(pts, fill=col)
            continue
        if shp.has_table if hasattr(shp, "has_table") else False:
            tbl = shp.table
            cy = y
            for ri, row in enumerate(tbl.rows):
                # row height grows with content, as in PowerPoint
                cells = list(row.cells)
                needed = 0
                for ci, cell in enumerate(cells):
                    cw = px(tbl.columns[ci].width)
                    tmp = []
                    ml = px(cell.margin_left)
                    mr = px(cell.margin_right)
                    hh = 0
                    for para in cell.text_frame.paragraphs:
                        lines, sz = layout_para(para, cw - ml - mr)
                        hh += sz * 1.2 * DPI / 72 * len(lines)
                    needed = max(needed, hh + px(cell.margin_top) + px(cell.margin_bottom))
                rh = max(px(row.height), int(needed))
                cx = x
                for ci, cell in enumerate(cells):
                    cw = px(tbl.columns[ci].width)
                    fill = rgb(cell.fill.fore_color, (255, 255, 255)) if cell.fill.type == 1 else (255, 255, 255)
                    d.rectangle([cx, cy, cx + cw, cy + rh], fill=fill)
                    d.line([cx, cy + rh, cx + cw, cy + rh], fill=(0xE4, 0xE0, 0xDD), width=1)
                    draw_text_frame(d, cell.text_frame, cx, cy, cw, rh, [], label)
                    cx += cw
                cy += rh
            if cy > px(Emu(int(6.85 * 914400))):
                issues.append(f"{label}: table grows to {cy / DPI:.2f} in, past the footer rule at 6.88 in")
            continue
        # autoshape / textbox / placeholder
        if shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            fill = None
            try:
                if shp.fill.type == 1:
                    fill = rgb(shp.fill.fore_color)
            except Exception:
                pass
            lp = line_props(shp)
            dash = shp.line._get_or_add_ln().find(qn("a:prstDash")) is not None if lp else False
            kind = shp.auto_shape_type
            box = [x, y, x + w, y + h]
            if int(kind) == 9:  # oval
                d.ellipse(box, fill=fill, outline=lp[0] if lp else None, width=lp[1] if lp else 0)
                if dash:
                    d.ellipse(box, outline=(255, 255, 255), width=1)
            else:
                r = 0
                if int(kind) == 5:  # rounded rectangle
                    r = int(min(w, h) * shp.adjustments[0])
                d.rounded_rectangle(box, radius=r, fill=fill, outline=lp[0] if lp else None, width=lp[1] if lp else 0)
        if shp.has_text_frame and shp.text_frame.text.strip():
            tf = shp.text_frame
            anchor = tf._txBody.find(qn("a:bodyPr")).get("anchor") == "ctr"
            draw_text_frame(d, tf, x, y, w, h, issues, label, anchor_mid=anchor)
            boxes.append((shp.name, x, y, w, h))
    return img


def main():
    prs = Presentation(DECK)
    size = (px(prs.slide_width), px(prs.slide_height))
    OUT.mkdir(parents=True, exist_ok=True)
    issues = []
    for i, slide in enumerate(prs.slides, 1):
        img = draw_slide(slide, size, issues, i)
        img.save(OUT / f"slide-{i:02d}.png")
    # contact sheet
    thumbs = [Image.open(OUT / f"slide-{i:02d}.png").resize((480, 270)) for i in range(1, len(prs.slides) + 1)]
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 490 + 10, rows * 280 + 10), (0xDD, 0xDD, 0xDD))
    for i, t in enumerate(thumbs):
        sheet.paste(t, (10 + (i % cols) * 490, 10 + (i // cols) * 280))
    sheet.save(OUT / "contact-sheet.png")
    print(f"{len(prs.slides)} slides -> {OUT}")
    print("\n".join(issues) if issues else "no overflow or bounds issues found")


if __name__ == "__main__":
    main()
