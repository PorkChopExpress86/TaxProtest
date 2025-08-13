import os
import threading
import time
from pathlib import Path

from flask import Flask, send_file, render_template, flash, session, request, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import Optional

from extract_data import extract_excel_file, search_properties

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))

app = Flask(__name__)
# Use environment variable for security, fallback to dev key
app.config["SECRET_KEY"] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')


class AccountForm(FlaskForm):
    acct = StringField("Tax Account Number", validators=[Optional()], 
                      render_kw={"placeholder": "Enter account number (optional)"})
    street = StringField("Street Name", validators=[Optional()], 
                        render_kw={"placeholder": "Enter street name (optional)"})
    zip_code = StringField("Zip Code", validators=[Optional()], 
                          render_kw={"placeholder": "Enter zip code (optional)"})
    exact_match = BooleanField("Exact street name match", default=False)
    submit = SubmitField("Search Properties")


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
    form = AccountForm()
    results = None
    search_params = None

    if form.validate_on_submit():
        acct = form.acct.data or ""
        street = form.street.data or ""
        zip_code = form.zip_code.data or ""
        exact_match = form.exact_match.data
        
        # At least one field must be provided
        if not any([acct.strip(), street.strip(), zip_code.strip()]):
            flash("Please enter at least one search criteria.", "warning")
            return render_template("index.html", form=form)

        try:
            # Search for properties and return results for display
            results = search_properties(acct, street, zip_code, exact_match)
            search_params = {'acct': acct, 'street': street, 'zip_code': zip_code, 'exact_match': exact_match}
            
            # Debug: Log search parameters and results count
            match_type = "exact" if exact_match else "partial"
            print(f"Search params - Account: '{acct}', Street: '{street}', Zip: '{zip_code}' (Match: {match_type})")
            print(f"Found {len(results)} results")
            if results:
                print(f"First result: {results[0]}")
            
            if not results:
                flash("No properties found matching your search criteria. Try using partial names or different spelling.", "info")
            else:
                flash(f"Found {len(results)} properties matching your search.", "success")
                # Store search params in session for download
                session['last_search'] = search_params
            
        except Exception as e:
            flash(f"Error searching properties: {str(e)}", "error")

    return render_template("index.html", form=form, results=results, search_params=search_params)


@app.route("/download")
def download():
    """Download the last search results as CSV"""
    if 'last_search' not in session:
        flash("No search results to download. Please perform a search first.", "warning")
        return redirect(url_for('index'))
    
    try:
        params = session['last_search']
        exact_match = params.get('exact_match', False)
        file_path = extract_excel_file(params['acct'], params['street'], params['zip_code'], exact_match)
        
        if not os.path.exists(file_path):
            flash("Error generating download file.", "error")
            return redirect(url_for('index'))
        
        # Schedule file deletion after download
        delete_file_later(file_path, delay_seconds=60)
        
        return send_file(file_path, as_attachment=True, 
                       download_name=os.path.basename(file_path))
        
    except Exception as e:
        flash(f"Error generating download: {str(e)}", "error")
        return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
