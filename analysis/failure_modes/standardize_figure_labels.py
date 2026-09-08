from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SOURCE = Path("/Users/justintiensmith/Documents/ICRA_paper_v5/Figures")
DEST = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5/ICRA_paper_v5_standardized/Figures"
)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def centered_multiline(draw: ImageDraw.ImageDraw, center_x: int, top_y: int, text: str, font: ImageFont.FreeTypeFont, fill=(0, 0, 0), spacing: int = 4) -> None:
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
    width = box[2] - box[0]
    draw.multiline_text((center_x - width / 2, top_y), text, font=font, fill=fill, spacing=spacing, align="center")


def relabel_familiar() -> None:
    image = Image.open(SOURCE / "familiar_spatial_grounding.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((205, 251, 2325, 370), fill="white")
    font = ImageFont.truetype(BOLD, 28)
    labels = [
        (349, "Counting"),
        (656, "Ordinal Position"),
        (965, "Relational Placement"),
        (1273, "Physical State"),
        (1581, "Relative Size"),
        (2040, "Referential\nDescription"),
    ]
    for x, label in labels:
        centered_multiline(draw, x, 268, label, font, spacing=2)
    # Restore the legend's top border after clearing the old two-line labels.
    draw.line((440, 351, 1671, 351), fill="black", width=2)
    image.save(DEST / "familiar_spatial_grounding.png", dpi=(300, 300))


def relabel_novel_matched() -> None:
    image = Image.open(SOURCE / "novel_spatial_grounding_matched_manipulation.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((205, 543, 2312, 710), fill="white")
    font = ImageFont.truetype(BOLD, 28)
    labels = [
        (349, "Counting"),
        (655, "Ordinal Position"),
        (961, "Relational Placement"),
        (1268, "Physical State"),
        (1575, "Relative Size"),
        (2024, "Referential\nDescription"),
    ]
    for x, label in labels:
        centered_multiline(draw, x, 620, label, font, spacing=2)
    image.save(DEST / "novel_spatial_grounding_matched_manipulation.png", dpi=(300, 300))


def relabel_no_movement() -> None:
    image = Image.open(SOURCE / "no_movement.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((190, 292, 1928, 430), fill="white")
    font = ImageFont.truetype(BOLD, 30)
    labels = [
        (330, "Counting: Goal\nAlready Satisfied"),
        (687, "Ordinal Position:\nInvalid Order"),
        (1045, "Physical State:\nNo Valid Target"),
        (1392, "Referential Description:\nNo Valid Candidate"),
        (1735, "Four-Task Aggregate"),
    ]
    for x, label in labels:
        centered_multiline(draw, x, 305, label, font, spacing=4)
    image.save(DEST / "no_movement.png", dpi=(300, 300))


def relabel_teaser() -> None:
    image = Image.open(SOURCE / "teaser.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    gray = image.getpixel((15, 80))
    draw.rectangle((5, 48, 1228, 122), fill=gray)
    draw.rectangle((5, 568, 1228, 642), fill=gray)
    font = ImageFont.truetype(BOLD, 29)
    for x, label in [(225, "Physical State"), (620, "Relative Size"), (1017, "Referential Description")]:
        centered_multiline(draw, x, 69, label, font)
    for x, label in [(225, "Relational Placement"), (620, "Ordinal Position"), (1017, "Counting")]:
        centered_multiline(draw, x, 589, label, font)
    image.save(DEST / "teaser.png", dpi=(300, 300))


def relabel_sankey() -> None:
    image = Image.open(SOURCE / "sankey_diagram.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((1325, 555, 2695, 1307), fill="white")
    font = ImageFont.truetype(BOLD, 43)
    labels = [
        (570, "Physical State - 200"),
        (680, "Relative Size - 200"),
        (790, "Referential Description - 200"),
        (900, "Ordinal Position - 200"),
        (1010, "Relational Placement - 200"),
        (1120, "Counting - 200"),
    ]
    for y, label in labels:
        draw.text((1345, y), label, font=font, fill="black")
    image.save(DEST / "sankey_diagram.png", dpi=(300, 300))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    relabel_familiar()
    relabel_novel_matched()
    relabel_no_movement()
    relabel_teaser()
    relabel_sankey()
    print(f"Wrote standardized figure labels to {DEST}")


if __name__ == "__main__":
    main()
