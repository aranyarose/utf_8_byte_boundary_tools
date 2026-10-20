# utf_8_byte_boundary_tools

Determines the number of bytes needed to complete a UTF-8 multi-byte sequence from a partial byte buffer, by inspecting the trailing lead byte.

```python
from utf_8_byte_boundary_tools import bytes_needed_to_complete

chunk = b"hello \xF0\x9F"  # ends mid-way through a 4-byte sequence (emoji)
needed = bytes_needed_to_complete(chunk)
print(needed)  # 3 -- but see note below; only the last byte is inspected

# In practice you split your buffer at the last clean boundary first:
from utf_8_byte_boundary_tools import utf8_sequence_length
last = chunk[-1]
seq_len = utf8_sequence_length(last)  # 0 for continuation bytes, 1-4 otherwise
```

The exported names are:

- `bytes_needed_to_complete(buffer)` — returns an `int` (0–3).
- `utf8_sequence_length(lead_byte)` — returns the structural sequence length (0–4) for a single lead byte.
- `is_valid_utf8_lead_byte(byte)` — returns `bool`.

## Why this exists

When reading UTF-8 text from a stream in fixed-size chunks, a multi-byte character may be split across two reads. To avoid feeding a truncated sequence to the decoder, you need to know how many more bytes to pull before retrying. This library answers that question with zero dependencies and no allocation beyond reading the final byte.

The trade-off: `bytes_needed_to_complete` only inspects the **last byte** of the buffer. It assumes the caller has already trimmed complete characters from the head. If the last byte is a continuation byte (0x80–0xBF), the function returns 0 because it cannot infer the original lead byte from a continuation byte alone — a continuation byte's high bits do not encode the sequence length. Handle that case upstream by tracking the last valid boundary position.

## The awkward edge

The most common surprise: if your buffer ends in the middle of a sequence *after* the lead byte (e.g. you have `F0 9F` for an emoji), `bytes_needed_to_complete` returns 0, not 2. This is deliberate. The function detects whether the buffer ends on a lead byte that needs completion; it does not reconstruct a partially-consumed sequence from continuation bytes. To handle mid-sequence splits robustly, keep a running offset of the last consumed boundary and re-slice from there.
