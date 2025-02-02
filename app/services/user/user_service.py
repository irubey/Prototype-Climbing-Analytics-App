from typing import Tuple, Optional
from uuid import UUID
import enum
import logging
from datetime import datetime
from flask_login import login_user, current_user
from app.models import User, UserTicks, PerformancePyramid, db
from app import bcrypt
import os
import re

logger = logging.getLogger(__name__)

class UserType(enum.Enum):
    NEW_TEMP = "new_temp"
    EXISTING_TEMP = "existing_temp"
    EXISTING_PERMANENT = "existing_permanent"
    NEW_PERMANENT = "new_permanent"

class UserCreationError(Exception):
    """Custom exception for user creation errors"""
    pass

class UserService:
    def __init__(self, db_session):
        self.db_session = db_session
    
    def determine_user_type(self, profile_url: str) -> UserType:
        """
        Determine the type of user based on profile URL and existing records
        """
        try:
            # Check for existing permanent user with this URL
            existing_permanent = User.query.filter(
                User.mtn_project_profile_url == profile_url,
                ~User.username.endswith('_temp')
            ).first()
            
            if existing_permanent:
                return UserType.EXISTING_PERMANENT
            
            # Check for existing temp user with this URL
            existing_temp = User.query.filter(
                User.mtn_project_profile_url == profile_url,
                User.username.endswith('_temp')
            ).first()
            
            if existing_temp:
                return UserType.EXISTING_TEMP
            
            return UserType.NEW_TEMP
            
        except Exception as e:
            logger.error(f"Error determining user type: {str(e)}")
            raise UserCreationError(f"Failed to determine user type: {str(e)}")

    def handle_user_creation(self, profile_url: str) -> Tuple[User, bool]:
        """
        Main entry point for user creation/retrieval
        Returns: (User, is_new_user)
        """
        try:
            user_type = self.determine_user_type(profile_url)
            logger.info(f"Determined user type: {user_type} for profile: {profile_url}")
            
            if user_type == UserType.EXISTING_PERMANENT:
                user = self.get_existing_user(profile_url)
                return user, False
                
            elif user_type == UserType.EXISTING_TEMP:
                user = self.get_temp_user(profile_url)
                return user, False
                
            elif user_type == UserType.NEW_TEMP:
                user = self.create_temp_user(profile_url)
                return user, True
                
            else:
                raise UserCreationError(f"Unsupported user type: {user_type}")
                
        except Exception as e:
            logger.error(f"Error handling user creation: {str(e)}")
            raise UserCreationError(f"Failed to handle user creation: {str(e)}")

    def create_temp_user(self, profile_url: str) -> User:
        """Create a new temporary user"""
        try:
            # Extract username from profile URL
            username = self._extract_username_from_url(profile_url)
            if not username:
                raise UserCreationError("Could not extract valid username from URL")
            
            # Generate temp username and email
            temp_username = f"{username.lower()}_temp"
            temp_email = self._generate_temp_email(username)
            
            # Create user
            user = User(
                username=temp_username,
                email=temp_email,
                mtn_project_profile_url=profile_url,
                tier='basic',
                payment_status='unpaid'
            )
            
            # Set random password for temp user
            user.set_password(os.urandom(24).hex())
            
            # Save to database
            with self.db_session.begin_nested():
                self.db_session.add(user)
                self.db_session.commit()
            
            logger.info(f"Created temp user: {temp_username}")
            return user
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error creating temp user: {str(e)}")
            raise UserCreationError(f"Failed to create temp user: {str(e)}")

    def create_permanent_user(self, email: str, username: str, password: str, profile_url: Optional[str] = None) -> User:
        """Create a new permanent user"""
        try:
            # Validate inputs
            if not all([email, username, password]):
                raise UserCreationError("Email, username, and password are required")
            
            # Check if email or username already exists
            if User.query.filter_by(email=email).first():
                raise UserCreationError("Email already registered")
            if User.query.filter_by(username=username).first():
                raise UserCreationError("Username already taken")
            
            # Validate and clean profile URL if provided
            if profile_url:
                profile_url = profile_url.strip()
                # First check for temporary user with this URL
                temp_user = User.query.filter(
                    User.mtn_project_profile_url == profile_url,
                    User.username.endswith('_temp')
                ).first()
                
                if temp_user:
                    logger.info(f"Removing temporary user {temp_user.username} and associated data for permanent registration")
                    try:
                        with self.db_session.begin_nested():
                            # Delete performance pyramid records first (child table)
                            PerformancePyramid.query.filter_by(user_id=temp_user.id).delete()
                            
                            # Delete user ticks (child table)
                            UserTicks.query.filter_by(user_id=temp_user.id).delete()
                            
                            # Finally delete the temp user
                            self.db_session.delete(temp_user)
                            
                        self.db_session.commit()
                        logger.info("Successfully deleted temporary user and associated data")
                    except Exception as e:
                        self.db_session.rollback()
                        logger.error(f"Error deleting temporary user data: {str(e)}")
                        raise UserCreationError(f"Failed to delete temporary user data: {str(e)}")
                
                # Then check if URL exists for another permanent user
                existing_user = User.query.filter(
                    User.mtn_project_profile_url == profile_url,
                    ~User.username.endswith('_temp')
                ).first()
                
                if existing_user:
                    raise UserCreationError("Mountain Project profile already linked to another account")
            
            # Create user
            user = User(
                email=email,
                username=username,
                mtn_project_profile_url=profile_url,
                tier='basic',
                payment_status='unpaid'
            )
            user.set_password(password)
            
            # Save to database
            with self.db_session.begin_nested():
                self.db_session.add(user)
                self.db_session.commit()
            
            logger.info(f"Created permanent user: {username} with profile URL: {profile_url}")
            return user
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error creating permanent user: {str(e)}")
            raise UserCreationError(f"Failed to create permanent user: {str(e)}")

    def get_existing_user(self, profile_url: str) -> User:
        """Get existing permanent user by profile URL"""
        user = User.query.filter(
            User.mtn_project_profile_url == profile_url,
            ~User.username.endswith('_temp')
        ).first()
        
        if not user:
            raise UserCreationError("User not found")
            
        return user

    def get_temp_user(self, profile_url: str) -> User:
        """Get existing temporary user by profile URL"""
        user = User.query.filter(
            User.mtn_project_profile_url == profile_url,
            User.username.endswith('_temp')
        ).first()
        
        if not user:
            raise UserCreationError("Temporary user not found")
            
        return user

    def login_user_if_needed(self, user: User) -> None:
        """Login user if not already logged in"""
        try:
            if not current_user.is_authenticated or current_user.id != user.id:
                login_user(user, remember=False)
                user.last_login = datetime.utcnow()
                self.db_session.commit()
                logger.info(f"Logged in user: {user.username}")
            else:
                logger.debug(f"User {user.username} already logged in")
                
        except Exception as e:
            logger.error(f"Error logging in user: {str(e)}")
            raise UserCreationError(f"Failed to log in user: {str(e)}")

    def _extract_username_from_url(self, url: str) -> str:
        """Extract username from Mountain Project URL"""
        try:
            # Handle both numeric IDs and vanity URLs
            parts = url.strip('/').split('/')
            if parts[-1].isdigit():
                return "unknown_climber"
            return parts[-1].split('?')[0]  # Remove query params
        except Exception:
            return "unknown_climber"

    def _generate_temp_email(self, username: str) -> str:
        """Generate unique temporary email"""
        base_email = f"{username}@temp.sendsage.com"
        counter = 1
        while User.query.filter_by(email=base_email).first():
            base_email = f"{username}{counter}@temp.sendsage.com"
            counter += 1
        return base_email

    def convert_temp_to_permanent(self, temp_user: User, email: str, username: str, password: str) -> User:
        """Convert temporary user to permanent user"""
        try:
            with self.db_session.begin_nested():
                # Update user information
                temp_user.email = email
                temp_user.username = username
                temp_user.set_password(password)
                temp_user.payment_status = 'unpaid'  # Reset payment status
                
                self.db_session.commit()
                logger.info(f"Converted temp user to permanent: {username}")
                return temp_user
                
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error converting temp user: {str(e)}")
            raise UserCreationError(f"Failed to convert temp user: {str(e)}")

    def update_mountain_project_url(self, user: User, profile_url: str) -> User:
        """Update user's Mountain Project profile URL"""
        try:
            if not profile_url:
                raise UserCreationError("Profile URL cannot be empty")
                
            profile_url = profile_url.strip()
            
            # Check if URL already exists for another user
            existing_user = User.query.filter(
                User.mtn_project_profile_url == profile_url,
                User.id != user.id
            ).first()
            
            if existing_user:
                raise UserCreationError("Mountain Project profile already linked to another account")
            
            with self.db_session.begin_nested():
                user.mtn_project_profile_url = profile_url
                user.mtn_project_last_sync = datetime.utcnow()
                self.db_session.commit()
                
            logger.info(f"Updated Mountain Project URL for user {user.username}: {profile_url}")
            return user
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error updating Mountain Project URL: {str(e)}")
            raise UserCreationError(f"Failed to update Mountain Project URL: {str(e)}")
