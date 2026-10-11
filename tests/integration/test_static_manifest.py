"""Production static storage must build a manifest that covers every template reference."""

import re
from pathlib import Path

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import override_settings

from System_Config.static_storage import build_storages

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "Main" / "templates"
STATIC_REFERENCE = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""")


def test_collectstatic_manifest_resolves_every_template_static_reference(tmp_path):
    references = {
        reference
        for template in TEMPLATE_DIR.rglob("*.html")
        for reference in STATIC_REFERENCE.findall(template.read_text(encoding="utf-8"))
    }

    with override_settings(STORAGES=build_storages(debug=False), STATIC_ROOT=tmp_path):
        call_command("collectstatic", interactive=False, verbosity=0)
        hashed = {reference: staticfiles_storage.stored_name(reference) for reference in references}

    assert (tmp_path / "staticfiles.json").is_file()
    assert references
    assert [ref for ref, name in hashed.items() if name == ref] == []
    assert list(tmp_path.rglob("*.css.gz"))
