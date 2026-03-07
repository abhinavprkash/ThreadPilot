"""Amazon Bedrock client wrapper for LLM operations."""

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
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    region: str = "us-east-1"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9


class BedrockClient:
    """
    Wrapper for Amazon Bedrock foundation models.

    Supports Claude 3 models from Anthropic for team digest generation.
    """

    def __init__(
        self,
        config: Optional[BedrockConfig] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """
        Initialize Bedrock client.

        Args:
            config: Bedrock configuration
            aws_access_key_id: AWS access key (or use AWS_ACCESS_KEY_ID env var)
            aws_secret_access_key: AWS secret key (or use AWS_SECRET_ACCESS_KEY env var)
            aws_session_token: AWS session token (optional,for temporary credentials)
        """
        if not BEDROCK_AVAILABLE:
            raise ImportError("boto3 is required. Install with: pip install boto3")

        self.config = config or BedrockConfig()

        # Initialize boto3 client
        session_kwargs = {}
        if aws_access_key_id:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        if aws_session_token:
            session_kwargs['aws_session_token'] = aws_session_token

        # Use environment variables if credentials not provided
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.config.region,
            **session_kwargs
        )

    def generate_content(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate content using Claude 3 model.

        Args:
            prompt: User prompt/question
            system_prompt: System instructions (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            Generated text response
        """
        # Build request body for Claude 3
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "top_p": self.config.top_p,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        try:
            response = self.client.invoke_model(
                modelId=self.config.model_id,
                body=json.dumps(body),
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Claude 3 response format
            if 'content' in response_body:
                # Extract text from content blocks
                content_blocks = response_body['content']
                if isinstance(content_blocks, list) and len(content_blocks) > 0:
                    return content_blocks[0].get('text', '')

            # Fallback: return entire response as string
            return json.dumps(response_body)

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            raise Exception(f"Bedrock API error ({error_code}): {error_message}")

    def generate_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output using Claude 3.

        Args:
            prompt: User prompt requesting JSON output
            system_prompt: System instructions
            schema: Optional JSON schema for validation

        Returns:
            Parsed JSON response
        """
        # Enhance prompt to request JSON
        json_prompt = f"{prompt}\n\nPlease respond with valid JSON only, no additional text."

        response_text = self.generate_content(
            prompt=json_prompt,
            system_prompt=system_prompt,
        )

        # Try to extract JSON from response
        try:
            # Try parsing the entire response
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in markdown code blocks
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_str = response_text[json_start:json_end].strip()
                return json.loads(json_str)
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                json_str = response_text[json_start:json_end].strip()
                return json.loads(json_str)
            else:
                # Return raw text if can't parse as JSON
                return {"error": "Could not parse JSON", "raw_response": response_text}

    @classmethod
    def from_env(cls) -> "BedrockClient":
        """
        Create client from environment variables.

        Environment variables:
        - BEDROCK_MODEL_ID (default: anthropic.claude-3-sonnet-20240229-v1:0)
        - BEDROCK_REGION (default: us-east-1)
        - AWS_ACCESS_KEY_ID (required)
        - AWS_SECRET_ACCESS_KEY (required)
        - AWS_SESSION_TOKEN (optional)
        """
        config = BedrockConfig(
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"),
            region=os.getenv("BEDROCK_REGION", "us-east-1"),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
        )

        return cls(
            config=config,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )


# Example usage
if __name__ == "__main__":
    # Test Bedrock client
    client = BedrockClient.from_env()

    response = client.generate_content(
        prompt="What are the key benefits of using Amazon Bedrock for AI applications?",
        system_prompt="You are a helpful AWS solutions architect.",
    )

    print("Response:", response)
