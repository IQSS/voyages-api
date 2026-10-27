# -- Build --

FROM python:3.9-slim AS build

WORKDIR /srv/voyages-stats

COPY requirements.txt .

RUN pip install --user --no-cache-dir -r ./requirements.txt

# -- Release

FROM python:3.9-slim AS release

WORKDIR /srv/voyages-stats

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

COPY --from=build /root/.local /root/.local

COPY . .

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]