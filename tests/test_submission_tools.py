import pytest

from tools.add_pdf_links import validate_public_url as validate_pdf_video_url
from tools.build_presentation import validate_public_url as validate_presentation_video_url


@pytest.mark.parametrize(
    "validator", (validate_pdf_video_url, validate_presentation_video_url)
)
def test_submission_video_url_requires_public_https(validator):
    url = "https://example.com/demo"
    assert validator(url) == url

    for invalid in ("", "PUBLIC_VIDEO_URL", "http://example.com/demo"):
        with pytest.raises(ValueError, match="public HTTPS URL"):
            validator(invalid)
