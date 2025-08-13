import os
import threading
import time
from pathlib import Path

from flask import Flask, send_file, render_template, flash, abort
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import Optional

from extract_data import extract_excel_file

BASE_DIR = Path(os.path.abspath(os.path.dirname(__file__)))

app = Flask(__name__)
app.config["SECRET_KEY"] = "LJg5vQJrbC9P9g"


class AccountForm(FlaskForm):
    acct = StringField("Tax Account Number", validators=[Optional()], 
                      render_kw={"placeholder": "Enter account number (optional)"})
    street = StringField("Street Name", validators=[Optional()], 
                        render_kw={"placeholder": "Enter street name (optional)"})
    zip_code = StringField("Zip Code", validators=[Optional()], 
                          render_kw={"placeholder": "Enter zip code (optional)"})
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

    if form.validate_on_submit():
        acct = form.acct.data or ""
        street = form.street.data or ""
        zip_code = form.zip_code.data or ""
        
        # At least one field must be provided
        if not any([acct.strip(), street.strip(), zip_code.strip()]):
            flash("Please enter at least one search criteria.", "warning")
            return render_template("index.html", form=form)

        try:
            file_path = extract_excel_file(acct, street, zip_code)
            
            if not os.path.exists(file_path):
                flash("No data found for your search criteria.", "info")
                return render_template("index.html", form=form)
            
            # Schedule file deletion after download
            delete_file_later(file_path, delay_seconds=60)
            
            return send_file(file_path, as_attachment=True, 
                           download_name=os.path.basename(file_path))
            
        except Exception as e:
            flash(f"Error generating report: {str(e)}", "error")
            return render_template("index.html", form=form)

    return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
