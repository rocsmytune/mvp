"""对称加密原语：加密落库的敏感配置（如 LLM api_key）。

用 SECRET_KEY 派生的 HMAC-SHA256 密钥流 + 随机 IV 做流加密，避免明文落库；
仅标准库实现，不引入第三方加密库。对内网单部门场景（防备份/快照泄露）足够。

注意：密文含随机 IV，同一明文每次加密结果不同，仅可解、不可直接比较。
"""

import base64
import hashlib
import hmac
import secrets

from app.core.config import settings

_IV_LEN = 16


def _key() -> bytes:
    """由 SECRET_KEY 稳定派生 32 字节密钥。"""
    return hashlib.sha256(settings.secret_key.encode("utf-8")).digest()


def _keystream(key: bytes, iv: bytes, length: int) -> bytes:
    """HMAC-SHA256 计数器模式派生密钥流，长度不足时按块扩展。"""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(key, iv + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt_secret(plaintext: str) -> str:
    """加密为 URL 安全的 base64 字符串（含 IV 前缀）。"""
    iv = secrets.token_bytes(_IV_LEN)
    data = plaintext.encode("utf-8")
    ks = _keystream(_key(), iv, len(data))
    ct = bytes(a ^ b for a, b in zip(data, ks))
    return base64.urlsafe_b64encode(iv + ct).decode("ascii")


def decrypt_secret(token: str) -> str:
    """解密 encrypt_secret 的产物；token 非法时抛 ValueError。"""
    raw = base64.urlsafe_b64decode(token.encode("ascii"))
    iv, ct = raw[:_IV_LEN], raw[_IV_LEN:]
    ks = _keystream(_key(), iv, len(ct))
    data = bytes(a ^ b for a, b in zip(ct, ks))
    return data.decode("utf-8")


def mask_secret(plaintext: str | None) -> str | None:
    """回显打码：保留前 4 后 4 字符，其余以 **** 代替。"""
    if not plaintext:
        return None
    if len(plaintext) <= 8:
        return "****"
    return plaintext[:4] + "****" + plaintext[-4:]
