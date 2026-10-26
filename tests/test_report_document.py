import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DOCX = ROOT / "reports" / "RetinaScan_AI_Minor_Project_Report.docx"
REPORT_MD = ROOT / "reports" / "RetinaScan_AI_Minor_Project_Report.md"


def test_report_source_has_no_submission_placeholders_and_has_citations():
    text = REPORT_MD.read_text(encoding="utf-8")
    assert "[NAME OF THE STUDENT]" not in text
    assert "[ENROLLMENT NUMBER]" not in text
    assert "Placeholder fields to complete" not in text
    assert "Supervisor name to be confirmed" in text
    assert "Head of Department name to be confirmed" in text
    assert "Principal name to be confirmed" in text
    body = text.split("## Bibliography", 1)[0]
    for reference_number in range(1, 23):
        assert re.search(rf"\[{reference_number}\]", body)
    assert "https://github.com/minitttt/AI-Based-Diabetic-Retinopathy-Detection-Monitoring" in text


def test_report_docx_contains_automatic_lists_captions_and_media():
    with zipfile.ZipFile(REPORT_DOCX) as archive:
        assert archive.testzip() is None
        document = archive.read("word/document.xml").decode("utf-8")
        settings = archive.read("word/settings.xml").decode("utf-8")

    assert document.count("TOC \\t") == 3
    assert len(re.findall(r"SEQ (?:Table|Figure)", document)) >= 30
    assert document.count("<w:tbl>") >= 15
    assert "Update this field in Microsoft Word" not in document
    assert "w:updateFields" in settings

    first_paragraph = re.search(
        r"<w:p>.*?<w:pStyle w:val=\"Title\".*?<w:jc w:val=\"center\".*?</w:p>",
        document,
        flags=re.DOTALL,
    )
    assert first_paragraph is not None


def test_report_captions_follow_document_order():
    text = REPORT_MD.read_text(encoding="utf-8")
    expected = [
        "Figure 5.1:",
        "Figure 5.2:",
        "Figure 5.3:",
        "Figure 5.4:",
        "Figure 5.5:",
        "Figure 5.6:",
        "Figure 5.7:",
        "Figure 5.8:",
        "Figure 5.9:",
        "Figure 5.10:",
    ]
    positions = [text.index(caption) for caption in expected]
    assert positions == sorted(positions)
    assert "Figure 4.4: Entity relationship model" in text
    assert "Figure 4.2: Entity relationship model" not in text


def test_report_has_required_chapter_boundaries():
    text = REPORT_MD.read_text(encoding="utf-8")
    assert "# CHAPTER 7: SUMMARY AND CONCLUSION" in text
    assert "# CHAPTER 8: LIMITATIONS AND FUTURE WORK" in text
    assert "# CHAPTER 7: RESULTS AND DISCUSSION" not in text
