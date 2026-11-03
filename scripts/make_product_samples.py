from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

out = Path(__file__).resolve().parents[1] / "app" / "static" / "img" / "products"
out.mkdir(parents=True, exist_ok=True)

specs = [
    ("camisa-oversize.jpg", (18, 18, 20), (42, 42, 48), "OVERSIZE TEE", "Negro"),
    ("jean-indigo.jpg", (20, 28, 48), (36, 52, 92), "RECTO JEAN", "Índigo"),
    ("hoodie-stone.jpg", (58, 56, 52), (92, 88, 80), "HOODIE", "Stone"),
    ("gorra-snapback.jpg", (12, 12, 14), (28, 28, 32), "SNAPBACK", "Gold"),
    ("bomber-night.jpg", (8, 8, 10), (22, 22, 28), "BOMBER", "Night"),
    ("tee-crown.jpg", (236, 236, 232), (210, 210, 205), "CROWN TEE", "Blanco"),
]

W, H = 900, 1125


def try_font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


title_font = try_font(54, bold=True)
meta_font = try_font(28, bold=False)
brand_font = try_font(26, bold=True)

for name, bg, accent, label, tone in specs:
    img = Image.new("RGB", (W, H), bg)
    overlay = Image.new("RGB", (W, H), accent)
    mask = Image.new("L", (W, H), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((-120, -80, W + 120, int(H * 0.72)), fill=210)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    img = Image.composite(overlay, img, mask)
    draw = ImageDraw.Draw(img)

    panel = [140, 210, W - 140, H - 260]
    draw.rounded_rectangle(panel, radius=36, fill=accent)
    outline = (255, 255, 255) if sum(bg) < 360 else (30, 30, 30)
    draw.rounded_rectangle(
        [panel[0] + 18, panel[1] + 18, panel[2] - 18, panel[3] - 18],
        radius=28,
        outline=outline,
        width=2,
    )

    ink = (250, 250, 250) if sum(bg) < 360 else (20, 20, 22)
    muted = (210, 210, 214) if sum(bg) < 360 else (70, 70, 75)

    brand = "URBANOX"
    bw = draw.textlength(brand, font=brand_font)
    draw.text(((W - bw) / 2, 70), brand, font=brand_font, fill=ink)

    cx, cy = W // 2, 150
    draw.polygon([(cx, cy - 18), (cx - 22, cy + 10), (cx + 22, cy + 10)], fill=ink)

    lw = draw.textlength(label, font=title_font)
    draw.text(((W - lw) / 2, H - 180), label, font=title_font, fill=ink)
    tw = draw.textlength(tone, font=meta_font)
    draw.text(((W - tw) / 2, H - 118), tone, font=meta_font, fill=muted)

    path = out / name
    img.save(path, quality=92)
    print("wrote", path.name)

print("done")
