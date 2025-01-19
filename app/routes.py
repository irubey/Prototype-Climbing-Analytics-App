from flask import render_template, request, redirect, url_for, jsonify, flash, make_response
from app import app, db, cache
from app.models import (
    BinnedCodeDict, 
    UserTicks, 
    ClimberSummary,
)
from app.services import DataProcessor
from app.services.database_service import DatabaseService
from app.services.analytics_service import AnalyticsService
from app.services.climber_summary import ClimberSummaryService, UserInputData
from app.services.ai.api import get_completion, get_climber_context
from datetime import date
import json
from app.services.grade_processor import GradeProcessor
from app.services.pyramid_update_service import PyramidUpdateService
import psutil
import os
from sqlalchemy.sql import text
from datetime import datetime

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        if hasattr(obj, 'value'):  # Handle enum objects
            return obj.value
        return super(CustomJSONEncoder, self).default(obj)


@app.route("/", methods=['GET', 'POST']) 
def index():
    if request.method == 'POST':
        profile_url = request.form.get('profile_url')
        app.logger.info(f"Received form data - profile_url: {profile_url}")
        
        # Log memory usage at start of request
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / 1024 / 1024
        app.logger.info(f"Memory usage at start: {start_memory:.2f} MB")
        
        if not profile_url:
            app.logger.error("No profile_url provided")
            return jsonify({
                'error': 'Please provide a Mountain Project profile URL'
            }), 400
            
        try:
            # Clean the input URL
            profile_url = profile_url.strip()
            app.logger.info(f"Processing URL after strip: '{profile_url}'")
            
            # More flexible URL validation
            if 'mountainproject.com/user/' not in profile_url:
                app.logger.error(f"URL validation failed for: '{profile_url}'")
                return jsonify({
                    'error': 'Please provide a valid Mountain Project profile URL'
                }), 400

            # Extract userId from URL
            try:
                # URL format: mountainproject.com/user/{userId}/{username}
                url_parts = profile_url.split('/')
                userId = int(url_parts[-2])  # Convert to int to validate it's a number
                app.logger.info(f"Extracted userId: {userId}")
            except (IndexError, ValueError):
                app.logger.error(f"Failed to extract valid userId from URL: {profile_url}")
                return jsonify({
                    'error': 'Invalid Mountain Project URL format'
                }), 400

            # Clean and encode the URL
            profile_url = profile_url.replace(' ', '%20')
            app.logger.info(f"URL after encoding: '{profile_url}'")

            # Check if user data exists
            existing_ticks = UserTicks.query.filter_by(userId=int(userId)).first()
            if existing_ticks:
                app.logger.info(f"Found existing data for userId: {userId}")
                return redirect(url_for('userviz', userId=int(userId)))

            # If no existing data, process the profile
            processor = DataProcessor(db.session)
            sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, username, extracted_userId = processor.process_profile(profile_url)

            # Verify userId matches
            if int(extracted_userId) != int(userId):
                app.logger.error(f"URL userId ({userId}) doesn't match extracted userId ({extracted_userId})")
                return jsonify({
                    'error': 'Invalid user profile URL'
                }), 400

            # Log memory usage before database operations
            current_memory = process.memory_info().rss / 1024 / 1024
            app.logger.info(f"Memory usage before DB ops: {current_memory:.2f} MB (Change: {current_memory - start_memory:.2f} MB)")

            try:
                # Clear existing data for this userId
                DatabaseService.clear_user_data(userId=int(userId))

                # Update the calculated data using DatabaseService
                DatabaseService.save_calculated_data({
                    'sport_pyramid': sport_pyramid,
                    'trad_pyramid': trad_pyramid,
                    'boulder_pyramid': boulder_pyramid,
                    'user_ticks': user_ticks
                })
            except Exception as db_error:
                app.logger.error(f"Database operation failed: {str(db_error)}")
                return jsonify({
                    'error': 'Database operation failed. Please try again.'
                }), 500
            
            # Log final memory usage
            end_memory = process.memory_info().rss / 1024 / 1024
            app.logger.info(f"Final memory usage: {end_memory:.2f} MB (Total change: {end_memory - start_memory:.2f} MB)")
            
            return redirect(url_for('userviz', userId=int(userId)))
            
        except Exception as e:
            app.logger.error(f"Error processing request: {str(e)}")
            # Log memory on error
            error_memory = process.memory_info().rss / 1024 / 1024
            app.logger.error(f"Memory usage at error: {error_memory:.2f} MB (Change: {error_memory - start_memory:.2f} MB)")
            return jsonify({
                'error': 'An error occurred while processing your data. Please try again.'
            }), 500

   
    return render_template('index.html')

