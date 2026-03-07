"""Base agent class for all digest agents."""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..observability import logger

try:
    from ..bedrock_client import BedrockClient, BedrockConfig
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


class BaseAgent(ABC):
    """
    Base class for all digest agents.

    Each agent:
    - Takes a list of formatted messages as input
    - Uses a specific prompt to extract information
    - Returns structured JSON output

    Supports mock mode for testing without API keys.
    Uses AWS Bedrock (Claude) as the LLM provider.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        mock_mode: bool = False,
    ):
        self.model_name = model_name or os.getenv(
            "BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0"
        )
        self.temperature = temperature or float(os.getenv("TEMPERATURE", "0.3"))
        self.mock_mode = mock_mode or os.getenv("MOCK_LLM", "").lower() == "true"

        self.client = None

        # Only initialize client if not in mock mode
        if not self.mock_mode:
            try:
                if not BEDROCK_AVAILABLE:
                    raise ImportError("boto3 not installed. Run: pip install boto3")

                config = BedrockConfig(
                    model_id=self.model_name,
                    temperature=self.temperature,
                    region=os.getenv("BEDROCK_REGION", "us-east-1"),
                )
                self.client = BedrockClient(config=config)
                logger.info(f"Initialized Bedrock client with model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize Bedrock client, falling back to mock mode: {e}")
                self.mock_mode = True

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

    def _get_feedback_instructions(self, team_name: str = "") -> str:
        """Get feedback-based instructions to enhance the prompt."""
        try:
            from ..feedback import PromptEnhancer
            enhancer = PromptEnhancer()

            # Get item type from agent name (e.g., "BlockerDetector" -> "blocker")
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

    def _build_prompt(self, messages_text: str, team_name: str = "") -> str:
        """Build the complete prompt with feedback-enhanced instructions."""
        # Get feedback-based instructions
        feedback_instructions = self._get_feedback_instructions(team_name)

        # Enhance system prompt with feedback
        system_prompt = "You are an expert at analyzing Slack messages and extracting structured information. Always respond with valid JSON."
        if feedback_instructions:
            system_prompt += feedback_instructions

        # Format the complete prompt
        user_prompt = self.prompt_template.format(
            messages=messages_text,
            team_name=team_name
        )

        return f"{system_prompt}\n\n{user_prompt}"

    def process(self, messages_text: str, team_name: str = "") -> dict:
        """
        Process messages and extract information.

        Args:
            messages_text: Formatted message text for LLM
            team_name: Name of the team for context

        Returns:
            Structured dictionary with extracted information
        """
        if not messages_text.strip():
            logger.warning(f"{self.agent_name}: No messages to process")
            return self._empty_result()

        # Use mock responses if in mock mode
        if self.mock_mode:
            logger.info(f"{self.agent_name}: Using mock response (no API key)")
            return self._mock_result(messages_text, team_name)

        try:
            # Build prompt
            prompt = self._build_prompt(messages_text, team_name)

            # Call AWS Bedrock (Claude) API
            system_prompt = (
                "You are an expert at analyzing Slack messages and extracting structured information. "
                "Always respond with valid JSON only, no additional text or markdown."
            )
            response_text = self.client.generate_content(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=self.temperature,
            )

            # Parse JSON response
            result = json.loads(response_text)
            logger.debug(f"{self.agent_name} result: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"{self.agent_name} JSON parse error: {e}")
            return self._empty_result()
        except Exception as e:
            logger.error(f"{self.agent_name} error: {e}")
            return self._empty_result()

    @abstractmethod
    def _empty_result(self) -> dict:
        """Return empty result structure for this agent."""
        pass

    def _mock_result(self, messages_text: str, team_name: str) -> dict:
        """
        Generate a mock result for testing.

        Override in subclasses for more realistic mocks.
        """
        return self._empty_result()

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count."""
        # Approximation: 1 token ≈ 4 characters
        return len(text) // 4
