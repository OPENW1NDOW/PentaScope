import re
from src.tools.trace_writer import TraceWriter


def test_new_trace_id_format(tmp_path):
    tid = TraceWriter.new_trace_id(base_dir=tmp_path)
    assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", tid)


def test_new_trace_id_collision_avoidance(tmp_path):
    tid = TraceWriter.new_trace_id(base_dir=tmp_path)
    (tmp_path / tid).mkdir()
    tid2 = TraceWriter.new_trace_id(base_dir=tmp_path)
    assert tid2 != tid
