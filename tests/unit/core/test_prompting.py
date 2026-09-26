import pytest
from transformers import AutoTokenizer

from innards.data import Message, PromptRecord
from innards.prompting import prepare_prompt

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
IM_END, NEWLINE, PERIOD = 151645, 198, 13 # from scratch/template_probe.py output at REVISION

@pytest.fixture(scope="module")
def tok():
    return AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION)

def user_prompt(content: str, id: str = "t-1") -> PromptRecord:
    return PromptRecord(id=id, messages=(Message(role="user", content=content),), category="test", family="f-1")

def test_mech_001_positions_match_hand_inspected_tokens(tok):
    prepared = prepare_prompt(tok, user_prompt("write a haiku about autumn leaves."))

    # assertions
    assert prepared.t_inst == 10 and prepared.input_ids[10] == PERIOD
