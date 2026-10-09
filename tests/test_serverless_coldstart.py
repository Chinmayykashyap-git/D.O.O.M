"""Automated tests for Vercel serverless SQLite cold-start safety and concurrency."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from doom.api import (
    acquire_initialization_lock,
    ensure_database_ready,
    is_valid_database,
    release_initialization_lock,
)


def test_is_valid_database_nonexistent(tmp_path: Path):
    db_file = tmp_path / "nonexistent.sqlite3"
    assert not is_valid_database(db_file)


def test_is_valid_database_empty_file(tmp_path: Path):
    db_file = tmp_path / "empty.sqlite3"
    db_file.touch()
    assert not is_valid_database(db_file)


def test_is_valid_database_corrupt_file(tmp_path: Path):
    db_file = tmp_path / "corrupt.sqlite3"
    db_file.write_bytes(b"NOT A SQLITE DATABASE FILE")
    assert not is_valid_database(db_file)


def test_is_valid_database_schema_no_records(tmp_path: Path):
    db_file = tmp_path / "empty_schema.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE records (record_id TEXT PRIMARY KEY, payload TEXT)")
    conn.commit()
    conn.close()
    assert not is_valid_database(db_file)


def test_is_valid_database_with_records(tmp_path: Path):
    db_file = tmp_path / "valid.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE records (record_id TEXT PRIMARY KEY, payload TEXT)")
    conn.execute("INSERT INTO records VALUES ('REC-1', '{}')")
    conn.commit()
    conn.close()
    assert is_valid_database(db_file)


def test_lock_acquire_and_release(tmp_path: Path):
    lock_file = tmp_path / "test.lock"
    fd = acquire_initialization_lock(lock_file, timeout_seconds=1.0)
    assert fd is not None
    assert lock_file.exists()

    # Second acquisition within timeout should fail
    fd2 = acquire_initialization_lock(lock_file, timeout_seconds=0.1)
    assert fd2 is None

    release_initialization_lock(fd, lock_file)
    assert not lock_file.exists()


def test_stale_lock_recovery(tmp_path: Path):
    lock_file = tmp_path / "stale.lock"
    # Create a lock file and set its mtime to 60 seconds ago
    lock_file.write_text("old_pid:1000")
    stale_time = time.time() - 60.0
    os.utime(lock_file, (stale_time, stale_time))

    # Should break stale lock and acquire successfully
    fd = acquire_initialization_lock(lock_file, timeout_seconds=1.0)
    assert fd is not None
    release_initialization_lock(fd, lock_file)


def test_ensure_database_ready_cold_start(tmp_path: Path):
    db_file = tmp_path / "cold_start" / "doom.sqlite3"
    assert not db_file.exists()

    ensure_database_ready(db_file, seed_count=40)
    assert is_valid_database(db_file)

    conn = sqlite3.connect(db_file)
    count = conn.execute("SELECT count(*) FROM records").fetchone()[0]
    conn.close()
    assert count >= 40

    # Warm invocation should not fail or reseed
    mtime_before = db_file.stat().st_mtime
    ensure_database_ready(db_file, seed_count=40)
    assert db_file.stat().st_mtime == mtime_before


def test_ensure_database_ready_recovers_corrupted(tmp_path: Path):
    db_file = tmp_path / "corrupt_test" / "doom.sqlite3"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.write_bytes(b"CORRUPTED TRUNCATED DATA")
    assert not is_valid_database(db_file)

    ensure_database_ready(db_file, seed_count=40)
    assert is_valid_database(db_file)
    conn = sqlite3.connect(db_file)
    count = conn.execute("SELECT count(*) FROM records").fetchone()[0]
    conn.close()
    assert count >= 40

