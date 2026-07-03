import json

import pytest

from backend.domain.subagent_config import load_subagents, parse_subagents


def test_load_subagents_valid_defaults(tmp_path):
    config = [
        {
            "name": "sales_agent",
            "type": "genie",
            "space_id": "space-1",
            "description": "genie",
        },
        {
            "name": "knowledge_assistant",
            "type": "serving_endpoint",
            "endpoint": "knowledge_assistant",
            "description": "serving",
        },
    ]
    config_path = tmp_path / "subagents.json"
    config_path.write_text(json.dumps(config))

    subagents = load_subagents(config_path)

    assert len(subagents) == 2
    assert subagents[0].auth_mode == "obo"
    assert subagents[1].auth_mode == "app"


def test_load_subagents_missing_file_raises_value_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(ValueError, match="file not found"):
        load_subagents(missing_path)


def test_load_subagents_invalid_root_type_raises_value_error(tmp_path):
    config_path = tmp_path / "subagents.json"
    config_path.write_text(json.dumps({"name": "not-a-list"}))

    with pytest.raises(ValueError, match="root must be a list"):
        load_subagents(config_path)


@pytest.mark.parametrize(
    ("raw", "msg"),
    [
        (
            [
                {
                    "name": "bad_kind",
                    "type": "invalid",
                    "description": "x",
                    "endpoint": "ep",
                }
            ],
            "unsupported type",
        ),
        (
            [
                {
                    "name": "bad_auth",
                    "type": "serving_endpoint",
                    "auth_mode": "invalid",
                    "description": "x",
                    "endpoint": "ep",
                }
            ],
            "unsupported auth_mode",
        ),
        (
            [
                {
                    "name": "missing_space",
                    "type": "genie",
                    "description": "x",
                }
            ],
            "must define space_id",
        ),
        (
            [
                {
                    "name": "missing_endpoint",
                    "type": "serving_endpoint",
                    "description": "x",
                }
            ],
            "must define endpoint",
        ),
    ],
)
def test_parse_subagents_invalid_entries_raise_value_error(raw, msg):
    with pytest.raises(ValueError, match=msg):
        parse_subagents(raw)
