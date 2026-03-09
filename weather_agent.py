#!/usr/bin/env python3
"""
Harrisburg Weather Agent
Monitors weather forecasts for Harrisburg International Airport,
learns from forecast accuracy, and sends email updates.
"""

import time
import schedule
from datetime import datetime, timedelta
from database import WeatherDatabase
from nws_api import NWSWeatherAPI
from forecast_analyzer import ForecastAnalyzer
from email_notifier import EmailNotifier
import config

class HarrisburgWeatherAgent:
    """Main agent that coordinates weather monitoring, learning, and notifications."""

    def __init__(self):
        self.db = WeatherDatabase()
        self.nws = NWSWeatherAPI()
        self.analyzer = ForecastAnalyzer(self.db, self.nws)
        self.notifier = EmailNotifier(self.db)
        print("Harrisburg Weather Agent initialized")

    def fetch_and_store_forecast(self):
        """Fetch current forecasts and store them."""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching forecasts...")

        try:
            # Get daily forecast summaries
            forecasts = self.nws.get_daily_forecast_summary(days=config.FORECAST_DAYS)

            if not forecasts:
                print("No forecasts available")
                return []

            stored_forecasts = []

            for forecast in forecasts:
                # Calculate hours ahead
                target_date = datetime.fromisoformat(forecast['target_date'])
                hours_ahead = int((target_date - datetime.now()).total_seconds() / 3600)

                # Apply learned adjustments
                adjusted_forecast = self.analyzer.apply_learned_adjustments(
                    forecast, hours_ahead
                )

                # Store the forecast in database
                forecast_id = self.db.store_forecast(
                    target_date=forecast['target_date'],
                    forecast_data=adjusted_forecast
                )

                adjusted_forecast['forecast_id'] = forecast_id
                stored_forecasts.append(adjusted_forecast)

                print(f"  Stored forecast for {forecast['target_date']}")

            return stored_forecasts

        except Exception as e:
            error_msg = f"Error fetching forecasts: {e}"
            print(error_msg)
            self.notifier.send_error_email(error_msg)
            return []

    def collect_observations(self):
        """Collect observations for yesterday and analyze forecast accuracy."""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collecting observations...")

        try:
            self.analyzer.collect_and_analyze_yesterday()
        except Exception as e:
            error_msg = f"Error collecting observations: {e}"
            print(error_msg)
            # Don't email for this - might be normal if data isn't available yet

    def send_forecast_update(self):
        """Send email with current forecasts and accuracy report."""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sending forecast update...")

        try:
            # Fetch and store forecasts
            forecasts = self.fetch_and_store_forecast()

            if not forecasts:
                print("No forecasts to send")
                return

            # Get accuracy report
            accuracy_report = self.analyzer.get_accuracy_report()

            # Send email
            success = self.notifier.send_forecast_email(forecasts, accuracy_report)

            if success:
                print("Forecast email sent successfully")
            else:
                print("Failed to send forecast email")

        except Exception as e:
            error_msg = f"Error sending forecast update: {e}"
            print(error_msg)
            self.notifier.send_error_email(error_msg)

    def run_scheduled_tasks(self):
        """Run all scheduled tasks."""
        self.send_forecast_update()
        self.collect_observations()

    def run_once(self):
        """Run the agent once and exit."""
        print("Running Harrisburg Weather Agent (single execution)...")
        self.run_scheduled_tasks()
        print("Done!")

    def run_daemon(self):
        """Run the agent as a daemon with scheduled checks."""
        print(f"Starting Harrisburg Weather Agent daemon...")
        print(f"Station: {config.NWS_STATION} (Harrisburg International Airport)")
        print(f"Schedule: 12:15, 22:15 UTC (~7-8 AM and 5-6 PM ET)")
        print(f"Email notifications to: {config.EMAIL_TO}")
        print()

        # Schedule twice-daily runs (morning and evening ET)
        schedule.every().day.at("12:15").do(self.run_scheduled_tasks)
        schedule.every().day.at("22:15").do(self.run_scheduled_tasks)

        # Run immediately on startup
        self.run_scheduled_tasks()

        # Keep running
        print("Agent running. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\nStopping Harrisburg Weather Agent...")

def main():
    """Main entry point."""
    import sys

    agent = HarrisburgWeatherAgent()

    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once and exit
        agent.run_once()
    else:
        # Run as daemon
        agent.run_daemon()

if __name__ == '__main__':
    main()
