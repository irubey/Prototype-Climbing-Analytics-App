from models import db, UserMeta, Routes, UserTicks, Locations, Tags
from sqlalchemy.exc import SQLAlchemyError

#CRUD OPPERATIONS:
#Creates a new user, saves it to UserMeta, and returns new_user object
def create_user(username, email, password):
    try:
        new_user = UserMeta(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return new_user
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

#Creates a new route, saves it to Routes, and returns new_route object
def create_route(name, location, **kwargs):  # Add other necessary parameters
    try:
        new_route = Routes(name=name, location=location, **kwargs)
        db.session.add(new_route)
        db.session.commit()
        return new_route
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

#Creates a new locaiton, saves it to Routes, and returns new_loation object
def create_location(location, area_group, **additional_fields):
    try:
        new_location = Locations(location=location, area_group=area_group, **additional_fields)
        db.session.add(new_location)
        db.session.commit()
        return new_location
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

# Creates a new user tick, saves it to UserTicks, and returns new_user_tick object
def create_user_tick(user_id, route_id, tick_date, **additional_fields):
    try:
        new_user_tick = UserTicks(user_id=user_id, route_id=route_id, tick_date=tick_date, **additional_fields)
        db.session.add(new_user_tick)
        db.session.commit()
        return new_user_tick
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

# Read Operations
def get_user_by_id(user_id):
    try:
        return UserMeta.query.get(user_id)
    except SQLAlchemyError as e:
        raise e

def get_route_by_id(route_id):
    try:
        return Routes.query.get(route_id)
    except SQLAlchemyError as e:
        raise e

def get_location_by_id(location_id):
    try:
        return Locations.query.get(location_id)
    except SQLAlchemyError as e:
        raise e
    
# Update Operations
def update_user(user_id, **kwargs):
    try:
        user = UserMeta.query.get(user_id)
        if user:
            for key, value in kwargs.items():
                setattr(user, key, value)
            db.session.commit()
            return user
        return None
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def update_route(route_id, **kwargs):
    try:
        route = Routes.query.get(route_id)
        if route:
            for key, value in kwargs.items():
                setattr(route, key, value)
            db.session.commit()
            return route
        return None
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def update_location(location_id, **kwargs):
    try:
        location = Locations.query.get(location_id)
        if location:
            for key, value in kwargs.items():
                setattr(location, key, value)
            db.session.commit()
            return location
        return None
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def update_user_tick(tick_id, **kwargs):
    try:
        user_tick = UserTicks.query.get(tick_id)
        if user_tick:
            for key, value in kwargs.items():
                setattr(user_tick, key, value)
            db.session.commit()
            return user_tick
        return None
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

# Delete Operations
def delete_user(user_id):
    try:
        user = UserMeta.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def delete_route(route_id):
    try:
        route = Routes.query.get(route_id)
        if route:
            db.session.delete(route)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def delete_location(location_id):
    try:
        location = Locations.query.get(location_id)
        if location:
            db.session.delete(location)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def delete_user_tick(tick_id):
    try:
        user_tick = UserTicks.query.get(tick_id)
        if user_tick:
            db.session.delete(user_tick)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e

def delete_tag(tag_id):
    try:
        tag = Tags.query.get(tag_id)
        if tag:
            db.session.delete(tag)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        raise e








#Advanced Query Fuctions
#Routes 
#retrieves all routes associated with a specific tag.
def get_routes_by_tag(tag_name):
    try:
        tag = Tags.query.filter(Tags.tag_name == tag_name).first()
        if tag:
            return tag.routes.all()
    except SQLAlchemyError as e:
        raise e

# most popular routes based on the number of ticks. 
def get_routes_by_ticks(limit=10):
    try:
        return Routes.query.outerjoin(UserTicks, Routes.id == UserTicks.route_id)\
                           .group_by(Routes.id)\
                           .order_by(db.func.count(UserTicks.id).desc())\
                           .limit(limit).all()
    except SQLAlchemyError as e:
        raise e

# retrieves all routes that have a specific quality rating.
def get_routes_by_quality(quality_rating):
    try:
        return Routes.query.filter(Routes.quality == quality_rating).all()
    except SQLAlchemyError as e:
        raise e

#retrieves all routes that fall within a specified length range.
def get_routes_by_length_range(min_length, max_length):
    try:
        return Routes.query.filter(Routes.length.between(min_length, max_length)).all()
    except SQLAlchemyError as e:
        raise e

#Fetches routes based on a specific location.
def get_routes_by_location(location_name):
    try:
        # If 'all' is specified, return all routes
        if location_name.lower() == 'all':
            return Routes.query.all()

        # Else, fetch routes for the specific location
        location = Locations.query.filter(Locations.location == location_name).first()
        if location:
            return location.routes.all()

        # If the location is not found, return an empty list or handle accordingly
        return []
    except SQLAlchemyError as e:
        # Add error logging here
        raise e

#Fetches all routes that are in a specific location group.
def get_routes_by_location_group(location_group):
    try:
        locations = Locations.query.filter(Locations.area_group == location_group).all()
        location_ids = [location.id for location in locations]
        return Routes.query.filter(Routes.location_id.in_(location_ids)).all()
    except SQLAlchemyError as e:
        raise e

#Finds routes that have similar attributes in the same area_group
def find_similar_routes_gen(route_id):
    try:
        route = Routes.query.get(route_id)
        if route:
            return Routes.query.join(Locations, Routes.location_id == Locations.id)\
                               .filter(Routes.id != route_id,
                                       Routes.style == route.style,
                                       Routes.grade_code == route.grade_code,
                                       Locations.area_group == route.location.area_group)\
                               .all()
    except SQLAlchemyError as e:
        raise e
def find_similar_routes_kwargs(route_id, **kwargs):
    try:
        route = Routes.query.get(route_id)
        if not route:
            return None

        query = Routes.query.join(Locations, Routes.location_id == Locations.id)\
                            .filter(Routes.id != route_id)

        # Apply filters based on kwargs
        for key, value in kwargs.items():
            if hasattr(Routes, key) and value is not None:
                query = query.filter(getattr(Routes, key) == value)
            elif key == 'area_group' and value is not None:
                query = query.filter(Locations.area_group == value)

        return query.all()
    except SQLAlchemyError as e:
        raise e



#Locations 
#fetches all locations that are part of a specified location group.
def get_locations_by_location_group(location_group):
    try:
        return Locations.query.filter(Locations.area_group == location_group).all()
    except SQLAlchemyError as e:
        raise e



#UserMeta 
#Finds users who have ticked similar routes.
def get_users_with_similar_interests(user_id):
    try:
        user_routes = [tick.route_id for tick in UserTicks.query.filter_by(user_id=user_id)]
        similar_users = UserTicks.query.filter(UserTicks.route_id.in_(user_routes),
                                               UserTicks.user_id != user_id)\
                                       .distinct(UserTicks.user_id)\
                                       .all()
        return [user_tick.user for user_tick in similar_users]
    except SQLAlchemyError as e:
        raise e

#Tags 
#Fetches all unique tags used by a specific user in their ticks.
def get_tags_used_by_user(user_id):
    try:
        ticks = UserTicks.query.filter_by(user_id=user_id).all()
        route_ids = [tick.route_id for tick in ticks]
        return Tags.query.join(Routes, Tags.routes)\
                         .filter(Routes.id.in_(route_ids))\
                         .distinct().all()
    except SQLAlchemyError as e:
        raise e


#UserTicks
#Retrieves the most recent ticks for a given user, useful for tracking recent activity.
def get_recent_user_ticks(user_id, limit=10):
    try:
        return UserTicks.query.filter_by(user_id=user_id)\
                              .order_by(UserTicks.tick_date.desc())\
                              .limit(limit).all()
    except SQLAlchemyError as e:
        raise e

#Get user ticks with Routes fields
def get_user_ticks_with_route_details(user_id):
    try:
        return UserTicks.query.filter_by(user_id=user_id)\
                              .join(Routes, UserTicks.route_id == Routes.id)\
                              .add_columns(Routes.name, Routes.length, Routes.quality, Routes.style)\
                              .all()
    except SQLAlchemyError as e:
        raise e

#Top Sends filters by discipline
def get_user_ticks_within_top_grades(user_id, tick_discipline, grade_range=4):
    try:
        # Fetch route_ids with successful sends
        successful_route_ids = db.session.query(UserTicks.route_id)\
                                         .filter(UserTicks.user_id == user_id,
                                                 UserTicks.num_sends > 0)\
                                         .distinct().subquery()

        # Fetch user ticks with joined route info
        user_ticks_query = UserTicks.query.filter(
            UserTicks.user_id == user_id,
            UserTicks.tick_discipline == tick_discipline
        ).join(Routes, UserTicks.route_id == Routes.id)\
         .filter(UserTicks.route_id.in_(successful_route_ids))

        # Extract grade codes and find the maximum grade code
        grade_codes = [tick.grade_code for tick in user_ticks_query.with_entities(Routes.grade_code)]
        if not grade_codes:
            return []
        max_grade_code = max(grade_codes)

        # Calculate the range of grade codes
        grade_range = [max_grade_code - i for i in range(grade_range)] + [max_grade_code]

        # Query for ticks within the grade range
        filtered_ticks = user_ticks_query.filter(Routes.grade_code.in_(grade_range)).all()

        return filtered_ticks
    except SQLAlchemyError as e:
        # Add error logging here
        raise e

#UserTicks by season -- Spring, Summer, Autumn, Winter
def get_user_ticks_by_season_and_year(user_id, season, year):
    try:
        # Define month ranges for each season
        season_months = {
            'Spring': [(year, 3), (year, 4), (year, 5)],    # March, April, May
            'Summer': [(year, 6), (year, 7), (year, 8)],    # June, July, August
            'Autumn': [(year, 9), (year, 10), (year, 11)],  # September, October, November
            'Winter': [(year - 1, 12), (year, 1), (year, 2)] # December (prev year), January, February
        }

        # Fetch user ticks for the specified season and year
        user_ticks = UserTicks.query.filter(
            UserTicks.user_id == user_id,
            db.or_(*[db.and_(db.extract('year', UserTicks.tick_date) == y,
                            db.extract('month', UserTicks.tick_date) == m)
                     for y, m in season_months.get(season, [])])
        ).all()

        return user_ticks
    except SQLAlchemyError as e:
        print(user_ticks)
        # Add error logging here
        raise e

#UserTicks projects
def get_top_unsuccessful_routes(user_id, tick_discipline, num_routes = 10):
    try:
        # Fetch route_ids where num_sends is always 0 for the user in the specified discipline
        all_unsuccessful_route_ids = db.session.query(UserTicks.route_id)\
            .join(Routes, UserTicks.route_id == Routes.id)\
            .filter(UserTicks.user_id == user_id, 
                    UserTicks.tick_discipline == tick_discipline, 
                    UserTicks.num_sends == 0)\
            .group_by(UserTicks.route_id)\
            .having(db.func.count(db.case([(UserTicks.num_sends > 0, 1)])) == 0)\
            .subquery()

        # Sort these routes by grade codes in descending order and select top 10
        top_route_ids_query = db.session.query(all_unsuccessful_route_ids.c.route_id)\
            .join(Routes, all_unsuccessful_route_ids.c.route_id == Routes.id)\
            .order_by(Routes.grade_code.desc())\
            .limit(num_routes)\
            .subquery()

        # Fetch all UserTicks records for the top 10 route IDs
        top_attempts = UserTicks.query.filter(
            UserTicks.user_id == user_id,
            UserTicks.tick_discipline == tick_discipline,
            UserTicks.route_id.in_(top_route_ids_query)
        ).all()

        return top_attempts
    except SQLAlchemyError as e:
        # Add error logging here
        raise e

#Fetches routes based on a user's most frequently ticked types (style, grade, etc.).
def get_routes_by_user_preference(user_id):
    try:
        user_ticks = UserTicks.query.filter_by(user_id=user_id).all()
        # Assuming the existence of methods to determine the most common style and grade
        most_common_style = determine_most_common_style(user_ticks)
        most_common_grade = determine_most_common_grade(user_ticks)
        return Routes.query.filter(Routes.style == most_common_style,
                                   Routes.grade_code == most_common_grade)\
                           .all()
    except SQLAlchemyError as e:
        raise e


# Aggregation Functions:
#Total Ticks
def get_total_ticks_per_user(user_id):
    return UserTicks.query.filter_by(user_id=user_id).count()

#Total Ticks by Discipline
def get_total_ticks_by_discipline(user_id):
    return db.session.query(UserTicks.tick_discipline, db.func.count(UserTicks.id))\
                     .filter(UserTicks.user_id == user_id)\
                     .group_by(UserTicks.tick_discipline)\
                     .all()

#Total distinct Routes by Discipline
def get_distinct_route_codes_by_user_and_discipline(user_id, discipline):
    try:
        distinct_route_codes_count = db.session.query(db.func.count(db.distinct(Routes.grade_code)))\
                                              .join(UserTicks, Routes.id == UserTicks.route_id)\
                                              .filter(UserTicks.user_id == user_id,
                                                      UserTicks.tick_discipline == discipline)\
                                              .scalar()
        return distinct_route_codes_count
    except SQLAlchemyError as e:
        # Add error logging here
        raise e

#Most popular Routes by discipline and location
def get_most_popular_routes_by_discipline_and_location_group(discipline, location_group, limit=10):
    try:
        popular_routes = db.session.query(
            Routes, db.func.count(UserTicks.id).label('ticks_count')
        ).join(UserTicks, Routes.id == UserTicks.route_id)\
         .join(Locations, Routes.location_id == Locations.id)\
         .filter(UserTicks.tick_discipline == discipline,
                 Locations.area_group == location_group)\
         .group_by(Routes.id)\
         .order_by(db.func.count(UserTicks.id).desc())\
         .limit(limit)\
         .all()

        return popular_routes
    except SQLAlchemyError as e:
        # Add error logging here
        raise e









# User Progress Tracking:

# Functions to track a user's progress over time, like improvements in grades, increase in number of routes climbed, or variations in climbing disciplines.



# Community Engagement Metrics:

# If your application has social features, functions to calculate metrics like most popular routes among all users, trending locations, or routes with the most 'likes' or 'comments'.




# User-Centric Recommendations:

# Enhanced recommendation functions that suggest routes, locations, or climbing styles based on the user’s history and preferences.



# Data Visualization Support:

# Functions that format data specifically for visualization, such as monthly or yearly climbing activity, which can be used to generate graphs or charts on the client side.




# Dynamic Filter Functions:

# Functions that allow users to dynamically filter routes or ticks based on multiple criteria, providing a more personalized and interactive experience.

