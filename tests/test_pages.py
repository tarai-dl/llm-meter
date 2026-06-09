from pathlib import Path


def test_pages_index_exists_and_links_demo_assets():
    index = Path("docs/index.html")
    assert index.exists()
    html = index.read_text(encoding="utf-8")

    assert "LLM Meter" in html
    assert "demo-assets/demo-report.html" in html
    assert "demo-assets/demo-report.zip" in html
    assert "demo-assets/demo-gateway.jsonl" in html
    assert "demo-assets/report.json" in html


def test_pages_workflow_exists():
    workflow = Path(".github/workflows/pages.yml")
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")

    assert "github-pages" in text
    assert "actions/upload-pages-artifact" in text
    assert "actions/deploy-pages" in text
