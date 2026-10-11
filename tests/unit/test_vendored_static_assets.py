"""Frontend libraries are served from Main/static/vendor, not from CDNs."""

import re
from pathlib import Path

import pytest

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "Main" / "templates"
STATIC_DIR = TEMPLATE_DIR.parent / "static"
CDN_HOSTS = ("cdn.jsdelivr.net", "code.jquery.com", "unpkg.com", "cdnjs.cloudflare.com")
VENDOR_REFERENCE = re.compile(r"""\{%\s*static\s+['"](vendor/[^'"]+)['"]\s*%\}""")

TEMPLATES = sorted(TEMPLATE_DIR.rglob("*.html"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "template", TEMPLATES, ids=lambda path: str(path.relative_to(TEMPLATE_DIR))
)
def test_templates_do_not_load_libraries_from_cdns(template: Path) -> None:
    source = template.read_text(encoding="utf-8")

    assert not [host for host in CDN_HOSTS if host in source]


@pytest.mark.unit
@pytest.mark.parametrize(
    "template", TEMPLATES, ids=lambda path: str(path.relative_to(TEMPLATE_DIR))
)
def test_vendor_references_exist_and_load_static_tag(template: Path) -> None:
    source = template.read_text(encoding="utf-8")
    references = VENDOR_REFERENCE.findall(source)
    if not references:
        return

    assert "{% load static %}" in source
    assert [ref for ref in references if not (STATIC_DIR / ref).is_file()] == []


@pytest.mark.unit
def test_vendored_assets_keep_source_maps_for_manifest_storage() -> None:
    vendor_dir = STATIC_DIR / "vendor"
    pattern = re.compile(r"sourceMappingURL=(\S+?)\s*(?:\*/)?$", re.MULTILINE)
    missing = []
    for asset in [*vendor_dir.rglob("*.js"), *vendor_dir.rglob("*.css")]:
        for target in pattern.findall(asset.read_text(encoding="utf-8")):
            if not (asset.parent / target).is_file():
                missing.append(f"{asset.relative_to(vendor_dir)} -> {target}")

    assert missing == []
