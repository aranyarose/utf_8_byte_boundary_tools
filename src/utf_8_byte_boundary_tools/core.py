"""Core logic for inspecting UTF-8 byte boundaries.

This module provides tools to answer a single question: given a buffer that
may end in the middle of a UTF-8 multi-byte sequence, how many more bytes are
required to complete that sequence? This is a common concern when reading
UTF-8 data in arbitrary-sized chunks from a stream where a multi-byte
character may be split across read boundaries.

The implementation only inspects the *lead byte* (the first byte) of the
sequence at the end of the buffer. It deliberately does not validate
continuation bytes already present in the buffer. The rationale is that this
function is intended to be called *after* a successful decode of the leading,
complete portion of the buffer has failed or stopped. Validating the
continuation bytes here would duplicate work the decoder is already
responsible for and would conflate two concerns (boundary detection vs.
sequence validation).

Invalid lead bytes (e.g. 0xFF, 0xFE, or lone continuation bytes 0x80-0xBF)
return a needed count of 0, since there is no well-defined multi-byte
sequence to complete.
"""


def is_valid_utf8_lead_byte(byte: int) -> bool:
    """Return True if *byte* is a valid lead byte for a UTF-8 sequence.

    Valid lead bytes are 0x00-0x7F (ASCII), 0xC0-0xC1 (overlong 2-byte,
    technically invalid but we report as leads so the caller can decide),
    0xC2-0xF4 (well-formed 2/3/4-byte leads), and 0xF5-0xF7 (would encode
    code points beyond U+10FFFF, invalid but still syntactically leads).

    0x80-0xBF are continuation bytes, not leads. 0xFE and 0xFF are never
    valid in UTF-8. For 0xC0/0xC1 and 0xF5-0xF7 we still return True because
    they *syntactically* introduce a multi-byte sequence; semantic validity
    of the encoded code point is out of scope for this function. This keeps
    boundary detection purely structural.
    """
    if not 0 <= byte <= 0xFF:
        raise ValueError("byte must be in range [0, 255]")
    if byte <= 0x7F:
        return True
    if 0xC0 <= byte <= 0xF7:
        return True
    return False


def utf8_sequence_length(lead_byte: int) -> int:
    """Return the expected total length of a UTF-8 sequence from its lead byte.

    Returns 0 if the lead byte is not a valid sequence start. Note that
    'valid' here means 'structurally introduces a sequence of a known
    length'; it does not mean the sequence is semantically valid UTF-8
    (e.g. overlong encodings are still reported with their structural
    length).

    We raise ValueError on out-of-range input rather than returning 0 so
    that programmer errors (passing a full character or a negative int) are
    not silently swallowed.
    """
    if not 0 <= lead_byte <= 0xFF:
        raise ValueError("lead_byte must be in range [0, 255]")

    if lead_byte <= 0x7F:
        return 1
    if lead_byte <= 0xBF:
        # 0x80-0xBF: continuation bytes, not leads.
        return 0
    if lead_byte <= 0xDF:
        # 0xC0-0xDF: structural 2-byte lead. 0xC0 and 0xC1 are overlong,
        # but we still report length 2 for boundary purposes.
        return 2
    if lead_byte <= 0xEF:
        return 3
    if lead_byte <= 0xF7:
        # 0xF5-0xF7 would encode beyond U+10FFFF, but structurally a
        # 4-byte lead.
        return 4
    # 0xF8-0xFF: invalid in any well-formed UTF-8.
    return 0


def bytes_needed_to_complete(buffer) -> int:
    """Return the number of additional bytes required to finish the trailing
    UTF-8 sequence in *buffer*.

    *buffer* must be a bytes-like object. If the buffer is empty, returns 0.

    If the last byte is a valid lead byte for a multi-byte sequence (length
    2, 3, or 4), returns (sequence_length - 1) since only the lead byte is
    present. For example, a buffer ending in 0xE0 (a 3-byte lead) needs 2
    more bytes.

    If the last byte is an ASCII byte (0x00-0x7F), a continuation byte
    (0x80-0xBF), or an invalid byte (0xF8-0xFF), returns 0. The reasoning:

    - ASCII bytes are complete on their own.
    - A trailing continuation byte indicates a *different* problem (a
      truncated sequence where even the lead byte is missing, or corrupt
      data) that this function is not designed to diagnose. The caller
      should treat the buffer as ending at a non-boundary; returning 0
      signals 'no well-defined completion target'.
    - Invalid bytes cannot start a sequence, so there is nothing to
      complete.

    This function does *not* look at more than the last byte. It assumes the
    caller has already arranged the buffer so that any complete characters at
    the head have been consumed. The common usage pattern is:

        complete = buffer[:last_boundary]
        rest = buffer[last_boundary:]
        needed = bytes_needed_to_complete(rest)
        # read `needed` more bytes, append, then retry decode.
    """
    if not isinstance(buffer, (bytes, bytearray, memoryview)):
        raise TypeError(
            "buffer must be a bytes-like object (bytes, bytearray, or memoryview)"
        )

    length = len(buffer)

    if length == 0:
        return 0

    lead_byte = buffer[-1]
    # Normalize memoryview/bytearray elements to a plain int.
    if isinstance(lead_byte, (bytes, bytearray)):
        lead_byte = lead_byte[0]
    if not isinstance(lead_byte, int):
        raise TypeError("buffer elements must be integers")

    seq_len = utf8_sequence_length(lead_byte)
    if seq_len <= 1:
        # Either a complete single-byte character, or an invalid/continuation
        # byte that we do not attempt to interpret.
        return 0
    return seq_len - 1
