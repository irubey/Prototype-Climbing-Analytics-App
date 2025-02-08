# Product Design Requirements & Implementation Plan

## Project: ClimberSummary Schema Refactor

### Objective

Update the data model and supporting services to align the persistent storage, backend services, and UI forms with the new user context structure for our AI chatbot.

## 1. Overview

Our current ClimberSummary table acts as the foundation for user-provided context. However, its structure no longer aligns with the latest specification (see this.md). The goal is to refactor the schema by:

- Renaming fields (e.g. renaming `years_climbing_outside` to `years_climbing`, and `sends_last_30_days` to `activity_last_30_days`)
- Consolidating redundant fields (combining `current_injuries` and `injury_history` into one unified field for injury information)
- Introducing several new fields:
  - `current_training_description`
  - `interests`
  - `training_history`
  - `typical_session_intensity`
  - `home_equipment`
  - `access_to_commercial_gym`
  - `supplemental_training`
- Removing any fields not explicitly called out in the new spec
- Updating all integration points (services, API routes, and UI templates) that reference or update fields on ClimberSummary

This refactor also needs to respect business rules (such as proper ENUM validations, input sanitization, and data completeness) and impact how the AI chatbot context is assembled.

## 2. Detailed Requirements

### Database Schema Changes

#### Metadata

No changes.

#### Core Context Changes

- **Climbing Goals**: Remains unchanged
- **Years Climbing**: Rename `years_climbing_outside` to `years_climbing` (INTEGER, no default, allow NULL)
- **Current Training Description**: New TEXT field
- **Interests List**: New JSON field to support multiple selections. Inputs should be validated against allowed ENUM options (e.g., "sport", "trad", "boulder", "indoor", "outdoor")
- **Injury Information**: Replace `current_injuries` and `injury_history` with one combined TEXT field (`injury_information`)
- **Additional Notes**: No changes if already exists; otherwise, add as a TEXT field

#### Advanced Settings

##### Performance Metrics

They remain one-to-one with existing fields.

##### Training Context Changes

- **Training History**: New TEXT field
- **Current Training Frequency**: Rename `training_frequency` to `current_training_frequency` (VARCHAR(255), allow NULL)
- **Typical Session Length**: Remains unchanged
- **Typical Session Intensity**: Add new ENUM field (requires new ENUM definition or validated list)
- **Home Equipment**: New TEXT field to consolidate existing boolean indicators (`has_hangboard` and `has_home_wall`)
- **Access to Commercial Gym**: Rename `goes_to_gym` to `access_to_commercial_gym` (BOOLEAN; if omitted, default is False)
- **Supplemental Training**: New TEXT field

#### Experience Base Metrics

Remain unchanged.

#### Lifestyle

Remains unchanged.

#### Recent Activity Changes

- **Activity Last 30 Days**: Rename `sends_last_30_days` to `activity_last_30_days`
- **Current Projects & Recent Favorite Routes**: Remain unchanged

#### Style Preferences

Remains unchanged.

Any fields not mentioned above (or extraneous fields) should be removed.

### Business Rules and Validations

1. **Consistency**: Ensure valid ENUM values are enforced in both the UI (select fields, checkboxes) and backend (data type validations) for all relevant fields
2. **Sanitization**: All TEXT fields must be checked for maximum length and sanitized to prevent injections
3. **Data Completeness**: The data completeness check (in `routes.py` in the `check_data_completeness` function) must be updated to verify the new required fields
4. **Transformation**: Legacy fields must be migrated appropriately. For example, when renaming fields, data should be copied and the original dropped post-verification. Combine injury information by concatenating the existing two fields if both contain data

### Integration Impact

#### Backend Services

- **ClimberSummaryService** in `app/services/climber_summary.py` must be updated to read/write the new field names and apply transformation logic
- **Context Services**: Both `context_formatter.py` and `data_integrator.py` must adjust field names in the structured and conversational contexts

#### UI Forms and Templates

- Update `settings.html` and `advanced_settings.html` (and associated partials) to display and let users edit new fields
- Update form bindings in `update_climber_summary.html` to match new model attributes

#### Routing/Endpoints

