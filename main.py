from __future__ import annotations

import base64
import hashlib
import io
import os
import struct
import zlib
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import cv2  # type: ignore
except Exception as exc:  # pragma: no cover
    cv2 = None


APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")

MAGIC = b"STG1"
HEADER_FMT = ">4sI16s12s"
HEADER_LEN = struct.calcsize(HEADER_FMT)
PBKDF2_ITERS = 200_000
REDUNDANCY = 3


@dataclass
class Metrics:
    mse: float
    psnr: float
    capacity_bytes: int
    used_bytes: int


def derive_key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase:
        raise ValueError("Key is required.")
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERS,
        dklen=32,
    )


def encrypt_payload(plaintext: bytes, passphrase: str) -> Tuple[bytes, bytes, bytes]:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return ciphertext, salt, nonce


def decrypt_payload(ciphertext: bytes, passphrase: str, salt: bytes, nonce: bytes) -> bytes:
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def build_inner_payload(data: bytes, filename: str) -> bytes:
    data_hash = hashlib.sha256(data).digest()
    name_bytes = filename.encode("utf-8") if filename else b""
    if len(name_bytes) > 65535:
        raise ValueError("Filename too long.")
    compressed = zlib.compress(data, level=9)
    header = struct.pack(">32sH", data_hash, len(name_bytes))
    return header + name_bytes + compressed


def parse_inner_payload(payload: bytes) -> Tuple[bytes, str, bytes]:
    if len(payload) < 34:
        raise ValueError("Payload too small.")
    data_hash, name_len = struct.unpack(">32sH", payload[:34])
    name_start = 34
    name_end = name_start + name_len
    if name_end > len(payload):
        raise ValueError("Invalid payload name length.")
    name = payload[name_start:name_end].decode("utf-8", errors="replace")
    compressed = payload[name_end:]
    data = zlib.decompress(compressed)
    return data_hash, name, data


def image_to_array(image_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes))
    image = image.convert("RGB")
    return np.array(image, dtype=np.uint8)


def array_to_png_bytes(arr: np.ndarray) -> bytes:
    image = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def compute_edge_depth_map(arr: np.ndarray) -> np.ndarray:
    if cv2 is None:
        raise RuntimeError("OpenCV is required for adaptive embedding.")
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    edges = cv2.Laplacian(gray, cv2.CV_64F)
    mag = np.abs(edges)
    max_val = mag.max() if mag.size else 0.0
    norm = mag / (max_val + 1e-6)
    depth = np.where(norm > 0.25, 2, 1).astype(np.uint8)
    return depth


