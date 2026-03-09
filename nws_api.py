import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import config
import time

class NWSWeatherAPI:
    """Interface to National Weather Service API for Harrisburg International Airport."""

    def __init__(self):
        self.station = config.NWS_STATION
        self.base_url = config.NWS_API_BASE
        self.headers = {
            'User-Agent': config.NWS_USER_AGENT,
            'Accept': 'application/geo+json'
        }
        self.station_info = None

    def _make_request(self, url: str, retries: int = 3) -> Optional[Dict]:
        """Make a request to NWS API with retry logic."""
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    print(f"Failed to fetch {url} after {retries} attempts: {e}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def get_station_info(self) -> Optional[Dict]:
        """Get station metadata."""
        if self.station_info:
            return self.station_info

        url = f"{self.base_url}/stations/{self.station}"
        data = self._make_request(url)

        if data:
            self.station_info = data.get('properties', {})
        return self.station_info

    def get_latest_observation(self) -> Optional[Dict]:
        """Get the latest observation from the station."""
        url = f"{self.base_url}/stations/{self.station}/observations/latest"
        data = self._make_request(url)

        if not data or 'properties' not in data:
            return None

        props = data['properties']

        # Parse observation data
        observation = {
            'timestamp': props.get('timestamp'),
            'temperature': self._celsius_to_fahrenheit(props.get('temperature', {}).get('value')),
            'dewpoint': self._celsius_to_fahrenheit(props.get('dewpoint', {}).get('value')),
            'wind_speed': self._ms_to_mph(props.get('windSpeed', {}).get('value')),
            'wind_direction': props.get('windDirection', {}).get('value'),
            'barometric_pressure': props.get('barometricPressure', {}).get('value'),
            'visibility': props.get('visibility', {}).get('value'),
            'weather': props.get('textDescription'),
            'raw': props
        }

        return observation

    def get_observations_for_date(self, target_date: str) -> List[Dict]:
        """Get all observations for a specific date."""
        url = f"{self.base_url}/stations/{self.station}/observations"
        params = {
            'start': f"{target_date}T00:00:00Z",
            'end': f"{target_date}T23:59:59Z"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Failed to fetch observations for {target_date}: {e}")
            return []

        observations = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            obs = {
                'timestamp': props.get('timestamp'),
                'temperature': self._celsius_to_fahrenheit(props.get('temperature', {}).get('value')),
                'raw': props
            }
            observations.append(obs)

        return observations

    def calculate_daily_stats(self, target_date: str) -> Optional[Dict]:
        """Calculate daily high/low from observations."""
        observations = self.get_observations_for_date(target_date)

        if not observations:
            return None

        temps = [o['temperature'] for o in observations if o['temperature'] is not None]

        if not temps:
            return None

        return {
            'temperature_high': max(temps),
            'temperature_low': min(temps),
            'observation_count': len(observations),
            'raw': observations
        }

    def get_gridpoint_forecast(self) -> Optional[Dict]:
        """Get gridpoint forecast for the station location."""
        # First get station info to get coordinates
        station_info = self.get_station_info()
        if not station_info:
            return None

        # Get coordinates from station
        geometry = station_info.get('geometry', {})
        if 'coordinates' in geometry:
            lon, lat = geometry['coordinates']
        else:
            # Harrisburg International Airport coordinates as fallback
            lat, lon = 40.1935, -76.7631

        # Get gridpoint info
        points_url = f"{self.base_url}/points/{lat},{lon}"
        points_data = self._make_request(points_url)

        if not points_data or 'properties' not in points_data:
            return None

        forecast_url = points_data['properties'].get('forecast')
        if not forecast_url:
            return None

        return self._make_request(forecast_url)

    def get_forecast(self, days: int = 2) -> List[Dict]:
        """Get forecast for the next N days."""
        forecast_data = self.get_gridpoint_forecast()

        if not forecast_data or 'properties' not in forecast_data:
            return []

        periods = forecast_data['properties'].get('periods', [])
        forecasts = []

        # Process periods to extract daily forecasts
        today = datetime.now().date()
        forecast_dates = set()

        for period in periods:
            # Parse the start time
            start_time = datetime.fromisoformat(period['startTime'].replace('Z', '+00:00'))
            period_date = start_time.date()

            # Only include next N days
            days_ahead = (period_date - today).days
            if days_ahead < 0 or days_ahead > days:
                continue

            # Create a unique key for this date
            date_key = period_date.isoformat()

            if date_key not in forecast_dates:
                forecast_dates.add(date_key)

                forecast = {
                    'target_date': date_key,
                    'days_ahead': days_ahead,
                    'name': period.get('name'),
                    'temperature': period.get('temperature'),
                    'temperature_unit': period.get('temperatureUnit'),
                    'is_daytime': period.get('isDaytime'),
                    'short_forecast': period.get('shortForecast'),
                    'detailed_forecast': period.get('detailedForecast'),
                    'wind_speed': period.get('windSpeed'),
                    'wind_direction': period.get('windDirection'),
                    'icon': period.get('icon'),
                    'raw': period
                }

                # Extract precipitation info from forecast text
                forecast = self._extract_precipitation(forecast)
                forecasts.append(forecast)

        return forecasts[:days * 2]  # Return up to 2 periods per day

    def _extract_precipitation(self, forecast: Dict) -> Dict:
        """Extract precipitation information from forecast text."""
        import re
        detailed = (forecast.get('detailed_forecast') or '').lower()
        short = (forecast.get('short_forecast') or '').lower()
        combined = f"{detailed} {short}"

        # Look for snow mentions
        snowfall = None
        if 'snow' in combined:
            snow_pattern = r'(\d+(?:\.\d+)?)\s*(?:to\s*(\d+(?:\.\d+)?))?\s*inch(?:es)?.*?(?:of\s+)?snow'
            match = re.search(snow_pattern, combined)
            if match:
                low = float(match.group(1))
                high = float(match.group(2)) if match.group(2) else low
                snowfall = (low + high) / 2

        # Look for ice/freezing rain
        ice = None
        if 'ice' in combined or 'freezing rain' in combined or 'sleet' in combined:
            ice_pattern = r'(\d+(?:\.\d+)?)\s*(?:to\s*(\d+(?:\.\d+)?))?\s*inch(?:es)?.*?(?:of\s+)?(?:ice|sleet)'
            match = re.search(ice_pattern, combined)
            if match:
                low = float(match.group(1))
                high = float(match.group(2)) if match.group(2) else low
                ice = (low + high) / 2

        # Look for heavy rain
        rainfall = None
        if 'rain' in combined:
            rain_pattern = r'(\d+(?:\.\d+)?)\s*(?:to\s*(\d+(?:\.\d+)?))?\s*inch(?:es)?.*?(?:of\s+)?rain'
            match = re.search(rain_pattern, combined)
            if match:
                low = float(match.group(1))
                high = float(match.group(2)) if match.group(2) else low
                rainfall = (low + high) / 2

        # Look for thunderstorms
        thunderstorm_risk = any(kw in combined for kw in (
            'thunderstorm', 'severe thunderstorm', 'lightning'
        ))

        # Look for flooding risk
        flooding_risk = any(kw in combined for kw in (
            'flood', 'flash flood', 'excessive rainfall'
        ))

        forecast['snowfall_inches'] = snowfall
        forecast['ice_accumulation_inches'] = ice
        forecast['rainfall_inches'] = rainfall
        forecast['thunderstorm_risk'] = thunderstorm_risk
        forecast['flooding_risk'] = flooding_risk
        forecast['has_winter_weather'] = snowfall is not None or ice is not None

        return forecast

    def get_daily_forecast_summary(self, days: int = 2) -> List[Dict]:
        """Get daily forecast summary combining day/night periods."""
        forecasts = self.get_forecast(days)

        daily_summaries = {}

        for forecast in forecasts:
            date = forecast['target_date']

            if date not in daily_summaries:
                daily_summaries[date] = {
                    'target_date': date,
                    'days_ahead': forecast['days_ahead'],
                    'temperature_high': None,
                    'temperature_low': None,
                    'snowfall_inches': forecast.get('snowfall_inches'),
                    'ice_accumulation_inches': forecast.get('ice_accumulation_inches'),
                    'rainfall_inches': forecast.get('rainfall_inches'),
                    'thunderstorm_risk': forecast.get('thunderstorm_risk', False),
                    'flooding_risk': forecast.get('flooding_risk', False),
                    'forecast_text': [],
                    'raw': []
                }

            summary = daily_summaries[date]

            # Update high/low temps
            temp = forecast.get('temperature')
            if temp:
                if forecast.get('is_daytime'):
                    summary['temperature_high'] = temp
                else:
                    summary['temperature_low'] = temp

            # Accumulate snow/ice/rain if present
            if forecast.get('snowfall_inches'):
                current = summary['snowfall_inches'] or 0
                summary['snowfall_inches'] = max(current, forecast['snowfall_inches'])

            if forecast.get('ice_accumulation_inches'):
                current = summary['ice_accumulation_inches'] or 0
                summary['ice_accumulation_inches'] = max(current, forecast['ice_accumulation_inches'])

            if forecast.get('rainfall_inches'):
                current = summary['rainfall_inches'] or 0
                summary['rainfall_inches'] = max(current, forecast['rainfall_inches'])

            # OR the boolean flags across periods
            if forecast.get('thunderstorm_risk'):
                summary['thunderstorm_risk'] = True

            if forecast.get('flooding_risk'):
                summary['flooding_risk'] = True

            summary['forecast_text'].append(forecast.get('detailed_forecast', ''))
            summary['raw'].append(forecast.get('raw'))

        return list(daily_summaries.values())

    @staticmethod
    def _celsius_to_fahrenheit(celsius: Optional[float]) -> Optional[float]:
        """Convert Celsius to Fahrenheit."""
        if celsius is None:
            return None
        return (celsius * 9/5) + 32

    @staticmethod
    def _ms_to_mph(meters_per_second: Optional[float]) -> Optional[float]:
        """Convert meters per second to miles per hour."""
        if meters_per_second is None:
            return None
        return meters_per_second * 2.237
