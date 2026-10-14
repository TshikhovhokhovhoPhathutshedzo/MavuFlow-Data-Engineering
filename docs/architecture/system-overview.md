# MavuFlow Studio Architecture

## Purpose
The system provides a secure, versioned data engineering workflow for authenticated users. It supports dataset upload, profiling, cleaning, transformation, ETL pipeline execution, version management, and export operations.

## Core Principles
- Domain separation between API, storage, processing, and frontend logic.
- Strict ownership checks for all datasets and generated files.
- Preservation of original uploads and immutable processing versions.
- Event-driven processing with Redis and Celery for large jobs.
- Traceability via PostgreSQL metadata records and audit logs.

## Invariant Rules
- No path is built from untrusted user input.
- Original uploads are never overwritten.
- Every successful operation produces a new dataset version.
- Every file is tracked with database metadata and a storage key.
- Every API call verifies ownership or explicit permission.

## Phase roadmap
1. Foundation and project setup
2. Authentication and secure sessions
3. Projects and file management
4. Dataset preview and profiling
5. Cleaning engine and versioning
6. Processing and live refresh
7. Transformation engine
8. Pipeline builder
9. Export system
10. Analytics and quality reporting
11. Test suite and CI
12. Deployment and production readiness
