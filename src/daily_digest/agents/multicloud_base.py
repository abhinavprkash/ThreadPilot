"""Agent base using AWS Bedrock for foundation model access."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Literal

from ..observability import logger

# Optional imports
try:
    from ..bedrock_client import BedrockClient, BedrockConfig
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


LLMProvider = Literal["bedrock", "mock"]


class MultiCloudAgent(ABC):
    """
    Base agent class using AWS Bedrock as foundation model provider.

    Supports:
    - AWS Bedrock (Claude 3)
    - Mock mode for testing

    Provider priority:
    1. Explicit provider parameter
    2. LLM_PROVIDER environment variable
    3. Auto-detect based on AWS credentials
    4. Fall back to mock mode
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        mock_mode: bool = False,
    ):
        """
        Initialize agent with Bedrock provider.

        Args:
            provider: "bedrock" or "mock"
            model_name: Bedrock model ID
            temperature: Sampling temperature
            mock_mode: If True, use mock responses
        """
        self.temperature = temperature or float(os.getenv("TEMPERATURE", "0.7"))
        self.mock_mode = mock_mode or os.getenv("MOCK_LLM", "").lower() == "true"

        # Determine provider
        if self.mock_mode:
            self.provider = "mock"
        elif provider:
            self.provider = provider
        else:
            self.provider = self._detect_provider()

        # Initialize client based on provider
        self.client = None
        self.model_name = model_name

        if self.provider == "bedrock":
            self._init_bedrock()
        else:
            logger.info("Using mock mode (no LLM client)")

    def _detect_provider(self) -> LLMProvider:
        """Auto-detect provider based on environment variables."""
        # Check explicit provider setting
        env_provider = os.getenv("LLM_PROVIDER", "").lower()
        if env_provider in ["bedrock", "mock"]:
            return env_provider

        # Auto-detect based on AWS credentials
        if os.getenv("AWS_ACCESS_KEY_ID") and BEDROCK_AVAILABLE:
            logger.info("Auto-detected AWS credentials, using Bedrock")
            return "bedrock"
        else:
            logger.warning("No AWS credentials found, falling back to mock mode")
            return "mock"

    def _init_bedrock(self):
        """Initialize AWS Bedrock client."""
        if not BEDROCK_AVAILABLE:
            logger.warning("boto3 not available, falling back to mock mode")
            self.provider = "mock"
            return

        try:
            config = BedrockConfig(
                model_id=self.model_name or os.getenv(
                    "BEDROCK_MODEL_ID",
                    "amazon.nova-micro-v1:0"
                ),
                temperature=self.temperature,
                region=os.getenv("BEDROCK_REGION", "us-east-1"),
            )

            self.client = BedrockClient(config=config)
            self.model_name = config.model_id
            logger.info(f"Initialized Bedrock client with model: {self.model_name}")

        except Exception as e:
            logger.warning(f"Failed to initialize Bedrock client: {e}")
            self.provider = "mock"

    @property
    @abstractmethod
    def prompt_template(self) -> str:
        """The prompt template for this agent."""
        pass

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Name of this agent for logging."""
        pass

    def _build_prompt(self, messages_text: str, team_name: str = "") -> str:
        """Build the full prompt from template and messages."""
        feedback_instructions = self._get_feedback_instructions(team_name)

        prompt = self.prompt_template.format(
            messages=messages_text,
            feedback_instructions=feedback_instructions or ""
        )

        return prompt

    def _get_feedback_instructions(self, team_name: str = "") -> str:
        """Get feedback-based instructions (optional feature)."""
        try:
            from ..feedback import PromptEnhancer
            enhancer = PromptEnhancer()

            # Determine item type from agent name
            item_type = ""
            if "Blocker" in self.agent_name:
                item_type = "blocker"
            elif "Decision" in self.agent_name:
                item_type = "decision"
            elif "Extractor" in self.agent_name or "Update" in self.agent_name:
                item_type = "update"

            return enhancer.get_prompt_instructions(team=team_name, item_type=item_type)
        except Exception:
            return ""

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate text using AWS Bedrock.

        Args:
            prompt: User prompt
            system_prompt: System instructions

        Returns:
            Generated text
        """
        if self.provider == "mock":
            return self._generate_mock(prompt)
        elif self.provider == "bedrock":
            return self._generate_bedrock(prompt, system_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _generate_bedrock(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Generate using AWS Bedrock."""
        return self.client.generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=self.temperature,
        )

    def _generate_mock(self, prompt: str) -> str:
        """Generate mock response for testing."""
        logger.debug(f"Mock mode: returning empty JSON for {self.agent_name}")
        return json.dumps({
            "mock": True,
            "agent": self.agent_name,
            "message": "Mock response - no real LLM called"
        })

    def run(self, messages: list[dict], team_name: str = "") -> dict[str, Any]:
        """
        Run the agent on messages and return structured output.

        Args:
            messages: List of Slack messages
            team_name: Team name for context

        Returns:
            Parsed JSON response
        """
        # Format messages for prompt
        messages_text = self._format_messages(messages)

        # Build prompt
        prompt = self._build_prompt(messages_text, team_name)

        # Generate response
        response_text = self.generate(prompt)

        # Parse JSON response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"{self.agent_name} returned invalid JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return {"error": str(e), "raw_response": response_text}

    def _format_messages(self, messages: list[dict]) -> str:
        """Format Slack messages for LLM prompt."""
        formatted = []
        for msg in messages:
            user = msg.get("user", "Unknown")
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            formatted.append(f"[{ts}] {user}: {text}")
        return "\n".join(formatted)
