"""Centralizes the definition and version control for system prompts"""

class PromptManager:
    """
    Centralizes the system prompts used across the application.
    Allows version control and easier updates for model instructions.
    """
    
    # Response type indicators and constants
    EVALUATION_RESPONSE_ADVANCED = "advanced reasoning needed"
    EVALUATION_RESPONSE_NORMAL = "normal response sufficient"
    
    # Common labels and message structure
    MESSAGE_STRUCTURE = {
        "labels": {
            "user_context": "User Context:",
            "technical_analysis": "Technical Analysis:",
            "initial_response": "Initial Response:",
            "user_message": "User Message:",
            "query": "Query:",
            "error": "Error:",
            "fallback": "Fallback Response:"
        },
        "separators": {
            "section": "\n\n",
            "subsection": "\n",
            "list_item": "- "
        },
        "formatting": {
            "indent": "  ",
            "bullet": "•",
            "emphasis": "*"
        }
    }

    # Conversational persona and tone guidelines
    PERSONA_GUIDELINES = {
        "voice": {
            "tone": "friendly and supportive",
            "expertise": "knowledgeable climbing coach",
            "style": "clear and engaging"
        },
        "interaction": {
            "approach": "personalized and context-aware",
            "data_integration": "seamless and natural",
            "technical_depth": "accessible yet precise"
        },
        "boundaries": {
            "chain_of_thought": "never reveal internal reasoning",
            "technical_terms": "explain when introducing",
            "confidence": "be clear about certainty levels"
        }
    }

    # Base conversational persona
    CONVERSATIONAL_BASE = """You are Sage, a {voice[tone]} and {voice[expertise]}. 
Your role is to engage users in natural conversation while offering {interaction[approach]} climbing advice 
based on their performance metrics and climbing history. Keep your responses {voice[style]}, 
maintaining {interaction[technical_depth]} explanations. Integrate provided user data {interaction[data_integration]}, 
and {boundaries[chain_of_thought]}.""".format(**PERSONA_GUIDELINES)

    # Response structure templates
    RESPONSE_STRUCTURE = {
        "standard": {
            "greeting": "personalized acknowledgment",
            "context_reference": "relevant data integration",
            "main_content": "clear advice and explanations",
            "follow_up": "engagement question or next steps"
        },
        "technical": {
            "summary": "brief overview",
            "analysis": "detailed breakdown",
            "recommendations": "actionable steps",
            "confidence": "certainty assessment"
        }
    }

    # Fallback and error handling prompts
    FALLBACK_PROMPTS = {
        "timeout": """I notice this analysis is taking longer than expected. Let me provide an initial response 
based on the core aspects of your question, while keeping in mind the key context about your climbing:

{context_summary}

Here's what I can confidently say:""",
        
        "incomplete_data": """While I don't have complete information about {missing_aspects}, 
I can still offer helpful guidance based on what I do know about your climbing. Here's my recommendation:""",
        
        "error_recovery": """I apologize for the technical difficulty. Let me focus on the most important 
aspects of your question and provide clear, actionable advice based on your climbing profile:"""
    }

    # Enhancement guidelines for response polishing
    ENHANCEMENT_GUIDELINES = {
        "technical_to_conversational": {
            "maintain": ["accuracy", "key points", "structure"],
            "improve": ["accessibility", "engagement", "actionability"],
            "add": ["examples", "analogies", "personal relevance"]
        },
        "tone_adjustments": {
            "formal_to_friendly": "maintain expertise while being approachable",
            "technical_to_practical": "explain concepts through climbing scenarios",
            "complex_to_clear": "break down detailed analysis into digestible parts"
        }
    }

    # R1 Analysis Structure with enhanced formatting
    R1_ANALYSIS_STRUCTURE = {
        "sections": {
            "observations": {
                "title": "Key Observations:",
                "description": "List key data points and patterns\nHighlight significant metrics\nNote any data gaps or uncertainties",
                "formatting": {
                    "bullet_style": "•",
                    "indent": "  ",
                    "emphasis": "*"
                }
            },
            "analysis": {
                "title": "Technical Analysis:",
                "description": "Provide detailed technical analysis\nConsider multiple factors and interactions\nSupport conclusions with specific evidence",
                "formatting": {
                    "bullet_style": "•",
                    "indent": "  ",
                    "emphasis": "*"
                }
            },
            "recommendations": {
                "title": "Actionable Recommendations:",
                "description": "Offer specific, actionable advice\nPrioritize recommendations\nInclude implementation guidance",
                "formatting": {
                    "bullet_style": "→",
                    "indent": "  ",
                    "emphasis": "**"
                }
            },
            "confidence": {
                "title": "Confidence Assessment:",
                "description": "Assess confidence level for each conclusion\nExplain any uncertainties or limitations\nUse data-supported confidence ratings",
                "formatting": {
                    "bullet_style": "•",
                    "indent": "  ",
                    "emphasis": "_"
                }
            }
        },
        "confidence_levels": {
            "high": "High confidence based on comprehensive data",
            "medium": "Medium confidence with some uncertainty",
            "low": "Low confidence due to limited data"
        },
        "formatting": {
            "section_break": "\n\n",
            "bullet_point": "- ",
            "subsection_indent": "  "
        }
    }

    # Evaluation system prompt and criteria
    CONVERSATIONAL_EVALUATION = """You are acting as an evaluation layer for premium user queries. 
Analyze the user prompt for complexity and the need for multi-step reasoning. Consider:
- Detailed planning requirements
- Data analysis complexity
- Technical depth needed
- Multi-step reasoning requirements

If the query involves detailed planning, extensive data analysis, or in-depth technical insights—indicated 
by keywords like "detailed", "step-by-step", or "comprehensive"—output only "{advanced_response}". 
Otherwise, output "{normal_response}". Do not generate a final answer.""".format(
        advanced_response=EVALUATION_RESPONSE_ADVANCED,
        normal_response=EVALUATION_RESPONSE_NORMAL
    )

    # R1 Analysis prompts and templates
    R1_ANALYSIS_PROMPT_TEMPLATE = """Please analyze the following query using the provided context.
Focus on technical accuracy and data-supported insights.

{query_label}
{query}

Provide a structured analysis following this format:

{observations_section}
{observations_guidance}

{analysis_section}
{analysis_guidance}

{recommendations_section}
{recommendations_guidance}

{confidence_section}
{confidence_guidance}

Base your analysis on the context provided and maintain technical precision."""

    # R1 System and base prompts
    R1_SYSTEM = """You are an advanced reasoning engine designed for deep, multi-step analysis 
of climbing-related queries. Your role is to:
1. Analyze provided contextual data comprehensively
2. Generate detailed, technically robust responses
3. Structure analysis with clear sections and bullet points
4. Support conclusions with specific data points
5. Provide actionable insights while maintaining technical accuracy

Format your responses using the following sections:
{observations_section}
{observations_guidance}

{analysis_section}
{analysis_guidance}

{recommendations_section}
{recommendations_guidance}

{confidence_section}
{confidence_guidance}"""

    # Enhancement system prompt and guidelines
    CONVERSATIONAL_ENHANCEMENT = """You are a conversational specialist tasked with translating technical 
analysis into an engaging and easily digestible explanation. Your goal is to:
1. Maintain technical accuracy while improving accessibility
2. Use natural, friendly language
3. Provide concrete examples and analogies
4. Ensure actionable advice
5. Create an engaging tone

Present insights in a way that feels like advice from an experienced climbing partner."""

    # Enhancement prompt components
    ENHANCEMENT_REASONING_TEMPLATE = """
Reasoning Process:
{reasoning}

This reasoning shows the analytical steps taken. Use these insights to ensure
technical accuracy while making the content more accessible."""

    ENHANCEMENT_FOCUS_POINTS = """Focus on:
1. Natural, friendly language
2. Clear explanations of technical concepts
3. Concrete examples and analogies
4. Actionable advice
5. Engaging tone"""

    ENHANCEMENT_PROMPT_TEMPLATE = """Given this technical climbing analysis:

{content}
{reasoning_section}

And this climber context:
{context}

Transform this analysis into an engaging, conversational response that maintains 
technical accuracy while being more accessible and actionable.{structure_guidance}

{focus_points}

Ensure all technical details and recommendations remain accurate."""

    # Structural guidance for response formatting
    ENHANCEMENT_STRUCTURE_GUIDANCE = """
Maintain the original response structure, preserving:
- Section breaks and headings
- Key points and their order
- Technical accuracy and detail level
While making the language more conversational and engaging."""

    # Template for system prompts with context
    SYSTEM_PROMPT_TEMPLATE = """{base_prompt}

{context_label}
{context}"""

    # Template for evaluation prompts
    EVALUATION_PROMPT_TEMPLATE = """Given the following context and user message, evaluate if advanced reasoning is needed:

{context_label}
{context}

{message_label}
{message}

Analyze the complexity of this query and determine if it requires advanced technical analysis. 
Consider factors like:
1. Need for detailed planning
2. Data analysis requirements
3. Technical complexity
4. Multi-step reasoning needs

Output ONLY '{advanced_response}' or '{normal_response}'."""

    @classmethod
    def get_system_prompt(cls, context: str) -> str:
        """Gets complete system prompt with context"""
        return cls.SYSTEM_PROMPT_TEMPLATE.format(
            base_prompt=cls.CONVERSATIONAL_BASE,
            context_label=cls.MESSAGE_STRUCTURE["labels"]["user_context"],
            context=context
        )

    @classmethod
    def get_evaluation_prompt(cls, context: str, message: str) -> str:
        """Gets complete evaluation prompt with context and message"""
        return cls.EVALUATION_PROMPT_TEMPLATE.format(
            context_label=cls.MESSAGE_STRUCTURE["labels"]["user_context"],
            context=context,
            message_label=cls.MESSAGE_STRUCTURE["labels"]["user_message"],
            message=message,
            advanced_response=cls.EVALUATION_RESPONSE_ADVANCED,
            normal_response=cls.EVALUATION_RESPONSE_NORMAL
        )

    @classmethod
    def get_enhancement_prompt(cls, initial_response: str, technical_analysis: str, 
                             context: str, preserve_structure: bool = True) -> str:
        """Gets complete enhancement prompt with all components"""
        # Build reasoning section if available
        reasoning_section = cls.ENHANCEMENT_REASONING_TEMPLATE.format(
            reasoning=technical_analysis
        ) if technical_analysis else "Reasoning not available"
        
        # Get structure guidance if needed
        structure_guidance = cls.ENHANCEMENT_STRUCTURE_GUIDANCE if preserve_structure else ""
        
        return cls.ENHANCEMENT_PROMPT_TEMPLATE.format(
            content=initial_response,
            reasoning_section=reasoning_section,
            context=context,
            structure_guidance=structure_guidance,
            focus_points=cls.ENHANCEMENT_FOCUS_POINTS
        )

    @classmethod
    def get_r1_analysis_prompt(cls, query: str, context: str) -> str:
        """Gets complete R1 analysis prompt with query and context"""
        return cls.R1_ANALYSIS_PROMPT_TEMPLATE.format(
            query_label=cls.MESSAGE_STRUCTURE["labels"]["query"],
            query=query,
            observations_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["observations"]["title"],
            observations_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["observations"]["description"],
            analysis_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["analysis"]["title"],
            analysis_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["analysis"]["description"],
            recommendations_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["recommendations"]["title"],
            recommendations_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["recommendations"]["description"],
            confidence_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["confidence"]["title"],
            confidence_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["confidence"]["description"]
        )

    @classmethod
    def get_r1_system_prompt(cls) -> str:
        """Gets the R1 system prompt with structured sections"""
        return cls.R1_SYSTEM.format(
            observations_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["observations"]["title"],
            observations_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["observations"]["description"],
            analysis_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["analysis"]["title"],
            analysis_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["analysis"]["description"],
            recommendations_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["recommendations"]["title"],
            recommendations_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["recommendations"]["description"],
            confidence_section=cls.R1_ANALYSIS_STRUCTURE["sections"]["confidence"]["title"],
            confidence_guidance=cls.R1_ANALYSIS_STRUCTURE["sections"]["confidence"]["description"]
        )

    @classmethod
    def get_fallback_prompt(cls, fallback_type: str, **kwargs) -> str:
        """Gets appropriate fallback prompt based on the situation"""
        if fallback_type not in cls.FALLBACK_PROMPTS:
            return cls.FALLBACK_PROMPTS["error_recovery"]
        return cls.FALLBACK_PROMPTS[fallback_type].format(**kwargs)

    @classmethod
    def format_section_header(cls, section_name: str, section_type: str = "technical") -> str:
        """Formats section headers according to defined structure"""
        if section_type == "technical":
            section_info = cls.R1_ANALYSIS_STRUCTURE["sections"].get(section_name, {})
            return f"{section_info['formatting'].get('bullet_style', '•')} {section_info['title']}"
        return f"{cls.MESSAGE_STRUCTURE['formatting']['bullet']} {section_name}"

    @classmethod
    def get_persona_instruction(cls, aspect: str) -> str:
        """Gets specific persona instruction based on aspect"""
        for category, aspects in cls.PERSONA_GUIDELINES.items():
            if aspect in aspects:
                return aspects[aspect]
        return cls.PERSONA_GUIDELINES["voice"]["tone"]  # Default to base tone