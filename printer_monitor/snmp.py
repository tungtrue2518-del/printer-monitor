"""Minimal SNMPv1 GET / GETNEXT client using only the standard library.

Enough to read the standard Printer-MIB (RFC 3805) and Host-Resources-MIB
values every network printer publishes. No pysnmp or other package needed.
"""
import random
import socket

GET = 0xA0
GET_NEXT = 0xA1


def _encode_length(n):
    if n < 0x80:
        return bytes([n])
    b = []
    while n:
        b.insert(0, n & 0xFF)
        n >>= 8
    return bytes([0x80 | len(b)]) + bytes(b)


def _encode_tlv(tag, value):
    return bytes([tag]) + _encode_length(len(value)) + value


def encode_int(n):
    if n == 0:
        return _encode_tlv(0x02, b"\x00")
    b = []
    neg = n < 0
    nn = -n - 1 if neg else n
    while nn or not b:
        b.insert(0, nn & 0xFF)
        nn >>= 8
    if not neg and b[0] & 0x80:
        b.insert(0, 0)
    if neg:
        b = [(~x) & 0xFF for x in b]
        if not b[0] & 0x80:
            b.insert(0, 0xFF)
    return _encode_tlv(0x02, bytes(b))


def encode_oid(oid_str):
    parts = [int(x) for x in oid_str.split(".")]
    out = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        if p < 0x80:
            out += bytes([p])
            continue
        chunk = []
        while p:
            chunk.insert(0, p & 0x7F)
            p >>= 7
        for i in range(len(chunk) - 1):
            chunk[i] |= 0x80
        out += bytes(chunk)
    return _encode_tlv(0x06, out)


def decode_oid(data):
    if not data:
        return ""
    parts = [data[0] // 40, data[0] % 40]
    val = 0
    for b in data[1:]:
        val = (val << 7) | (b & 0x7F)
        if not b & 0x80:
            parts.append(val)
            val = 0
    return ".".join(str(p) for p in parts)


def build_request(pdu_tag, community, oid_str, request_id):
    varbind = _encode_tlv(0x30, encode_oid(oid_str) + _encode_tlv(0x05, b""))
    pdu_body = encode_int(request_id) + encode_int(0) + encode_int(0) + _encode_tlv(0x30, varbind)
    message = encode_int(0) + _encode_tlv(0x04, community.encode()) + _encode_tlv(pdu_tag, pdu_body)
    return _encode_tlv(0x30, message)


def _read_tlv(data, idx):
    """-> (tag, value_start, value_end) for the TLV starting at idx."""
    tag = data[idx]
    idx += 1
    first = data[idx]
    idx += 1
    if first < 0x80:
        length = first
    else:
        n = first & 0x7F
        length = int.from_bytes(data[idx:idx + n], "big")
        idx += n
    return tag, idx, idx + length


def parse_response(data):
    """-> (request_id, error_status, oid, value_tag, value_bytes) for a one-varbind response."""
    _, i, _ = _read_tlv(data, 0)               # message SEQUENCE
    _, _, i = _read_tlv(data, i)               # version
    _, _, i = _read_tlv(data, i)               # community
    _, i, _ = _read_tlv(data, i)               # PDU
    _, s, e = _read_tlv(data, i)               # request-id
    request_id = int.from_bytes(data[s:e], "big", signed=True)
    _, s, i = _read_tlv(data, e)               # error-status
    error_status = int.from_bytes(data[s:i], "big") if i > s else 0
    _, _, i = _read_tlv(data, i)               # error-index
    _, i, _ = _read_tlv(data, i)               # varbind list
    _, i, _ = _read_tlv(data, i)               # varbind
    _, s, e = _read_tlv(data, i)               # name
    oid = decode_oid(data[s:e])
    tag, s, e = _read_tlv(data, e)             # value
    return request_id, error_status, oid, tag, data[s:e]


def decode_value(tag, val):
    if tag == 0x04:                                   # OCTET STRING
        return val.decode("utf-8", errors="replace")
    if tag == 0x02:                                   # INTEGER
        return int.from_bytes(val, "big", signed=True)
    if tag in (0x41, 0x42, 0x43, 0x46):               # Counter32 / Gauge32 / TimeTicks / Counter64
        return int.from_bytes(val, "big")
    if tag == 0x06:
        return decode_oid(val)
    return None                                       # NULL, noSuchObject, endOfMibView, ...


class Session:
    """One UDP socket to one device. Use as a context manager."""

    def __init__(self, host, community="public", timeout=1.5, port=161):
        self.addr = (host, port)
        self.community = community
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.sock.close()

    def _request(self, pdu_tag, oid):
        rid = random.randint(1, 0x7FFFFFFF)
        self.sock.sendto(build_request(pdu_tag, self.community, oid, rid), self.addr)
        while True:
            data, _ = self.sock.recvfrom(65535)
            got_rid, err, name, tag, val = parse_response(data)
            if got_rid == rid:                        # ignore late replies to an earlier request
                return (None if err else (name, decode_value(tag, val)))

    def get(self, oid):
        """Value of one OID, or None if missing / no answer."""
        try:
            res = self._request(GET, oid)
        except (OSError, IndexError, ValueError):
            return None
        return res[1] if res else None

    def walk(self, base_oid, max_rows=64):
        """[(oid, value), ...] for every OID under base_oid."""
        rows, current = [], base_oid
        try:
            for _ in range(max_rows):
                res = self._request(GET_NEXT, current)
                if not res:
                    break
                oid, value = res
                if not oid.startswith(base_oid + "."):
                    break
                rows.append((oid, value))
                current = oid
        except (OSError, IndexError, ValueError):
            pass
        return rows

    def table(self, base_oid, columns):
        """{row_index: {name: value}} for several columns of one SNMP table.
        columns = {column_number: name}."""
        rows = {}
        for col, name in columns.items():
            prefix = f"{base_oid}.{col}"
            for oid, value in self.walk(prefix):
                rows.setdefault(oid[len(prefix) + 1:], {})[name] = value
        return rows


def tcp_reachable(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
