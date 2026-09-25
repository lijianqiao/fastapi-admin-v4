"""认证请求、响应与 JWT 载荷 Schema。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiModel, NormalizedEmail, Password, ResponseModel, Username


class UserRegister(ApiModel):
    """用户注册请求。"""

    username: Username = Field(description="用户名")
    email: NormalizedEmail = Field(description="邮箱地址")
    password: Password = Field(description="密码")


class UserLogin(ApiModel):
    """登录表单的安全边界模型。"""

    username: str = Field(min_length=1, max_length=255, description="用户名或邮箱")
    password: str = Field(min_length=1, max_length=128, description="密码")

    @field_validator("username")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("用户名或邮箱不能为空")
        return normalized.casefold()


class TokenResponse(ResponseModel):
    """access token 响应。"""

    access_token: str = Field(description="访问令牌")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0, description="access token 剩余有效秒数")


class TokenPayload(BaseModel):
    """已验证 JWT 的强类型载荷。

    不继承 ``ApiModel``：JWT 不是请求边界模型，禁止额外字段会让未来新增的
    claim（如 ``nbf``、``scope``）直接把旧代码的解析打成无效 token。
    """

    model_config = ConfigDict(extra="ignore")

    sub: str = Field(min_length=1, description="用户 ID")
    exp: int = Field(description="过期时间戳")
    iat: int = Field(description="签发时间戳")
    iss: str = Field(min_length=1, description="签发方")
    aud: str = Field(min_length=1, description="受众")
    jti: str = Field(min_length=32, max_length=64, description="令牌唯一 ID")
    type: Literal["access", "refresh"]
    ver: int = Field(ge=0, description="用户令牌版本")
    sid: str = Field(min_length=32, max_length=64, description="会话族 ID")

    @property
    def user_id(self) -> int:
        """将 JWT subject 安全转换为正整数用户 ID。"""
        try:
            user_id = int(self.sub)
        except ValueError as exc:
            raise ValueError("Token subject 不是有效用户 ID") from exc
        if user_id <= 0:
            raise ValueError("Token subject 必须是正整数")
        return user_id
