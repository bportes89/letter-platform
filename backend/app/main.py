from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.config import settings
from app.db import Base, engine
from app.core.logging import configure_logging
import logging
from app.security_service import rate_limiter
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, version="0.21.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

@app.middleware("http")
async def security_and_correlation(request,call_next):
    request_id=request.headers.get("x-request-id") or str(uuid4());started=perf_counter()
    ip=request.client.host if request.client else "unknown"
    allowed,retry=rate_limiter.allow(f"public:{ip}",settings.public_rate_limit_per_minute)
    if not allowed:
        return JSONResponse(status_code=429,content={"detail":"Limite de requisições excedido"},headers={"Retry-After":str(retry),"X-Request-ID":request_id})
    response=await call_next(request)
    response.headers["X-Request-ID"]=request_id
    response.headers["X-Response-Time-Ms"]=f"{(perf_counter()-started)*1000:.2f}"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'none'; frame-ancestors 'none'"
    logging.getLogger("letter.http").info("request_completed",extra={"request_id":request_id,"method":request.method,"path":request.url.path,"status_code":response.status_code,"duration_ms":round((perf_counter()-started)*1000,2)})
    return response


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
