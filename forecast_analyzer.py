from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import WeatherDatabase
from nws_api import NWSWeatherAPI

class ForecastAnalyzer:
    """Compares forecasts to actual observations and tracks accuracy."""

    def __init__(self, db: WeatherDatabase, nws: NWSWeatherAPI):
        self.db = db
        self.nws = nws

    def compare_forecast_to_observation(self, forecast_id: int, forecast_data: Dict,
                                       observation_data: Dict, hours_ahead: int) -> Dict:
        """Compare a single forecast to actual observation and calculate errors."""
        errors = {}

        # Temperature high error
        if forecast_data.get('temperature_high') and observation_data.get('temperature_high'):
            errors['temp_high_error'] = (
                forecast_data['temperature_high'] - observation_data['temperature_high']
            )

        # Temperature low error
        if forecast_data.get('temperature_low') and observation_data.get('temperature_low'):
            errors['temp_low_error'] = (
                forecast_data['temperature_low'] - observation_data['temperature_low']
            )

        # Snowfall error
        forecast_snow = forecast_data.get('snowfall_inches') or 0
        actual_snow = observation_data.get('snowfall_inches') or 0
        errors['snowfall_error'] = forecast_snow - actual_snow

        # Ice accumulation error
        forecast_ice = forecast_data.get('ice_accumulation_inches') or 0
        actual_ice = observation_data.get('ice_accumulation_inches') or 0
        errors['ice_error'] = forecast_ice - actual_ice

        # Rainfall error
        forecast_rain = forecast_data.get('rainfall_inches') or 0
        actual_rain = observation_data.get('rainfall_inches') or 0
        errors['rainfall_error'] = forecast_rain - actual_rain

        return errors

    def analyze_past_forecasts(self, target_date: str):
        """Analyze all forecasts made for a specific date against actual observation."""
        # Get observation for the date
        observation = self.db.get_observation(target_date)
        if not observation:
            print(f"No observation found for {target_date}")
            return

        # Get all forecasts made for this date
        forecasts = self.db.get_forecasts_for_date(target_date)
        if not forecasts:
            print(f"No forecasts found for {target_date}")
            return

        target_dt = datetime.fromisoformat(target_date)

        # Analyze each forecast
        for forecast in forecasts:
            forecast_dt = datetime.fromisoformat(forecast['forecast_timestamp'])
            hours_ahead = int((target_dt - forecast_dt).total_seconds() / 3600)

            if hours_ahead < 0:
                continue  # Skip forecasts made after the target date

            errors = self.compare_forecast_to_observation(
                forecast['id'], forecast, observation, hours_ahead
            )

            # Store accuracy record
            self.db.store_accuracy_record(
                forecast['id'],
                observation['id'],
                target_date,
                hours_ahead,
                errors
            )

        print(f"Analyzed {len(forecasts)} forecasts for {target_date}")

    def update_learned_models(self):
        """Update the learned adjustment models based on historical accuracy."""
        # Define time buckets for learning
        time_buckets = [
            (0, 12, '0-12h'),      # Very short term
            (12, 24, '12-24h'),    # Short term
            (24, 36, '24-36h'),    # Medium term
            (36, 48, '36-48h'),    # Longer term
        ]

        for hours_min, hours_max, label in time_buckets:
            stats = self.db.get_accuracy_stats(hours_min, hours_max)

            if stats and stats['sample_count'] >= 5:  # Need at least 5 samples
                self.db.update_learned_adjustments(
                    adjustment_type=label,
                    hours_ahead_min=hours_min,
                    hours_ahead_max=hours_max,
                    stats=stats
                )
                print(f"Updated adjustments for {label}: {stats['sample_count']} samples")

    def apply_learned_adjustments(self, forecast: Dict, hours_ahead: int) -> Dict:
        """Apply learned adjustments to a forecast."""
        adjustment = self.db.get_learned_adjustment(hours_ahead)

        if not adjustment or adjustment['sample_count'] < 5:
            # Not enough data, return forecast as-is
            forecast['adjusted'] = False
            return forecast

        # Apply adjustments (subtract the bias/error)
        adjusted_forecast = forecast.copy()
        adjusted_forecast['adjusted'] = True
        adjusted_forecast['adjustment_sample_count'] = adjustment['sample_count']

        if forecast.get('temperature_high') is not None:
            adjusted_forecast['temperature_high_raw'] = forecast['temperature_high']
            adjusted_forecast['temperature_high'] = (
                forecast['temperature_high'] - adjustment['temp_high_bias']
            )

        if forecast.get('temperature_low') is not None:
            adjusted_forecast['temperature_low_raw'] = forecast['temperature_low']
            adjusted_forecast['temperature_low'] = (
                forecast['temperature_low'] - adjustment['temp_low_bias']
            )

        if forecast.get('snowfall_inches') is not None:
            adjusted_forecast['snowfall_inches_raw'] = forecast['snowfall_inches']
            adjusted_forecast['snowfall_inches'] = max(
                0, forecast['snowfall_inches'] - adjustment['snowfall_bias']
            )

        if forecast.get('ice_accumulation_inches') is not None:
            adjusted_forecast['ice_accumulation_inches_raw'] = forecast['ice_accumulation_inches']
            adjusted_forecast['ice_accumulation_inches'] = max(
                0, forecast['ice_accumulation_inches'] - adjustment['ice_bias']
            )

        if forecast.get('rainfall_inches') is not None and adjustment.get('rainfall_bias'):
            adjusted_forecast['rainfall_inches_raw'] = forecast['rainfall_inches']
            adjusted_forecast['rainfall_inches'] = max(
                0, forecast['rainfall_inches'] - adjustment['rainfall_bias']
            )

        return adjusted_forecast

    def collect_and_analyze_yesterday(self):
        """Collect observations for yesterday and analyze forecasts."""
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

        # Try to get daily stats from NWS observations
        daily_stats = self.nws.calculate_daily_stats(yesterday)

        if daily_stats:
            # Store observation
            observation_data = {
                'temperature_high': daily_stats['temperature_high'],
                'temperature_low': daily_stats['temperature_low'],
                'snowfall_inches': None,  # NWS API doesn't provide this easily
                'ice_accumulation_inches': None,
                'raw': daily_stats
            }
            self.db.store_observation(yesterday, observation_data)
            print(f"Stored observation for {yesterday}")

            # Analyze past forecasts for this date
            self.analyze_past_forecasts(yesterday)

            # Update learned models
            self.update_learned_models()
        else:
            print(f"Could not collect observations for {yesterday}")

    def get_accuracy_report(self) -> Dict:
        """Generate a report on forecast accuracy."""
        report = {
            'time_periods': []
        }

        time_buckets = [
            (0, 12, '0-12 hours ahead'),
            (12, 24, '12-24 hours ahead'),
            (24, 36, '24-36 hours ahead'),
            (36, 48, '36-48 hours ahead'),
        ]

        for hours_min, hours_max, label in time_buckets:
            stats = self.db.get_accuracy_stats(hours_min, hours_max)
            if stats:
                report['time_periods'].append({
                    'label': label,
                    'hours_min': hours_min,
                    'hours_max': hours_max,
                    'avg_temp_high_error': round(stats['avg_temp_high_error'], 2),
                    'avg_temp_low_error': round(stats['avg_temp_low_error'], 2),
                    'avg_snowfall_error': round(stats['avg_snowfall_error'], 2),
                    'avg_ice_error': round(stats['avg_ice_error'], 2),
                    'avg_rainfall_error': round(stats['avg_rainfall_error'], 2) if stats.get('avg_rainfall_error') is not None else None,
                    'sample_count': stats['sample_count']
                })

        return report
