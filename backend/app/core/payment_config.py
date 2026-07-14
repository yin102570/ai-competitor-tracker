"""
支付配置与签名工具 - 微信支付 / 支付宝
安全规则: 所有密钥从环境变量注入，严禁硬编码

支持渠道:
  - 微信支付 v3 API（HMAC-SHA256签名 + AES-256-GCM解密）
  - 支付宝（RSA2签名验签）

引用 app.core.config.settings 用于环境判断
"""

import base64
import hashlib
import hmac
import json
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings


# ============================================================
# 支付配置 - 从环境变量 / .env 读取
# ============================================================

class PaymentSettings(BaseSettings):
    """
    支付模块独立配置
    与主 Settings 分离，避免污染核心配置；复用同一份 .env 文件
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 微信支付 v3 ===
    wechat_app_id: str = ""
    wechat_mch_id: str = ""
    wechat_api_v3_key: str = ""          # APIv3密钥（用于回调解密）
    wechat_api_key: str = ""             # 商户API密钥（v2兼容）
    wechat_serial_no: str = ""           # 商户证书序列号
    wechat_private_key: str = ""         # 商户私钥（PEM，用于请求签名）
    wechat_public_key: str = ""          # 微信平台公钥（用于验签回调）
    wechat_notify_url: str = ""          # 支付回调通知地址
    wechat_base_url: str = "https://api.mch.weixin.qq.com"

    # === 支付宝 ===
    alipay_app_id: str = ""
    alipay_private_key: str = ""         # 应用私钥（PEM，用于请求签名）
    alipay_public_key: str = ""          # 支付宝公钥（用于验签回调）
    alipay_notify_url: str = ""          # 异步回调通知地址
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"
    alipay_sign_type: str = "RSA2"

    # === 订单超时（分钟）===
    order_expire_minutes: int = 30

    @property
    def wechat_configured(self) -> bool:
        """微信支付是否已配置关键参数"""
        return bool(self.wechat_app_id and self.wechat_mch_id and self.wechat_api_v3_key)

    @property
    def alipay_configured(self) -> bool:
        """支付宝是否已配置关键参数"""
        return bool(self.alipay_app_id and self.alipay_private_key and self.alipay_public_key)


@lru_cache
def get_payment_settings() -> PaymentSettings:
    """获取支付配置单例"""
    return PaymentSettings()


payment_settings = get_payment_settings()


# ============================================================
# 微信支付 v3 签名工具
# ============================================================

class WechatSigner:
    """
    微信支付 v3 签名/验签工具
    请求签名: 使用商户私钥对 (HTTP方法\nURL\n时间戳\n随机串\nbody) 做RSA-SHA256签名
    回调验签: 使用微信平台公钥验证签名头
    回调解密: 使用APIv3密钥做AES-256-GCM解密
    """

    @staticmethod
    def build_signature_message(
        method: str,
        url: str,
        timestamp: str,
        nonce: str,
        body: str,
    ) -> str:
        """
        构造微信v3待签名串
        格式: HTTP_METHOD\n请求URL\n时间戳\n随机字符串\n请求报文主体\n
        """
        return f"{method}\n{url}\n{timestamp}\n{nonce}\n{body}\n"

    @staticmethod
    def sign(
        method: str,
        url: str,
        timestamp: str,
        nonce: str,
        body: str,
        private_key_pem: str | None = None,
    ) -> str:
        """
        使用商户私钥生成RSA-SHA256签名（请求签名）
        返回 Base64 编码的签名字符串
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        pem = private_key_pem or payment_settings.wechat_private_key
        if not pem:
            raise ValueError("微信支付商户私钥未配置")

        message = WechatSigner.build_signature_message(
            method, url, timestamp, nonce, body
        )
        private_key = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
        signature = private_key.sign(
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify(
        timestamp: str,
        nonce: str,
        body: str,
        signature: str,
        public_key_pem: str | None = None,
    ) -> bool:
        """
        验证微信回调签名
        参数:
            timestamp: 微信回调头 Wechatpay-Timestamp
            nonce:     微信回调头 Wechatpay-Nonce
            body:      微信回调原始报文（JSON字符串）
            signature: 微信回调头 Wechatpay-Signature（Base64）
        返回: True=验签通过
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        pem = public_key_pem or payment_settings.wechat_public_key
        if not pem:
            raise ValueError("微信平台公钥未配置")

        # 微信v3回调验签待签名串: timestamp\nnonce\nbody\n
        message = f"{timestamp}\n{nonce}\n{body}\n"
        public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
        try:
            public_key.verify(
                base64.b64decode(signature),
                message.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    @staticmethod
    def decrypt_resource(
        ciphertext: str,
        nonce: str,
        associated_data: str,
        api_v3_key: str | None = None,
    ) -> dict[str, Any]:
        """
        解密微信回调中的加密资源（AES-256-GCM）
        参数:
            ciphertext:       resource.ciphertext（Base64）
            nonce:            resource.nonce
            associated_data:  resource.associated_data
        返回: 解密后的JSON字典（含 out_trade_no / transaction_id 等）
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = (api_v3_key or payment_settings.wechat_api_v3_key).encode("utf-8")
        ciphertext_bytes = base64.b64decode(ciphertext)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(
            ciphertext_bytes,
            nonce.encode("utf-8"),
            associated_data.encode("utf-8") if associated_data else None,
        )
        return json.loads(plaintext.decode("utf-8"))

    @staticmethod
    def build_auth_header(
        method: str,
        url: str,
        body: str,
    ) -> str:
        """
        构建微信v3请求 Authorization 头
        格式: WECHATPAY2-SHA256-RSA2048 mchid="...",nonce_str="...",timestamp="...",serial_no="...",signature="..."
        """
        import secrets
        import time

        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = WechatSigner.sign(method, url, timestamp, nonce, body)

        return (
            f'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{payment_settings.wechat_mch_id}",'
            f'nonce_str="{nonce}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{payment_settings.wechat_serial_no}",'
            f'signature="{signature}"'
        )


# ============================================================
# 支付宝签名工具
# ============================================================

class AlipaySigner:
    """
    支付宝签名/验签工具（RSA2 / RSA-SHA256）
    签名: 对参数按 ASCII 升序拼接，使用应用私钥签名
    验签: 对回调参数（剔除 sign/sign_type）按 ASCII 升序拼接，使用支付宝公钥验签
    """

    @staticmethod
    def build_sign_data(params: dict[str, Any]) -> str:
        """
        构造支付宝待签名串
        规则: 参数按key升序拼接为 key=value&key=value，空值与sign/sign_type排除
        """
        filtered = {
            k: v for k, v in params.items()
            if v not in (None, "") and k not in ("sign", "sign_type")
        }
        sorted_items = sorted(filtered.items(), key=lambda x: x[0])
        return "&".join(f"{k}={v}" for k, v in sorted_items)

    @staticmethod
    def sign(params: dict[str, Any], private_key_pem: str | None = None) -> str:
        """
        使用应用私钥对参数签名（RSA-SHA256）
        返回 Base64 编码的签名字符串
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        pem = private_key_pem or payment_settings.alipay_private_key
        if not pem:
            raise ValueError("支付宝应用私钥未配置")

        message = AlipaySigner.build_sign_data(params)
        private_key = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
        signature = private_key.sign(
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def verify(
        params: dict[str, Any],
        sign: str,
        public_key_pem: str | None = None,
    ) -> bool:
        """
        验证支付宝回调签名
        参数:
            params: 回调参数字典（含 sign/sign_type，验签时自动剔除）
            sign:   回调中的 sign 字段（Base64）
        返回: True=验签通过
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature

        pem = public_key_pem or payment_settings.alipay_public_key
        if not pem:
            raise ValueError("支付宝公钥未配置")

        message = AlipaySigner.build_sign_data(params)
        public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
        try:
            public_key.verify(
                base64.b64decode(sign),
                message.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False


# ============================================================
# 通用工具
# ============================================================

def generate_order_no(prefix: str = "PAY") -> str:
    """
    生成业务订单号
    格式: PAY{yyyyMMddHHmmss}{6位随机}
    保证高概率唯一，数据库层有 unique 约束兜底
    """
    import secrets
    from datetime import datetime, timezone, timedelta

    cst = timezone(timedelta(hours=8))
    ts = datetime.now(cst).strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(3).upper()  # 6位十六进制
    return f"{prefix}{ts}{rand}"


def md5_sign(params: dict[str, Any], api_key: str) -> str:
    """
    微信v2兼容 MD5 签名（部分接口仍需）
    规则: 参数升序拼接 + &key=API_KEY 后做 MD5 大写
    """
    filtered = {
        k: v for k, v in params.items()
        if v is not None and k != "sign" and v != ""
    }
    sorted_items = sorted(filtered.items(), key=lambda x: x[0])
    raw = "&".join(f"{k}={v}" for k, v in sorted_items)
    raw += f"&key={api_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def hmac_sha256_sign(params: dict[str, Any], api_key: str) -> str:
    """
    微信v2 HMAC-SHA256 签名
    """
    filtered = {
        k: v for k, v in params.items()
        if v is not None and k != "sign" and v != ""
    }
    sorted_items = sorted(filtered.items(), key=lambda x: x[0])
    raw = "&".join(f"{k}={v}" for k, v in sorted_items)
    raw += f"&key={api_key}"
    return hmac.new(
        api_key.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()
