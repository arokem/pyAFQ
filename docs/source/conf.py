# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

from plotly.io._sg_scraper import plotly_sg_scraper
from AFQ.utils.docs import PNGScraper

import sys
import os
import AFQ

sys.path.insert(0, os.path.abspath('.'))
sys.path.append(os.path.abspath('sphinxext'))


# -- Project information -----------------------------------------------------

project = 'AFQ'
copyright = '2018--, The pyAFQ Contributors'
author = ''

# The short X.Y version
version = ''
# The full version, including alpha/beta/rc tags
release = AFQ.__version__


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx_gallery.gen_gallery',
    'sphinx_design',
    'sphinx.ext.autosummary',
    'autoapi.extension',
    'numpydoc',
    'updatedocs',
    'kwargsdocs',
    'methodsdocs',
    'myst_nb',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = 'alabaster'
html_theme = 'pydata_sphinx_theme'

# Added theme configuration. See: https://pydata-sphinx-theme.readthedocs.io/
html_logo = "_static/logo.png"

html_sidebars = {
    "**": ["search-field", "sidebar-nav-bs", "globaltoc.html"]
}
html_theme_options = {
    "use_edit_page_button": True,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/yeatmanlab/pyAFQ",
            "icon": "fab fa-github-square",
        }]

}

html_sidebars = {
    "**": ['search-field.html', 'sidebar-nav-bs.html'],
}

html_context = {
    "github_url": "https://github.com",
    "github_user": "yeatmanlab",
    "github_repo": "pyAFQ",
    "github_version": "master",
    "doc_path": "docs/source",
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}

# html_css_files = [
#     'css/custom.css'
# ]

html_css_files = ['custom.css']

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'pyAFQdoc'


# -- Options for LaTeX output ------------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'pyAFQ.tex', 'pyAFQ Documentation',
     'Ariel Rokem', 'manual'),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'pyafq', 'pyAFQ Documentation',
     [author], 1)
]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'pyAFQ', 'pyAFQ Documentation',
     author, 'pyAFQ', 'One line description of project.',
     'Miscellaneous'),
]


# -- Extension configuration -------------------------------------------------

# -- Options for intersphinx extension ---------------------------------------

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'python': ('https://docs.python.org/3/', None),
                       'numpy': ('https://docs.scipy.org/doc/numpy/', None),
                       'dipy': ('https://dipy.org/documentation/latest',
                                'https://dipy.org/documentation/1.4.1./objects.inv/')
                       }

image_scrapers = ('matplotlib', plotly_sg_scraper, PNGScraper())

from _progressbars import reset_progressbars  # noqa

sphinx_gallery_conf = {
    # path to your examples scripts
    'examples_dirs': ['../../examples/howto_examples',
                      '../../examples/tutorial_examples'],
    # path where to save gallery generated examples
    'gallery_dirs': ['howto/howto_examples', 'tutorials/tutorial_examples'],
    'ignore_pattern': 'plot_baby_afq.py',  # noqa
    'image_scrapers': image_scrapers,
    'reset_modules': (reset_progressbars),
    'show_memory': True,
}

# Auto API
autoapi_type = 'python'
autoapi_dirs = ['../../AFQ']
autoapi_ignore = ['*test*', '*_fixes*', '*version*', 'pyAFQ', 'License']
autoapi_root = 'reference/api'
