import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ['DATABASE_URL']

binned_code_data = { 
            1: "5.0", 
            2: "5.1",
            3: "5.2", 
            4: "5.3",
            5: "5.4", 
            6: "5.5",
            7: "5.6", 
            8: "5.7", 
            9: "5.8", 
            10: "5.9",
            11: "5.10-",
            12: "5.10",
            13: "5.10+",
            14: "5.11-",
            15: "5.11",
            16: "5.11+",
            17: "5.12-",
            18: "5.12",
            19: "5.12+",
            20: "5.13-",
            21: "5.13",
            22: "5.13+", 
            23: "5.14-",
            24: "5.14",
            25:  "5.14+",
            26: "5.15-",
            27: "5.15",
            28: "5.15+",
            101: "V-easy",
            102: "V0",
            103: "V1",
            104: "V2",
            105: "V3",
            106: "V4",
            107: "V5",
            108: "V6",
            109: "V7",
            110: "V8",
            111: "V9",
            112: "V10",
            113: "V11",
            114: "V12",
            115: "V13",
            116: "V14",
            117: "V15",
            118: "V16",
            119: "V17",
            120: "V18",
            201: "WI1",
            202: "WI2",
            203: "WI3",
            204: "WI4",
            205: "WI5",
            206: "WI6",
            207: "WI7",
            208: "WI8",
            301: "M1",
            302: "M2",
            303: "M3",
            304: "M4",
            305: "M5",
            306: "M6",
            307: "M7",
            308: "M8",
            309: "M9",
            310: "M10",
            311: "M11",
            312: "M12",
            313: "M13",
            314: "M14",
            315: "M15",
            316: "M16",
            317: "M17",
            318: "M18",
            319: "M19",
            401: "A0",
            402: "A1",
            403: "A2",
            404: "A3",
            405: "A4",
            501: "3rd",
            502: "4th",
            503: "5th",
            601: "Snow",
            701: "C0",
            702: "C1",
            703: "C2",
            704: "C3",
            705: "C4",
            801: "AI0",
            802: "AI1",
            803: "AI2",
            804: "AI3",
            805: "AI4"
            }


def create_tables():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Create binned_code_dict table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS binned_code_dict (
            binned_code INT PRIMARY KEY,
            binned_grade VARCHAR(50) NOT NULL
        );
    """)

    # Create tables with similar structure for boulder_pyramid, sport_pyramid, trad_pyramid
    for table_name in ['boulder_pyramid', 'sport_pyramid', 'trad_pyramid', 'user_ticks']:
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id SERIAL PRIMARY KEY,
                route_name VARCHAR(255),
                tick_date DATE,
                route_grade VARCHAR(255),
                binned_grade VARCHAR(255),
                binned_code INT,
                length INT,
                pitches INT,
                location VARCHAR(255),
                lead_style VARCHAR(255),
                discipline VARCHAR(255),
                length_category VARCHAR(255),
                season_category VARCHAR(255),
                route_url VARCHAR(255),
                user_grade VARCHAR(255),
                username VARCHAR(255),
                route_characteristic VARCHAR(255),
                num_attempts INT,
                route_style VARCHAR(255)
            );
        """).format(sql.Identifier(table_name)))

    # Adjust user_ticks table to match the specific structure
    cur.execute("""
        ALTER TABLE user_ticks
        ADD COLUMN IF NOT EXISTS cur_max_rp_sport INT,
        ADD COLUMN IF NOT EXISTS cur_max_rp_trad INT,
        ADD COLUMN IF NOT EXISTS cur_max_boulder INT,
        ADD COLUMN IF NOT EXISTS difficulty_category VARCHAR(255),
        ADD COLUMN IF NOT EXISTS send_bool BOOLEAN;
    """)

    conn.commit()
    cur.close()
    conn.close()

def populate_binned_code_dict():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    for binned_code, binned_grade in binned_code_data.items():
        cur.execute("""
            INSERT INTO binned_code_dict (binned_code, binned_grade)
            VALUES (%s, %s) ON CONFLICT (binned_code) DO UPDATE SET binned_grade = EXCLUDED.binned_grade;
        """, (binned_code, binned_grade))

    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    create_tables()
    populate_binned_code_dict()