FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir pip setuptools wheel
RUN pip install --no-cache-dir django psycopg-binary
ENV DJANGO_SETTINGS_MODULE=taxprotest_site.settings
CMD ["gunicorn", "taxprotest_site.wsgi:application", "-b", "0.0.0.0:8000"]
