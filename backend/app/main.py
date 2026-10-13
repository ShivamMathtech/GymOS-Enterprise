import json, logging, time, uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.db import engine
from app.api import auth, crm, commerce, attendance, resources, operations, reports, portal

log = logging.getLogger("gymos")
logging.basicConfig(level=logging.INFO, format="%(message)s")
app = FastAPI(
    title="GymOS Enterprise API",
    version="1.0.0",
    description="Tenant-scoped gym operations. All amounts use decimal strings; all timestamps include time zones.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    start = time.perf_counter()
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in settings().origins:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "origin_denied",
                    "message": "Origin not allowed",
                    "request_id": request.state.request_id,
                }
            },
        )
    if int(request.headers.get("content-length", "0") or 0) > 4_000_000:
        return JSONResponse(
            status_code=413, content={"error": {"code": "too_large", "message": "Request exceeds 4 MB"}}
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    # Never log query strings, bodies, bearer tokens, emails or reset links.
    log.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "request_rejected",
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Check the supplied fields",
                "fields": errors,
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "conflict",
                "message": "Record conflicts with existing data or a related record. Refresh and check duplicates.",
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected(request, exc):
    log.error(json.dumps({"request_id": getattr(request.state, "request_id", ""), "error_type": type(exc).__name__}))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Unexpected server error. Contact an administrator with this request ID.",
                "request_id": getattr(request.state, "request_id", ""),
            }
        },
    )


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["Health"])
def ready():
    try:
        with engine.connect() as db:
            version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if version != "0001":
                raise ValueError("Migration mismatch")
        return {"status": "ready", "schema": version}
    except Exception:
        raise HTTPException(503, "Database unavailable or migrations not applied")


for router in [
    auth.router,
    auth.staff,
    crm.router,
    commerce.router,
    attendance.router,
    resources.router,
    operations.router,
    reports.router,
    portal.router,
]:
    app.include_router(router, prefix="/api/v1")
