"""FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router

# Starlette spools the entire request body (to disk) BEFORE route dependencies run, so
# auth/size checks in the upload route can't stop an oversized body. This cheap
# Content-Length gate protects the no-proxy (dev / direct) path; the prod Caddyfile
# additionally enforces a proxy-level request_body cap.
_MAX_BODY_BYTES = 128 * 1024 * 1024


def create_app() -> FastAPI:
    app = FastAPI(
        title="VC Market Analysis Engine",
        description="Multi-agent consensus pipeline for VC-grade sector analysis.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def body_size_gate(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        return await call_next(request)

    app.include_router(router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
