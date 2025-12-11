import struct
import time

MAX_BITS = 1600
MAX_BYTES = MAX_BITS // 8  # 200 bytes total
HEADER_SIZE = 9  

# Message types
MSG_INIT = 0
MSG_DATA = 1
HEART_BEAT = 2
NACK_MSG = 3

# --- Simple numeric-only encryption helpers ---
# Shared numeric key (can be changed by user to any integer)
CRYPT_KEY = 0xC0FFEE

def _lcg32(seed):
    """Simple 32-bit LCG PRNG (deterministic)."""
    # constants from Numerical Recipes
    return (1664525 * seed + 1013904223) & 0xFFFFFFFF

def _prng_float(seed, index):
    """Produce a deterministic pseudo-random float in range [-1.0, 1.0].

    seed: base integer seed
    index: small integer to vary per-value
    """
    s = (seed ^ index) & 0xFFFFFFFF
    s = _lcg32(s)
    # map to [0,1)
    f = s / 2**32
    return (f * 2.0) - 1.0

def encrypt_numeric_payload(payload, device_id, seq_num, key=CRYPT_KEY):
    """Encrypt a comma-separated numeric payload (bytes or str).

    The encrypted payload is returned as bytes representing comma-separated
    floats (only digits, signs, decimal point and commas — no letters).

    Encryption is a reversible per-value offset: v_enc = v + offset
    where offset is a deterministic pseudo-random float derived from
    (key, device_id, seq_num, index).
    """
    if isinstance(payload, bytes):
        s = payload.decode('utf-8', errors='ignore')
    else:
        s = str(payload)

    parts = [p.strip() for p in s.split(',') if p.strip()]
    out = []
    base_seed = (int(key) ^ (int(device_id) << 8) ^ int(seq_num)) & 0xFFFFFFFF
    for i, token in enumerate(parts):
        try:
            v = float(token)
            rnd = _prng_float(base_seed, i)
            # offset range approx [-5, 5]
            offset = rnd * 5.0
            v_enc = v + offset
            out.append(f"{v_enc:.6f}")
        except Exception:
            # non-numeric token -> pass through unchanged (but still keep as token)
            out.append(token)

    return (",".join(out)).encode('utf-8')

def decrypt_numeric_payload(payload, device_id, seq_num, key=CRYPT_KEY):
    """Decrypt a payload produced by `encrypt_numeric_payload`.

    Accepts bytes or str and returns a string containing comma-separated
    original numeric values (or passthrough tokens for non-numeric parts).
    """
    if isinstance(payload, bytes):
        s = payload.decode('utf-8', errors='ignore')
    else:
        s = str(payload)

    parts = [p.strip() for p in s.split(',') if p.strip()]
    out = []
    base_seed = (int(key) ^ (int(device_id) << 8) ^ int(seq_num)) & 0xFFFFFFFF
    for i, token in enumerate(parts):
        try:
            v_enc = float(token)
            rnd = _prng_float(base_seed, i)
            offset = rnd * 5.0
            v = v_enc - offset
            out.append(f"{v:.6f}")
        except Exception:
            out.append(token)

    return ",".join(out)

# Units mapping
UNITS = {
    "celsius": 0,
    "fahrenheit": 1,
    "kelvin": 2,
    "percent": 3,
    "volts": 4,
    "amps": 5,
    "watts": 6,
    "meters": 7,
    "liters": 8,
    "grams": 9,
    "pascal": 10,
    "hertz": 11,
    "lux": 12,
    "db": 13,
    "ppm": 14,
    "unknown": 15
}

def unit_to_code(unit):
    """Convert unit name to code."""
    return UNITS.get(unit.lower(), 15)  # default to unknown

def code_to_unit(code):
    """Convert code to unit name."""
    for name, c in UNITS.items():
        if c == code:
            return name
    return "unknown"


def build_header(device_id, batch_count, seq_num, msg_type):
    """
    Build a 9-byte header for the UDP IoT protocol (no custom fields).
    """
    timestamp = int(time.time())
    proto_version = 1
    ms = int((time.time() * 1000) % 1000)  # 0–999 ms
    ms_high = (ms >> 8) & 0x03
    ms_low = ms & 0xFF

    # Byte 1: upper 4 bits device ID, lower 4 bits batch count
    byte1 = ((device_id & 0x0F) << 4) | (batch_count & 0x0F)

    # Byte 8: 2 bits protocol version + 2 bits message type + 00 + 2 bits ms_high
    byte8 = ((proto_version & 0x03) << 6) | ((msg_type & 0x03) << 4) | (ms_high & 0x03)

    # Pack into 9 bytes
    header = struct.pack('!B H I B B', byte1, seq_num, timestamp, byte8, ms_low)
    return header


def parse_header(data):
    """
    Decode a 9-byte header and return a dictionary of fields.
    """
    if len(data) < HEADER_SIZE:
        raise ValueError("Invalid packet: too short")

    byte1, seq, timestamp, byte8, ms_low = struct.unpack('!B H I B B', data[:HEADER_SIZE])

    device_id = (byte1 >> 4) & 0x0F
    batch_count = byte1 & 0x0F
    proto_version = (byte8 >> 6) & 0x03
    msg_type = (byte8 >> 4) & 0x03
    ms_high = byte8 & 0x03
    milliseconds = (ms_high << 8) | ms_low

    return {
        "device_id": device_id,
        "batch_count": batch_count,
        "seq": seq,
        "timestamp": timestamp,
        "proto_version": proto_version,
        "msg_type": msg_type,
        "milliseconds": milliseconds,
    }
