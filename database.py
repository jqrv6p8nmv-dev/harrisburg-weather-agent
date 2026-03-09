import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List
import config

class WeatherDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self.init_database()

    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize the database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Forecasts table - stores all forecasts made
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_timestamp TIMESTAMP NOT NULL,
                target_date DATE NOT NULL,
                temperature_high REAL,
                temperature_low REAL,
                snowfall_inches REAL,
                ice_accumulation_inches REAL,
                forecast_raw TEXT,
                source TEXT DEFAULT 'NWS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Observations table - stores actual weather that occurred
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_date DATE NOT NULL UNIQUE,
                temperature_high REAL,
                temperature_low REAL,
                snowfall_inches REAL,
                ice_accumulation_inches REAL,
                observation_raw TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Forecast accuracy tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forecast_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_id INTEGER,
                observation_id INTEGER,
                target_date DATE NOT NULL,
                hours_ahead INTEGER,
                temp_high_error REAL,
                temp_low_error REAL,
                snowfall_error REAL,
                ice_error REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (forecast_id) REFERENCES forecasts(id),
                FOREIGN KEY (observation_id) REFERENCES observations(id)
            )
        ''')

        # Learned adjustments - ML component
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_type TEXT NOT NULL,
                hours_ahead_min INTEGER,
                hours_ahead_max INTEGER,
                avg_temp_high_bias REAL DEFAULT 0,
                avg_temp_low_bias REAL DEFAULT 0,
                avg_snowfall_bias REAL DEFAULT 0,
                avg_ice_bias REAL DEFAULT 0,
                sample_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Email log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subject TEXT,
                body TEXT,
                success BOOLEAN,
                error_message TEXT
            )
        ''')

        conn.commit()
        conn.close()
        self._migrate_database()

    def _migrate_database(self):
        """Add any missing columns to support schema upgrades."""
        conn = self.get_connection()
        cursor = conn.cursor()
        migrations = [
            ("forecasts", "rainfall_inches", "REAL DEFAULT 0.0"),
            ("forecasts", "thunderstorm_risk", "INTEGER DEFAULT 0"),
            ("forecasts", "flooding_risk", "INTEGER DEFAULT 0"),
            ("observations", "rainfall_inches", "REAL DEFAULT 0.0"),
            ("observations", "thunderstorm_risk", "INTEGER DEFAULT 0"),
            ("observations", "flooding_risk", "INTEGER DEFAULT 0"),
            ("forecast_accuracy", "rainfall_error", "REAL"),
            ("learned_adjustments", "avg_rainfall_bias", "REAL DEFAULT 0"),
        ]
        for table, column, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
        conn.close()

    def store_forecast(self, target_date: str, forecast_data: Dict) -> int:
        """Store a forecast."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO forecasts (
                forecast_timestamp, target_date, temperature_high, temperature_low,
                snowfall_inches, ice_accumulation_inches, rainfall_inches,
                thunderstorm_risk, flooding_risk, forecast_raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            target_date,
            forecast_data.get('temperature_high'),
            forecast_data.get('temperature_low'),
            forecast_data.get('snowfall_inches'),
            forecast_data.get('ice_accumulation_inches'),
            forecast_data.get('rainfall_inches'),
            int(bool(forecast_data.get('thunderstorm_risk', False))),
            int(bool(forecast_data.get('flooding_risk', False))),
            json.dumps(forecast_data.get('raw', {}))
        ))

        forecast_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return forecast_id

    def store_observation(self, observation_date: str, observation_data: Dict):
        """Store or update an observation."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO observations (
                observation_date, temperature_high, temperature_low,
                snowfall_inches, ice_accumulation_inches, rainfall_inches,
                thunderstorm_risk, flooding_risk, observation_raw
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(observation_date) DO UPDATE SET
                temperature_high = excluded.temperature_high,
                temperature_low = excluded.temperature_low,
                snowfall_inches = excluded.snowfall_inches,
                ice_accumulation_inches = excluded.ice_accumulation_inches,
                rainfall_inches = excluded.rainfall_inches,
                thunderstorm_risk = excluded.thunderstorm_risk,
                flooding_risk = excluded.flooding_risk,
                observation_raw = excluded.observation_raw,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            observation_date,
            observation_data.get('temperature_high'),
            observation_data.get('temperature_low'),
            observation_data.get('snowfall_inches'),
            observation_data.get('ice_accumulation_inches'),
            observation_data.get('rainfall_inches'),
            int(bool(observation_data.get('thunderstorm_risk', False))),
            int(bool(observation_data.get('flooding_risk', False))),
            json.dumps(observation_data.get('raw', {}))
        ))

        conn.commit()
        conn.close()

    def get_forecasts_for_date(self, target_date: str) -> List[Dict]:
        """Get all forecasts made for a specific date."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, forecast_timestamp, temperature_high, temperature_low,
                   snowfall_inches, ice_accumulation_inches
            FROM forecasts
            WHERE target_date = ?
            ORDER BY forecast_timestamp
        ''', (target_date,))

        results = cursor.fetchall()
        conn.close()

        return [{
            'id': r[0],
            'forecast_timestamp': r[1],
            'temperature_high': r[2],
            'temperature_low': r[3],
            'snowfall_inches': r[4],
            'ice_accumulation_inches': r[5]
        } for r in results]

    def get_observation(self, observation_date: str) -> Optional[Dict]:
        """Get observation for a specific date."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, temperature_high, temperature_low,
                   snowfall_inches, ice_accumulation_inches
            FROM observations
            WHERE observation_date = ?
        ''', (observation_date,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'temperature_high': result[1],
                'temperature_low': result[2],
                'snowfall_inches': result[3],
                'ice_accumulation_inches': result[4]
            }
        return None

    def store_accuracy_record(self, forecast_id: int, observation_id: int,
                            target_date: str, hours_ahead: int, errors: Dict):
        """Store forecast accuracy comparison."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO forecast_accuracy (
                forecast_id, observation_id, target_date, hours_ahead,
                temp_high_error, temp_low_error, snowfall_error, ice_error, rainfall_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            forecast_id, observation_id, target_date, hours_ahead,
            errors.get('temp_high_error'),
            errors.get('temp_low_error'),
            errors.get('snowfall_error'),
            errors.get('ice_error'),
            errors.get('rainfall_error')
        ))

        conn.commit()
        conn.close()

    def get_accuracy_stats(self, hours_ahead_min: int, hours_ahead_max: int) -> Dict:
        """Get accuracy statistics for a time range."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                AVG(temp_high_error) as avg_temp_high_error,
                AVG(temp_low_error) as avg_temp_low_error,
                AVG(snowfall_error) as avg_snowfall_error,
                AVG(ice_error) as avg_ice_error,
                AVG(rainfall_error) as avg_rainfall_error,
                COUNT(*) as sample_count
            FROM forecast_accuracy
            WHERE hours_ahead >= ? AND hours_ahead < ?
            AND temp_high_error IS NOT NULL
        ''', (hours_ahead_min, hours_ahead_max))

        result = cursor.fetchone()
        conn.close()

        if result and result[5] > 0:
            return {
                'avg_temp_high_error': result[0] or 0,
                'avg_temp_low_error': result[1] or 0,
                'avg_snowfall_error': result[2] or 0,
                'avg_ice_error': result[3] or 0,
                'avg_rainfall_error': result[4] or 0,
                'sample_count': result[5]
            }
        return None

    def update_learned_adjustments(self, adjustment_type: str, hours_ahead_min: int,
                                   hours_ahead_max: int, stats: Dict):
        """Update or insert learned adjustments."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO learned_adjustments (
                adjustment_type, hours_ahead_min, hours_ahead_max,
                avg_temp_high_bias, avg_temp_low_bias, avg_snowfall_bias,
                avg_ice_bias, avg_rainfall_bias, sample_count, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(adjustment_type, hours_ahead_min, hours_ahead_max)
            DO UPDATE SET
                avg_temp_high_bias = excluded.avg_temp_high_bias,
                avg_temp_low_bias = excluded.avg_temp_low_bias,
                avg_snowfall_bias = excluded.avg_snowfall_bias,
                avg_ice_bias = excluded.avg_ice_bias,
                avg_rainfall_bias = excluded.avg_rainfall_bias,
                sample_count = excluded.sample_count,
                last_updated = CURRENT_TIMESTAMP
        ''', (
            adjustment_type, hours_ahead_min, hours_ahead_max,
            stats['avg_temp_high_error'], stats['avg_temp_low_error'],
            stats['avg_snowfall_error'], stats['avg_ice_error'],
            stats.get('avg_rainfall_error', 0),
            stats['sample_count']
        ))

        conn.commit()
        conn.close()

    def get_learned_adjustment(self, hours_ahead: int) -> Optional[Dict]:
        """Get learned adjustment for given hours ahead."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT avg_temp_high_bias, avg_temp_low_bias, avg_snowfall_bias,
                   avg_ice_bias, avg_rainfall_bias, sample_count
            FROM learned_adjustments
            WHERE hours_ahead_min <= ? AND hours_ahead_max > ?
            AND sample_count >= 5
            ORDER BY last_updated DESC
            LIMIT 1
        ''', (hours_ahead, hours_ahead))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'temp_high_bias': result[0],
                'temp_low_bias': result[1],
                'snowfall_bias': result[2],
                'ice_bias': result[3],
                'rainfall_bias': result[4],
                'sample_count': result[5]
            }
        return None

    def log_email(self, subject: str, body: str, success: bool, error_message: str = None):
        """Log email sending attempt."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO email_log (subject, body, success, error_message)
            VALUES (?, ?, ?, ?)
        ''', (subject, body, success, error_message))

        conn.commit()
        conn.close()
