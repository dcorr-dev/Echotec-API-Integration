# Echotec-API-Integration

Academic project to API consumers.

## Python API base

This repository now includes a minimal Python API base using FastAPI so you can start implementing endpoints.

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run the API

```bash
uvicorn app.main:app --reload
```

### 3) Run tests

```bash
pytest -q
```
