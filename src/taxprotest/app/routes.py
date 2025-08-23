from __future__ import annotations

import os
import threading
import time
from typing import Any

from flask import (
    Blueprint,
    render_template,
    flash,
    session,
    request,
    redirect,
    url_for,
    send_file,
)
from markupsafe import Markup, escape
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import Optional

from extract_data import extract_excel_file, search_properties
from taxprotest.comparables import find_comps, export_comparables

bp = Blueprint("main", __name__)


class AccountForm(FlaskForm):  # type: ignore[misc]
    acct = StringField(
        "Tax Account Number",
        validators=[Optional()],
        render_kw={"placeholder": "Enter account number (optional)"},
    )
    owner = StringField(
        "Owner Name",
        validators=[Optional()],
        render_kw={"placeholder": "Enter owner name (optional, partial OK)"},
    )
    street = StringField(
        "Street Name",
        validators=[Optional()],
        render_kw={"placeholder": "Enter street name (optional)"},
    )
    zip_code = StringField(
        "Zip Code",
        validators=[Optional()],
        render_kw={"placeholder": "Enter zip code (optional)"},
    )
    exact_match = BooleanField("Exact street name match", default=False)
    submit = SubmitField("Search Properties")


def _highlight(text: str, needle: str):
    if not text:
        return ""
    if not needle:
        return escape(text)
    import re

    pattern = re.escape(needle)

    def repl(m: Any):  # pragma: no cover - trivial
        return f"<mark>{escape(m.group(0))}</mark>"

    return Markup(re.sub(pattern, repl, text, flags=re.IGNORECASE))


def register_template_filters(app):  # type: ignore[no-untyped-def]
    app.jinja_env.filters["highlight"] = _highlight


def _delete_file_later(file_path: str, delay_seconds: int = 30) -> None:
    def delete_after_delay():  # pragma: no cover - side-effect timing
        time.sleep(delay_seconds)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    threading.Thread(target=delete_after_delay, daemon=True).start()


@bp.route("/", methods=["GET", "POST"])
def index():  # type: ignore[no-untyped-def]
    form = AccountForm()
    ALLOWED_PAGE_SIZES = [25, 50, 100, 200]
    DEFAULT_PAGE_SIZE = 50

    if request.method == "POST" and form.validate_on_submit():
        acct = (form.acct.data or "").strip()
        owner = (form.owner.data or "").strip()
        street = (form.street.data or "").strip()
        zip_code = (form.zip_code.data or "").strip()
        exact_match = form.exact_match.data
        try:
            posted_page_size = int(request.form.get("page_size", DEFAULT_PAGE_SIZE))
        except ValueError:
            posted_page_size = DEFAULT_PAGE_SIZE
        if posted_page_size not in ALLOWED_PAGE_SIZES:
            posted_page_size = DEFAULT_PAGE_SIZE
        if not any([acct, owner, street, zip_code]):
            flash("Please enter at least one search criteria.", "warning")
            return render_template("index.html", form=form, results=None, search_params=None)
        return redirect(
            url_for(
                "main.index",
                acct=acct,
                owner=owner,
                street=street,
                zip_code=zip_code,
                exact_match=int(bool(exact_match)),
                page=1,
                page_size=posted_page_size,
            )
        )

    acct = request.args.get("acct", "").strip()
    owner = request.args.get("owner", "").strip()
    street = request.args.get("street", "").strip()
    zip_code = request.args.get("zip_code", "").strip()
    exact_match = request.args.get("exact_match", "").strip() in {"1", "true", "True"}
    form.acct.data = acct
    form.owner.data = owner
    form.street.data = street
    form.zip_code.data = zip_code
    form.exact_match.data = exact_match

    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    try:
        page_size = int(request.args.get("page_size", DEFAULT_PAGE_SIZE))
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = DEFAULT_PAGE_SIZE

    results = None
    total = 0
    total_pages = 0
    search_params = None

    if any([acct, owner, street, zip_code]):
        try:
            all_results = search_properties(acct, street, zip_code, owner, exact_match)
            total = len(all_results)
            if total == 0:
                flash(
                    "No properties found matching your search criteria. Try using partial names or different spelling.",
                    "info",
                )
            else:
                flash(f"Found {total} properties matching your search.", "success")
            total_pages = max(1, (total + page_size - 1) // page_size)
            if page > total_pages:
                page = total_pages
            start = (page - 1) * page_size
            end = start + page_size
            results = all_results[start:end]
            search_params = {
                "acct": acct,
                "owner": owner,
                "street": street,
                "zip_code": zip_code,
                "exact_match": exact_match,
            }
            session["last_search"] = {
                **search_params,
                "page": page,
                "total": total,
                "page_size": page_size,
            }
        except Exception as e:  # pragma: no cover - defensive logging path
            flash(f"Error searching properties: {e}", "error")

    return render_template(
        "index.html",
        form=form,
        results=results,
        search_params=search_params,
        page=page,
        total=total,
        total_pages=total_pages,
        page_size=page_size,
        allowed_page_sizes=ALLOWED_PAGE_SIZES,
    )


@bp.route("/download")
def download():  # type: ignore[no-untyped-def]
    if "last_search" not in session:
        flash("No search results to download. Please perform a search first.", "warning")
        return redirect(url_for("main.index"))
    try:
        params = session["last_search"]
        exact_match = params.get("exact_match", False)
        file_path = extract_excel_file(
            params.get("acct", ""),
            params.get("street", ""),
            params.get("zip_code", ""),
            exact_match,
            params.get("owner", ""),
        )
        if not os.path.exists(file_path):
            flash("Error generating download file.", "error")
            return redirect(url_for("main.index"))
        _delete_file_later(file_path, delay_seconds=60)
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))
    except Exception as e:  # pragma: no cover - defensive
        flash(f"Error generating download: {e}", "error")
        return redirect(url_for("main.index"))


