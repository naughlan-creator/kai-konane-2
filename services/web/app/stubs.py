"""Placeholders for endpoints not yet ported from the api.

Templates were written against the full route set, and `url_for` raises
BuildError for an endpoint that does not exist -- so a single shared nav bar
naming `admin.admin_home` stops *every* page rendering until that blueprint is
ported. This registers a placeholder for each missing endpoint so the site stays
clickable throughout the migration.

Self-erasing: the list is derived from the templates themselves, and an endpoint
stops being stubbed the moment a real route claims it. With Phase 5 complete
this registers nothing, and the module can be deleted.
"""
import re
from pathlib import Path

from flask import render_template_string

URL_FOR = re.compile(r"url_for\(\s*['\"]([a-z_]+\.[a-z_0-9]+)['\"]")

PAGE = """<!doctype html>
<title>Not ported yet</title>
<h1>Not ported yet</h1>
<p><code>{{ endpoint }}</code> still lives in the api service.</p>
<p><a href="/">Back</a></p>
"""


def _referenced_endpoints(template_dir):
    found = set()
    for path in Path(template_dir).rglob('*.html'):
        found.update(URL_FOR.findall(path.read_text(encoding='utf-8', errors='ignore')))
    return found


def register_stubs(app):
    """Add a placeholder for every referenced endpoint with no real view.

    Must run *after* every real blueprint is registered, or it will stub an
    endpoint that already exists.
    """
    stubbed = []
    for endpoint in sorted(_referenced_endpoints(app.template_folder)):
        if endpoint in app.view_functions:
            continue

        def view(endpoint=endpoint, **kwargs):
            return render_template_string(PAGE, endpoint=endpoint), 501

        # A dotted endpoint name registered straight on the app is what makes
        # url_for('user.signup') resolve without the 'user' blueprint owning it.
        app.add_url_rule(f'/_stub/{endpoint}', endpoint=endpoint, view_func=view,
                         methods=['GET', 'POST'])
        stubbed.append(endpoint)

    if stubbed:
        app.logger.warning("%d endpoints still stubbed: %s",
                           len(stubbed), ', '.join(stubbed))
    return stubbed
