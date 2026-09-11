import argparse
from pathlib import Path
from urllib.parse import urlparse

import pymupdf


REPOSITORY = "https://github.com/AT-14/ModelSentry"
VIDEO_URL = "https://drive.google.com/file/d/16yUgLW3690mo8zR9VjFixuZROb7sJyWL/view"


def validate_public_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The video URL must be a public HTTPS URL")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Add final ModelSentry PDF links")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--video-url", default=VIDEO_URL)
    args = parser.parse_args()
    video_url = validate_public_url(args.video_url)

    document = pymupdf.open(args.pdf)
    if document.page_count != 5:
        raise ValueError(f"Expected five pages, found {document.page_count}")
    page = document[4]
    height = page.rect.height
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(678, height - 167, 897, height - 91),
            "uri": REPOSITORY,
        }
    )
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(53, height - 74, 435, height - 48),
            "uri": video_url,
        }
    )
    temporary = args.pdf.with_suffix(".linked.pdf")
    document.save(temporary, garbage=4, deflate=True)
    document.close()
    temporary.replace(args.pdf)
    print(f"Linked {args.pdf}")


if __name__ == "__main__":
    main()
