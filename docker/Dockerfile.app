FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src
WORKDIR /app
COPY requirements/app.txt requirements/app.txt
RUN pip install -r requirements/app.txt
COPY src/ src/
COPY prompts/ prompts/
COPY contracts/ contracts/
COPY eval/ eval/
COPY tests/ tests/
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
