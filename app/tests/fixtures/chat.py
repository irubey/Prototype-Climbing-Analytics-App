"""
Chat-specific fixtures for tests.

This module contains fixtures for chat-related tests,
including LLM responses, context data, and conversation histories.
"""

import pytest
import pytest_asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.tests.fixtures.test_data import create_conversation_data
from app.tests.factories import ChatServiceFactory


@pytest.fixture
def sample_prompt_templates():
    """Sample LLM prompt templates for testing."""
    return {
        "basic_chat": (
            "You are SendSage, a helpful climbing assistant. "
            "Respond to the user's question: {user_message}"
        ),
        "context_enhanced": (
            "You are SendSage, a helpful climbing assistant.\n"
            "User profile: {user_profile}\n"
            "Recent climbing activity: {recent_activity}\n"
            "Respond to the user's question: {user_message}"
        ),
        "recommendation": (
            "You are SendSage, a helpful climbing assistant.\n"
            "User profile: {user_profile}\n"
            "Recent climbing activity: {recent_activity}\n"
            "Current climbing grade: {current_grade}\n"
            "Provide a personalized recommendation for the user."
        )
    }


@pytest.fixture
def sample_user_contexts():
    """Sample user context data for chat tests."""
    return {
        "beginner_user": {
            "user_id": "user1",
            "user_profile": {
                "name": "Alex",
                "experience_level": "beginner",
                "climbing_since": "2023-01",
                "preferred_disciplines": ["Sport", "Boulder"],
                "current_grade": {
                    "sport": "5.9",
                    "boulder": "V2"
                },
                "goal_grade": {
                    "sport": "5.10b",
                    "boulder": "V3"
                }
            },
            "recent_activity": [
                {"route": "Easy Slab", "grade": "5.8", "status": "sent"},
                {"route": "Crimpy Face", "grade": "5.9", "status": "project"},
                {"route": "Juggy Problem", "grade": "V1", "status": "sent"}
            ],
            "preferences": {
                "training_frequency": "2-3 times per week",
                "session_duration": "1-2 hours",
                "outdoor_preference": "50%"
            }
        },
        "intermediate_user": {
            "user_id": "user2",
            "user_profile": {
                "name": "Jordan",
                "experience_level": "intermediate",
                "climbing_since": "2020-06",
                "preferred_disciplines": ["Sport", "Trad", "Boulder"],
                "current_grade": {
                    "sport": "5.11b",
                    "trad": "5.10a",
                    "boulder": "V5"
                },
                "goal_grade": {
                    "sport": "5.12a",
                    "trad": "5.11a", 
                    "boulder": "V7"
                }
            },
            "recent_activity": [
                {"route": "Crimpy Face", "grade": "5.11a", "status": "sent"},
                {"route": "Overhang Project", "grade": "5.11c", "status": "project"},
                {"route": "Slab Problem", "grade": "V4", "status": "sent"}
            ],
            "preferences": {
                "training_frequency": "3-4 times per week",
                "session_duration": "2-3 hours",
                "outdoor_preference": "70%"
            }
        },
        "advanced_user": {
            "user_id": "user3",
            "user_profile": {
                "name": "Sam",
                "experience_level": "advanced",
                "climbing_since": "2015-03",
                "preferred_disciplines": ["Sport", "Trad", "Boulder", "Alpine"],
                "current_grade": {
                    "sport": "5.13a",
                    "trad": "5.12b",
                    "boulder": "V8",
                    "alpine": "5.10 A2"
                },
                "goal_grade": {
                    "sport": "5.13d",
                    "trad": "5.12d",
                    "boulder": "V10"
                }
            },
            "recent_activity": [
                {"route": "Power Endurance", "grade": "5.12d", "status": "sent"},
                {"route": "Thin Face", "grade": "5.13b", "status": "project"},
                {"route": "Compression Problem", "grade": "V8", "status": "sent"}
            ],
            "preferences": {
                "training_frequency": "5-6 times per week",
                "session_duration": "2-4 hours",
                "outdoor_preference": "80%"
            }
        }
    }


