# Polishes r1 output via v3 into accessible language

from typing import Dict, Any, List, Optional, Set
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
import time
import asyncio

from ..model_wrappers.v3_client import DeepseekV3Client
from ...context.context_formatter import ContextFormatter
from ..prompt_manager import PromptManager

logger = logging.getLogger(__name__)

@dataclass
class EnhancementResult:
    """Container for enhanced response data"""
    enhanced_text: str
    original_structure: bool  # Whether original structure was preserved
    readability_score: float  # 0-1 score for estimated readability
    metadata: Dict[str, Any]
    reasoning_trace: Optional[str] = None  # Store original reasoning content

class ResponseEnhancer:
    """
    Enhances technical R1 output into engaging, accessible language using Deepseek V3.
    Maintains technical accuracy while improving readability and engagement.
    """

    # Readability markers
    COMPLEXITY_MARKERS = {
        "technical_terms": [
            "periodization", "hypertrophy", "antagonist", "proprioception",
            "biomechanical", "recruitment", "adaptation"
        ],
        "climbing_jargon": [
            "beta", "crux", "redpoint", "onsight", "flash", "project",
            "sequence", "crimps", "slopers", "jugs"
        ]
    }

    def __init__(
        self,
        v3_client: DeepseekV3Client,
        context_formatter: ContextFormatter
    ):
        self.v3_client = v3_client
        self.context_formatter = context_formatter
        self.logger = logging.getLogger(__name__ + ".ResponseEnhancer")
        self.enhancement_guidelines = PromptManager.ENHANCEMENT_GUIDELINES
        self.formatting = PromptManager.MESSAGE_STRUCTURE["formatting"]

    async def enhance_response(
        self,
        r1_content: str,
        r1_reasoning: str,
        user_context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        preserve_structure: bool = True
    ) -> EnhancementResult:
        """
        Enhances technical response into engaging, accessible language.
        
        Args:
            r1_content: Main content from R1 response
            r1_reasoning: Reasoning trace from R1 response
            user_context: User's climbing context
            conversation_history: Optional conversation history
            preserve_structure: Whether to maintain original response structure
            
        Returns:
            Enhanced response with metadata
        """
        start_time = time.time()
        
        try:
            # Format context for enhancement
            context_start = time.time()
            formatted_context = self._prepare_context(user_context)
            context_time = time.time() - context_start
            
            # Build enhancement prompt with reasoning
            prompt_start = time.time()
            enhancement_prompt = self._build_enhancement_prompt(
                r1_content,
                r1_reasoning,
                formatted_context,
                preserve_structure
            )
            prompt_time = time.time() - prompt_start
            
            # Get enhanced response
            enhance_start = time.time()
            try:
                enhanced_text = await asyncio.wait_for(
                    self.v3_client.get_chat_completion(
                        system_prompt=PromptManager.CONVERSATIONAL_ENHANCEMENT,
                        user_message=enhancement_prompt,
                        conversation_history=conversation_history
                    ),
                    timeout=30  # 30 second timeout
                )
            except asyncio.TimeoutError:
                # Use fallback prompt on timeout
                self.logger.warning("Enhancement timed out, using fallback response")
                enhanced_text = await self.v3_client.get_chat_completion(
                    system_prompt=PromptManager.CONVERSATIONAL_ENHANCEMENT,
                    user_message=PromptManager.get_fallback_prompt(
                        "timeout",
                        context_summary=formatted_context
                    )
                )
            enhance_time = time.time() - enhance_start
            
            # Calculate readability metrics
            metrics_start = time.time()
            readability_score = self._calculate_readability(
                enhanced_text,
                r1_content
            )
            metrics_time = time.time() - metrics_start
            
            # Verify structure preservation if requested
            structure_preserved = True
            if preserve_structure:
                structure_preserved = self._verify_structure_preservation(
                    r1_content,
                    enhanced_text
                )
            
            # Log enhancement metrics
            self._log_enhancement_metrics(
                original_length=len(r1_content),
                enhanced_length=len(enhanced_text),
                readability_score=readability_score,
                timing={
                    "context_preparation": context_time,
                    "prompt_generation": prompt_time,
                    "enhancement": enhance_time,
                    "metrics_calculation": metrics_time,
                    "total": time.time() - start_time
                },
                has_reasoning=bool(r1_reasoning)
            )
            
            return EnhancementResult(
                enhanced_text=enhanced_text,
                original_structure=structure_preserved,
                readability_score=readability_score,
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "processing_time": time.time() - start_time,
                    "original_length": len(r1_content),
                    "enhanced_length": len(enhanced_text),
                    "has_reasoning": bool(r1_reasoning),
                    "enhancement_guidelines": self.enhancement_guidelines["technical_to_conversational"]
                },
                reasoning_trace=r1_reasoning
            )
            
        except Exception as e:
            self.logger.error(
                "Response enhancement failed",
                extra={
                    "error": str(e),
                    "original_length": len(r1_content),
                    "processing_time": time.time() - start_time,
                    "has_reasoning": bool(r1_reasoning)
                },
                exc_info=True
            )
            # Return original text with error recovery prompt
            error_response = await self.v3_client.get_chat_completion(
                system_prompt=PromptManager.CONVERSATIONAL_ENHANCEMENT,
                user_message=PromptManager.get_fallback_prompt("error_recovery")
            )
            return EnhancementResult(
                enhanced_text=error_response,
                original_structure=True,
                readability_score=0.0,
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                    "fallback": "error_recovery"
                },
                reasoning_trace=r1_reasoning
            )

    def _prepare_context(self, user_context: Dict[str, Any]) -> str:
        """Formats user context for enhancement prompt."""
        return self.context_formatter.format_context(
            user_context,
            PromptManager.MESSAGE_STRUCTURE["context_labels"]
        )

    def _build_enhancement_prompt(
        self,
        initial_response: str,
        technical_analysis: str,
        context: str,
        preserve_structure: bool = True
    ) -> str:
        """
        Builds the enhancement prompt using centralized components.
        
        Args:
            initial_response: Original technical response
            technical_analysis: Technical reasoning/analysis
            context: Formatted user context
            preserve_structure: Whether to maintain original structure
            
        Returns:
            Complete enhancement prompt
        """
        return PromptManager.get_enhancement_prompt(
            initial_response=initial_response,
            technical_analysis=technical_analysis,
            context=context,
            preserve_structure=preserve_structure,
            formatting=self.formatting
        )

    def _calculate_readability(
        self,
        enhanced_text: str,
        original_text: str
    ) -> float:
        """
        Calculates readability improvement score.
        
        Considers:
        - Technical term reduction
        - Sentence complexity
        - Climbing jargon usage
        """
        enhanced_words = enhanced_text.lower().split()
        original_words = original_text.lower().split()
        
        # Calculate technical term reduction
        tech_terms_enhanced = sum(
            1 for word in enhanced_words
            if word in self.COMPLEXITY_MARKERS["technical_terms"]
        )
        tech_terms_original = sum(
            1 for word in original_words
            if word in self.COMPLEXITY_MARKERS["technical_terms"]
        )
        
        # Calculate climbing jargon retention
        jargon_enhanced = sum(
            1 for word in enhanced_words
            if word in self.COMPLEXITY_MARKERS["climbing_jargon"]
        )
        jargon_original = sum(
            1 for word in original_words
            if word in self.COMPLEXITY_MARKERS["climbing_jargon"]
        )
        
        # Normalize scores
        tech_reduction = 1.0 - (tech_terms_enhanced / max(tech_terms_original, 1))
        jargon_retention = jargon_enhanced / max(jargon_original, 1)
        
        # Weight the components (technical reduction more important)
        return (0.7 * tech_reduction) + (0.3 * jargon_retention)

    def _verify_structure_preservation(
        self,
        original_text: str,
        enhanced_text: str
    ) -> bool:
        """Verifies that the enhanced text maintains the original structure."""
        original_sections = self._extract_sections(original_text)
        enhanced_sections = self._extract_sections(enhanced_text)
        
        # Check if all original sections are present
        return all(
            section in enhanced_sections
            for section in original_sections
        )

    def _extract_sections(self, text: str) -> Set[str]:
        """Extracts section headers from text using centralized formatting."""
        sections = set()
        for line in text.split("\n"):
            line = line.strip()
            if any(
                line.startswith(marker)
                for marker in self.formatting["section_markers"]
            ):
                sections.add(line)
        return sections

    def _log_enhancement_metrics(
        self,
        original_length: int,
        enhanced_length: int,
        readability_score: float,
        timing: Dict[str, float],
        has_reasoning: bool
    ) -> None:
        """Logs metrics about the enhancement process."""
        self.logger.info(
            "Response enhancement completed",
            extra={
                "metrics": {
                    "original_length": original_length,
                    "enhanced_length": enhanced_length,
                    "length_ratio": enhanced_length / original_length,
                    "readability_score": readability_score,
                    "processing_time": timing,
                    "has_reasoning": has_reasoning
                }
            }
        )