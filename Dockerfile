# Stage 1: build the React app
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Django API + the built SPA (single process, single port)
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=web /web/dist frontend/dist
ENV DEBUG=0 DATABASE_URL=sqlite:////app/data/aramana.sqlite3 GROUND_TRUTH_PATH=/app/data/ground_truth.json
RUN mkdir -p data && cd backend && python manage.py migrate -v0 && python manage.py seed_demo --detect
WORKDIR /app/backend
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "-b", "0.0.0.0:8000", "--workers", "2"]
