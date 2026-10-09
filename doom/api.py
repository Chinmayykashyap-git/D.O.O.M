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
        is_serverless = os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV") is not None
        if start_stream and not is_serverless:
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
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "*"],
        allow_methods=["GET", "POST", "OPTIONS"],
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

    @app.get("/api/reports/sar")
    def suspicious_activity_report() -> dict[str, Any]:
        """Generate a real-time Suspicious Activity Report (SAR) synchronized with current store."""
        return store.get_sar()

    @app.post("/api/ingest")
    async def ingest_record(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        """Ingest single or batch records incrementally into the stream pipeline."""
        if isinstance(payload, list):
            events = []
            for item in payload:
                ev = await stream.publish(item)
                events.append(public_event(ev))
            return {"status": "success", "count": len(events), "events": events}

        record_data = payload.get("record", payload) if "record" in payload and isinstance(payload["record"], dict) else payload
        event_id = payload.get("event_id") if isinstance(payload, dict) else None
        timestamp = payload.get("timestamp") if isinstance(payload, dict) else None
        ev = await stream.publish(record_data, event_id=event_id, timestamp=timestamp)
        return {
            "status": "success",
            "event": public_event(ev),
            "latency_ms": getattr(stream, "last_latency_ms", 0.0),
        }

    @app.post("/api/records/modify")
    async def modify_record(payload: dict[str, Any]) -> dict[str, Any]:
        """Modify an existing record in real-time to assess shifting-waters forensic behavior."""
        record_id = str(payload.get("record_id", ""))
        updates = payload.get("updates", {})
        if not record_id or not isinstance(updates, dict):
            raise HTTPException(422, "record_id and updates object are required")
        current = store.record(record_id)
        if current is None:
            raise HTTPException(404, f"Record {record_id} not found in store")
        modified = {**current, **updates}
        event_id = payload.get("event_id")
        ev = await stream.publish(modified, event_id=event_id)
        return {
            "status": "success",
            "record_id": record_id,
            "modified_fields": list(updates.keys()),
            "event": public_event(ev),
            "incident": ev.get("incident"),
            "live_reconstruction": ev.get("live_reconstruction"),
            "latency_ms": getattr(stream, "last_latency_ms", 0.0),
        }

    @app.get("/api/stream/events")
    def stream_events(limit: int = 50) -> list[dict[str, Any]]:
        return [public_event(item) for item in stream.snapshot(max(1, min(limit, 100)))]

    @app.websocket("/api/stream")
    async def stream_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        if len(stream.clients) >= stream.client_limit:
            await websocket.close(code=1013, reason="Live stream client capacity reached.")
            return
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


LOCK_STALE_SECONDS = 30.0


def is_valid_database(path: Path) -> bool:
    """Return True if path is an existing, readable SQLite database with records."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size == 0:
            return False
        import sqlite3
        conn = sqlite3.connect(str(path), timeout=2.0)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM records")
            row = cursor.fetchone()
            return row is not None and row[0] > 0
        finally:
            conn.close()
    except (Exception, OSError):
        return False


def acquire_initialization_lock(lock_path: Path, timeout_seconds: float = 15.0) -> int | None:
    """Acquire an exclusive initialization lock with stale-lock detection."""
    import time
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()}:{time.time()}".encode("utf-8"))
            except OSError:
                pass
            return fd
        except FileExistsError:
            try:
                mtime = lock_path.stat().st_mtime
                if time.time() - mtime > LOCK_STALE_SECONDS:
                    try:
                        lock_path.unlink()
                        continue
                    except OSError:
                        pass
            except OSError:
                pass
            time.sleep(0.05)
    return None


def release_initialization_lock(fd: int, lock_path: Path) -> None:
    """Release and remove the initialization lock."""
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def ensure_database_ready(db_path: Path, seed_count: int = 300) -> None:
    """Ensure db_path contains valid seeded data, using concurrency locks and stale recovery."""
    if is_valid_database(db_path):
        return

    lock_path = db_path.with_suffix(".init.lock")
    fd = acquire_initialization_lock(lock_path)
    if fd is not None:
        try:
            if is_valid_database(db_path):
                return
            if db_path.exists():
                try:
                    db_path.unlink()
                except OSError:
                    pass
            target_dir = db_path.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            old_data_dir = os.environ.get("DOOM_DATA_DIR")
            os.environ["DOOM_DATA_DIR"] = str(target_dir)
            try:
                from doom.demo import prepare_demo
                prepare_demo(count=seed_count, seed=1907, data_dir=target_dir)
            finally:
                if old_data_dir is not None:
                    os.environ["DOOM_DATA_DIR"] = old_data_dir
                else:
                    os.environ.pop("DOOM_DATA_DIR", None)
        finally:
            release_initialization_lock(fd, lock_path)
    else:
        if not is_valid_database(db_path):
            if db_path.exists():
                try:
                    db_path.unlink()
                except OSError:
                    pass
            old_data_dir = os.environ.get("DOOM_DATA_DIR")
            os.environ["DOOM_DATA_DIR"] = str(db_path.parent)
            try:
                from doom.demo import prepare_demo
                prepare_demo(count=seed_count, seed=1907, data_dir=db_path.parent)
            finally:
                if old_data_dir is not None:
                    os.environ["DOOM_DATA_DIR"] = old_data_dir
                else:
                    os.environ.pop("DOOM_DATA_DIR", None)


def _default_database() -> Path:
    if "DOOM_DATA_DIR" in os.environ:
        path = Path(os.environ["DOOM_DATA_DIR"]) / "doom.sqlite3"
        if os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV") is not None:
            ensure_database_ready(path, seed_count=300)
        return path
    if os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV") is not None:
        import tempfile
        tmp_dir = Path(tempfile.gettempdir()) / "doom_data"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_dir / "doom.sqlite3"
        ensure_database_ready(db_path, seed_count=300)
        return db_path
    return Path("data") / "doom.sqlite3"


app = create_app(_default_database())