- Verify that endpoints in `routes.py` (such as `/sage-chat/onboard` and `/update-climber-summary`) are updated to both capture and validate the transformed data

### Context Services Implementation Details

#### Field Mapping Reference

The following table defines the complete mapping between legacy and new fields that must be updated across all context services:

| Legacy Field                         | New Field                      | Type         | Notes                       |
| ------------------------------------ | ------------------------------ | ------------ | --------------------------- |
| `years_climbing_outside`             | `years_climbing`               | INTEGER      | Core experience metric      |
| `sends_last_30_days`                 | `activity_last_30_days`        | INTEGER      | Activity tracking           |
| `current_injuries`, `injury_history` | `injury_information`           | TEXT         | Consolidated injury data    |
| `training_frequency`                 | `current_training_frequency`   | VARCHAR(255) | Training context            |
| `has_hangboard`, `has_home_wall`     | `home_equipment`               | TEXT         | Consolidated equipment info |
| `goes_to_gym`                        | `access_to_commercial_gym`     | BOOLEAN      | Facility access             |
| N/A (New)                            | `current_training_description` | TEXT         | Training details            |
| N/A (New)                            | `interests`                    | JSON         | Multiple selection field    |
| N/A (New)                            | `training_history`             | TEXT         | Historical context          |
| N/A (New)                            | `typical_session_intensity`    | STRING/ENUM  | Training intensity          |
| N/A (New)                            | `supplemental_training`        | TEXT         | Additional training info    |

#### Context Formatter Updates (`context_formatter.py`)

##### Conversational Context Changes

The `_create_conversational_context` method must be updated to:

1. Replace legacy field references:

```python
# Before
exp_text = f"{summary.years_climbing_outside} years"
# After
exp_text = f"{summary.years_climbing} years"
```

2. Consolidate injury information:

```python
# Before
if summary.current_injuries:
    health_parts.append(f"current injuries: {summary.current_injuries}")
# After
if summary.injury_information:
    health_parts.append(f"injury information: {summary.injury_information}")
```

3. Add new training context:

```python
# Add after existing training context
if summary.current_training_description:
    training_parts.append(f"current training: {summary.current_training_description}")
if summary.training_history:
    training_parts.append(f"training background: {summary.training_history}")
```

4. Update facility references:

```python
# Before
if summary.has_hangboard:
    training_parts.append("has access to a hangboard")
if summary.has_home_wall:
    training_parts.append("has a home wall")
if summary.goes_to_gym:
    training_parts.append("climbs in a gym")
# After
if summary.home_equipment:
    training_parts.append(f"home equipment: {summary.home_equipment}")
if summary.access_to_commercial_gym:
    training_parts.append("has access to a commercial gym")
```

##### Structured Context Changes

The `_create_structured_context` method must be updated to:

1. Update experience metrics:

```python
"experience": {
    "years_climbing": summary.years_climbing,  # Updated from years_climbing_outside
    "primary_discipline": summary.favorite_discipline.value if summary.favorite_discipline else None,
    "total_climbs": summary.total_climbs,
    "recent_activity": summary.activity_last_30_days  # Updated from sends_last_30_days
}
```

2. Consolidate training context:

```python
"training_context": {
    "current_description": summary.current_training_description,  # New field
    "frequency": summary.current_training_frequency,  # Renamed
    "session_length": summary.typical_session_length.value if summary.typical_session_length else None,
    "session_intensity": summary.typical_session_intensity,  # New field
    "facilities": {
        "home_equipment": summary.home_equipment,  # Consolidated field
        "commercial_gym_access": summary.access_to_commercial_gym  # Renamed
    },
    "history": summary.training_history,  # New field
    "supplemental": summary.supplemental_training  # New field
}
```

3. Update health metrics:

```python
"health_metrics": {
    "sleep_score": summary.sleep_score.value if summary.sleep_score else None,
    "nutrition_score": summary.nutrition_score.value if summary.nutrition_score else None,
    "injury_information": summary.injury_information,  # Consolidated field
    "physical_limitations": summary.physical_limitations
}
```

##### Experience Level Calculation

Update the `_calculate_experience_level` method to use new field names:

