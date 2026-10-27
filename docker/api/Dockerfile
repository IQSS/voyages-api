###
### Python 3.9 slim
###

# -- Base --

FROM python:3.9-slim AS base

RUN apt-get update -y \
    && apt-get install --yes --no-upgrade --no-install-recommends \
	    default-libmysqlclient-dev \
    && apt-get clean \
    && rm -rf \
        /tmp/* \
        /usr/share/doc/* \
        /var/cache/apt/* \
        /var/lib/apt/lists/* \
        /var/tmp/*

# -- Build --

FROM base AS build

RUN apt-get update -y \
    && apt-get install --yes --no-upgrade --no-install-recommends \
	    build-essential \
    && apt-get clean \
    && rm -rf \
        /tmp/* \
        /usr/share/doc/* \
        /var/cache/apt/* \
        /var/lib/apt/lists/* \
        /var/tmp/*

WORKDIR /srv/voyages-api

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r ./requirements.txt

# -- Release --

FROM base AS release

WORKDIR /srv/voyages-api

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

COPY --from=build /root/.local /root/.local
COPY . .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--reload", "--workers", "3", "--threads", "2", "--worker-class", "gthread", "voyages3.wsgi"]