def bits_from_bytes(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def bytes_from_bits(bits: np.ndarray) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("Bit length must be multiple of 8.")
    return np.packbits(bits).tobytes()


def seed_from_key(passphrase: str) -> int:
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def embed_bits(arr: np.ndarray, bits: np.ndarray, passphrase: str) -> np.ndarray:
    h, w, _ = arr.shape
    depth_map = compute_edge_depth_map(arr)
    capacity_bits = int(depth_map.sum() * 3)
    encoded_bits = np.repeat(bits, REDUNDANCY)
    if len(encoded_bits) > capacity_bits:
        raise ValueError("Payload too large for this image.")
    flat = arr.reshape(-1, 3).copy()
    order = np.arange(h * w)
    rng = np.random.default_rng(seed_from_key(passphrase))
    rng.shuffle(order)
    bit_idx = 0
    for idx in order:
        depth = int(depth_map.flat[idx])
        if depth <= 0:
            continue
        for ch in range(3):
            if bit_idx >= len(encoded_bits):
                return flat.reshape(h, w, 3)
            take = min(depth, len(encoded_bits) - bit_idx)
            bit_chunk = encoded_bits[bit_idx:bit_idx + take]
            bit_idx += take
            value = 0
            for bit in bit_chunk:
                value = (value << 1) | int(bit)
            mask = (1 << take) - 1
            flat[idx, ch] = (flat[idx, ch] & ~mask) | value
    return flat.reshape(h, w, 3)


def extract_bits(arr: np.ndarray, total_bits: int, passphrase: str) -> np.ndarray:
    h, w, _ = arr.shape
    depth_map = compute_edge_depth_map(arr)
    flat = arr.reshape(-1, 3)
    order = np.arange(h * w)
    rng = np.random.default_rng(seed_from_key(passphrase))
    rng.shuffle(order)
    raw_bits = np.zeros(total_bits * REDUNDANCY, dtype=np.uint8)
    bit_idx = 0
    for idx in order:
        depth = int(depth_map.flat[idx])
        if depth <= 0:
            continue
        for ch in range(3):
            if bit_idx >= len(raw_bits):
                return decode_redundancy(raw_bits)
            take = min(depth, len(raw_bits) - bit_idx)
            mask = (1 << take) - 1
            value = flat[idx, ch] & mask
            bits = np.unpackbits(np.array([value], dtype=np.uint8))[-take:]
            raw_bits[bit_idx:bit_idx + take] = bits
            bit_idx += take
    return decode_redundancy(raw_bits)


def decode_redundancy(raw_bits: np.ndarray) -> np.ndarray:
    if len(raw_bits) % REDUNDANCY != 0:
        raw_bits = raw_bits[: len(raw_bits) - (len(raw_bits) % REDUNDANCY)]
    blocks = raw_bits.reshape(-1, REDUNDANCY)
    votes = np.sum(blocks, axis=1)
    return (votes >= (REDUNDANCY // 2 + 1)).astype(np.uint8)


def compute_metrics(original: np.ndarray, stego: np.ndarray, used_bits: int) -> Metrics:
    diff = original.astype(np.float32) - stego.astype(np.float32)
    mse = float(np.mean(np.square(diff)))
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = 20 * np.log10(255.0 / np.sqrt(mse))
    depth_map = compute_edge_depth_map(original)
    capacity_bits = int(depth_map.sum() * 3)
    effective_bits = capacity_bits // REDUNDANCY
    capacity_bytes = effective_bits // 8
    used_bytes = used_bits // 8
    return Metrics(mse=mse, psnr=float(psnr), capacity_bytes=capacity_bytes, used_bytes=used_bytes)


def detect_steg(arr: np.ndarray) -> Tuple[float, str]:
    channels = [arr[:, :, i] for i in range(3)]
    entropies = []
    chis = []
    corrs = []
    for ch in channels:
        lsb = (ch & 1).flatten()
        counts = np.bincount(lsb, minlength=2).astype(np.float64)
        p = counts / (counts.sum() + 1e-9)
        entropy = -np.sum(p * np.log2(p + 1e-12))
        entropies.append(entropy)
        expected = counts.sum() / 2.0
        chi = float(np.sum((counts - expected) ** 2 / (expected + 1e-9)))
        chis.append(chi)
        if len(lsb) > 1:
            corrs.append(float(np.corrcoef(lsb[:-1], lsb[1:])[0, 1]))
        else:
            corrs.append(0.0)
    entropy_avg = float(np.mean(entropies) / 1.0)
    chi_norm = float(np.mean(chis) / 5.0)
    corr_avg = float(np.mean(np.abs(corrs)))
    score = 0.55 * entropy_avg + 0.25 * (1.0 / (1.0 + chi_norm)) + 0.20 * (1.0 - corr_avg)
    label = "Likely contains hidden data" if score >= 0.62 else "Likely clean image"
    return score, label


app = FastAPI(title="Advanced Image Steganography System")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/api/embed")
async def embed(
    image: UploadFile = File(...),
    key: str = Form(...),
    secret_text: str | None = Form(None),
    secret_file: UploadFile | None = File(None),
) -> JSONResponse:
    if not image:
        raise HTTPException(status_code=400, detail="Cover image is required.")
    img_bytes = await image.read()
    arr = image_to_array(img_bytes)

    data: bytes
    filename = ""
    if secret_file is not None:
        data = await secret_file.read()
        filename = secret_file.filename or ""
    elif secret_text is not None and secret_text.strip():
        data = secret_text.encode("utf-8")
        filename = "secret.txt"
    else:
        raise HTTPException(status_code=400, detail="Secret text or file is required.")

    inner = build_inner_payload(data, filename)
    ciphertext, salt, nonce = encrypt_payload(inner, key)
    header = struct.pack(HEADER_FMT, MAGIC, len(ciphertext), salt, nonce)
    payload = header + ciphertext
    bits = bits_from_bytes(payload)
    stego = embed_bits(arr, bits, key)
    metrics = compute_metrics(arr, stego, len(bits))
    stego_png = array_to_png_bytes(stego)
    encoded = base64.b64encode(stego_png).decode("ascii")
    return JSONResponse(
        {
            "stego_image_base64": encoded,
            "filename": "stego.png",
            "metrics": {
                "mse": metrics.mse,
                "psnr": metrics.psnr,
                "capacity_bytes": metrics.capacity_bytes,
                "used_bytes": metrics.used_bytes,
            },
        }
    )


@app.post("/api/extract")
async def extract(
    image: UploadFile = File(...),
    key: str = Form(...),
) -> JSONResponse:
    if not image:
        raise HTTPException(status_code=400, detail="Stego image is required.")
    img_bytes = await image.read()
    arr = image_to_array(img_bytes)

    header_bits = extract_bits(arr, HEADER_LEN * 8, key)
    header = bytes_from_bits(header_bits)
    magic, payload_len, salt, nonce = struct.unpack(HEADER_FMT, header)
    if magic != MAGIC:
        raise HTTPException(status_code=400, detail="No hidden data found or wrong key.")
    total_bits = (HEADER_LEN + payload_len) * 8
    all_bits = extract_bits(arr, total_bits, key)
    payload_bytes = bytes_from_bits(all_bits)[HEADER_LEN:]
    plaintext = decrypt_payload(payload_bytes, key, salt, nonce)
    expected_hash, filename, data = parse_inner_payload(plaintext)
    actual_hash = hashlib.sha256(data).digest()
    verified = expected_hash == actual_hash
    data_b64 = base64.b64encode(data).decode("ascii")
    return JSONResponse(
        {
            "filename": filename or "extracted.bin",
            "data_base64": data_b64,
            "verified": verified,
            "sha256": actual_hash.hex(),
        }
    )


@app.post("/api/detect")
async def detect(image: UploadFile = File(...)) -> JSONResponse:
    if not image:
        raise HTTPException(status_code=400, detail="Image is required.")
    img_bytes = await image.read()
    arr = image_to_array(img_bytes)
    score, label = detect_steg(arr)
    return JSONResponse({"score": score, "label": label})
