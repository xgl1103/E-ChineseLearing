from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]


def _load_local_env() -> None:
    for env_path in (ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "mock"
    model: str = "gpt-4.1-mini"
    api_key: str = ""
    timeout_seconds: float = 20.0
    max_retries: int = 1
    enable_real: bool = False

    @classmethod
    def from_env(cls) -> "LLMConfig":
        _load_local_env()
        provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
        default_model = "deepseek-v4-pro" if provider == "deepseek" else "gpt-4.1-mini"
        api_key_env = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL", default_model).strip() or default_model,
            api_key=os.getenv(api_key_env, "").strip(),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
            enable_real=os.getenv("LLM_ENABLE_REAL", "0") == "1",
        )

    def real_mode_blocker(self) -> str:
        if not self.enable_real:
            return "LLM_ENABLE_REAL is not 1"
        if self.provider not in {"openai", "deepseek"}:
            return f"unsupported LLM_PROVIDER: {self.provider}"
        if not self.api_key:
            api_key_name = "DEEPSEEK_API_KEY" if self.provider == "deepseek" else "OPENAI_API_KEY"
            return f"{api_key_name} is missing"
        return ""