@pytest.fixture
def sample_conversation_histories():
    """Sample conversation histories for chat tests."""
    return {
        "training_conversation": [
            {"role": "system", "content": "You are SendSage, a helpful climbing assistant."},
            {"role": "user", "content": "I want to improve my finger strength for climbing. What exercises should I do?"},
            {"role": "assistant", "content": "Improving finger strength is crucial for climbing. Here are some effective exercises:\n\n1. **Hangboard training** - Start with 7-10 second hangs on jugs, rest 3 minutes between sets. Do 5 sets 2-3 times weekly.\n\n2. **Finger curls** - Use a light weight and curl your fingers toward your palm slowly.\n\n3. **Therapeutic putty exercises** - Great for antagonist training.\n\n4. **Boulder problem repeats** - Find problems that stress finger strength and repeat them with good form.\n\nMake sure you warm up properly before any finger training and start conservatively to avoid injury. How often are you climbing each week?"},
            {"role": "user", "content": "I climb about 3 times a week. How should I incorporate these exercises into my routine?"},
            {"role": "assistant", "content": "With a 3-day climbing schedule, here's how to incorporate finger strength training:\n\n**Week Schedule:**\n\n- **Day 1:** Climbing session + 2-3 sets of hangboard after proper warm-up\n- **Day 2:** Rest or light antagonist training\n- **Day 3:** Climbing session focusing on technique\n- **Day 4:** Rest day with finger curls and putty exercises\n- **Day 5:** Climbing session with focus on boulder problem repeats\n- **Day 6-7:** Complete rest days\n\nKey principles:\n1. Always warm up thoroughly\n2. Start with easier hangs than you think you need\n3. Rest at least 48 hours between intense finger training\n4. Listen to your body and back off if you feel pain (not just fatigue)\n\nAs you progress, increase hang time or decrease edge size before adding weight. Would you like a specific hangboard routine to get started?"}
        ],
        "gear_conversation": [
            {"role": "system", "content": "You are SendSage, a helpful climbing assistant."},
            {"role": "user", "content": "I'm looking to buy my first pair of climbing shoes. Any recommendations?"},
            {"role": "assistant", "content": "For your first pair of climbing shoes, I recommend focusing on comfort while maintaining enough performance for progression. Here are some great beginner-friendly options:\n\n**All-Around Beginner Shoes:**\n- La Sportiva Tarantula/Tarantulace: Comfortable, affordable, and versatile\n- Scarpa Origin: Slightly stiffer, great for gym and outdoor climbing\n- Black Diamond Momentum: Very comfortable with knit upper, good ventilation\n- Evolv Defy/Elektra: Durable and versatile\n\n**Sizing Tips:**\n- Shoes should be snug but not painfully tight\n- Toes should be flat or slightly bent, not scrunched\n- Try on in the afternoon when feet are slightly larger\n- Many beginners size 0.5-1 size down from street shoe size\n\nDo you climb primarily indoors or outdoors? And what type of climbing do you enjoy most (slab, vertical, overhanging)?"},
            {"role": "user", "content": "I climb mostly indoors on vertical walls and slight overhangs. I'm looking for something under $100 if possible."},
            {"role": "assistant", "content": "Perfect! For indoor climbing on vertical and slightly overhanging terrain, while staying under $100, these options would work well:\n\n**Best Options Under $100:**\n\n1. **La Sportiva Tarantulace** (~$85): Probably your best bet - versatile, adjustable lacing, and good rubber. The neutral profile works well for vertical climbing and slight overhangs without being painful for longer gym sessions.\n\n2. **Evolv Defy** (men's) or **Elektra** (women's) (~$89): Very durable shoes with good rubber that perform well on gym surfaces. Slightly softer than the Tarantulace.\n\n3. **Black Diamond Momentum** (~$95): Super comfortable knit upper with good breathability, ideal for longer gym sessions.\n\nAll these options frequently go on sale, so you might find last season's colors even cheaper.\n\n**Pro Tip:** Many gyms have pro shops that let you try on shoes, which is ideal for finding the right fit. Some even offer discounts on your first pair!\n\nI'd recommend trying all three if possible, as foot shape matters as much as performance for your first pair."}
        ],
        "injury_conversation": [
            {"role": "system", "content": "You are SendSage, a helpful climbing assistant."},
            {"role": "user", "content": "I think I have tendonitis in my elbow. What should I do?"},
            {"role": "assistant", "content": "I understand you're dealing with possible elbow tendonitis, which is common among climbers. Here's what you should consider:\n\n**First steps:**\n1. **Rest from aggravating activities** - This doesn't mean complete rest from climbing, but avoid movements that cause pain\n2. **Ice** - 15-20 minutes several times daily to reduce inflammation\n3. **Compression** - Using an elbow sleeve or wrap can provide support\n4. **Anti-inflammatory medication** - NSAIDs like ibuprofen can help manage pain and inflammation\n\n**Important note:** If pain is severe, persists more than 1-2 weeks despite rest, or includes weakness/numbness, see a healthcare provider as soon as possible.\n\n**Is your pain on the inside of the elbow (medial/golfer's elbow) or outside (lateral/tennis elbow)?** This helps determine appropriate exercises."},
            {"role": "user", "content": "It's on the inside of my elbow. I've been climbing a lot of overhanging routes lately."},
            {"role": "assistant", "content": "You're likely experiencing medial epicondylitis (golfer's elbow), which is very common in climbers, especially with overhanging routes that load the flexor tendons through crimping and overhanging movements.\n\n**Short-term approach:**\n1. **Reduce volume** - Temporarily decrease climbing frequency and intensity, particularly on overhangs\n2. **Continue with RICE** - Rest, ice, compression, elevation\n3. **Avoid aggravating grips** - Limit full crimping and deep pocket moves\n\n**Rehabilitation exercises (start gently):**\n1. **Eccentric wrist curls** - Hold light weight (2-5 lbs), curl wrist up with other hand, then slowly lower over 3-5 seconds\n2. **Pronation/supination** - Hold light weight with elbow at 90°, rotate palm up and down slowly\n3. **Finger extensions** - Use rubber band around fingers and practice opening against resistance\n4. **Massage** - Gentle massage of forearm flexors with tennis/lacrosse ball\n\n**Climbing modifications:**\n* Focus on open-handed grips and vertical terrain\n* Reduce session length and increase warm-up time\n* Consider taping for support during easier climbing\n\n**Prevention for future:**\n* Regular antagonist training (pushups, dips)\n* Forearm stretching after sessions\n* Gradual progression with overhanging terrain\n\nConsistently performing these exercises 3-4 times weekly for 6-8 weeks typically shows improvement. If pain persists or worsens after 2 weeks of modified activity, consulting a sports medicine physician or physical therapist would be recommended."}
        ]
    }


