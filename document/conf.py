import django
import os
import sys

sys.path.insert(0, os.path.abspath('../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'System_Config.settings')
django.setup()

language = 'ja'


project = 'systema'
copyright = '2025, WataruTezuka'
author = 'WataruTezuka'
release = '1.0.0'

templates_path = ['_templates']
exclude_patterns = []
html_theme = 'sphinx_rtd_theme'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'myst_parser',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
master_doc = 'index'
source_dir = '.'

# ドキュメント生成のコマンドsphinx-build -b html document/ document/build/html
