from pathlib import Path

from core.database_manager import DatabaseManager
from core.relationship_detection import analyze_registered_python_files


def test_python_detector_creates_reviewable_candidate(tmp_path):
    source_path = tmp_path / "analysis.py"
    target_path = tmp_path / "data.csv"
    source_path.write_text('import pandas as pd\ndf = pd.read_csv("data.csv")\n', encoding="utf-8")
    target_path.write_text("value\n1\n", encoding="utf-8")

    database = DatabaseManager(":memory:")
    database.init_db()
    source_id = database.add_node(source_path, node_type="FILE")
    target_id = database.add_node(target_path, node_type="FILE")

    result = analyze_registered_python_files(database)
    candidates = database.list_relationship_candidates()

    assert result == {"detected": 1, "created": 1}
    assert len(candidates) == 1
    assert candidates[0]["source_node_id"] == source_id
    assert candidates[0]["target_node_id"] == target_id
    assert candidates[0]["suggested_relation_type_code"] == "READS"
    assert "read_csv" in candidates[0]["evidence"]
    database.close()


def test_approved_candidate_becomes_confirmed_relation(tmp_path):
    source_path = tmp_path / "analysis.py"
    target_path = tmp_path / "result.csv"
    source_path.write_text('df.to_csv("result.csv")\n', encoding="utf-8")
    target_path.write_text("", encoding="utf-8")

    database = DatabaseManager(":memory:")
    database.init_db()
    database.add_node(source_path, node_type="FILE")
    database.add_node(target_path, node_type="FILE")
    analyze_registered_python_files(database)
    candidate = database.list_relationship_candidates()[0]

    relation_id = database.approve_relationship_candidate(candidate["candidate_id"])
    relation = database.get_relation(relation_id)

    assert relation["relation_type_code"] == "WRITES"
    assert relation["source"] == "CONFIRMED"
    assert relation["confidence"] == 0.95
    assert database.list_relationship_candidates(status="APPROVED")[0]["candidate_id"] == candidate["candidate_id"]
    database.close()
