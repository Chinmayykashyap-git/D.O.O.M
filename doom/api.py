"""FastAPI application and local operator API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from doom.schema import PORTS
from doom.store import EvidenceStore
from doom.streaming import StreamingService, public_event


def create_app(
    database_path: str | Path = "data/doom.sqlite3",
    start_stream: bool = True,
) -> FastAPI:
    store = EvidenceStore(database_path)
    stream = StreamingService(store)
    task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        nonlocal task
        if start_stream:
            task = asyncio.create_task(stream.run())
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="D.O.O.M. | Cargo Forensic Intelligence",
        version="1.0.0",
        description="Local-first manifest integrity, evidence, and reconstruction API.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.stream = stream
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "operational", "product": "D.O.O.M."}

    @app.get("/api/overview")
    def overview() -> dict[str, Any]:
        incidents = store.incidents(limit=100_000)
        all_records = store.records(limit=100_000)
        recon = store.reconstruction()
        metrics = store.metrics()
        statuses: dict[str, int] = {}
        for decision in recon:
            state = decision["status"]
            statuses[state] = statuses.get(state, 0) + 1
        return {
            "record_count": len(all_records),
            "incident_count": len(incidents),
            "critical_count": sum(item["risk_score"] >= 90 for item in incidents),
            "integrity_score": round(
                100 * (1 - len(incidents) / max(len(all_records), 1)), 1
            ),
            "reconstruction_counts": statuses,
            "metrics": metrics,
            "stream_status": "LIVE",
        }

    @app.get("/api/incidents")
    def incidents(
        limit: int = 100, severity: str | None = None
    ) -> list[dict[str, Any]]:
        result = store.incidents(limit=max(1, min(limit, 500)))
        if severity:
            minimum = {"critical": 90, "high": 75, "medium": 55, "low": 0}.get(
                severity.lower()
            )
            if minimum is None:
                raise HTTPException(422, "severity must be critical, high, medium, or low")
            result = [item for item in result if item["risk_score"] >= minimum]
        return result

    @app.get("/api/incidents/{record_id}")
    def incident_detail(record_id: str) -> dict[str, Any]:
        incident = store.incident(record_id)
        decision = store.reconstruction(record_id)
        record = store.record(record_id)
        if incident is None and decision == []:
            raise HTTPException(404, "Incident not found")
        return {
            "incident": incident,
            "record": record,
            "reconstruction": decision[0] if decision else None,
            "timeline": [
                {"event": "RECORD OBSERVED", "time": record.get("event_ts") if record else None},
                {"event": "ANOMALY DETECTED", "time": None},
                {"event": "RECONSTRUCTION DECIDED", "time": None},
            ],
        }

    @app.get("/api/records")
    def records(limit: int = 100) -> list[dict[str, Any]]:
        return store.records(max(1, min(limit, 1000)))

    @app.get("/api/reconstruction")
    def reconstruction(limit: int = 500) -> list[dict[str, Any]]:
        return store.reconstruction()[:max(1, min(limit, 5000))]

    @app.get("/api/reconstruction/manifest")
    def reconstructed_manifest(limit: int = 5000) -> list[dict[str, Any]]:
        return store.reconstructed_records(max(1, min(limit, 5000)))

    @app.get("/api/routes")
    def routes() -> dict[str, Any]:
        return {
            "ports": [
                {"code": code, "name": details[0], "latitude": details[1], "longitude": details[2]}
                for code, details in PORTS.items()
            ],
        }

    @app.get("/api/metrics")
    def metrics() -> dict[str, Any]:
        return store.metrics()

    @app.get("/api/stream/events")
    def stream_events(limit: int = 50) -> list[dict[str, Any]]:
        return [public_event(item) for item in stream.snapshot(max(1, min(limit, 100)))]

    @app.websocket("/api/stream")
    async def stream_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        stream.clients.add(queue)
        try:
            for event in stream.snapshot():
                await websocket.send_json(public_event(event))
            while True:
                event = await queue.get()
                await websocket.send_json(public_event(event))
        except WebSocketDisconnect:
            pass
        finally:
            stream.clients.discard(queue)

    frontend = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend.is_dir():
        @app.get("/", include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(frontend / "index.html")

        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app(Path(os.environ.get("DOOM_DATA_DIR", "data")) / "doom.sqlite3")
