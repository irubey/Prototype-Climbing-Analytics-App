# Handles calls to the r1 advanced reasoning module

from typing import Dict, Any, List, Optional, Tuple
import logging
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import time
import statistics
from enum import Enum
from collections import defaultdict

from ..model_wrappers.r1_client import R1Client
from ...context.context_formatter import ContextFormatter
from ...grade_processor import GradeProcessor
from app.services.ai.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

@dataclass
class ReasoningStep:
    """Represents a single step in the reasoning process"""
    step_type: str  # 'analysis', 'comparison', 'recommendation', etc.
    description: str
    data_points: List[str]
    confidence: float

@dataclass
class R1Response:
    """Container for R1's split response format"""
    reasoning_content: str
    content: str

@dataclass
class ReasoningResult:
    """Container for complete reasoning analysis"""
    conclusion: str
    steps: List[ReasoningStep]
    confidence: float
    metadata: Dict[str, Any]
    reasoning_trace: Optional[str] = None  # Store original reasoning content

class ResponseFormat(Enum):
    """Supported response formats from R1 model"""
    STEP_BASED = "step_based"
    ANALYSIS_BASED = "analysis_based"
    STRUCTURED_JSON = "structured_json"

@dataclass
class AnalysisMetrics:
    """Container for detailed analysis metrics"""
    processing_time: float
    step_count: int
    confidence: float
    context_completeness: float
    error_count: int
    step_distribution: Dict[str, int]
    timing_breakdown: Dict[str, float]
    has_reasoning_trace: bool

