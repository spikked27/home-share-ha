"""Generate original Home Share vector artwork and supersampled PNG exports.

Development-only dependency: Pillow. The runtime has no imaging dependency.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components/home_share/brand"
TEAL = "#23846a"
WHITE = "#f6fcf8"
MINT = "#a3efd2"

# A roof shelters a simple three-node sharing path. Broad strokes and circular
# terminals stay legible at the tiny sizes used by HA and HACS.
SVG_MARK = f'''<rect x="16" y="16" width="480" height="480" rx="120" fill="{TEAL}"/>
<path d="M116 246L256 126L396 246M148 222V374H234" fill="none" stroke="{WHITE}" stroke-width="32" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M250 286L352 240M250 286L352 350" fill="none" stroke="{MINT}" stroke-width="24" stroke-linecap="round"/>
<circle cx="250" cy="286" r="30" fill="{WHITE}"/>
<circle cx="352" cy="240" r="30" fill="{MINT}"/>
<circle cx="352" cy="350" r="30" fill="{MINT}"/>'''


def mark(size):
    scale = 4
    image = Image.new("RGBA", (512 * scale, 512 * scale))
    draw = ImageDraw.Draw(image)
    xy = lambda points: [(int(x * scale), int(y * scale)) for x, y in points]
    draw.rounded_rectangle((64, 64, 1984, 1984), radius=480, fill=TEAL)
    def stroke(points, width, color):
        draw.line(xy(points), fill=color, width=width * scale, joint="curve")
        for x, y in points:
            radius = width * scale / 2
            draw.ellipse((x*scale-radius, y*scale-radius, x*scale+radius, y*scale+radius), fill=color)
    stroke([(116,246),(256,126),(396,246)],32,WHITE)
    stroke([(148,222),(148,374),(234,374)],32,WHITE)
    stroke([(250,286),(352,240)],24,MINT)
    stroke([(250,286),(352,350)],24,MINT)
    for x,y,color in [(250,286,WHITE),(352,240,MINT),(352,350,MINT)]:
        draw.ellipse(((x-30)*scale,(y-30)*scale,(x+30)*scale,(y+30)*scale),fill=color)
    return image.resize((size,size),Image.Resampling.LANCZOS)


def font(size):
    for candidate in ["C:/Windows/Fonts/seguisb.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate,size)
    raise RuntimeError("Install Segoe UI Semibold or DejaVu Sans to regenerate the wordmark.")


def generate():
    BRAND.mkdir(parents=True,exist_ok=True)
    (BRAND/"icon.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{SVG_MARK}</svg>\n',encoding="utf-8")
    for dark in [False,True]:
        prefix="dark_" if dark else ""
        ink="#e9f5ee" if dark else "#203d33"
        for factor in [1,2]:
            suffix="@2x" if factor==2 else ""
            mark(256*factor).save(BRAND/f"{prefix}icon{suffix}.png",optimize=True)
            image=Image.new("RGBA",(640*factor,160*factor))
            image.alpha_composite(mark(152*factor),(0,4*factor))
            draw=ImageDraw.Draw(image)
            draw.text((174*factor,34*factor),"Home Share",fill=ink,font=font(66*factor),stroke_width=0)
            image.save(BRAND/f"{prefix}logo{suffix}.png",optimize=True)
        (BRAND/f"{prefix}logo.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 320"><g transform="translate(0 8) scale(.59375)">{SVG_MARK}</g><text x="348" y="211" fill="{ink}" font-family="Segoe UI,DejaVu Sans,sans-serif" font-size="132" font-weight="600" letter-spacing="-4">Home Share</text></svg>\n',encoding="utf-8")
    # The panel and README consume the same source artwork as platform exports.
    frontend=ROOT/"custom_components/home_share/frontend"
    (frontend/"home-share-mark.svg").write_bytes((BRAND/"icon.svg").read_bytes())
    print("Created original SVG artwork and eight transparent PNG brand variants.")


if __name__=="__main__":
    generate()
