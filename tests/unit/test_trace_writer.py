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


import json
from datetime import datetime
from pydantic import BaseModel


class _Dummy(BaseModel):
    name: str
    when: datetime  # 验证 model_dump(mode="json") 处理 datetime


def test_save_stage_single_model(tmp_path):
    tw = TraceWriter("t-1", base_dir=tmp_path)
    tw.save_stage("02_analysis", _Dummy(name="a", when=datetime(2026, 6, 2, 14, 30)))
    f = tmp_path / "t-1" / "02_analysis.json"
    assert f.exists()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["name"] == "a"
    assert isinstance(data["when"], str)


def test_save_stage_list(tmp_path):
    tw = TraceWriter("t-2", base_dir=tmp_path)
    tw.save_stage("01_profiles", [_Dummy(name="x", when=datetime(2026, 6, 2)),
                                  _Dummy(name="y", when=datetime(2026, 6, 2))])
    data = json.loads((tmp_path / "t-2" / "01_profiles.json").read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2


def test_save_stage_empty_list(tmp_path):
    tw = TraceWriter("t-3", base_dir=tmp_path)
    tw.save_stage("01_profiles", [])
    data = json.loads((tmp_path / "t-3" / "01_profiles.json").read_text(encoding="utf-8"))
    assert data == []


def test_save_stage_creates_v1_snapshot_on_rewrite(tmp_path):
    tw = TraceWriter("t-4", base_dir=tmp_path)
    tw.save_stage("03_report", _Dummy(name="first", when=datetime(2026, 6, 2)))
    tw.save_stage("03_report", _Dummy(name="second", when=datetime(2026, 6, 2)))
    d = tmp_path / "t-4"
    latest = json.loads((d / "03_report.json").read_text(encoding="utf-8"))
    v1 = json.loads((d / "03_report_v1.json").read_text(encoding="utf-8"))
    assert latest["name"] == "second"
    assert v1["name"] == "first"


def test_save_stage_v_number_from_disk(tmp_path):
    """进程重启场景：内存计数归零，但 N 应取磁盘已有最大版本+1"""
    tw = TraceWriter("t-5", base_dir=tmp_path)
    tw.save_stage("03_report", _Dummy(name="r1", when=datetime(2026, 6, 2)))
    tw.save_stage("03_report", _Dummy(name="r2", when=datetime(2026, 6, 2)))  # 产生 _v1
    tw2 = TraceWriter("t-5", base_dir=tmp_path)  # 新实例，内存计数清零
    tw2.save_stage("03_report", _Dummy(name="r3", when=datetime(2026, 6, 2)))  # 应产生 _v2，不覆盖 _v1
    d = tmp_path / "t-5"
    assert (d / "03_report_v1.json").exists()
    assert (d / "03_report_v2.json").exists()
    assert json.loads((d / "03_report_v1.json").read_text(encoding="utf-8"))["name"] == "r1"
