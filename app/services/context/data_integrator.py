from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import ClimberSummary, UserTicks, PerformancePyramid, UserUpload

class DataIntegrator:
    """
    Integrates supplemental context data from various sources into a unified format.
    Works alongside core logbook services to enrich the context available to the AI chat feature.
    """
    
    def __init__(self):
        self.supported_file_types = ['.csv', '.json', '.txt']

    async def integrate_supplemental_data(
        self, db: Session, user_id: str, 
        custom_instructions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Aggregates and normalizes supplemental context data from various sources.
        
        Args:
            db: Database session
            user_id: User identifier
            custom_instructions: Optional user-provided context/instructions
            
        Returns:
            Integrated context data combining core and supplemental information
        """
        # Get core context from database models
        core_context = await self._get_core_context(db, user_id)
        
        # Process any user uploads
        upload_context = await self._process_user_uploads(db, user_id)
        
        # Merge custom instructions if provided
        instruction_context = self._process_custom_instructions(custom_instructions)
        
        # Combine all context sources
        return self._merge_context_sources(
            core_context,
            upload_context,
            instruction_context
        )

    async def _get_core_context(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Retrieves core context from database models"""
        return {
            "climber_summary": await self._get_climber_summary(db, user_id),
            "performance_metrics": await self._get_performance_metrics(db, user_id),
            "recent_activity": await self._get_recent_activity(db, user_id)
        }

    async def _get_climber_summary(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Extracts relevant fields from ClimberSummary"""
        summary = db.query(ClimberSummary).filter(
            ClimberSummary.user_id == user_id
        ).first()
        
        if not summary:
            return {}
            
        return {
            "experience_level": {
                "years_climbing": summary.years_climbing_outside,
                "total_climbs": summary.total_climbs,
                "preferred_discipline": summary.favorite_discipline.value if summary.favorite_discipline else None
            },
            "training_context": {
                "frequency": summary.training_frequency,
                "session_length": summary.typical_session_length.value if summary.typical_session_length else None,
                "facilities": {
                    "has_hangboard": summary.has_hangboard,
                    "has_home_wall": summary.has_home_wall,
                    "goes_to_gym": summary.goes_to_gym
                }
            },
            "style_preferences": {
                "angles": {
                    "favorite": summary.favorite_angle.value if summary.favorite_angle else None,
                    "strongest": summary.strongest_angle.value if summary.strongest_angle else None,
                    "weakest": summary.weakest_angle.value if summary.weakest_angle else None
                },
                "energy_types": {
                    "favorite": summary.favorite_energy_type.value if summary.favorite_energy_type else None,
                    "strongest": summary.strongest_energy_type.value if summary.strongest_energy_type else None
                },
                "hold_types": {
                    "favorite": summary.favorite_hold_types.value if summary.favorite_hold_types else None,
                    "strongest": summary.strongest_hold_types.value if summary.strongest_hold_types else None
                }
            }
        }

    async def _get_performance_metrics(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Extracts relevant performance data from PerformancePyramid"""
        metrics = db.query(PerformancePyramid).filter(
            PerformancePyramid.user_id == user_id
        ).order_by(PerformancePyramid.send_date.desc()).limit(50).all()
        
        if not metrics:
            return {}
            
        return {
            "recent_sends": [
                {
                    "date": metric.send_date.isoformat(),
                    "location": metric.location,
                    "grade": metric.binned_code,
                    "style": {
                        "angle": metric.crux_angle.value if metric.crux_angle else None,
                        "energy": metric.crux_energy.value if metric.crux_energy else None
                    },
                    "attempts": metric.num_attempts,
                    "days_to_send": metric.days_attempts
                }
                for metric in metrics
            ]
        }

    async def _get_recent_activity(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Extracts recent activity data from UserTicks"""
        recent_ticks = db.query(UserTicks).filter(
            UserTicks.user_id == user_id
        ).order_by(UserTicks.tick_date.desc()).limit(30).all()
        
        if not recent_ticks:
            return {}
            
        return {
            "recent_ticks": [
                {
                    "date": tick.tick_date.isoformat(),
                    "route_name": tick.route_name,
                    "grade": tick.route_grade,
                    "location": tick.location,
                    "discipline": tick.discipline.value if tick.discipline else None,
                    "send_bool": tick.send_bool,
                    "notes": tick.notes
                }
                for tick in recent_ticks
            ]
        }

    async def _process_user_uploads(self, db: Session, user_id: str) -> Dict[str, Any]:
        """Processes and integrates user-uploaded supplemental data"""
        uploads = db.query(UserUpload).filter(
            UserUpload.user_id == user_id
        ).order_by(UserUpload.uploaded_at.desc()).all()
        
        if not uploads:
            return {}
            
        processed_uploads = []
        for upload in uploads:
            try:
                if upload.file_type == 'json':
                    data = json.loads(upload.content)
                elif upload.file_type in ['csv', 'txt']:
                    data = self._parse_text_content(upload.content)
                else:
                    continue
                    
                processed_uploads.append({
                    "source": upload.filename,
                    "uploaded_at": upload.uploaded_at.isoformat(),
                    "content": data
                })
            except Exception as e:
                continue  # Skip problematic uploads
                
        return {"user_uploads": processed_uploads} if processed_uploads else {}

    def _parse_text_content(self, content: str) -> List[Dict[str, Any]]:
        """Parses CSV/TXT content into structured format"""
        parsed_data = []
        lines = content.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) >= 3:  # Minimum: Date,Route,Grade
                entry = {
                    "date": parts[0].strip(),
                    "route": parts[1].strip(),
                    "grade": parts[2].strip()
                }
                
                # Add optional fields if present
                if len(parts) > 3:
                    entry["style"] = parts[3].strip()
                if len(parts) > 4:
                    entry["location"] = parts[4].strip()
                if len(parts) > 5:
                    entry["notes"] = parts[5].strip()
                    
                parsed_data.append(entry)
                
        return parsed_data

    def _process_custom_instructions(
        self, custom_instructions: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Processes user-provided custom instructions/context"""
        if not custom_instructions:
            return {}
            
        # Extract relevant fields from custom instructions
        processed_instructions = {
            "training_focus": custom_instructions.get("training_focus"),
            "injury_considerations": custom_instructions.get("injury_considerations"),
            "goals": custom_instructions.get("goals"),
            "preferences": custom_instructions.get("preferences"),
            "restrictions": custom_instructions.get("restrictions")
        }
        
        # Remove None values
        return {k: v for k, v in processed_instructions.items() if v is not None}

    def _merge_context_sources(
        self, core_context: Dict[str, Any],
        upload_context: Dict[str, Any],
        instruction_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merges different context sources into unified format"""
        return {
            "core_data": core_context,
            "supplemental_data": {
                "user_uploads": upload_context.get("user_uploads", []),
                "custom_instructions": instruction_context
            },
            "metadata": {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "context_sources": [
                    source for source, data in {
                        "core_data": bool(core_context),
                        "user_uploads": bool(upload_context),
                        "custom_instructions": bool(instruction_context)
                    }.items() if data
                ]
            }
        }