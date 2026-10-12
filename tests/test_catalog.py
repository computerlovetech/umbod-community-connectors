import json
from pathlib import Path

from umbod_community_connectors.server import CONNECTORS, WRITES


def test_catalog_matches_distributed_tools():
    root = Path(__file__).resolve().parents[1]
    for name, connector in CONNECTORS.items():
        catalog = json.loads((root / "catalog" / f"{name}.json").read_text())
        declared = {tool["name"] for tool in catalog["tools"]}
        assert declared == {tool.operation_name for tool in connector.definition().tools}
        assert {tool["name"] for tool in catalog["tools"] if tool["side_effects"]} == WRITES[name]
        assert catalog["reference"]["author"] == "Mark Ruvald"
        assert len(catalog["reference"]["revision"]) == 40
        assert (root / catalog["documentation"]).is_file()
        assert catalog["validation"]["live_provider"] == "unverified"
