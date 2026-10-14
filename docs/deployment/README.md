# Deployment Guide

This project ships with a containerized local deployment model and a CI workflow for pull requests and main-branch pushes.

## Local stack

Use Docker Compose to stand up the full application in one command:

```bash
docker compose up --build
```

The stack includes:
- frontend on http://localhost:5173
- backend API on http://localhost:8000
- PostgreSQL on localhost:5432
- Redis on localhost:6379
- NGINX on http://localhost

## Smoke checks

After startup, verify the core services are healthy:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
curl http://localhost:5173
```

A successful deployment should return HTTP 200 responses from the backend health endpoints and the frontend should render the application shell.

## CI validation

The GitHub Actions workflow runs:
- backend dependency installation
- backend pytest suite
- frontend dependency installation
- frontend production build

This keeps both the API and the UI aligned with the same release gate before merge.

## Production notes

For production deployment, consider:
- replacing the local filesystem storage with an object store such as S3 or MinIO
- moving secrets into environment-backed configuration instead of committed `.env` files
- enabling TLS termination at the ingress layer or reverse proxy
- establishing backup and retention policies for PostgreSQL and generated datasets
- adding a dedicated monitoring and alerting layer for API latency, worker health, and storage usage