@app.route("/terms-privacy")
@cache.cached(timeout=86400) 
def terms_and_privacy():
    return render_template('termsAndPrivacy.html')

@app.route("/userviz")
def userviz():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404
        
    # Get pyramids from database
    pyramids = DatabaseService.get_pyramids_by_user_id(userId)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks_by_id(userId)

    # Get analytics metrics
    analytics_service = AnalyticsService(db)
    metrics = analytics_service.get_all_metrics(userId=userId)

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]
    user_ticks_data = [r.as_dict() for r in user_ticks]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))
    
    return render_template('userViz.html', 
                         userId=userId,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json,
                         **metrics)

@app.route("/performance-pyramid")
def performance_pyramid():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404

    # Get pyramids directly from database
    pyramids = DatabaseService.get_pyramids_by_user_id(userId)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks_by_id(userId)

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    user_ticks_data = [r.as_dict() for r in user_ticks]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('performancePyramid.html',
                         userId=userId,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json)

@app.route("/base-volume")
def base_volume():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(userId)
    binned_code_dict = BinnedCodeDict.query.all()

    # Convert to dictionaries and handle serialization
    user_ticks_data = [r.as_dict() for r in user_ticks]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    user_ticks_json = json.loads(encoder.encode(user_ticks_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('baseVolume.html',
                         userId=userId,
                         username=user.username,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json)

@app.route("/progression")
def progression():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(userId)
    binned_code_dict = BinnedCodeDict.query.all()

    return render_template('progression.html',
                         userId=userId,
                         username=user.username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder),
                         binned_code_dict=json.dumps([r.as_dict() for r in binned_code_dict], cls=CustomJSONEncoder))

@app.route("/when-where")
def when_where():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404

    user_ticks = DatabaseService.get_user_ticks_by_id(userId)

    return render_template('whenWhere.html',
                         userId=userId,
                         username=user.username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder))


REQUIRED_FIELDS = ['climbing_goals']

@app.route("/sage-chat")
def sage_chat():
    user_id = request.args.get('userId')
    app.logger.info(f"Sage chat request for userId: {user_id}")
    
    # First check if user exists in UserTicks
    user = UserTicks.query.filter_by(userId=user_id).first()
    if not user:
        app.logger.error(f"User not found in UserTicks: {user_id}")
        return "User not found", 404

    try:
        # Get or create ClimberSummary using the service
        summary_service = ClimberSummaryService(user_id=user_id, username=user.username)
        summary = ClimberSummary.query.get(user_id)
        
        if not summary:
            app.logger.info(f"Creating new ClimberSummary for user: {user_id}")
            # This will create a complete summary with all available data
            summary = summary_service.update_summary()
        else:
            # Update existing summary to ensure all fields are populated
            summary = summary_service.update_summary()
        
        app.logger.info(f"Found/created climber summary for user: {summary.username}")
        data_complete = check_data_completeness(summary)
        app.logger.info(f"Data completeness check: {data_complete}")
        
        # Initialize grade processor for grade lists
        grade_processor = GradeProcessor()
        routes_grade_list = grade_processor.routes_grade_list
        boulders_grade_list = grade_processor.boulders_grade_list
        
        return render_template('sageChat.html', 
                             summary=summary, 
                             data_complete=data_complete, 
                             required_fields=REQUIRED_FIELDS,
                             routes_grade_list=routes_grade_list,
                             boulders_grade_list=boulders_grade_list)
    except Exception as e:
        app.logger.error(f"Error in sage_chat route: {str(e)}")
        db.session.rollback()
        raise

