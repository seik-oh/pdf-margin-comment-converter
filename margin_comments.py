#!/usr/bin/env python3
"""
PDF 주석(코멘트)을 Word처럼 페이지 오른쪽 여백에 펼쳐 보여주는 PDF를 만듭니다.

사용법:
    python3 margin_comments.py 입력.pdf [출력.pdf]

필요 패키지:  pip3 install pypdf reportlab
입력 파일은 Zotero의 "PDF 내보내기…"로 저장한 (주석 포함) PDF를 쓰세요.
"""
import io
import os
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MARGIN_W = 230          # 오른쪽에 추가할 여백 폭(pt)
BOX_PAD = 5
FONT_SIZE = 8.5
MIN_FONT = 6
GAP = 6                 # 코멘트 박스 사이 간격
SKIP_SUBTYPES = {"/Popup", "/Link", "/Widget", "/FreeText"}

FONT_CANDIDATES = [
    # macOS
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0),
    ("/Library/Fonts/NanumGothic.ttf", 0),
    (os.path.expanduser("~/Library/Fonts/NanumGothic.ttf"), 0),
    # Windows
    ("C:/Windows/Fonts/malgun.ttf", 0),
    # Linux
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
]


def register_font():
    for path, idx in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("KFont", path, subfontIndex=idx))
                return "KFont"
            except Exception:
                continue
    print("경고: 한글 폰트를 찾지 못해 한글이 깨질 수 있습니다.")
    return "Helvetica"


def to_text(v):
    if v is None:
        return ""
    s = str(v).replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()


def wrap(text, font, size, width):
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            cand = word if not cur else cur + " " + word
            if pdfmetrics.stringWidth(cand, font, size) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
                cur = ""
            # 단어 자체가 길면(한글 등) 글자 단위로 자르기
            for ch in word:
                if pdfmetrics.stringWidth(cur + ch, font, size) <= width:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return lines


def color_of(annot):
    c = annot.get("/C")
    try:
        if c and len(c) == 3:
            return tuple(float(x) for x in c)
    except Exception:
        pass
    return (1.0, 0.8, 0.0)


def collect(page, x0, y0):
    items = []
    for ref in page.get("/Annots") or []:
        a = ref.get_object()
        sub = a.get("/Subtype")
        if sub in SKIP_SUBTYPES:
            continue
        text = to_text(a.get("/Contents"))
        if not text:
            continue
        r = RectangleObject(a["/Rect"])
        items.append({
            "text": text,
            "ax": float(r.right) - x0,
            "ay": float(r.top) - y0,
            "color": color_of(a),
        })
    items.sort(key=lambda d: (-d["ay"], d["ax"]))
    return items


def layout(items, font, size, box_w, page_h):
    for it in items:
        it["lines"] = wrap(it["text"], font, size, box_w - 2 * BOX_PAD)
        it["h"] = len(it["lines"]) * size * 1.3 + 2 * BOX_PAD
    top_limit, bottom_limit = page_h - 12, 12
    # 위에서부터: 원하는 위치에 두되 겹치면 아래로
    cursor = top_limit
    for it in items:
        top = min(it["ay"] + 6, cursor)
        it["top"] = top
        cursor = top - it["h"] - GAP
    # 아래로 넘치면 아래에서부터 위로 밀어올림
    floor = bottom_limit
    for it in reversed(items):
        if it["top"] - it["h"] < floor:
            it["top"] = floor + it["h"]
        floor = it["top"] + GAP
    total = sum(it["h"] + GAP for it in items)
    return total <= (top_limit - bottom_limit)


def build_overlay(items, pw, ph, font):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pw + MARGIN_W, ph))
    # 여백 배경
    c.setFillColorRGB(0.965, 0.965, 0.965)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.rect(pw, 0, MARGIN_W, ph, fill=1, stroke=0)
    c.line(pw, 0, pw, ph)

    box_x = pw + 10
    box_w = MARGIN_W - 20
    size = FONT_SIZE
    while not layout(items, font, size, box_w, ph) and size > MIN_FONT:
        size -= 0.5

    for it in items:
        r, g, b = it["color"]
        top, h = it["top"], it["h"]
        # 연결선: 주석 위치 → 페이지 오른쪽 끝 → 코멘트 박스
        c.setStrokeColorRGB(r, g, b)
        c.setLineWidth(0.7)
        c.setDash(2, 2)
        mid_y = top - min(h / 2, 10)
        p = c.beginPath()
        p.moveTo(it["ax"], it["ay"])
        p.lineTo(pw - 2, it["ay"])
        p.lineTo(box_x, mid_y)
        c.drawPath(p, stroke=1, fill=0)
        c.setDash()
        c.circle(it["ax"], it["ay"], 1.5, stroke=1, fill=0)
        # 박스
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(r, g, b)
        c.setLineWidth(0.9)
        c.roundRect(box_x, top - h, box_w, h, 3, fill=1, stroke=1)
        c.setFillColorRGB(r, g, b)
        c.rect(box_x, top - h, 3, h, fill=1, stroke=0)
        # 글자
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(font, size)
        y = top - BOX_PAD - size
        for line in it["lines"]:
            c.drawString(box_x + BOX_PAD + 2, y, line)
            y -= size * 1.3
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + "_코멘트.pdf"
    font = register_font()

    writer = PdfWriter(clone_from=src)
    total = 0
    for page in writer.pages:
        if page.get("/Rotate", 0) % 360:
            page.transfer_rotation_to_content()
        mb = page.mediabox
        x0, y0 = float(mb.left), float(mb.bottom)
        pw, ph = float(mb.width), float(mb.height)
        items = collect(page, x0, y0)
        # 페이지를 오른쪽으로 넓힘 (주석은 원래 위치 그대로 유지)
        new_box = RectangleObject([x0, y0, x0 + pw + MARGIN_W, y0 + ph])
        page.mediabox = new_box
        page.cropbox = new_box
        if "/TrimBox" in page:
            del page["/TrimBox"]
        if "/BleedBox" in page:
            del page["/BleedBox"]
        overlay = build_overlay(items, pw, ph, font)
        page.merge_transformed_page(overlay, (1, 0, 0, 1, x0, y0))
        total += len(items)

    with open(dst, "wb") as f:
        writer.write(f)
    print(f"완료: 코멘트 {total}개 → {dst}")


if __name__ == "__main__":
    main()