class ResponseParser:
    """Handles parsing and structuring of R1 model responses"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".ResponseParser")
        self._format_handlers = {
            ResponseFormat.STEP_BASED: self._parse_step_based,
            ResponseFormat.ANALYSIS_BASED: self._parse_analysis_based,
            ResponseFormat.STRUCTURED_JSON: self._parse_structured_json
        }

    def parse_response(
        self,
        response: str,
        expected_format: ResponseFormat = ResponseFormat.STEP_BASED
    ) -> List[Dict[str, Any]]:
        """Parses R1 response into structured steps"""
        try:
            handler = self._format_handlers.get(expected_format)
            if not handler:
                raise ValueError(f"Unsupported response format: {expected_format}")
                
            parse_start = time.time()
            structured_steps = handler(response)
            parse_time = time.time() - parse_start
            
            self.logger.debug(
                "Response parsed successfully",
                extra={
                    "format": expected_format.value,
                    "step_count": len(structured_steps),
                    "parse_time": parse_time
                }
            )
            
            return structured_steps
            
        except Exception as e:
            self.logger.error(
                "Response parsing failed",
                extra={
                    "error": str(e),
                    "format": expected_format.value,
                    "response_length": len(response)
                },
                exc_info=True
            )
            return [{
                "type": "error",
                "description": "Failed to parse analysis response",
                "data_points": [str(e)],
                "confidence": 0.0
            }]

    def _parse_step_based(self, response: str) -> List[Dict[str, Any]]:
        """Parses step-based response format"""
        sections = response.split("\n\n")
        structured_steps = []
        current_step = None
        current_points = []
        
        for section in sections:
            if section.startswith("Step ") or section.startswith("Analysis "):
                if current_step:
                    structured_steps.append(self._create_step_dict(
                        current_step, current_points
                    ))
                current_step = section.strip()
                current_points = []
            elif section.strip().startswith("-"):
                current_points.extend(self._extract_points(section))
        
        if current_step:
            structured_steps.append(self._create_step_dict(
                current_step, current_points
            ))
            
        return structured_steps

    def _parse_analysis_based(self, response: str) -> List[Dict[str, Any]]:
        """Parses analysis-based response format"""
        sections = response.split("\n\n")
        structured_steps = []
        
        for section in sections:
            if not section.strip():
                continue
                
            lines = section.split("\n")
            description = lines[0].strip()
            points = self._extract_points("\n".join(lines[1:]))
            
            if description and points:
                structured_steps.append(self._create_step_dict(
                    description, points
                ))
                
        return structured_steps

    def _parse_structured_json(self, response: str) -> List[Dict[str, Any]]:
        """Parses JSON-structured response format"""
        try:
            data = json.loads(response)
            structured_steps = []
            
            for step in data.get("steps", []):
                structured_steps.append({
                    "type": step.get("type", "general"),
                    "description": step.get("description", ""),
                    "data_points": step.get("points", []),
                    "confidence": step.get("confidence", 0.5)
                })
                
            return structured_steps
            
        except json.JSONDecodeError as e:
            self.logger.error("JSON parsing failed", exc_info=True)
            return self._parse_step_based(response)  # Fallback to step-based parsing

    def _create_step_dict(
        self,
        description: str,
        points: List[str]
    ) -> Dict[str, Any]:
        """Creates a structured step dictionary"""
        return {
            "type": self._determine_step_type(description),
            "description": description,
            "data_points": points,
            "confidence": self._estimate_step_confidence(description, points)
        }

    def _extract_points(self, section: str) -> List[str]:
        """Extracts and cleans bullet points from text"""
        return [
            point.strip("- ").strip()
            for point in section.split("\n")
            if point.strip() and point.strip().startswith("-")
        ]

    def _determine_step_type(self, step_text: str) -> str:
        """Determines the type of analysis step from its text"""
        step_text = step_text.lower()
        if "compar" in step_text:
            return "comparison"
        elif "analy" in step_text:
            return "analysis"
        elif "recommend" in step_text:
            return "recommendation"
        else:
            return "general"

    def _estimate_step_confidence(self, description: str, data_points: List[str]) -> float:
        """Estimates confidence in a step based on its content"""
        # Base confidence on multiple factors
        confidence = 0.5  # Start at middle
        
        # Adjust based on specificity
        if len(data_points) >= 3:
            confidence += 0.2
        
        # Adjust based on quantitative content
        if any(self._contains_numeric(point) for point in data_points):
            confidence += 0.2
            
        # Adjust based on certainty language
        certainty_markers = ["clearly", "definitely", "shows", "demonstrates"]
        uncertainty_markers = ["might", "could", "possibly", "perhaps"]
        
        text = description.lower() + " " + " ".join(data_points).lower()
        confidence += 0.1 * sum(marker in text for marker in certainty_markers)
        confidence -= 0.1 * sum(marker in text for marker in uncertainty_markers)
        
        return max(0.0, min(1.0, confidence))

    def _contains_numeric(self, text: str) -> bool:
        """Checks if text contains numeric data"""
        return any(char.isdigit() for char in text)

class MetricsCollector:
    """Collects and aggregates analysis metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".MetricsCollector")
        self.metrics_history = defaultdict(list)
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initializes metrics containers"""
        self.current_session = {
            "processing_times": defaultdict(list),
            "confidence_scores": defaultdict(list),
            "error_rates": defaultdict(int),
            "context_completeness": [],
            "step_distributions": defaultdict(lambda: defaultdict(int))
        }

    def record_metrics(
        self,
        metrics: AnalysisMetrics,
        analysis_type: str
    ) -> None:
        """Records metrics for the current analysis"""
        try:
            # Update processing times
            self.current_session["processing_times"][analysis_type].append(
                metrics.processing_time
            )
            
            # Update confidence scores
            self.current_session["confidence_scores"][analysis_type].append(
                metrics.confidence
            )
            
            # Update error counts
            if metrics.error_count > 0:
                self.current_session["error_rates"][analysis_type] += 1
            
            # Update step distributions
            for step_type, count in metrics.step_distribution.items():
                self.current_session["step_distributions"][analysis_type][step_type] += count
            
            # Update context completeness
            self.current_session["context_completeness"].append(
                metrics.context_completeness
            )
            
            # Log detailed metrics
            self.logger.info(
                "Analysis metrics recorded",
                extra={
                    "metrics": asdict(metrics),
                    "analysis_type": analysis_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to record metrics",
                extra={"error": str(e)},
                exc_info=True
            )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Generates summary statistics for the current session"""
        try:
            summary = {
                "processing_times": {},
                "confidence_scores": {},
                "error_rates": {},
                "context_completeness": {
                    "mean": statistics.mean(self.current_session["context_completeness"]),
                    "std": statistics.stdev(self.current_session["context_completeness"])
                    if len(self.current_session["context_completeness"]) > 1 else 0
                }
            }
            
            # Calculate statistics for each analysis type
            for analysis_type in self.current_session["processing_times"].keys():
                times = self.current_session["processing_times"][analysis_type]
                scores = self.current_session["confidence_scores"][analysis_type]
                
                summary["processing_times"][analysis_type] = {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "std": statistics.stdev(times) if len(times) > 1 else 0
                }
                
                summary["confidence_scores"][analysis_type] = {
                    "mean": statistics.mean(scores),
                    "median": statistics.median(scores),
                    "std": statistics.stdev(scores) if len(scores) > 1 else 0
                }
                
                total_analyses = len(times)
                error_count = self.current_session["error_rates"][analysis_type]
                summary["error_rates"][analysis_type] = {
                    "count": error_count,
                    "rate": error_count / total_analyses if total_analyses > 0 else 0
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(
                "Failed to generate performance summary",
                extra={"error": str(e)},
                exc_info=True
            )
            return {}

class ReasoningEngine:
    """
    Handles advanced reasoning and analysis using the R1 model.
    Provides structured, multi-step analysis for complex climbing queries.
    """

    def __init__(
        self,
        r1_client: R1Client,
        context_formatter: ContextFormatter,
        grade_processor: GradeProcessor
    ):
        self.r1_client = r1_client
        self.context_formatter = context_formatter
        self.grade_processor = grade_processor
        self.analysis_timeout = 45  # seconds
        
        # Initialize components
        self.response_parser = ResponseParser()
        self.metrics_collector = MetricsCollector()
        self.logger = logging.getLogger(__name__)

    async def analyze_query(
        self,
        query: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> ReasoningResult:
        """
        Performs deep analysis of user query using available context.
        
        Args:
            query: User's question or request
            context: Complete user context including climbing history
            conversation_history: Optional conversation history
            
        Returns:
            Structured reasoning result with analysis steps
        """
        start_time = time.time()
        try:
            # Track processing steps with timing
            step_times = {}
            
            # Format context
            context_start = time.time()
            formatted_context = self._prepare_context(context)
            step_times["context_preparation"] = time.time() - context_start
            
            # Create analysis plan
            plan_start = time.time()
            analysis_plan = self._create_analysis_plan(query, formatted_context)
            step_times["plan_creation"] = time.time() - plan_start
            
            # Execute analysis
            analysis_start = time.time()
            reasoning_steps = await self._execute_analysis(
                query, formatted_context, analysis_plan, conversation_history
            )
            step_times["analysis_execution"] = time.time() - analysis_start
            
            # Synthesize results
            synthesis_start = time.time()
            conclusion = self._synthesize_conclusion(reasoning_steps)
            confidence = self._calculate_confidence(reasoning_steps)
            step_times["synthesis"] = time.time() - synthesis_start
            
            # Log detailed metrics
            self._log_analysis_metrics(
                query=query,
                plan=analysis_plan,
                steps=reasoning_steps,
                timing=step_times,
                confidence=confidence
            )
            
            return ReasoningResult(
                conclusion=conclusion,
                steps=reasoning_steps,
                confidence=confidence,
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "context_completeness": self._assess_context_completeness(context),
                    "analysis_approach": analysis_plan["approach"],
                    "processing_time": time.time() - start_time,
                    "step_timing": step_times
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Analysis failed",
                extra={
                    "error": str(e),
                    "query": query,
                    "processing_time": time.time() - start_time,
                    "context_size": len(json.dumps(context))
                },
                exc_info=True
            )
            raise

    def _prepare_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepares and enriches context for advanced reasoning"""
        try:
            # Get formatted context
            formatted_context = self.context_formatter.format_climber_context(
                context.get("core_data", {}).get("climber_summary", {})
            )
            
            # Enrich with grade analysis
            enriched_context = self._enrich_grade_context(
                formatted_context.structured_context
            )
            
            # Add performance metrics
            if "performance_metrics" in context.get("core_data", {}):
                enriched_context["performance_analysis"] = self._analyze_performance(
                    context["core_data"]["performance_metrics"]
                )
            
            return enriched_context
            
        except Exception as e:
            logger.error(f"Context preparation failed: {str(e)}", exc_info=True)
            return formatted_context.structured_context  # Fall back to basic context

    def _create_analysis_plan(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Creates structured plan for analyzing the query"""
        # Identify key analysis dimensions based on R1 structure
        dimensions = []
        query_lower = query.lower()
        
        # Map query keywords to R1 analysis sections
        section_mappings = {
            "observations": ["data", "metrics", "patterns", "history"],
            "analysis": ["compare", "evaluate", "analyze", "breakdown", "technical"],
            "recommendations": ["plan", "advice", "suggest", "improve", "should"],
            "confidence": ["certain", "confidence", "sure", "likely"]
        }
        
        for section, keywords in section_mappings.items():
            if any(keyword in query_lower for keyword in keywords):
                dimensions.append(section)
                
        # Determine analysis depth
        depth = "comprehensive" if len(dimensions) > 1 else "focused"
        
        return {
            "dimensions": dimensions,
            "depth": depth,
            "approach": "multi_dimensional" if len(dimensions) > 1 else "single_focus",
            "required_context": self._determine_required_context(dimensions)
        }

    async def _execute_analysis(
        self,
        query: str,
        context: Dict[str, Any],
        analysis_plan: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> List[ReasoningStep]:
        """Executes the analysis plan using R1 model"""
        execution_start = time.time()
        
        try:
            # Build analysis prompt
            prompt_start = time.time()
            analysis_prompt = self._build_analysis_prompt(
                query, context, analysis_plan
            )
            prompt_time = time.time() - prompt_start
            
            # Get R1 analysis with split response
            analysis_start = time.time()
            raw_response = await self.r1_client.get_analysis(
                analysis_prompt,
                context,
                conversation_history
            )
            analysis_time = time.time() - analysis_start
            
            # Extract reasoning and content parts
            r1_response = R1Response(
                reasoning_content=raw_response.choices[0].message.reasoning_content,
                content=raw_response.choices[0].message.content
            )
            
            # Log reasoning trace for debugging
            self.logger.debug(
                "R1 reasoning trace",
                extra={
                    "reasoning_content": r1_response.reasoning_content,
                    "content_length": len(r1_response.content)
                }
            )
            
            # Parse and structure the content part
            parse_start = time.time()
            structured_analysis = self.response_parser.parse_response(
                r1_response.content,
                ResponseFormat.STEP_BASED
            )
            parse_time = time.time() - parse_start
            
            # Convert to reasoning steps
            steps = [
                ReasoningStep(
                    step_type=step["type"],
                    description=step["description"],
                    data_points=step["data_points"],
                    confidence=self._calculate_step_confidence(
                        step,
                        r1_response.reasoning_content
                    )
                )
                for step in structured_analysis
            ]
            
            # Record metrics with reasoning trace info
            self.metrics_collector.record_metrics(
                AnalysisMetrics(
                    processing_time=time.time() - execution_start,
                    step_count=len(steps),
                    confidence=sum(s.confidence for s in steps) / len(steps) if steps else 0,
                    context_completeness=self._assess_context_completeness(context),
                    error_count=sum(1 for s in steps if s.step_type == "error"),
                    step_distribution={
                        step_type: len([s for s in steps if s.step_type == step_type])
                        for step_type in set(s.step_type for s in steps)
                    },
                    timing_breakdown={
                        "prompt_generation": prompt_time,
                        "model_analysis": analysis_time,
                        "response_parsing": parse_time
                    },
                    has_reasoning_trace=bool(r1_response.reasoning_content)
                ),
                analysis_plan["depth"]
            )
            
            return steps
            
        except Exception as e:
            self.logger.error(
                "Analysis execution failed",
                extra={
                    "error": str(e),
                    "execution_time": time.time() - execution_start,
                    "analysis_plan": analysis_plan
                },
                exc_info=True
            )
            return [ReasoningStep(
                step_type="error",
                description="Analysis failed due to technical error",
                data_points=[str(e)],
                confidence=0.0
            )]

    def _calculate_step_confidence(
        self,
        step: Dict[str, Any],
        reasoning_content: str
    ) -> float:
        """
        Calculates confidence for a step, incorporating reasoning trace.
        Adjusts confidence based on alignment between step and reasoning.
        """
        # Base confidence from step content
        base_confidence = self._estimate_step_confidence(
            step["description"],
            step["data_points"]
        )
        
        # If no reasoning content, return base confidence
        if not reasoning_content:
            return base_confidence
            
        try:
            # Check alignment with reasoning
            reasoning_alignment = self._calculate_reasoning_alignment(
                step,
                reasoning_content
            )
            
            # Combine base confidence with reasoning alignment
            adjusted_confidence = (base_confidence * 0.7) + (reasoning_alignment * 0.3)
            
            return min(1.0, max(0.0, adjusted_confidence))
            
        except Exception as e:
            self.logger.warning(
                f"Failed to incorporate reasoning into confidence: {str(e)}",
                exc_info=True
            )
            return base_confidence

    def _calculate_reasoning_alignment(
        self,
        step: Dict[str, Any],
        reasoning_content: str
    ) -> float:
        """Calculates how well a step aligns with the reasoning trace"""
        try:
            # Extract key concepts from step
            step_concepts = set(
                word.lower()
                for text in [step["description"]] + step["data_points"]
                for word in text.split()
            )
            
            # Extract concepts from relevant reasoning section
            reasoning_concepts = set(
                word.lower()
                for word in reasoning_content.split()
            )
            
            # Calculate concept overlap
            if not step_concepts:
                return 0.0
                
            overlap = len(step_concepts.intersection(reasoning_concepts))
            alignment = overlap / len(step_concepts)
            
            return min(1.0, alignment)
            
        except Exception as e:
            self.logger.warning(
                f"Failed to calculate reasoning alignment: {str(e)}",
                exc_info=True
            )
            return 0.0

    def _enrich_grade_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enriches context with grade analysis"""
        enriched = context.copy()
        
        try:
            # Add grade comparisons
            if "grades" in context:
                sport_grades = context["grades"].get("sport", {})
                trad_grades = context["grades"].get("trad", {})
                boulder_grades = context["grades"].get("boulder", {})
                
                enriched["grade_analysis"] = {
                    "relative_difficulty": {
                        "sport_to_trad_delta": self._compare_grades(
                            sport_grades.get("highest_clean"),
                            trad_grades.get("highest_clean"),
                            "sport",
                            "trad"
                        ),
                        "onsight_to_redpoint_delta": self._compare_grades(
                            sport_grades.get("onsight"),
                            sport_grades.get("highest_clean"),
                            "sport",
                            "sport"
                        )
                    }
                }
            
            return enriched
            
        except Exception as e:
            logger.error(f"Grade enrichment failed: {str(e)}", exc_info=True)
            return context

    def _analyze_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes performance metrics for patterns and insights"""
        try:
            recent_sends = metrics.get("recent_sends", [])
            
            if not recent_sends:
                return {}
                
            # Analyze send patterns
            send_analysis = {
                "attempts_distribution": self._analyze_attempts(recent_sends),
                "style_patterns": self._analyze_styles(recent_sends),
                "grade_progression": self._analyze_progression(recent_sends)
            }
            
            return send_analysis
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {str(e)}", exc_info=True)
            return {}

    def _synthesize_conclusion(self, steps: List[ReasoningStep]) -> str:
        """Synthesizes analysis steps into final conclusion"""
        try:
            # Filter out error steps
            valid_steps = [s for s in steps if s.step_type != "error"]
            
            if not valid_steps:
                return "Analysis could not be completed due to errors."
                
            # Use R1 structure for conclusion formatting
            sections = PromptManager.R1_ANALYSIS_STRUCTURE["sections"]
            conclusion_parts = []
            
            # Add observations
            high_confidence_observations = [
                step.description for step in valid_steps
                if step.confidence >= 0.7 and step.step_type == "observations"
            ]
            if high_confidence_observations:
                conclusion_parts.append(f"{sections['observations']['title']}")
                conclusion_parts.extend([f"{sections['observations']['formatting']['bullet_style']} {obs}" 
                                      for obs in high_confidence_observations])
            
            # Add analysis
            analysis_points = [
                step.description for step in valid_steps
                if step.step_type == "analysis"
            ]
            if analysis_points:
                conclusion_parts.append(f"\n{sections['analysis']['title']}")
                conclusion_parts.extend([f"{sections['analysis']['formatting']['bullet_style']} {point}" 
                                      for point in analysis_points])
            
            # Add recommendations
            recommendations = [
                point for step in valid_steps
                for point in step.data_points if "recommend" in point.lower()
            ]
            if recommendations:
                conclusion_parts.append(f"\n{sections['recommendations']['title']}")
                conclusion_parts.extend([f"{sections['recommendations']['formatting']['bullet_style']} {rec}" 
                                      for rec in recommendations])
            
            # Add confidence assessment
            confidence_parts = []
            for step in valid_steps:
                confidence_level = "high" if step.confidence >= 0.8 else "medium" if step.confidence >= 0.5 else "low"
                confidence_parts.append(f"{sections['confidence']['formatting']['bullet_style']} {PromptManager.R1_ANALYSIS_STRUCTURE['confidence_levels'][confidence_level]}")
            
            if confidence_parts:
                conclusion_parts.append(f"\n{sections['confidence']['title']}")
                conclusion_parts.extend(confidence_parts)
            
            return "\n".join(conclusion_parts)
            
        except Exception as e:
            logger.error(f"Conclusion synthesis failed: {str(e)}", exc_info=True)
            return "Error synthesizing conclusion."

    def _calculate_confidence(self, steps: List[ReasoningStep]) -> float:
        """Calculates overall confidence in the analysis"""
        if not steps:
            return 0.0
            
        # Weight steps by type
        weights = {
            "analysis": 1.0,
            "comparison": 0.8,
            "recommendation": 0.7,
            "error": 0.0
        }
        
        weighted_sum = sum(
            step.confidence * weights.get(step.step_type, 0.5)
            for step in steps
        )
        
        return weighted_sum / len(steps)

    def _compare_grades(
        self,
        grade1: Optional[str],
        grade2: Optional[str],
        discipline1: str,
        discipline2: str
    ) -> Dict[str, Any]:
        """Compares two grades and provides relative difficulty analysis"""
        if not grade1 or not grade2:
            return {"comparable": False}
            
        try:
            code1 = self.grade_processor.convert_grades_to_codes(
                [grade1], discipline1
            )[0]
            code2 = self.grade_processor.convert_grades_to_codes(
                [grade2], discipline2
            )[0]
            
            return {
                "comparable": True,
                "difference": code1 - code2,
                "relative_difficulty": "harder" if code1 > code2 else "easier"
            }
            
        except Exception as e:
            logger.error(f"Grade comparison failed: {str(e)}", exc_info=True)
            return {"comparable": False, "error": str(e)}

    def _assess_context_completeness(self, context: Dict[str, Any]) -> float:
        """Assesses how complete the available context is"""
        required_fields = [
            "climber_summary",
            "performance_metrics",
            "recent_activity"
        ]
        
        available = sum(
            1 for field in required_fields
            if field in context.get("core_data", {})
        )
        
        return available / len(required_fields)

    def _determine_required_context(self, dimensions: List[str]) -> List[str]:
        """Determines required context fields based on analysis dimensions"""
        # Map R1 sections to required context fields
        context_mapping = {
            "observations": ["grades", "performance_metrics"],
            "analysis": ["style_preferences", "recent_activity"],
            "recommendations": ["training_context", "health_metrics"],
            "confidence": ["data_completeness", "historical_accuracy"]
        }
        
        required = set()
        for dim in dimensions:
            required.update(context_mapping.get(dim, []))
            
        return list(required)

    def _build_analysis_prompt(
        self,
        query: str,
        context: Dict[str, Any],
        analysis_plan: Dict[str, Any]
    ) -> str:
        """Builds the complete prompt for R1 analysis"""
        return PromptManager.get_r1_analysis_prompt(query, context)

    def _format_context_summary(self, context: Dict[str, Any]) -> str:
        """Formats context for inclusion in prompt"""
        summary_parts = []
        
        # Climber profile
        if "climber_profile" in context:
            profile = context["climber_profile"]
            summary_parts.append(f"{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['observations']['title']}")
            summary_parts.append(f"- Experience: {profile.get('experience', {}).get('years_outside', 'unknown')} years")
            summary_parts.append(f"- Primary Discipline: {profile.get('experience', {}).get('primary_discipline', 'unknown')}")
            
            # Grade information
            grades = profile.get("grades", {})
            for discipline, data in grades.items():
                if data.get("highest_clean"):
                    summary_parts.append(f"- {discipline.title()} Highest Clean: {data['highest_clean']}")
        
        # Performance metrics
        if "performance_analysis" in context:
            perf = context["performance_analysis"]
            summary_parts.append(f"\n{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['analysis']['title']}")
            if "attempts_distribution" in perf:
                summary_parts.append("- Send Patterns: " + json.dumps(perf["attempts_distribution"]))
            if "grade_progression" in perf:
                summary_parts.append("- Grade Progression: " + json.dumps(perf["grade_progression"]))
        
        # Training context
        if "training_context" in context:
            training = context["training_context"]
            summary_parts.append(f"\n{PromptManager.R1_ANALYSIS_STRUCTURE['sections']['recommendations']['title']}")
            summary_parts.append(f"- Frequency: {training.get('frequency', 'unknown')}")
            summary_parts.append(f"- Session Length: {training.get('session_length', 'unknown')}")
            
        return "\n".join(summary_parts)

    def _format_analysis_requirements(self, plan: Dict[str, Any]) -> str:
        """Formats analysis requirements for prompt"""
        requirements = []
        
        # Add depth-specific requirements based on R1 structure
        sections = PromptManager.R1_ANALYSIS_STRUCTURE["sections"]
        
        if plan["depth"] == "comprehensive":
            requirements.extend([
                sections["observations"]["description"],
                sections["analysis"]["description"],
                sections["recommendations"]["description"],
                sections["confidence"]["description"]
            ])
        else:
            # For focused analysis, use core sections
            requirements.extend([
                sections["observations"]["description"],
                sections["recommendations"]["description"]
            ])
        
        # Add required context fields
        requirements.append("\nRequired Analysis Fields:")
        for field in plan["required_context"]:
            requirements.append(f"- {field}")
        
        return "\n".join(requirements)

    def _log_analysis_metrics(
        self,
        query: str,
        plan: Dict[str, Any],
        steps: List[ReasoningStep],
        timing: Dict[str, float],
        confidence: float
    ) -> None:
        """Logs detailed metrics about the analysis process"""
        metrics = {
            "query_length": len(query),
            "analysis_dimensions": len(plan["dimensions"]),
            "analysis_depth": plan["depth"],
            "step_count": len(steps),
            "step_types": {
                step_type: len([s for s in steps if s.step_type == step_type])
                for step_type in set(s.step_type for s in steps)
            },
            "confidence_scores": {
                "overall": confidence,
                "steps": [s.confidence for s in steps]
            },
            "timing": timing,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "structure_adherence": self._calculate_structure_adherence(steps)
        }
        
        self.logger.info(
            "Analysis metrics",
            extra={
                "metrics": metrics,
                "analysis_plan": plan
            }
        )

    def _calculate_structure_adherence(self, steps: List[ReasoningStep]) -> float:
        """Calculates how well the analysis follows R1 structure"""
        expected_sections = set(PromptManager.R1_ANALYSIS_STRUCTURE["sections"].keys())
        found_sections = set(step.step_type for step in steps)
        return len(found_sections.intersection(expected_sections)) / len(expected_sections)