FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
COPY fmsi_un_recommendations ./fmsi_un_recommendations
COPY prompts ./prompts
RUN uv sync --frozen --no-dev

COPY . .
ENV PYTHONPATH=/app

CMD ["uv", "run", "app"]