@pytest.fixture
def sample_llm_responses():
    """Sample LLM responses for mocking model calls."""
    return {
        "training_plan": {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": """# 4-Week Training Plan for 5.11 Sport Climber

## Week 1: Assessment & Base Building
- **Monday**: 30 min easy cardio, technique drills on vertical terrain
- **Tuesday**: Strength - 3x5 pull-ups, 3x10 rows, core work
- **Wednesday**: Rest day
- **Thursday**: Endurance - 4x4s on 5.10- routes
- **Friday**: Active recovery - light stretching, 20 min cardio
- **Saturday**: Outdoor climbing - focus on mileage, not difficulty
- **Sunday**: Complete rest

## Week 2: Power Endurance Development
- **Monday**: Limit bouldering - work 3-4 hard problems
- **Tuesday**: Antagonist training - push-ups, dips, reverse wrist curls
- **Wednesday**: Rest day
- **Thursday**: Power endurance - linked bouldering circuits
- **Friday**: Active recovery - mobility work
- **Saturday**: Outdoor climbing - project slightly below limit
- **Sunday**: Complete rest

## Week 3: Intensity Week
- **Monday**: Campus board basics, core training
- **Tuesday**: Strength - weighted pull-ups, one-arm lockoffs
- **Wednesday**: Rest day
- **Thursday**: Interval climbing - 1 min on/1 min off, harder grades
- **Friday**: Active recovery - light yoga, stretching
- **Saturday**: Outdoor climbing - work a project at your limit
- **Sunday**: Complete rest

## Week 4: Recovery & Performance
- **Monday**: Light technique work, mobility
- **Tuesday**: Moderate endurance - laps on easy routes
- **Wednesday**: Complete rest
- **Thursday**: Short power session - 45 minutes max
- **Friday**: Complete rest
- **Saturday**: Performance day - attempt projects or onsights
- **Sunday**: Recovery activities - hike, swim, or light stretching

## Nutrition Tips:
- Hydrate adequately before sessions
- Consume protein within 30 minutes after training
- Consider 200-300 calorie carb snack 1-2 hours before hard sessions

## Recovery Recommendations:
- Sleep 7-9 hours nightly
- Consider contrast therapy for finger recovery
- Foam roll forearms and shoulders after intense sessions"""
                    }
                }
            ]
        },
        "gear_recommendation": {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": """# Recommended Sport Climbing Rack

Based on your current level (5.11c sport climber) and preferences, here's your optimal sport climbing rack:

## Essential Quickdraws (12 total)
- **8x Regular Quickdraws** - Petzl Spirit Express (12cm) offers the best combination of clipability, durability and reasonable weight
- **4x Longer Quickdraws** - DMM Alpha Sport 17cm for routes with meandering bolt lines

## Supplementary Gear
- **2x Alpine Draws** - For reducing rope drag on traverses
- **1x 120cm Sling** - For anchors or contingencies
- **4x Locking Carabiners** - Two HMS/pear shaped for belaying, two smaller ones for anchors

## Rope Recommendation
- **70m x 9.8mm Dynamic Rope** - Mammut Infinity or Petzl Arial
- Consider a bi-pattern or middle-marked rope for safer lowering

## Belay & Rappel Devices
- **Tube Device** - ATC Guide or Reverso (versatile for cragging and multi-pitch)
- **Assisted Braking Device** - Petzl GriGri for prolonged belaying sessions

## Accessories
- Helmet - Critical for safety
- Chalk bag with quality chalk
- Tape for emergency finger support
- Nut tool (for cleaning stuck quickdraws)
- Small first aid kit

## Optional Upgrades
- Knee bar pad for routes with potential knee bars
- Brush for cleaning holds on projects
- Stick clip for high first bolts

This setup will cover most sport climbing scenarios while providing redundancy for safety. Total estimated cost: $400-550 depending on brand choices."""
                    }
                }
            ]
        },
        "technique_advice": {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": """# Overcoming the V4-V5 Plateau

The V4-V5 range is a common plateau where significant technique improvements are needed. Here's how to break through:

## Technical Focus Areas

### 1. Body Positioning
- **Hip positioning** - Practice intentionally turning hips into the wall to increase reach
- **Body tension** - Work on keeping core engaged during dynamic movements
- **Silent feet** - Place feet deliberately and minimize readjustments

### 2. Movement Efficiency
- **Straight-arm climbing** - Conserve energy by hanging on skeleton instead of muscles
- **Momentum utilization** - Learn to use dynamic movement for efficiency, not just static positions
- **Rest positions** - Identify and utilize micro-rests on routes

### 3. Grip Techniques
- **Open-hand mastery** - Reduce dependence on full crimps for durability
- **Thumb catches** - Practice utilizing thumb opposition for stability
- **Contact strength** - Work on maintaining grip during movement

## Training Recommendations

### Focused Practice Sessions (2x weekly)
1. **System Board** - Work identical moves with different body positions
2. **Limit Bouldering** - Spend time on problems just beyond your level
3. **Movement Drills**:
   - Quiet feet exercises
   - One-touch climbing
   - Hover hands before placement

### Supplementary Training
- **Finger strength** - Hangboard protocol 2x weekly (7:3 repeaters or max hangs)
- **Core integration** - Front levers, TRX fallouts
- **Mobility work** - Hip and shoulder mobility to increase range of motion

## Mental Approach
- **Film yourself** - Review footage to identify inefficient movements
- **Climb with better climbers** - Learn from their beta and movement patterns
- **Focus on process** - Work on technique improvements rather than just sending

Start implementing these changes over 8-12 weeks with proper rest periods, and you should see progress through the V4-V5 plateau."""
                    }
                }
            ]
        }
    }


@pytest.fixture
def create_chat_context():
    """
    Create customized chat context for tests.
    
    Returns a function that can generate context data with customizable parameters.
    """
    def _create_context(
        user_level: str = "intermediate",
        custom_fields: Optional[Dict[str, Any]] = None,
        include_recent_activity: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate chat context with specific parameters.
        
        Args:
            user_level: User experience level ('beginner', 'intermediate', 'advanced')
            custom_fields: Custom fields to override defaults
            include_recent_activity: Whether to include recent activity data
            
        Returns:
            Context data dictionary
        """
        # Base contexts from predefined samples
        base_contexts = {
            "beginner": {
                "user_profile": {
                    "experience_level": "beginner",
                    "current_grade": {
                        "sport": "5.9",
                        "boulder": "V2"
                    }
                }
            },
            "intermediate": {
                "user_profile": {
                    "experience_level": "intermediate",
                    "current_grade": {
                        "sport": "5.11b",
                        "boulder": "V5"
                    }
                }
            },
            "advanced": {
                "user_profile": {
                    "experience_level": "advanced",
                    "current_grade": {
                        "sport": "5.13a",
                        "boulder": "V8"
                    }
                }
            }
        }
        
        # Start with the requested level
        if user_level in base_contexts:
            context = base_contexts[user_level].copy()
        else:
            # Default to intermediate if level not found
            context = base_contexts["intermediate"].copy()
        
        # Add recent activity if requested
        if include_recent_activity:
            context["recent_activity"] = [
                {"route": "Test Route 1", "grade": "5.10a", "status": "sent", "date": "2023-08-15"},
                {"route": "Test Route 2", "grade": "V4", "status": "project", "date": "2023-08-10"}
            ]
        
        # Add user ID
        context["user_id"] = str(uuid.uuid4())
        
        # Override with custom fields if provided
        if custom_fields:
            _recursive_update(context, custom_fields)
        
        return context
    
    def _recursive_update(dict1, dict2):
        """Recursively update dict1 with values from dict2."""
        for k, v in dict2.items():
            if k in dict1 and isinstance(dict1[k], dict) and isinstance(v, dict):
                _recursive_update(dict1[k], v)
            else:
                dict1[k] = v
    
    return _create_context


@pytest_asyncio.fixture
async def mock_chat_service(sample_llm_responses):
    """
    Create a mocked chat service for tests.
    
    Returns a pre-configured chat service with mock responses
    based on the sample_llm_responses fixture.
    """
    # Create default context data and conversation history
    context_data = {
        "user_info": {
            "name": "Test User",
            "climbing_grade": "5.11b",
            "climbing_style": "Sport"
        },
        "preferences": {
            "training_focus": "Strength",
            "goal_grade": "5.12a"
        }
    }
    
    conversation_history = [
        {"role": "user", "content": "Can you help me with a training plan?"},
        {"role": "assistant", "content": "I'd be happy to help! What's your current climbing level?"}
    ]
    
    # Create the service with mocked dependencies
    service = await ChatServiceFactory.create_service(
        context_data=context_data,
        conversation_history=conversation_history
    )
    
    # Configure the mocked model client to return appropriate responses
    model_client = service._test_mocks["model_client"]
    
    # Create a side effect function that returns different responses based on input
    async def mock_generate_response(prompt=None, messages=None, **kwargs):
        """Return appropriate mock response based on the input."""
        if messages:
            last_msg = messages[-1]["content"].lower() if messages and len(messages) > 0 else ""
            
            if "training" in last_msg or "plan" in last_msg:
                return sample_llm_responses["training_plan"]
            elif "gear" in last_msg or "equipment" in last_msg:
                return sample_llm_responses["gear_recommendation"]
            elif "technique" in last_msg or "skill" in last_msg:
                return sample_llm_responses["technique_advice"]
        
        # Default response if no specific match
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I'm happy to help with your climbing questions!"
                    }
                }
            ]
        }
    
    # Configure the mock to use our function
    model_client.generate_response.side_effect = mock_generate_response
    
    return service


@pytest.fixture
def mock_model_client(sample_llm_responses):
    """
    Create a mocked model client that returns predefined responses.
    
    This fixture provides a more lightweight alternative to the full
    mock_chat_service when only the model client needs to be mocked.
    """
    model_client = AsyncMock()
    
    # Configure the mock to return appropriate responses
    async def mock_generate_response(prompt=None, messages=None, **kwargs):
        """Return appropriate mock response based on the input."""
        if messages:
            last_msg = messages[-1]["content"].lower() if messages and len(messages) > 0 else ""
            
            if "training" in last_msg or "plan" in last_msg:
                return sample_llm_responses["training_plan"]
            elif "gear" in last_msg or "equipment" in last_msg:
                return sample_llm_responses["gear_recommendation"]
            elif "technique" in last_msg or "skill" in last_msg:
                return sample_llm_responses["technique_advice"]
        
        # Default response if no specific match
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "I'm happy to help with your climbing questions!"
                    }
                }
            ]
        }
    
    model_client.generate_response.side_effect = mock_generate_response
    
    return model_client 