import os
import threading
import time
from pathlib import Path

from flask import Flask, send_file, render_template, flash, session, request, redirect, url_for
from markupsafe import Markup, escape
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import Optional

from extract_data import extract_excel_file, search_properties, find_comparables, find_comps, export_comparables

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))

app = Flask(__name__)
# Use environment variable for security, fallback to dev key
app.config["SECRET_KEY"] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')


class AccountForm(FlaskForm):
    acct = StringField("Tax Account Number", validators=[Optional()],
                      render_kw={"placeholder": "Enter account number (optional)"})
    owner = StringField("Owner Name", validators=[Optional()],
                        render_kw={"placeholder": "Enter owner name (optional, partial OK)"})
    street = StringField("Street Name", validators=[Optional()],
                        render_kw={"placeholder": "Enter street name (optional)"})
    zip_code = StringField("Zip Code", validators=[Optional()],
                          render_kw={"placeholder": "Enter zip code (optional)"})
    exact_match = BooleanField("Exact street name match", default=False)
    submit = SubmitField("Search Properties")


def highlight(text: str, needle: str):
    """Return HTML with case-insensitive matches of needle wrapped in <mark>."""
    if not text:
        return ""
    if not needle:
        return escape(text)
    import re
    pattern = re.escape(needle)
    def repl(m):
        return f"<mark>{escape(m.group(0))}</mark>"
    return Markup(re.sub(pattern, repl, text, flags=re.IGNORECASE))

app.jinja_env.filters['highlight'] = highlight


def delete_file_later(file_path: str, delay_seconds: int = 30):
    """Delete file after a delay in a background thread"""
    def delete_after_delay():
        time.sleep(delay_seconds)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted export file: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
    
    thread = threading.Thread(target=delete_after_delay, daemon=True)
    thread.start()


@app.route("/", methods=["GET", "POST"])
def index():
    """Search & result page with pagination via query params."""
    form = AccountForm()
    ALLOWED_PAGE_SIZES = [25, 50, 100, 200]
    DEFAULT_PAGE_SIZE = 50

    # POST -> validate then redirect to GET (PRG pattern) to avoid resubmits
    if request.method == 'POST' and form.validate_on_submit():
        acct = (form.acct.data or '').strip()
        owner = (form.owner.data or '').strip()
        street = (form.street.data or '').strip()
        zip_code = (form.zip_code.data or '').strip()
        exact_match = form.exact_match.data
        try:
            posted_page_size = int(request.form.get('page_size', DEFAULT_PAGE_SIZE))
        except ValueError:
            posted_page_size = DEFAULT_PAGE_SIZE
        if posted_page_size not in ALLOWED_PAGE_SIZES:
            posted_page_size = DEFAULT_PAGE_SIZE
        if not any([acct, owner, street, zip_code]):
            flash("Please enter at least one search criteria.", "warning")
            return render_template("index.html", form=form, results=None, search_params=None)
        # Redirect with query params
        return redirect(url_for('index', acct=acct, owner=owner, street=street, zip_code=zip_code,
                                exact_match=int(bool(exact_match)), page=1, page_size=posted_page_size))

    # For GET populate form from query args
    acct = request.args.get('acct', '').strip()
    owner = request.args.get('owner', '').strip()
    street = request.args.get('street', '').strip()
    zip_code = request.args.get('zip_code', '').strip()
    exact_match = request.args.get('exact_match', '').strip() in {'1', 'true', 'True'}
    form.acct.data = acct
    form.owner.data = owner
    form.street.data = street
    form.zip_code.data = zip_code
    form.exact_match.data = exact_match

    page = 1
    try:
        page = max(1, int(request.args.get('page', '1')))
    except ValueError:
        page = 1

    results = None
    total = 0
    total_pages = 0
    search_params = None
    # Page size handling
    try:
        page_size = int(request.args.get('page_size', DEFAULT_PAGE_SIZE))
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = DEFAULT_PAGE_SIZE

    if any([acct, owner, street, zip_code]):
        try:
            all_results = search_properties(acct, street, zip_code, owner, exact_match)
            total = len(all_results)
            if total == 0:
                flash("No properties found matching your search criteria. Try using partial names or different spelling.", "info")
            else:
                flash(f"Found {total} properties matching your search.", "success")
            total_pages = max(1, (total + page_size - 1) // page_size)
            if page > total_pages:
                page = total_pages
            start = (page - 1) * page_size
            end = start + page_size
            results = all_results[start:end]
            search_params = {
                'acct': acct,
                'owner': owner,
                'street': street,
                'zip_code': zip_code,
                'exact_match': exact_match,
            }
            # Save for download (always keep full search params; re-run search on download)
            session['last_search'] = {**search_params, 'page': page, 'total': total, 'page_size': page_size}
        except Exception as e:
            flash(f"Error searching properties: {str(e)}", "error")

    return render_template("index.html", form=form, results=results, search_params=search_params,
                           page=page, total=total, total_pages=total_pages, page_size=page_size,
                           allowed_page_sizes=ALLOWED_PAGE_SIZES)


@app.route("/download")
def download():
    """Download the last search results as Excel (.xlsx) or CSV fallback"""
    if 'last_search' not in session:
        flash("No search results to download. Please perform a search first.", "warning")
        return redirect(url_for('index'))
    
    try:
        params = session['last_search']
        exact_match = params.get('exact_match', False)
        file_path = extract_excel_file(params.get('acct',''), params.get('street',''), params.get('zip_code',''), exact_match, params.get('owner',''))

        if not os.path.exists(file_path):
            flash("Error generating download file.", "error")
            return redirect(url_for('index'))

        delete_file_later(file_path, delay_seconds=60)
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))
    except Exception as e:
        flash(f"Error generating download: {e}", "error")
        return redirect(url_for('index'))