@app.route("/sage-chat/onboard", methods=['POST'])
def sage_chat_onboard():
    user_id = request.args.get('userId')
    summary = ClimberSummary.query.get_or_404(user_id)
    
    try:
        # Create UserInputData from form data
        user_input = UserInputData(
            # Core progression metrics
            highest_sport_grade_tried=request.form.get('highest_sport_grade_tried'),
            highest_trad_grade_tried=request.form.get('highest_trad_grade_tried'),
            highest_boulder_grade_tried=request.form.get('highest_boulder_grade_tried'),
            total_climbs=int(request.form.get('total_climbs')) if request.form.get('total_climbs') else None,
            favorite_discipline=request.form.get('favorite_discipline'),
            years_climbing_outside=int(request.form.get('years_climbing_outside')) if request.form.get('years_climbing_outside') else None,
            preferred_crag_last_year=request.form.get('preferred_crag_last_year'),
            
            # Training context
            training_frequency=request.form.get('training_frequency'),
            typical_session_length=request.form.get('typical_session_length'),
            has_hangboard=request.form.get('has_hangboard', '').lower() == 'true',
            has_home_wall=request.form.get('has_home_wall', '').lower() == 'true',
            goes_to_gym=request.form.get('goes_to_gym', '').lower() == 'true',
            
            # Performance metrics
            highest_grade_sport_sent_clean_on_lead=request.form.get('highest_grade_sport_sent_clean_on_lead'),
            highest_grade_tr_sent_clean=request.form.get('highest_grade_tr_sent_clean'),
            highest_grade_trad_sent_clean_on_lead=request.form.get('highest_grade_trad_sent_clean_on_lead'),
            highest_grade_boulder_sent_clean=request.form.get('highest_grade_boulder_sent_clean'),
            onsight_grade_sport=request.form.get('onsight_grade_sport'),
            onsight_grade_trad=request.form.get('onsight_grade_trad'),
            flash_grade_boulder=request.form.get('flash_grade_boulder'),
            
            # Injury history and limitations
            current_injuries=request.form.get('current_injuries'),
            injury_history=request.form.get('injury_history'),
            physical_limitations=request.form.get('physical_limitations'),
            
            # Goals and preferences
            climbing_goals=request.form.get('climbing_goals'),
            willing_to_train_indoors=request.form.get('willing_to_train_indoors', '').lower() == 'true',
            
            # Recent activity
            sends_last_30_days=int(request.form.get('sends_last_30_days')) if request.form.get('sends_last_30_days') else None,
            
            # Style preferences
            favorite_angle=request.form.get('favorite_angle'),
            favorite_hold_types=request.form.get('favorite_hold_types'),
            weakest_style=request.form.get('weakest_style'),
            strongest_style=request.form.get('strongest_style'),
            favorite_energy_type=request.form.get('favorite_energy_type'),
            
            # Lifestyle
            sleep_score=request.form.get('sleep_score'),
            nutrition_score=request.form.get('nutrition_score'),
            
            # Additional notes
            additional_notes=request.form.get('additional_notes')
        )
        
        # Validate required fields
        if not user_input.climbing_goals:
            return jsonify({"error": "climbing_goals is required"}), 400
            
        # Use service to update summary
        summary_service = ClimberSummaryService(user_id=user_id, username=summary.username)
        summary = summary_service.update_summary(user_input=user_input)
        
        # Return success with reset_chat flag to trigger frontend reset
        return jsonify({
            "success": True,
            "reset_chat": True  # Add this flag to indicate chat should be reset
        })
    except Exception as e:
        app.logger.error(f"Error in sage_chat_onboard: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Failed to update profile"}), 400

