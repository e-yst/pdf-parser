#!/usr/bin/env python3

"""
extract_pdf_text_images.py

Description: This script extracts text and images from a PDF file.

Author: Eason Tse
Date: 16 Jan 2024

Credit:
The script is based on the code from the article "Extracting Text from PDF Files with Python: A Comprehensive Guide"
by George Stavrakis, available at https://towardsdatascience.com/extracting-text-from-pdf-files-with-python-a-comprehensive-guide-9fc4003d517
"""
import hashlib
import io
import json
from argparse import ArgumentParser
from pathlib import Path

import PyPDF2
import tqdm
from pdf2image import convert_from_bytes
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTFigure, LTPage, LTTextContainer

IMG_HASHES = {}


def main():
    parser = build_parser()
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir) / pdf_path.with_suffix("").name
    img_out_path = output_dir / "images"
    if not img_out_path.exists():
        img_out_path.mkdir(parents=True)

    pdf_content = process_pdf_pages(pdf_path, img_out_path)

    json_path = output_dir / pdf_path.with_suffix(".json").name
    data = json.dumps(pdf_content, ensure_ascii=False, indent=2)
    with open(json_path, "w") as fout:
        fout.write(data)


def build_parser():
    parser = ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--output_dir", default=Path().absolute())
    return parser


def text_extraction(element: LTTextContainer):
    # Extracting the text from the in-line text element
    line_text = element.get_text()

    # Find the formats of the text
    # Initialize the list with all the formats that appeared in the line of text
    line_formats = []
    for text_line in element:
        if not isinstance(text_line, LTTextContainer):
            continue

        # Iterating through each character in the line of text
        str_list, str_font = [], ""
        for character in text_line:
            if character.get_text() == " ":
                str_list.append(" ")
                continue

            if not isinstance(character, LTChar):
                continue

            # Append the font name of the character
            font = character.fontname
            str_list.append(character.get_text())
            if str_font == "":
                str_font = font
            if font != str_font:
                line_formats.append(("".join(str_list), str_font))
                str_list, str_font = [character.get_text()], font

    # Return a tuple with the text in each line along with its format
    return line_text, line_formats


def extract_images(
    element: LTFigure,
    page_obj: PyPDF2.PageObject,
    img_out_path: Path,
) -> str:
    # Get the coordinates to crop the image from the PDF
    image_left, image_top, image_right, image_bottom = (
        element.x0,
        element.y0,
        element.x1,
        element.y1,
    )

    # Crop the page using coordinates (left, bottom, right, top)
    page_obj.mediabox.lower_left = image_left, image_bottom
    page_obj.mediabox.upper_right = image_right, image_top

    # Save the cropped page to a new PDF
    cropped_pdf_writer = PyPDF2.PdfWriter()
    cropped_pdf_writer.add_page(page_obj)

    # # Save the cropped PDF to a new file
    buffer = io.BytesIO()
    cropped_pdf_writer.write(buffer)

    images = convert_from_bytes(buffer.getbuffer())
    image = images[0]

    buffer.seek(0)
    buffer.truncate(0)

    image.save(buffer, "PNG")

    m = hashlib.sha256()
    m.update(buffer.getbuffer())
    img_hash = m.hexdigest()
    if not img_hash in IMG_HASHES:
        IMG_HASHES[img_hash] = img_out_path.name
        with open(img_out_path, "wb") as fout:
            fout.write(buffer.getbuffer())
    return img_hash


def process_pdf_pages(pdf_path: Path, img_out_path: Path):
    with open(pdf_path, "rb") as pdf_in:
        # create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(pdf_in)
        pdf_content = []

        # extract the pages from the PDF
        pdf_pages = (
            (pnum, page, pdf_reader.pages[pnum])
            for pnum, page in enumerate(extract_pages(pdf_path))
        )
        for pagenum, lt_page, pypdf2_page in tqdm.tqdm(
            pdf_pages,
            total=pdf_reader._get_num_pages(),
            desc="Processing pages from pdf",
        ):
            process_page_elements(
                pagenum,
                lt_page,
                pypdf2_page,
                img_out_path,
                pdf_content,
            )
    return pdf_content


def process_page_elements(
    pagenum: int,
    lt_page: LTPage,
    pypdf2_page: PyPDF2.PageObject,
    img_out_path: Path,
    pdf_content: list[dict[str, str | int]],
):
    # Find and sort all the elements
    page_elements = sorted(lt_page._objs, key=lambda el: el.y1, reverse=True)

    # Find the elements that composed a page
    for idx, element in enumerate(page_elements):
        # Check if the element is a text element
        if isinstance(element, LTTextContainer):
            # Use the function to extract the text and format for each text element
            line_text, format_per_line = text_extraction(element)
            # Append the text of each line to the page text
            pdf_content.append(
                {
                    "type": "text",
                    "content": line_text,
                    "page": pagenum,
                    "format": format_per_line,
                }
            )

        # Check the elements for images
        if isinstance(element, LTFigure):
            img_path = img_out_path / f"{pagenum}_el_{str(idx).zfill(3)}.png"

            # Crop the image from the PDF and convert the cropped pdf to an image
            img_hash = extract_images(element, pypdf2_page, img_path)
            pdf_content.append(
                {"type": "image", "content": f"{IMG_HASHES[img_hash]}", "page": pagenum}
            )


if __name__ == "__main__":
    main()