```python
def _calculate_experience_level(self, summary: Any) -> str:
    # Update field reference
    years_exp = summary.years_climbing or 0  # Changed from years_climbing_outside
    total_climbs = summary.total_climbs or 0

    # Rest of the logic remains unchanged
```

#### Data Integrator Updates (`data_integrator.py`)

##### Core Context Changes

The `_get_climber_summary` method must be updated to:

1. Update experience level mapping:

```python
"experience_level": {
    "years_climbing": summary.years_climbing,  # Updated from years_climbing_outside
    "total_climbs": summary.total_climbs,
    "preferred_discipline": summary.favorite_discipline.value if summary.favorite_discipline else None,
    "interests": summary.interests  # New field
}
```

2. Update training context:

```python
"training_context": {
    "current_description": summary.current_training_description,  # New field
    "frequency": summary.current_training_frequency,  # Renamed
    "session_length": summary.typical_session_length.value if summary.typical_session_length else None,
    "session_intensity": summary.typical_session_intensity,  # New field
    "facilities": {
        "home_equipment": summary.home_equipment,  # Consolidated
        "commercial_gym_access": summary.access_to_commercial_gym  # Renamed
    },
    "history": summary.training_history,  # New field
    "supplemental": summary.supplemental_training  # New field
}
```

##### Custom Instructions Processing

Update the `_process_custom_instructions` method to handle new fields:

```python
def _process_custom_instructions(
    self, custom_instructions: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not custom_instructions:
        return {}

    processed_instructions = {
        "training_focus": custom_instructions.get("training_focus"),
        "injury_information": custom_instructions.get("injury_information"),  # Updated
        "training_history": custom_instructions.get("training_history"),  # New
        "goals": custom_instructions.get("goals"),
        "preferences": custom_instructions.get("preferences"),
        "restrictions": custom_instructions.get("restrictions")
    }

    return {k: v for k, v in processed_instructions.items() if v is not None}
```

These updates ensure that all context generation logic aligns with the new ClimberSummary schema while maintaining the existing functionality and adding support for the new fields.

## 3. Implementation Plan

### Step 1: Setup & Planning

#### Branching

- `years_climbing` (INTEGER) ← `years_climbing_outside`
- New field: `current_training_description` (TEXT)
- New field: `interests` (JSON) with allowed values ["sport", "trad", "boulder", "indoor", "outdoor"]
- New field: `injury_information` (TEXT) ← merge of `current_injuries` and `injury_history`
- Rename: `training_frequency` → `current_training_frequency`
- New field: `typical_session_intensity` (ENUM or validated STRING)
- New field: `home_equipment` (TEXT)
- Rename: `goes_to_gym` → `access_to_commercial_gym` (BOOLEAN)
- New field: `supplemental_training` (TEXT)
- Rename: `sends_last_30_days` → `activity_last_30_days` (INTEGER)

### Step 2: Implementation

#### Database Changes

Update `app/models.py` in the ClimberSummary model:

