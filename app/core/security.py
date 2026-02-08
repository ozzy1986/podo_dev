"""
Security utilities for JWT, password hashing, and Waves signature verification.
"""

import base64
import hashlib
import logging
import secrets
import struct
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt
import bcrypt

from app.config import SecuritySettings
from app.core.exceptions import AuthError

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manager for security operations (JWT, passwords, signatures)."""

    def __init__(self, settings: SecuritySettings):
        self.settings = settings

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt(rounds=self.settings.bcrypt_rounds)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against a hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False

    def create_jwt_token(
        self,
        user_id: int,
        wallet_address: Optional[str] = None,
        extra_claims: Optional[Dict[str, Any]] = None,
        token_type: str = "access",
    ) -> str:
        """Create a JWT token (access or refresh).

        Args:
            user_id: User ID
            wallet_address: Optional wallet address to embed
            extra_claims: Extra payload claims
            token_type: ``"access"`` (short-lived) or ``"refresh"`` (long-lived)

        Returns:
            Encoded JWT string
        """
        now = datetime.now(timezone.utc)
        if token_type == "refresh":
            # Refresh tokens last 60 days
            expires_at = now + timedelta(days=60)
        else:
            expires_at = now + timedelta(hours=self.settings.jwt_expiry_hours)

        payload = {
            'user_id': user_id,
            'wallet': wallet_address,
            'type': token_type,
            'iat': now,
            'exp': expires_at,
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )

    def create_token_pair(
        self,
        user_id: int,
        wallet_address: Optional[str] = None,
    ) -> Dict[str, str]:
        """Create both access and refresh tokens.

        Returns:
            Dict with ``access_token`` and ``refresh_token`` keys.
        """
        return {
            'access_token': self.create_jwt_token(user_id, wallet_address, token_type="access"),
            'refresh_token': self.create_jwt_token(user_id, wallet_address, token_type="refresh"),
        }

    def verify_jwt_token(self, token: str, expected_type: str = "access") -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT string
            expected_type: Expected token type (``"access"`` or ``"refresh"``)

        Returns:
            Decoded payload dict
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            # Validate token type (backward compat: tokens without 'type' are access tokens)
            actual_type = payload.get('type', 'access')
            if actual_type != expected_type:
                raise AuthError(f"Expected {expected_type} token, got {actual_type}")
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthError(f"Invalid token: {str(e)}")

    def generate_nonce(self) -> str:
        """Generate a random nonce for verification."""
        return secrets.token_urlsafe(self.settings.nonce_length_bytes)

    # WX Network Web Auth API: signed data = Prefix + URL host + Provided Data,
    # each as length + UTF-8 value. See:
    # https://docs.waves.exchange/en/waves-exchange/waves-exchange-client-api/waves-exchange-web-auth-api#how-to-check-signature-validity
    WX_AUTH_PREFIX = "WavesWalletAuthentication"

    def _wx_auth_message_bytes(
        self, second_part: str, data: str, length_size: int = 2
    ) -> bytes:
        """Build the byte string that WX Network signs. second_part = referrer URL or host."""
        prefix_bytes = self.WX_AUTH_PREFIX.encode("utf-8")
        second_bytes = second_part.encode("utf-8")
        data_bytes = data.encode("utf-8")
        if length_size == 2:
            pack_len = lambda n: struct.pack(">H", n)
        else:
            pack_len = lambda n: struct.pack(">I", n)
        return (
            pack_len(len(prefix_bytes)) + prefix_bytes
            + pack_len(len(second_bytes)) + second_bytes
            + pack_len(len(data_bytes)) + data_bytes
        )

    def _verify_signature_bytes(
        self, pub_key_bytes: bytes, message_bytes: bytes, sig_bytes: bytes
    ) -> bool:
        """Verify signature once message is in bytes. Uses same curve as pywaves (axolotl_curve25519)."""
        try:
            import axolotl_curve25519 as curve
            return curve.verifySignature(pub_key_bytes, message_bytes, sig_bytes) == 0
        except ImportError as e:
            logger.warning("axolotl_curve25519 not available for signature verification: %s", e)
            return False

    def verify_waves_signature(
        self,
        message: str,
        signature: str,
        public_key: str,
        host: Optional[str] = None,
        referrer: Optional[str] = None,
    ) -> bool:
        """
        Verify a Waves blockchain signature (Ed25519/Curve25519).

        For WX Network Web Auth API, signed data = Prefix + (referrer or host) + Data,
        each as length+value. Docs say "your host parameter value" - the param is r= (full URL).
        We try: referrer (full origin), then host (hostname); and 2-byte then 4-byte length.

        Args:
            message: The `d=` data sent to WX (from sessionStorage).
            signature: Base58 signature from WX callback (`s=`).
            public_key: Base58 public key (`p=`).
            host: Hostname (e.g. dev.d.onl).
            referrer: Full referrer URL sent as r= (e.g. https://dev.d.onl).

        Returns:
            True if signature is valid.
        """
        try:
            pub_key_bytes = base58_decode(public_key)
            sig_bytes = base58_decode(signature)

            if pub_key_bytes is None or sig_bytes is None:
                logger.warning("Failed to decode base58 public key or signature")
                return False

            if len(pub_key_bytes) != 32:
                logger.warning(f"Invalid public key length: {len(pub_key_bytes)} (expected 32)")
                return False

            if len(sig_bytes) != 64:
                logger.warning(f"Invalid signature length: {len(sig_bytes)} (expected 64)")
                return False

            # 1. WX Web Auth (waves-transactions serializeAuthData): prefix + host + data, each LEN(SHORT)=2-byte big-endian + UTF-8. Try host first, then referrer; 2-byte then 4-byte length.
            second_parts = []
            if host and host.strip():
                second_parts.append(host.strip())
            if referrer and referrer.strip() and referrer.strip() not in second_parts:
                second_parts.append(referrer.strip())

            attempt = 0
            for second in second_parts:
                for length_size in (2, 4):
                    attempt += 1
                    wx_message = self._wx_auth_message_bytes(second, message, length_size)
                    ok = self._verify_signature_bytes(pub_key_bytes, wx_message, sig_bytes)
                    if ok:
                        logger.info(
                            "Waves signature verified (WX Web Auth, second=%s, len=%d)",
                            second[:50], length_size,
                        )
                        return True

            # 2. Raw message
            message_bytes = message.encode("utf-8")
            raw_ok = self._verify_signature_bytes(pub_key_bytes, message_bytes, sig_bytes)
            if raw_ok:
                logger.info("Waves signature verified (raw message)")
                return True

            # 3. Legacy binary prefix
            prefixed = b"\xff\x01" + struct.pack(">H", len(message_bytes)) + message_bytes
            leg_ok = self._verify_signature_bytes(pub_key_bytes, prefixed, sig_bytes)
            if leg_ok:
                logger.info("Waves signature verified (binary prefix)")
                return True

            logger.warning("Waves signature verification failed for all message formats")
            return False

        except ImportError:
            logger.error(
                "pywaves-ce not installed. Cannot verify Waves signatures. "
                "Install with: pip install pywaves-ce"
            )
            return False
        except Exception as e:
            logger.error(f"Waves signature verification error: {e}", exc_info=True)
            return False

    def verify_wallet_matches_public_key(self, wallet_address: str, public_key: str) -> bool:
        """
        Verify that a wallet address is derived from the given public key.
        Waves address = version(1) + chainId(1) + hash(hash(pubkey))(20) + checksum(4)

        Args:
            wallet_address: Waves address (base58)
            public_key: Base58-encoded public key

        Returns:
            True if the wallet matches the public key
        """
        try:
            import pywaves as pw

            pub_key_bytes = base58_decode(public_key)
            if pub_key_bytes is None or len(pub_key_bytes) != 32:
                return False

            # Derive address from public key using pywaves
            addr = pw.Address(publicKey=public_key)
            derived = addr.address if hasattr(addr, 'address') else str(addr)

            matches = derived == wallet_address
            if not matches:
                logger.warning(
                    f"Wallet mismatch: claimed={wallet_address}, derived={derived}"
                )
            return matches

        except Exception as e:
            logger.error(f"Error verifying wallet/pubkey match: {e}")
            return False


def base58_decode(data: str) -> Optional[bytes]:
    """Decode a base58-encoded string to bytes."""
    try:
        import base58
        return base58.b58decode(data)
    except ImportError:
        pass

    # Fallback: manual base58 decode
    try:
        alphabet = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        result = 0
        for char in data.encode('ascii'):
            result = result * 58 + alphabet.index(char)

        # Convert to bytes
        byte_length = (result.bit_length() + 7) // 8
        result_bytes = result.to_bytes(byte_length, 'big') if byte_length > 0 else b'\x00'

        # Handle leading zeros
        pad_size = 0
        for char in data:
            if char == '1':
                pad_size += 1
            else:
                break

        return b'\x00' * pad_size + result_bytes
    except Exception as e:
        logger.error(f"Base58 decode failed: {e}")
        return None
