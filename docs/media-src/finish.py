"""Shrinks the rendered PNGs and puts them where the README and the Agensi listing expect them."""
import shutil
import sys
from pathlib import Path

from PIL import Image

work, root = Path(sys.argv[1]), Path(sys.argv[2])


def save(src: Path, dst: Path, width: int | None = None, full_colour: bool = False) -> None:
    im = Image.open(src).convert("RGB")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if full_colour:  # gradients and logos: palette tricks wash them out
        im.save(dst, optimize=True)
    else:
        im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(dst, optimize=True)
    print(f"{dst.relative_to(root)}: {im.width}x{im.height}, {dst.stat().st_size // 1024} KB")


save(work / "evidence-check.png", root / "docs/evidence-check.png", 2000)
shutil.copyfile(root / "docs/evidence-check.png", root / "agensi/media/screenshot-1.png")
save(work / "rejected.png", root / "docs/rejected-plan.png", 1900)
shutil.copyfile(root / "docs/rejected-plan.png", root / "agensi/media/screenshot-2.png")
save(work / "social-preview.png", root / "docs/social-preview.png", full_colour=True)
