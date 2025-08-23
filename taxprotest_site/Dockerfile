FROM python:3.13-slim
WORKDIR /app
COPY . /app
# Install system packages needed for GeoDjango (GDAL, GEOS, PROJ) and build deps
RUN apt-get update \
	 && apt-get install -y --no-install-recommends \
		 gdal-bin libgdal-dev libgeos-dev libproj-dev \
		 build-essential \
	 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pip setuptools wheel
RUN pip install --no-cache-dir django gunicorn
# Install the project's pinned requirements to keep image in sync with repo
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
ENV DJANGO_SETTINGS_MODULE=taxprotest_site.taxprotest_site.settings
ENV PYTHONPATH=/app
WORKDIR /app/taxprotest_site
CMD ["gunicorn", "taxprotest_site.wsgi:application", "-b", "0.0.0.0:8000"]
