import unittest

from utf_8_byte_boundary_tools import (
    bytes_needed_to_complete,
    is_valid_utf8_lead_byte,
    utf8_sequence_length,
)


class TestUtf8SequenceLength(unittest.TestCase):
    def test_ascii(self):
        for b in range(0x00, 0x80):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 1)

    def test_two_byte_leads(self):
        for b in range(0xC0, 0xE0):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 2)

    def test_three_byte_leads(self):
        for b in range(0xE0, 0xF0):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 3)

    def test_four_byte_leads(self):
        for b in range(0xF0, 0xF8):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 4)

    def test_invalid_high_bytes(self):
        for b in range(0xF8, 0x100):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 0)

    def test_continuation_bytes_return_zero(self):
        for b in range(0x80, 0xC0):
            with self.subTest(byte=b):
                self.assertEqual(utf8_sequence_length(b), 0)

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            utf8_sequence_length(-1)
        with self.assertRaises(ValueError):
            utf8_sequence_length(256)


class TestIsValidUtf8LeadByte(unittest.TestCase):
    def test_ascii_is_lead(self):
        self.assertTrue(is_valid_utf8_lead_byte(0x41))  # 'A'
        self.assertTrue(is_valid_utf8_lead_byte(0x00))
        self.assertTrue(is_valid_utf8_lead_byte(0x7F))

    def test_continuation_not_lead(self):
        for b in range(0x80, 0xC0):
            with self.subTest(byte=b):
                self.assertFalse(is_valid_utf8_lead_byte(b))

    def test_multibyte_leads(self):
        self.assertTrue(is_valid_utf8_lead_byte(0xC2))
        self.assertTrue(is_valid_utf8_lead_byte(0xE0))
        self.assertTrue(is_valid_utf8_lead_byte(0xF0))
        self.assertTrue(is_valid_utf8_lead_byte(0xF4))

    def test_invalid_high(self):
        self.assertFalse(is_valid_utf8_lead_byte(0xFE))
        self.assertFalse(is_valid_utf8_lead_byte(0xFF))

    def test_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            is_valid_utf8_lead_byte(300)
        with self.assertRaises(ValueError):
            is_valid_utf8_lead_byte(-5)


class TestBytesNeededToComplete(unittest.TestCase):
    def test_empty_buffer(self):
        self.assertEqual(bytes_needed_to_complete(b""), 0)
        self.assertEqual(bytes_needed_to_complete(bytearray()), 0)
        self.assertEqual(bytes_needed_to_complete(memoryview(b"")), 0)

    def test_ascii_ending(self):
        self.assertEqual(bytes_needed_to_complete(b"hello"), 0)
        self.assertEqual(bytes_needed_to_complete(b"\x00"), 0)
        self.assertEqual(bytes_needed_to_complete(b"\x7F"), 0)

    def test_two_byte_lead_ending(self):
        # 0xC2 is the first valid 2-byte lead (e.g. start of 'Â')
        self.assertEqual(bytes_needed_to_complete(b"\x41\xC2"), 1)
        self.assertEqual(bytes_needed_to_complete(b"\xC3"), 1)
        self.assertEqual(bytes_needed_to_complete(b"\xDF"), 1)

    def test_three_byte_lead_ending(self):
        # 0xE0 is a 3-byte lead (e.g. start of 'à' in some encodings)
        self.assertEqual(bytes_needed_to_complete(b"\xE0"), 2)
        self.assertEqual(bytes_needed_to_complete(b"text\xEF"), 2)

    def test_four_byte_lead_ending(self):
        # 0xF0 is a 4-byte lead (e.g. start of an emoji like '😀')
        self.assertEqual(bytes_needed_to_complete(b"\xF0"), 3)
        self.assertEqual(bytes_needed_to_complete(b"abc\xF4"), 3)

    def test_continuation_byte_ending_returns_zero(self):
        # A trailing continuation byte means the lead byte is missing;
        # we do not guess how many bytes were in the original sequence.
        self.assertEqual(bytes_needed_to_complete(b"\x80"), 0)
        self.assertEqual(bytes_needed_to_complete(b"\xBF"), 0)
        self.assertEqual(bytes_needed_to_complete(b"abc\xAB"), 0)

    def test_invalid_byte_ending_returns_zero(self):
        self.assertEqual(bytes_needed_to_complete(b"\xFF"), 0)
        self.assertEqual(bytes_needed_to_complete(b"\xFE"), 0)
        self.assertEqual(bytes_needed_to_complete(b"\xF9"), 0)

    def test_bytearray_works(self):
        ba = bytearray(b"\xE2")
        self.assertEqual(bytes_needed_to_complete(ba), 2)

    def test_memoryview_works(self):
        # A memoryview ending in a 4-byte lead needs 3 more bytes.
        mv = memoryview(b"\xF0")
        self.assertEqual(bytes_needed_to_complete(mv), 3)
        # A memoryview ending in a continuation byte returns 0, since
        # only the last byte is inspected.
        mv2 = memoryview(b"\xF0\x9F")
        self.assertEqual(bytes_needed_to_complete(mv2), 0)

    def test_non_bytes_raises_type_error(self):
        with self.assertRaises(TypeError):
            bytes_needed_to_complete("not bytes")
        with self.assertRaises(TypeError):
            bytes_needed_to_complete(None)
        with self.assertRaises(TypeError):
            bytes_needed_to_complete([0xE0])

    def test_real_multibyte_split(self):
        # '😀' is U+1F600, encoded in UTF-8 as F0 9F 98 80.
        # If the buffer ends after the lead byte, we need 3 more.
        full = "😀".encode("utf-8")
        self.assertEqual(full, b"\xF0\x9F\x98\x80")
        self.assertEqual(bytes_needed_to_complete(full[:1]), 3)
        # After two bytes we are not at a boundary; last byte is a
        # continuation byte, so we report 0 (we only inspect the last byte).
        self.assertEqual(bytes_needed_to_complete(full[:2]), 0)
        self.assertEqual(bytes_needed_to_complete(full[:3]), 0)
        self.assertEqual(bytes_needed_to_complete(full), 0)

    def test_overlong_lead_still_structural(self):
        # 0xC0 is an overlong 2-byte lead, structurally length 2.
        # We report it as needing 1 more byte for boundary purposes.
        self.assertEqual(utf8_sequence_length(0xC0), 2)
        self.assertEqual(bytes_needed_to_complete(b"\xC0"), 1)


if __name__ == "__main__":
    unittest.main()
