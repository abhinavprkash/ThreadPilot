"""Amazon Bedrock client wrapper using the unified Converse API.

Uses the Bedrock Converse API which works uniformly across all models:
  - Amazon Nova Micro / Lite / Pro
  - Anthropic Claude 3 / 3.5
  - Meta Llama 3
  - Any future Bedrock model

This avoids model-specific request formats (e.g. anthropic_version) so
you can swap models by just changing BEDROCK_MODEL_ID in .env.
"""

import json
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import boto3
    from botocore.exceptions import ClientError
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False
    print("Warning: boto3 not installed. Install with: pip install boto3")


@dataclass
class BedrockConfig:
    """Configuration for Bedrock client."""
    model_id: str = "amazon.nova-micro-v1:0"
    region: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9


class BedrockClient:
    """
    Wrapper for Amazon Bedrock foundation models using the Converse API.

    The Converse API provides a single, consistent interface across all
    Bedrock models — no model-specific request body needed.
    """

    def __init__(
        self,
        config: Optional[BedrockConfig] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        if not BEDROCK_AVAILABLE:
            raise ImportError("boto3 is required. Install with: pip install boto3")

        self.config = config or BedrockConfig()

        session_kwargs = {}
        if aws_access_key_id:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.config.region,
            **session_kwargs,
        )

    def generate_content(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate text using the Bedrock Converse API.

        Works with Amazon Nova, Claude, Llama, and all other Bedrock models.

        Args:
            prompt: User message
            system_prompt: System instructions (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text string
        """
        messages = [
            {"role": "user", "content": [{"text": prompt}]}
        ]

        inference_config = {
            "maxTokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "topP": self.config.top_p,
        }

        converse_kwargs: Dict[str, Any] = {
            "modelId": self.config.model_id,
            "messages": messages,
            "inferenceConfig": inference_config,
        }

        if system_prompt:
            converse_kwargs["system"] = [{"text": system_prompt}]

        try:
            response = self.client.converse(**converse_kwargs)

            # Converse API unified response format
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if content and isinstance(content, list):
                return content[0].get("text", "")
            return ""

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            raise Exception(f"Bedrock API error ({error_code}): {error_message}")

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: System instructions
            schema: Unused (kept for API compatibility)

        Returns:
            Parsed JSON dict
        """
        json_system = (
            (system_prompt + "\n\n" if system_prompt else "")
            + "Respond with valid JSON only. No markdown, no explanation, just the JSON object."
        )

        response_text = self.generate_content(
            prompt=prompt,
            system_prompt=json_system,
        )

        # Try direct parse first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences if present
        for fence in ("```json", "```"):
            if fence in response_text:
                start = response_text.find(fence) + len(fence)
                end = response_text.find("```", start)
                snippet = response_text[start:end].strip()
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    pass

        return {"error": "Could not parse JSON", "raw_response": response_text}

    @classmethod
    def from_env(cls) -> "BedrockClient":
        """Create client from environment variables."""
        config = BedrockConfig(
            model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0"),
            region=os.getenv("BEDROCK_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
        )
        return cls(
            config=config,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )


if __name__ == "__main__":
    client = BedrockClient.from_env()
    response = client.generate_content(
        prompt="What are the key benefits of using Amazon Bedrock for AI applications?",
        system_prompt="You are a helpful AWS solutions architect.",
    )
    print("Response:", response)