@app.route("/sage-chat/message", methods=['POST'])
def sage_chat_message():
    user_id = request.args.get('userId')
    summary = ClimberSummary.query.get_or_404(user_id)
    
    data = request.get_json()
    user_prompt = data.get('user_prompt')
    if not user_prompt:
        return jsonify({"error": "Message cannot be empty"}), 400
        
    is_first_message = data.get('is_first_message', False)
    conversation_history = data.get('conversation_history', [])
    
    ai_response = get_completion(
        user_prompt, 
        climber_id=user_id, 
        is_first_message=is_first_message,
        messages=conversation_history
    )

    # For first message, get the context to send back
    response_data = {"response": ai_response}
    if is_first_message:
        additional_context = get_climber_context(user_id)
        context_str = "\n".join(f"- {k}: {v}" for k, v in additional_context.items())
        response_data["context"] = f"Here is your climbing context that I'll reference throughout our conversation:\n\n{context_str}"
    
    return jsonify(response_data)

def check_data_completeness(summary):
    required_fields = [
        'climbing_goals',  # Goals and preferences
        'favorite_discipline',  # Core progression
        'typical_session_length',  # Training context
        'favorite_angle',  # Style preferences
        'favorite_hold_types',  # Style preferences
        'weakest_style',  # Style preferences
        'strongest_style',  # Style preferences
        'favorite_energy_type',  # Style preferences
        'sleep_score',  # Lifestyle
        'nutrition_score'  # Lifestyle
    ]
    for field in required_fields:
        if getattr(summary, field) in [None, '']:
            return False
    return True

@app.route("/pyramid-input", methods=['GET', 'POST'])
def pyramid_input():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        flash('User not found.')
        return redirect(url_for('index'))
    # Initialize grade processor
    grade_processor = GradeProcessor()
    if request.method == 'POST':
        try:
            # Get the changes data from the form
            changes_data = request.form.get('changes_data')
            if changes_data:
                changes = json.loads(changes_data)
                app.logger.info(f"Received changes data: {changes}")
                
                # Process the changes directly to pyramid tables
                update_service = PyramidUpdateService()
                update_service.process_changes(userId=userId, changes=changes)
                
                return redirect(url_for('performance_characteristics', userId=userId))
            else:
                flash('No changes were submitted.', 'warning')
                return redirect(url_for('pyramid_input', userId=userId))
            
        except Exception as e:
            app.logger.error(f"Error processing changes: {str(e)}")
            flash('An error occurred while saving changes.', 'error')
            return redirect(url_for('pyramid_input', userId=userId))

    # GET request - show the form
    pyramids = DatabaseService.get_pyramids_by_user_id(userId)
    routes_grade_list = grade_processor.routes_grade_list
    boulders_grade_list = grade_processor.boulders_grade_list
    
    return render_template('pyramidInputs.html',
                         userId=userId,
                         username=user.username,
                         sport_pyramid=pyramids['sport'],
                         trad_pyramid=pyramids['trad'],
                         boulder_pyramid=pyramids['boulder'],
                         routes_grade_list=routes_grade_list,
                         boulders_grade_list=boulders_grade_list)

@app.route("/performance-characteristics")
def performance_characteristics():
    userId = request.args.get('userId')

    # Get user data
    user = UserTicks.query.filter_by(userId=userId).first()
    if not user:
        return "User not found", 404

    # Get pyramids directly from database
    pyramids = DatabaseService.get_pyramids_by_user_id(userId)
    binned_code_dict = BinnedCodeDict.query.all()

    # Convert to dictionaries and handle serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Pre-serialize the data using the custom encoder
    encoder = CustomJSONEncoder()
    sport_pyramid_json = json.loads(encoder.encode(sport_pyramid_data))
    trad_pyramid_json = json.loads(encoder.encode(trad_pyramid_data))
    boulder_pyramid_json = json.loads(encoder.encode(boulder_pyramid_data))
    binned_code_dict_json = json.loads(encoder.encode(binned_code_dict_data))

    return render_template('performanceCharacteristics.html',
                         userId=userId,
                         username=user.username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         binned_code_dict=binned_code_dict_json)

