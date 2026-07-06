import pytest

from src.api.routes import ProgressSnapshotQueue


@pytest.mark.asyncio
async def test_progress_snapshot_queue_replays_state():
    q = ProgressSnapshotQueue()

    await q.put({"event": "node_start", "data": {"node": "collector"}})
    await q.put({"event": "node_complete", "data": {"node": "collector", "duration_ms": 1000}})
    await q.put({"event": "node_start", "data": {"node": "analyzer"}})

    assert q.snapshot_events() == [
        {"event": "node_complete", "data": {"node": "collector", "duration_ms": 1000}},
        {"event": "node_start", "data": {"node": "analyzer"}},
    ]


@pytest.mark.asyncio
async def test_progress_snapshot_clears_current_on_complete():
    q = ProgressSnapshotQueue()

    await q.put({"event": "node_start", "data": {"node": "writer"}})
    await q.put({"event": "node_complete", "data": {"node": "writer", "duration_ms": 500}})

    assert q.current_node is None
    assert q.snapshot_events() == [
        {"event": "node_complete", "data": {"node": "writer", "duration_ms": 500}},
    ]
