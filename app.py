import os

from flask import Flask, send_file, render_template
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField

from extract_data import extract_excel_file

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

app.config["SECRET_KEY"] = "LJg5vQJrbC9P9g"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "data.sqlite")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


class AccountForm(FlaskForm):
    acct = StringField("Enter your tax account number: ")
    street = StringField("Enter you street name, ex. Wall: ")
    zip_code = StringField("Enter your zip code: ")
    submit = SubmitField("Submit")


@app.route("/", methods=["GET", "POST"])
def index():
    acct = False
    street = False
    zip_code = False

    form = AccountForm()

    if form.validate_on_submit():
        acct = form.acct.data
        street = form.street.data
        zip_code = form.zip_code.data
        basedir = os.path.abspath(os.path.dirname(__file__))

        empty_str = ""
        if (acct is not empty_str or street is not empty_str or zip_code is not empty_str):
            file_name = extract_excel_file(acct, street, zip_code)
            return send_file(os.path.join(basedir, "Exports", file_name), as_attachment=True)

    return render_template("index.html", form=form)


# Extract function


if __name__ == "__main__":
    app.run(port=8000)
