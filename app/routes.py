import pandas as pd
from flask import render_template, request, redirect, url_for, jsonify, flash
from app import app, db
from app.models import BinnedCodeDict, BoulderPyramid, SportPyramid, TradPyramid, UserTicks
from app.services import DataProcessor
from app.services.database_service import DatabaseService
from datetime import date
from collections import defaultdict
import json
from app.services.pyramid_builder import PyramidBuilder
from app.services.grade_processor import GradeProcessor
from app.services.pyramid_update_service import PyramidUpdateService
from flask import session

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        return super(CustomJSONEncoder, self).default(obj)

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        first_input = request.form.get('first_input')
        app.logger.info(f"Received form data - first_input: {first_input}")
        
        if not first_input:
            app.logger.error("No first_input provided")
            return jsonify({
                'error': 'Please provide a Mountain Project profile URL'
            }), 400
            
        try:
            # Clean the input URL
            first_input = first_input.strip()
            app.logger.info(f"Processing URL after strip: '{first_input}'")
            
            # More flexible URL validation
            if 'mountainproject.com/user/' not in first_input:
                app.logger.error(f"URL validation failed for: '{first_input}'")
                return jsonify({
                    'error': 'Please provide a valid Mountain Project profile URL'
                }), 400

            # Clean and encode the URL
            first_input = first_input.replace(' ', '%20')
            app.logger.info(f"URL after encoding: '{first_input}'")

            # Extract username from URL
            username = first_input.split('/')[-1]

            # Always process the profile data
            processor = DataProcessor()
            sport_pyramid, trad_pyramid, boulder_pyramid, user_ticks, username = processor.process_profile(first_input)

            # Clear existing data for this username
            DatabaseService.clear_user_data(username)

            # Update the calculated data using DatabaseService
            DatabaseService.save_calculated_data({
                'sport_pyramid': sport_pyramid,
                'trad_pyramid': trad_pyramid,
                'boulder_pyramid': boulder_pyramid,
                'user_ticks': user_ticks
            })
            
            return redirect(url_for('userviz', username=username))
            
        except Exception as e:
            app.logger.error(f"Error processing request: {str(e)}")
            return jsonify({
                'error': 'An error occurred while processing your data. Please try again.'
            }), 500

    return render_template('index.html')

@app.route("/terms-privacy")
def terms_and_privacy():
    return render_template('termsAndPrivacy.html')

@app.route("/userviz")
def userviz():
    username = request.args.get('username')
    if not username:
        return "Username is required", 400
        
    # Get pyramids from database
    pyramids = DatabaseService.get_pyramids_by_username(username)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks(username)
    
    # Convert to list of dicts and handle date serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]
    user_ticks_data = [r.as_dict() for r in user_ticks]

    # Convert dates to strings
    for item in sport_pyramid_data + trad_pyramid_data + boulder_pyramid_data + user_ticks_data:
        if 'tick_date' in item:
            item['tick_date'] = item['tick_date'].strftime('%Y-%m-%d')
    
    return render_template('userViz.html', 
                         username=username,
                         sport_pyramid=sport_pyramid_data,
                         trad_pyramid=trad_pyramid_data,
                         boulder_pyramid=boulder_pyramid_data,
                         user_ticks=user_ticks_data,
                         binned_code_dict=binned_code_dict_data)

@app.route("/performance-pyramid")
def performance_pyramid():
    username = request.args.get('username')
    if not username:
        return "Username is required", 400

    # Get pyramids directly from database
    pyramids = DatabaseService.get_pyramids_by_username(username)
    binned_code_dict = BinnedCodeDict.query.all()
    user_ticks = DatabaseService.get_user_ticks(username)

    # Convert to JSON
    sport_pyramid_json = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_json = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_json = [r.as_dict() for r in pyramids['boulder']]
    user_ticks_json = [r.as_dict() for r in user_ticks]
    binned_code_dict_json = [r.as_dict() for r in binned_code_dict]

    return render_template('performancePyramid.html',
                         username=username,
                         sport_pyramid=sport_pyramid_json,
                         trad_pyramid=trad_pyramid_json,
                         boulder_pyramid=boulder_pyramid_json,
                         user_ticks=user_ticks_json,
                         binned_code_dict=binned_code_dict_json)

