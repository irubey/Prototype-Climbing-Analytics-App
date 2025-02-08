# Implements premium query evaluation logic (using v3)

from typing import Dict, Any, List, Tuple, Optional
import logging
import re
from dataclasses import dataclass

from ..model_wrappers.v3_client import DeepseekV3Client
from ...context.context_formatter import ContextFormatter
from app.services.ai.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    """Container for query evaluation results"""
    needs_reasoning: bool
    confidence: float
    triggers: List[str]
    evaluation_type: str  # 'heuristic', 'model', or 'hybrid'

class QueryEvaluator:
    """
    Evaluates premium user queries to determine complexity and need for advanced reasoning.
    Uses both heuristic rules and model-based evaluation.
    """
    
    # Keywords and patterns that suggest need for advanced reasoning
    COMPLEXITY_TRIGGERS = {
        'planning': [
            r'training plan',
            r'progression',
            r'schedule',
            r'program',
            r'periodization',
            r'long[- ]term',
            r'roadmap'
        ],
        'analysis': [
            r'analyze',
            r'compare',
            r'evaluate',
            r'assessment',
            r'breakdown',
            r'detailed',
            r'comprehensive',
            r'in[- ]depth'
        ],
        'technical': [
            r'technique',
            r'form',
            r'beta',
            r'sequence',
            r'movement pattern',
            r'body position'
        ],
        'metrics': [
            r'grade[s]?',
            r'statistics',
            r'metrics',
            r'progress',
            r'trends',
            r'history',
            r'performance'
        ]
    }
    
    # Confidence thresholds
    HEURISTIC_THRESHOLD = 0.6
    MODEL_THRESHOLD = 0.8
    
    def __init__(
        self,
        v3_client: DeepseekV3Client,
        context_formatter: ContextFormatter,
        enable_hybrid: bool = True
    ):
        self.v3_client = v3_client
        self.context_formatter = context_formatter
        self.enable_hybrid = enable_hybrid

    async def evaluate_query(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> EvaluationResult:
        """
        Evaluates query complexity using hybrid approach (heuristics + model).
        
        Args:
            message: User's query
            context: User's climbing context
            conversation_history: Optional conversation history
            
        Returns:
            EvaluationResult containing evaluation details
        """
        try:
            # First check heuristic rules
            heuristic_result = self._apply_heuristics(message)
            
            # If heuristic result is highly confident, use it
            if heuristic_result.confidence >= self.HEURISTIC_THRESHOLD:
                logger.debug(
                    "Using heuristic evaluation",
                    extra={
                        "confidence": heuristic_result.confidence,
                        "triggers": heuristic_result.triggers
                    }
                )
                return heuristic_result
                
            # If hybrid mode enabled, use model evaluation
            if self.enable_hybrid:
                model_result = await self._get_model_evaluation(
                    message, context, conversation_history
                )
                
                # Combine results if model is confident
                if model_result.confidence >= self.MODEL_THRESHOLD:
                    return self._combine_evaluations(heuristic_result, model_result)
                    
            # Default to heuristic result if model evaluation isn't conclusive
            return heuristic_result
            
        except Exception as e:
            logger.error(f"Error evaluating query: {str(e)}", exc_info=True)
            # On error, default to simpler path
            return EvaluationResult(
                needs_reasoning=False,
                confidence=1.0,
                triggers=[],
                evaluation_type='fallback'
            )

    def _apply_heuristics(self, message: str) -> EvaluationResult:
        """Applies heuristic rules to evaluate query complexity"""
        message = message.lower()
        triggered_patterns = []
        category_scores = []
        
        # Check each category of triggers
        for category, patterns in self.COMPLEXITY_TRIGGERS.items():
            category_triggers = []
            
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    category_triggers.append(pattern)
                    
            if category_triggers:
                triggered_patterns.extend(category_triggers)
                # Score based on percentage of patterns matched in category
                category_scores.append(len(category_triggers) / len(patterns))
        
        # Calculate overall confidence
        if not category_scores:
            confidence = 0.0
        else:
            # Weight both breadth (number of categories) and depth (matches within categories)
            breadth = len(category_scores) / len(self.COMPLEXITY_TRIGGERS)
            depth = sum(category_scores) / len(category_scores)
            confidence = (breadth + depth) / 2
        
        needs_reasoning = confidence >= self.HEURISTIC_THRESHOLD
        
        return EvaluationResult(
            needs_reasoning=needs_reasoning,
            confidence=confidence,
            triggers=triggered_patterns,
            evaluation_type='heuristic'
        )

    async def _get_model_evaluation(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> EvaluationResult:
        """Gets model-based evaluation of query complexity"""
        try:
            # Format context for evaluation
            formatted_context = self.context_formatter.format_climber_context(
                context.get("core_data", {}).get("climber_summary", {})
            )
            
            # Get model evaluation
            evaluation = await self.v3_client.evaluate_complexity(
                message,
                formatted_context.conversational_context,
                conversation_history
            )
            
            # Parse evaluation response
            needs_reasoning = evaluation.lower().strip() == PromptManager.EVALUATION_RESPONSE_ADVANCED
            
            # Assign confidence based on response clarity
            confidence = 1.0 if evaluation.lower().strip() in [
                PromptManager.EVALUATION_RESPONSE_ADVANCED,
                PromptManager.EVALUATION_RESPONSE_NORMAL
            ] else 0.5
            
            return EvaluationResult(
                needs_reasoning=needs_reasoning,
                confidence=confidence,
                triggers=["model_evaluation"],
                evaluation_type='model'
            )
            
        except Exception as e:
            logger.error(f"Model evaluation failed: {str(e)}", exc_info=True)
            return EvaluationResult(
                needs_reasoning=False,
                confidence=0.0,
                triggers=[],
                evaluation_type='model_failed'
            )

    def _combine_evaluations(
        self,
        heuristic: EvaluationResult,
        model: EvaluationResult
    ) -> EvaluationResult:
        """Combines heuristic and model evaluations"""
        # If both agree, high confidence
        if heuristic.needs_reasoning == model.needs_reasoning:
            confidence = max(heuristic.confidence, model.confidence)
            triggers = list(set(heuristic.triggers + model.triggers))
            
            return EvaluationResult(
                needs_reasoning=heuristic.needs_reasoning,
                confidence=confidence,
                triggers=triggers,
                evaluation_type='hybrid'
            )
            
        # If they disagree, use the one with higher confidence
        if model.confidence > heuristic.confidence:
            return model
        return heuristic

    def update_heuristics(self, new_patterns: Dict[str, List[str]]) -> None:
        """
        Updates complexity trigger patterns.
        Allows dynamic updating of heuristics based on learning.
        """
        try:
            # Validate new patterns
            for category, patterns in new_patterns.items():
                if not all(isinstance(p, str) for p in patterns):
                    raise ValueError(f"Invalid patterns in category {category}")
                    
            # Update patterns
            self.COMPLEXITY_TRIGGERS.update(new_patterns)
            
            logger.info(
                "Updated complexity triggers",
                extra={"new_categories": list(new_patterns.keys())}
            )
            
        except Exception as e:
            logger.error(f"Failed to update heuristics: {str(e)}", exc_info=True)
            raise