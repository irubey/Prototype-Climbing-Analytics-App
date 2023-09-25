import os
import psycopg2
from urllib.parse import urlparse

DATABASE_URL = os.environ.get('DATABASE_URL')

def truncate_tables():
    conn = None
    try:
        # Parse the database URL
        result = urlparse(DATABASE_URL)
        username = result.username
        password = result.password
        database = result.path[1:]
        hostname = result.hostname
        port = result.port

        # Connect to the database
        conn = psycopg2.connect(
            dbname=database,
            user=username,
            password=password,
            host=hostname,
            port=port
        )

        # Create a cursor object
        cur = conn.cursor()

        # Execute the TRUNCATE command
        cur.execute("TRUNCATE user_ticks, sport_pyramid, trad_pyramid, boulder_pyramid;")

        # Close the communication with the PostgreSQL database server
        cur.close()

        # Commit the changes
        conn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    truncate_tables()