@app.route("/delete-tick/<int:tick_id>", methods=['DELETE'])
def delete_tick(tick_id):
    try:
        # Get user info before deletion for pyramid rebuild
        user_tick = UserTicks.query.get(tick_id)
        if not user_tick:
            return jsonify({
                'success': False, 
                'error': 'Tick not found'
            }), 404
            
        userId = user_tick.userId
        app.logger.info(f"Deleting tick {tick_id} for user {userId}")
        
        # Delete the tick and rebuild pyramids
        success = DatabaseService.delete_user_tick(tick_id)
        
        if success:
            # Get the fresh pyramid data to return
            pyramids = DatabaseService.get_pyramids_by_user_id(userId)
            pyramid_data = {
                'sport': [r.as_dict() for r in pyramids['sport']],
                'trad': [r.as_dict() for r in pyramids['trad']],
                'boulder': [r.as_dict() for r in pyramids['boulder']]
            }
            
            # Log pyramid data sizes
            app.logger.info(f"Returning pyramid data - Sport: {len(pyramid_data['sport'])}, Trad: {len(pyramid_data['trad'])}, Boulder: {len(pyramid_data['boulder'])}")
            
            # Convert dates to strings
            for discipline in pyramid_data.values():
                for item in discipline:
                    if 'tick_date' in item:
                        item['tick_date'] = item['tick_date'].strftime('%Y-%m-%d')
            
            return jsonify({
                'success': True,
                'pyramids': pyramid_data
            })
        else:
            app.logger.error(f"Failed to delete tick {tick_id}")
            return jsonify({
                'success': False, 
                'error': 'Error deleting tick'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error deleting tick {tick_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Server error while deleting tick'
        }), 500

@app.route("/refresh-data/<int:userId>", methods=['POST'])
def refresh_data(userId):
    try:
        # Get user data
        user = UserTicks.query.filter_by(userId=userId).first()
        if not user:
            return jsonify({
                'error': 'User not found'
            }), 404

        # Get the profile URL from user data
        profile_url = user.user_profile_url
        if not profile_url:
            return jsonify({
                'error': 'Profile URL not found'
            }), 404

        # Clear existing data
        DatabaseService.clear_user_data(userId=userId)
        
        # Process the profile
        processor = DataProcessor(db.session)
        sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, username, extracted_userId = processor.process_profile(profile_url)

        # Verify userId matches
        if int(extracted_userId) != userId:
            return jsonify({
                'error': 'User ID mismatch during refresh'
            }), 400

        # Update the calculated data using DatabaseService
        DatabaseService.save_calculated_data({
            'sport_pyramid': sport_pyramid,
            'trad_pyramid': trad_pyramid,
            'boulder_pyramid': boulder_pyramid,
            'user_ticks': user_ticks
        })

        return redirect(url_for('userviz', userId=userId))

    except Exception as e:
        app.logger.error(f"Error refreshing data for user {userId}: {str(e)}")
        return jsonify({
            'error': 'An error occurred while refreshing your data. Please try again.'
        }), 500

@app.route("/health")
def health_check():
    """Health check endpoint that includes database connection and memory status"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        db_status = "healthy"
        
        # Get memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return jsonify({
            'status': 'healthy',
            'database': {
                'status': db_status
            },
            'memory': {
                'rss': memory_info.rss / 1024 / 1024,  # RSS in MB
                'vms': memory_info.vms / 1024 / 1024,  # VMS in MB
                'percent': process.memory_percent()
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
    
@app.route("/api/support-count")
@cache.cached(timeout=3600)  # Cache for one hour
def get_support_count():
    # Query the database
    unique_users = db.session.query(UserTicks.username).distinct().count()
    
    app.logger.info(f"Support count calculated: {unique_users}")
    return jsonify({"count": unique_users})