@bp.route("/comparables/<acct>")
def comparables(acct: str):  # type: ignore[no-untyped-def]
    try:
        try:
            max_comps = int(request.args.get("max", "25"))
        except ValueError:
            max_comps = 25
        try:
            min_comps = int(request.args.get("min", "20"))
        except ValueError:
            min_comps = 20
        if min_comps > max_comps:
            min_comps = max_comps
        try:
            max_radius = request.args.get("max_radius")
            max_radius_f = float(max_radius) if max_radius not in (None, "", "0") else None
        except ValueError:
            max_radius_f = None
        radius_first_strict = request.args.get("strict_first", "0") in {"1", "true", "True"}
        result = find_comps(
            acct,
            max_comps=max_comps,
            min_comps=min_comps,
            radius_first_strict=radius_first_strict,
            max_radius=max_radius_f,
        )
        subject = result.get("subject")
        comps = result.get("comps", [])
        meta = result.get("meta", {})
        if not comps:
            flash("No comparables found with current criteria.", "info")
        return render_template(
            "comparables.html",
            acct=acct,
            subject=subject,
            comparables=comps,
            meta=meta,
            cfg={
                "max": max_comps,
                "min": min_comps,
                "max_radius": max_radius_f,
                "strict_first": radius_first_strict,
            },
        )
    except Exception as e:  # pragma: no cover - defensive
        flash(f"Error finding comparables: {e}", "error")
        return redirect(url_for("main.index"))


@bp.route("/comparables/<acct>/export")
def export_comparables_route(acct: str):  # type: ignore[no-untyped-def]
    fmt = request.args.get("fmt", "csv").lower()
    if fmt not in ("csv", "xlsx"):
        fmt = "csv"
    try:
        max_comps = int(request.args.get("max", "25")) if request.args.get("max") else 25
        min_comps = int(request.args.get("min", "20")) if request.args.get("min") else 20
        if min_comps > max_comps:
            min_comps = max_comps
        max_radius_arg = request.args.get("max_radius")
        try:
            max_radius_f = float(max_radius_arg) if max_radius_arg not in (None, "") else None
        except ValueError:
            max_radius_f = None
        radius_first_strict = request.args.get("strict_first", "0") in {"1", "true", "True"}
        result = find_comps(
            acct,
            max_comps=max_comps,
            min_comps=min_comps,
            radius_first_strict=radius_first_strict,
            max_radius=max_radius_f,
        )
        subject = result.get("subject", {})
        comps = result.get("comps", [])
        if not comps:
            flash("No comparables to export.", "info")
            return redirect(url_for("main.comparables", acct=acct))
        fpath = export_comparables(subject, comps, fmt=fmt)
        if not os.path.exists(fpath):
            flash("Export failed to create file", "error")
            return redirect(url_for("main.comparables", acct=acct))
        _delete_file_later(fpath, delay_seconds=120)
        return send_file(fpath, as_attachment=True, download_name=os.path.basename(fpath))
    except Exception as e:  # pragma: no cover
        flash(f"Error exporting comparables: {e}", "error")
        return redirect(url_for("main.comparables", acct=acct))


# Simple health endpoint for container orchestrators (K8s, ECS, etc.)
@bp.route("/health")
def health():  # type: ignore[no-untyped-def]
    return {"status": "ok"}