@app.route("/comparables/<acct>")
def comparables(acct: str):
    try:
        # User-configurable overrides via query string
        try:
            max_comps = int(request.args.get('max', '25'))
        except ValueError:
            max_comps = 25
        try:
            min_comps = int(request.args.get('min', '20'))
        except ValueError:
            min_comps = 20
        if min_comps > max_comps:
            min_comps = max_comps
        try:
            max_radius = request.args.get('max_radius')
            max_radius_f = float(max_radius) if max_radius not in (None, '', '0') else None
        except ValueError:
            max_radius_f = None
        radius_first_strict = request.args.get('strict_first', '0') in {'1','true','True'}

        result = find_comps(acct,
                             max_comps=max_comps,
                             min_comps=min_comps,
                             radius_first_strict=radius_first_strict,
                             max_radius=max_radius_f)
        subject = result.get('subject')
        comps = result.get('comps', [])
        meta = result.get('meta', {})
        if not comps:
            flash("No comparables found with current criteria.", "info")
        return render_template("comparables.html", acct=acct, subject=subject, comparables=comps, meta=meta,
                               cfg={'max':max_comps,'min':min_comps,'max_radius':max_radius_f,'strict_first':radius_first_strict})
    except Exception as e:
        flash(f"Error finding comparables: {e}", "error")
        return redirect(url_for('index'))


@app.route("/comparables/<acct>/export")
def export_comparables_route(acct: str):
    fmt = request.args.get('fmt','xlsx').lower()
    if fmt not in ('xlsx','csv'):
        fmt = 'xlsx'
    try:
        # Mirror query params used in comparables route
        max_comps = int(request.args.get('max','25')) if request.args.get('max') else 25
        min_comps = int(request.args.get('min','20')) if request.args.get('min') else 20
        if min_comps > max_comps: min_comps = max_comps
        max_radius_arg = request.args.get('max_radius')
        try:
            max_radius_f = float(max_radius_arg) if max_radius_arg not in (None,'') else None
        except ValueError:
            max_radius_f = None
        radius_first_strict = request.args.get('strict_first','0') in {'1','true','True'}
        fpath = export_comparables(acct,
                                   max_comps=max_comps,
                                   min_comps=min_comps,
                                   radius_first_strict=radius_first_strict,
                                   max_radius=max_radius_f,
                                   file_format=fmt)
        if not os.path.exists(fpath):
            flash('Export failed to create file','error')
            return redirect(url_for('comparables', acct=acct))
        delete_file_later(fpath, delay_seconds=120)
        return send_file(fpath, as_attachment=True, download_name=os.path.basename(fpath))
    except Exception as e:
        flash(f'Error exporting comparables: {e}','error')
        return redirect(url_for('comparables', acct=acct))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
