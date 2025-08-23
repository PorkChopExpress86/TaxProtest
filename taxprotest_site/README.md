Minimal Django scaffold to iterate a migration from Flask.

To run the minimal project locally:

1. Create a virtualenv and install Django

   python -m venv .venv
   .\.venv\Scripts\activate
   pip install django

2. Run the development server

   python manage.py runserver

This scaffold intentionally leaves models/services thin and reuses existing logic in `src/taxprotest/comparables` until a full migration is implemented.
