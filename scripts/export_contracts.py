"""Writes the published JSON Schemas to contracts/ from the pydantic models.

    docker compose run --rm --no-deps api python scripts/export_contracts.py
    (or locally with the app requirements installed: PYTHONPATH=src python scripts/export_contracts.py)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bpc.common.contracts import CONTRACT_VERSION, FeedbackIn, Proposal, RejectResponse, RunResult, SubmitResponse  # noqa: E402

OUT = ROOT / "contracts"
OUT.mkdir(exist_ok=True)
for name, model in {"proposal": Proposal, "submit_response": SubmitResponse, "run_result": RunResult,
                    "reject_response": RejectResponse, "feedback": FeedbackIn}.items():
    schema = model.model_json_schema()
    schema["$id"] = f"https://bpc.local/contracts/{name}.v{CONTRACT_VERSION}.json"
    schema["x-contract-version"] = CONTRACT_VERSION
    (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    print("wrote", OUT / f"{name}.schema.json")
