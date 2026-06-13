FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY src/ ./src/
COPY .env ./

EXPOSE 8000

CMD ["uv", "run", "dingding-spreadsheet"]
