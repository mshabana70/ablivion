from dataclasses import dataclass
from transformers import AutoTokenizer

from innards.data import PromptRecord

# offsets we care about
IM_END, NEWLINE, PERIOD = 151645, 198, 13

@dataclass(frozen=True)
class PreparedPrompt:
    prompt_id: str
    text: str                       # this will store the exact rendered template
    input_ids: tuple[int, ...]
    content_span: tuple[int, int]   # (start, end) chars of the last user message content in 'text'
    t_inst: int     # last token overlapping content_span
    t_post_inst: int    # last token in sequence
    left_edge_merged: bool          # the first content token also covers template chars

def prepare_prompt(tokenizer, record: PromptRecord) -> PreparedPrompt:

    # need to render tokenizer string first
    user_str = record.messages[0].content
    encoding = tokenizer(user_str, return_offsets_mapping=True)
    input_ids = encoding["input_ids"]
    offsets = encoding["offset_mapping"]

    # now let's search for t_inst and t_post_inst
    decoded_text = tokenizer.decode(input_ids)
    for idx in range(len(input_ids)):
        # don't believe this will actually get the true start and end, doesn't really address merged tokens yet...
        start, end = tokenizer.token_to_chars(idx, sequence=decoded_text)
        print(f"DEBUG: Token {idx} spans from char {start} to {end}.")


    return PreparedPrompt(
        prompt_id=record.id,
        text=user_str,
        input_ids=input_ids,
        content_span=...,
        t_inst=...,
        t_post_inst=...,
        left_edge_merged=...,
    )


    
