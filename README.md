<div align="center">
    <h1>MavuFlow Studio</h1>
    <p><strong>A practical workspace for exploring, transforming, and versioning datasets.</strong></p>
    <p>
        <a href="https://github.com/TshikhovhokhovhoPhathutshedzo/MavuFlow-Data-Engineering/actions/workflows/ci.yml"><img alt="CI status" src="https://img.shields.io/github/actions/workflow/status/TshikhovhokhovhoPhathutshedzo/MavuFlow-Data-Engineering/ci.yml?branch=main&label=CI"></a>
        <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
        <img alt="React and TypeScript" src="https://img.shields.io/badge/React-TypeScript-3178C6?logo=typescript&logoColor=white">
        <img alt="PostgreSQL" src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white">
    </p>
</div>

MavuFlow Studio combines dataset uploads, data quality insights, transformations, and repeatable pipelines in one full-stack application.

## What You Can Do

| Workspace | Capabilities |
| --- | --- |
| **Datasets** | Upload CSV and Excel `.xlsx` files, inspect metadata, and manage versions. |
| **Data preparation** | Clean columns, transform data, and preview the output. |
| **Code Lab** | Apply supported pandas and NumPy expressions; preview first, then explicitly save changes as a new dataset version. |
| **Pipelines** | Build and run ordered transformation workflows. |
| **Quality and exports** | Review dataset analytics and quality reports, then export results. |
| **Accounts** | Authenticated workspaces with user-scoped project and dataset access. |

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, TanStack Query |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Data processing | pandas, NumPy |
| Persistence | PostgreSQL; local filesystem storage for development |
| Background services | Celery and Redis |
| Local orchestration | Docker Compose and NGINX |

## Architecture

```mermaid
flowchart LR
        Person[User] --> Web[React and TypeScript]
        Web -->|REST API| API[FastAPI]
        API --> Auth[JWT authentication]
        API --> DB[(PostgreSQL)]
        API --> Files[Dataset storage]
        API --> Worker[Celery worker]
        Worker --> Redis[(Redis)]
        Worker --> Files
```

## Data Model

The diagram reflects the tables currently created by the application.

```mermaid
erDiagram
        USERS ||--o{ PROJECTS : owns
        USERS ||--o{ DATASETS : owns
        USERS ||--o{ AUTH_SESSIONS : signs_in
        USERS ||--o{ DATASET_VERSIONS : creates
        USERS ||--o{ STORED_FILES : uploads
        USERS ||--o{ PIPELINES : creates
        PROJECTS ||--o{ DATASETS : contains
        PROJECTS ||--o{ STORED_FILES : stores
        DATASETS ||--o{ DATASET_VERSIONS : versions
        DATASETS ||--o{ STORED_FILES : tracks
        DATASETS ||--o{ PIPELINES : processes
        PIPELINES ||--o{ PIPELINE_STEPS : contains
```

## Run Locally

### Option 1: Docker Compose

Requires Docker Desktop with Compose enabled.

```bash
git clone https://github.com/TshikhovhokhovhoPhathutshedzo/MavuFlow-Data-Engineering.git
cd MavuFlow-Data-Engineering
docker compose up --build
```

Open the frontend at [http://localhost:5173](http://localhost:5173). The API is at [http://localhost:8000](http://localhost:8000), with interactive API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

### Option 2: Run Frontend and API Separately

Requires Python 3.12 and Node.js 20 or newer. In one terminal:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Without a local backend `.env`, the API uses SQLite for development. Configure `DATABASE_URL`, `JWT_SECRET_KEY`, and `CORS_ORIGINS` through environment variables for a non-local deployment. Never commit `.env` files or production credentials.

## Deployment Notes

The included Compose stack runs the frontend, API, PostgreSQL, Redis, worker, and NGINX. See the [deployment guide](docs/deployment/README.md) for health checks and production notes.

Supabase can provide PostgreSQL and object storage, but it does not host this FastAPI service or the full React application. Deploy the frontend and API to application hosts, configure the API to use the Supabase database, and move uploaded files from local filesystem storage to persistent object storage before production use.

## CI

GitHub Actions runs the backend pytest suite and frontend production build on pushes to `main` and pull requests. See the [CI workflow](.github/workflows/ci.yml).
