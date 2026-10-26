import unittest

from printer_monitor import snmp


def response(request_id, oid, value_tlv, error_status=0):
    """Build a GetResponse the way a printer would send it."""
    tlv = snmp._encode_tlv
    varbind = tlv(0x30, snmp.encode_oid(oid) + value_tlv)
    pdu = (snmp.encode_int(request_id) + snmp.encode_int(error_status) + snmp.encode_int(0)
           + tlv(0x30, varbind))
    return tlv(0x30, snmp.encode_int(0) + tlv(0x04, b"public") + tlv(0xA2, pdu))


class EncodingTest(unittest.TestCase):
    def test_oid_round_trip(self):
        for oid in ("1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.43.11.1.1.9.1.1", "1.3.6.1.4.1.18334.1.1"):
            tlv = snmp.encode_oid(oid)
            self.assertEqual(snmp.decode_oid(tlv[2:]), oid)

    def test_int_encoding(self):
        self.assertEqual(snmp.encode_int(0), b"\x02\x01\x00")
        self.assertEqual(snmp.encode_int(127), b"\x02\x01\x7f")
        self.assertEqual(snmp.encode_int(128), b"\x02\x02\x00\x80")
        self.assertEqual(snmp.encode_int(-1), b"\x02\x01\xff")
        self.assertEqual(snmp.encode_int(-129), b"\x02\x02\xff\x7f")

    def test_long_length(self):
        long_string = snmp._encode_tlv(0x04, b"x" * 300)
        self.assertEqual(long_string[:4], b"\x04\x82\x01\x2c")


class ParseTest(unittest.TestCase):
    def test_string_value(self):
        data = response(42, "1.3.6.1.2.1.1.1.0", snmp._encode_tlv(0x04, b"Office printer"))
        rid, err, oid, tag, val = snmp.parse_response(data)
        self.assertEqual((rid, err, oid), (42, 0, "1.3.6.1.2.1.1.1.0"))
        self.assertEqual(snmp.decode_value(tag, val), "Office printer")

    def test_counter_is_unsigned(self):
        data = response(7, "1.3.6.1.2.1.43.10.2.1.4.1.1", snmp._encode_tlv(0x41, b"\x80\x00\x00\x01"))
        _, _, _, tag, val = snmp.parse_response(data)
        self.assertEqual(snmp.decode_value(tag, val), 0x80000001)

    def test_negative_integer(self):
        data = response(7, "1.3.6.1.2.1.43.8.2.1.10.1.1", snmp.encode_int(-3))
        _, _, _, tag, val = snmp.parse_response(data)
        self.assertEqual(snmp.decode_value(tag, val), -3)

    def test_error_status(self):
        data = response(9, "1.3.6.1.2.1.1.1.0", b"\x05\x00", error_status=2)
        self.assertEqual(snmp.parse_response(data)[1], 2)


if __name__ == "__main__":
    unittest.main()
