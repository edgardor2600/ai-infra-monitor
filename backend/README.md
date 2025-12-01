# AI Infra Monitor Backend

Backend API for AI Infrastructure Monitoring built with FastAPI.

## Features

- Health check endpoint with mock DB and Redis checks
- Clean, structured codebase following best practices
- Comprehensive test coverage

## Development

Run the development server:

```powershell
.\backend\run-dev.ps1
```

Or directly with uvicorn:

```bash
uvicorn backend.app.main:app --reload
```

## Testing

Run tests:

```bash
pytest backend/tests/
```

## API Documentation

Once the server is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
