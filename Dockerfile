# ---------- Frontend build stage ----------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
COPY VERSION ../VERSION
RUN npm run build

# ---------- Backend runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SYNC_MONITOR_DATA_DIR=/data \
    SYNC_MONITOR_FRONTEND_DIST=/app/frontend_dist

WORKDIR /app

COPY VERSION ./VERSION

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY --from=frontend-build /app/frontend/dist ./frontend_dist

COPY resources ./resources

RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
