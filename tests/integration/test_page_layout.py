"""Every page renders through base.html as one well-formed document with the shared assets."""

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "Main" / "templates"
FRAGMENTS = {"header.html", "footer.html"}
INCLUDE_ONLY = {
    "accounts/admin_setup.html",
    "accounts/signup.html",
    "registration/login.html",
    "registration/password_change_form.html",
}

ANONYMOUS_PAGES = ["login", "signup", "index", "introduction"]
AUTHENTICATED_PAGES = [
    "index",
    "introduction",
    "market_search",
    "yahuoku",
    "yahuoku_now",
    "yahuoku_history",
    "Deep_Analysis",
    "Deep_Analysis_now",
    "Yahuoku_prediction",
    "developer_dashboard",
    "seller_management",
    "seller_outcomes_page",
    "notifications_page",
    "alert_rules_page",
    "profile",
    "password_change",
    "password_change_done",
]
EMBEDDED_PAGES = ["yahuoku", "yahuoku_now", "yahuoku_history"]


def _page_templates():
    for path in sorted(TEMPLATE_DIR.rglob("*.html")):
        relative = path.relative_to(TEMPLATE_DIR).as_posix()
        if relative in FRAGMENTS | INCLUDE_ONLY or relative.startswith("base"):
            continue
        yield relative


@pytest.mark.parametrize("template", list(_page_templates()))
def test_page_templates_extend_the_shared_base(template):
    source = (TEMPLATE_DIR / template).read_text(encoding="utf-8")

    assert source.startswith(
        ("{% extends 'base.html' %}", "{% extends 'base_with_footer.html' %}")
    ), template
    assert not re.search(r"<(!DOCTYPE|html|head|body)\b", source, re.IGNORECASE), template
    assert "bootstrap.bundle.min.js" not in source
    assert "alert(" not in source


@pytest.mark.parametrize("fragment", sorted(FRAGMENTS))
def test_header_and_footer_are_markup_fragments(fragment):
    source = (TEMPLATE_DIR / fragment).read_text(encoding="utf-8")

    assert not re.search(r"<(!DOCTYPE|html|head|body|style)\b", source, re.IGNORECASE)


def test_page_scripts_use_in_page_feedback_instead_of_browser_dialogs():
    script_dir = TEMPLATE_DIR.parent / "static" / "JS"
    offenders = [
        path.name
        for path in script_dir.glob("*.js")
        if path.name != "Feedback.js"
        and re.search(r"(?<![.\w])alert\(|document\.write\(", path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def _assert_single_document(response, *, with_header=True):
    html = response.content.decode("utf-8")
    for tag in ("<!DOCTYPE", "<html", "<head>", "<body", "</body>", "</html>"):
        assert html.count(tag) == 1, (response.request["PATH_INFO"], tag, html.count(tag))
    assert html.count("bootstrap.bundle.min.js") == 1
    assert html.count("JS/Feedback.js") == 1
    assert html.count("JS/ClientErrors.js") == 1
    assert ("navbar-custom" in html) is with_header
    return html


@pytest.mark.django_db
@pytest.mark.parametrize("name", ANONYMOUS_PAGES)
def test_anonymous_pages_render_one_document(client, name):
    response = client.get(reverse(name))

    assert response.status_code == 200
    _assert_single_document(response)


@pytest.mark.django_db
@pytest.mark.parametrize("name", AUTHENTICATED_PAGES)
def test_authenticated_pages_render_one_document(client, name):
    user = get_user_model().objects.create_user("layout", password="password", is_staff=True)
    client.force_login(user)

    response = client.get(reverse(name))

    assert response.status_code == 200
    _assert_single_document(response)


@pytest.mark.django_db
@pytest.mark.parametrize("name", EMBEDDED_PAGES)
def test_embedded_pages_omit_header_and_footer(client, name):
    response = client.get(f"{reverse(name)}?embedded=1")

    html = _assert_single_document(response, with_header=False)
    assert "<footer" not in html


@pytest.mark.django_db
def test_error_page_renders_through_the_base_template(client):
    response = client.get("/taskle/no-such-page")

    assert response.status_code == 404
    _assert_single_document(response)