```python
    class ClimberSummary(BaseModel):
        __tablename__ = 'climber_summary'
        __table_args__ = (
            db.Index('idx_climber_summary_user_id', 'user_id'),
        )

        # Primary Key
        user_id = db.Column(db.ForeignKey('users.id'), primary_key=True)

        # Core progression metrics
        highest_sport_grade_tried = db.Column(db.String(255))
        highest_trad_grade_tried = db.Column(db.String(255))
        highest_boulder_grade_tried = db.Column(db.String(255))
        total_climbs = db.Column(db.Integer)
        favorite_discipline = db.Column(Enum(ClimbingDiscipline))
        years_climbing = db.Column(db.Integer)  # Renamed from years_climbing_outside
        preferred_crag_last_year = db.Column(db.String(255))

        # Core Context additions
        climbing_goals = db.Column(db.Text)
        current_training_description = db.Column(db.Text)  # New Field
        interests = db.Column(db.JSON)  # New Field
        injury_information = db.Column(db.Text)  # Consolidated from current_injuries and injury_history
        additional_notes = db.Column(db.Text)

        # Advanced Settings - Performance Metrics (No change)
        highest_grade_sport_sent_clean_on_lead = db.Column(db.String(255))
        highest_grade_tr_sent_clean = db.Column(db.String(255))
        highest_grade_trad_sent_clean_on_lead = db.Column(db.String(255))
        highest_grade_boulder_sent_clean = db.Column(db.String(255))
        onsight_grade_sport = db.Column(db.String(255))
        onsight_grade_trad = db.Column(db.String(255))
        flash_grade_boulder = db.Column(db.String(255))
        grade_pyramid_sport = db.Column(db.JSON)
        grade_pyramid_trad = db.Column(db.JSON)
        grade_pyramid_boulder = db.Column(db.JSON)

        # Advanced Settings - Training Context modifications
        current_training_frequency = db.Column(db.String(255))  # Renamed from training_frequency
        typical_session_length = db.Column(Enum(SessionLength, values_callable=lambda x: [e.value for e in x]))
        typical_session_intensity = db.Column(db.String(255))   # New: consider converting to ENUM later
        home_equipment = db.Column(db.Text)  # New Field replacing has_hangboard and has_home_wall
        access_to_commercial_gym = db.Column(db.Boolean)  # Renamed from goes_to_gym
        supplemental_training = db.Column(db.Text)  # New Field
        training_history = db.Column(db.Text)  # New Field

        # Experience Base Metrics:
        favorite_discipline = db.Column(Enum(ClimbingDiscipline))
        preferred_crag_last_year = db.Column(db.String(255))

        # Recent Activity (updated)
        activity_last_30_days = db.Column(db.Integer)  # Renamed from sends_last_30_days
        current_projects = db.Column(db.JSON)
        recent_favorite_routes = db.Column(db.JSON)

        # Style Preferences remain unchanged
        favorite_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
        weakest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
        strongest_angle = db.Column(Enum(CruxAngle, values_callable=lambda x: [e.value for e in x]))
        favorite_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
        weakest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
        strongest_energy_type = db.Column(Enum(CruxEnergyType, values_callable=lambda x: [e.value for e in x]))
        favorite_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
        weakest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))
        strongest_hold_types = db.Column(Enum(HoldType, values_callable=lambda x: [e.value for e in x]))

        # Lifestyle
        sleep_score = db.Column(Enum(SleepScore, values_callable=lambda x: [e.value for e in x]))
        nutrition_score = db.Column(Enum(NutritionScore, values_callable=lambda x: [e.value for e in x]))

        # Favorite Routes and Metadata
        recent_favorite_routes = db.Column(db.JSON)
        created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        current_info_as_of = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

Create an Alembic migration script to add, rename, and remove columns. Ensure data from years_climbing_outside is copied into years_climbing and that the contents of current_injuries and injury_history are merged into injury_information.

#### Service & Route Updates

- Update ClimberSummaryService to populate new fields from user input
- Adjust API endpoints to use the new field names
- Update the `check_data_completeness` function to validate the new/renamed fields

#### UI Template Adjustments

- Modify forms in `settings.html`, `advanced_settings.html`, and `update_climber_summary.html`
- Update data binding for renamed fields
- Add new inputs for all new fields

#### Context Integration

Update `context_formatter.py` and `data_integrator.py` for new field names in both conversational and structured contexts.

### Step 3: Testing & Verification

#### Unit Testing

- Write unit tests for new migration script and ClimberSummaryService methods
- Test legacy data transformation
- Create tests for ENUM and JSON field validations

#### Integration Testing

- Verify API endpoints correctly process user input
- Test context services output
- Verify data completeness features

#### User Acceptance Testing (UAT)

Coordinate beta rollout for UI testing and feedback collection.

### Step 4: Deployment & Rollback Strategy

#### Deployment

- Merge feature branch after testing and review
- Coordinate deployment schedule
- Monitor logs post-deployment

#### Rollback Plan

- Prepare automated rollback migration script
- Ensure database backups before migration

#### Post-Deployment Monitoring

- Monitor performance and correctness
- Verify database indexes and query performance

## Impact Summary

- **Database**: Changes to ClimberSummary require careful migration and transformation
- **Backend Services**: Update in service layers and context assembly components
- **UI/UX**: New field entries and modified error/validation handling in forms
- **APIs**: Adjusted endpoints to account for new/renamed fields and additional validations
- **Testing**: Comprehensive testing suite to ensure data integrity and performance