@app.route("/base-volume")
def base_volume():
    username = request.args.get('username')
    user_ticks = DatabaseService.get_user_ticks(username)
    binned_code_dict = BinnedCodeDict.query.all()

    return render_template('baseVolume.html',
                         username=username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder),
                         binned_code_dict=json.dumps([r.as_dict() for r in binned_code_dict], cls=CustomJSONEncoder))

@app.route("/progression")
def progression():
    username = request.args.get('username')
    user_ticks = DatabaseService.get_user_ticks(username)
    binned_code_dict = BinnedCodeDict.query.all()

    return render_template('progression.html',
                         username=username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder),
                         binned_code_dict=json.dumps([r.as_dict() for r in binned_code_dict], cls=CustomJSONEncoder))

@app.route("/when-where")
def when_where():
    username = request.args.get('username')
    user_ticks = DatabaseService.get_user_ticks(username)

    return render_template('whenWhere.html',
                         username=username,
                         user_ticks=json.dumps([r.as_dict() for r in user_ticks], cls=CustomJSONEncoder))

# Initialize grade processor
grade_processor = GradeProcessor()

@app.route("/pyramid-input", methods=['GET', 'POST'])
def pyramid_input():
    username = request.args.get('username')
    if not username:
        flash('Username is required.')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        try:
            # Get the changes data from the form
            changes_data = request.form.get('changes_data')
            if changes_data:
                changes = json.loads(changes_data)
                app.logger.info(f"Received changes data: {changes}")
                
                # Process the changes directly to pyramid tables
                PyramidUpdateService.process_changes(username, changes)
                
                # Clear any cached data
                db.session.expire_all()
                
                flash('Changes saved successfully!', 'success')
            else:
                flash('No changes were submitted.', 'warning')
                
            # Redirect to the user's dashboard visualization page
            return redirect(url_for('userviz', username=username))
            
        except Exception as e:
            app.logger.error(f"Error processing changes: {str(e)}")
            flash('An error occurred while saving changes.', 'error')
            return redirect(url_for('pyramid_input', username=username))
            
    # GET request - show the form
    pyramids = DatabaseService.get_pyramids_by_username(username)
    routes_grade_list = grade_processor.routes_grade_list
    boulders_grade_list = grade_processor.boulders_grade_list
    
    return render_template('pyramidInputs.html',
                         username=username,
                         sport_pyramid=pyramids['sport'],
                         trad_pyramid=pyramids['trad'],
                         boulder_pyramid=pyramids['boulder'],
                         routes_grade_list=routes_grade_list,
                         boulders_grade_list=boulders_grade_list)

@app.route("/performance-characteristics")
def performance_characteristics():
    username = request.args.get('username')
    
    # Initialize binned code dict if empty
    if not BinnedCodeDict.query.first():
        grade_processor = GradeProcessor()
        DatabaseService.init_binned_code_dict(grade_processor.binned_code_dict)
    
    pyramids = DatabaseService.get_pyramids_by_username(username)
    binned_code_dict = BinnedCodeDict.query.all()

    # Convert to list of dicts and handle date serialization
    sport_pyramid_data = [r.as_dict() for r in pyramids['sport']]
    trad_pyramid_data = [r.as_dict() for r in pyramids['trad']]
    boulder_pyramid_data = [r.as_dict() for r in pyramids['boulder']]
    binned_code_dict_data = [r.as_dict() for r in binned_code_dict]

    # Convert dates to strings
    for item in sport_pyramid_data + trad_pyramid_data + boulder_pyramid_data:
        if 'tick_date' in item:
            item['tick_date'] = item['tick_date'].strftime('%Y-%m-%d')

    return render_template('performanceCharacteristics.html',
                         username=username,
                         sport_pyramid=sport_pyramid_data,
                         trad_pyramid=trad_pyramid_data,
                         boulder_pyramid=boulder_pyramid_data,
                         binned_code_dict=binned_code_dict_data)

@app.route("/delete-tick/<int:tick_id>", methods=['DELETE'])
def delete_tick(tick_id):
    try:
        # Get username before deletion for pyramid rebuild
        user_tick = UserTicks.query.get(tick_id)
        if not user_tick:
            return jsonify({
                'success': False, 
                'error': 'Tick not found'
            }), 404
            
        username = user_tick.username
        app.logger.info(f"Deleting tick {tick_id} for user {username}")
        
        # Delete the tick and rebuild pyramids
        success = DatabaseService.delete_user_tick(tick_id)
        
        if success:
            # Get the fresh pyramid data to return
            pyramids = DatabaseService.get_pyramids_by_username(username)
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