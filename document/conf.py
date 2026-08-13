import os
import sys

import django

sys.path.insert(0, os.path.abspath("../"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "System_Config.settings")
django.setup()

language = "ja"


project = "Systema"
copyright = "2025-2026, Wataru Tezuka"
author = "WataruTezuka"
release = "1.0.0"

templates_path = ["_templates"]
exclude_patterns = ["build", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_title = "Systema Documentation"
html_static_path = []

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
master_doc = "index"
