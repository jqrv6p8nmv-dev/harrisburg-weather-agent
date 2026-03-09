import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import config
from database import WeatherDatabase
import requests

class EmailNotifier:
    """Sends email notifications with weather forecasts and analysis."""

    def __init__(self, db: WeatherDatabase):
        self.db = db
        self.use_brevo_api = hasattr(config, 'BREVO_API_KEY') and config.BREVO_API_KEY
        self.use_mailgun = hasattr(config, 'MAILGUN_API_KEY') and config.MAILGUN_API_KEY and not self.use_brevo_api

        # EMAIL_TO may be a list (comma-separated) or a single string
        raw_to = config.EMAIL_TO
        if isinstance(raw_to, list):
            self.to_emails = [e.strip() for e in raw_to if e.strip()]
        else:
            self.to_emails = [e.strip() for e in (raw_to or '').split(',') if e.strip()]

        if self.use_brevo_api:
            self.brevo_api_key = config.BREVO_API_KEY
            self.from_email = config.EMAIL_FROM
        elif self.use_mailgun:
            self.mailgun_api_key = config.MAILGUN_API_KEY
            self.mailgun_domain = config.MAILGUN_DOMAIN
            self.from_email = config.EMAIL_FROM
        else:
            self.smtp_server = config.SMTP_SERVER
            self.smtp_port = config.SMTP_PORT
            self.username = config.SMTP_USERNAME
            self.password = config.SMTP_PASSWORD
            self.from_email = config.EMAIL_FROM

    def send_email(self, subject: str, body: str, html_body: str = None) -> bool:
        """Send an email notification."""
        if self.use_brevo_api:
            return self._send_via_brevo_api(subject, body, html_body)
        elif self.use_mailgun:
            return self._send_via_mailgun(subject, body, html_body)
        else:
            return self._send_via_smtp(subject, body, html_body)

    def _send_via_brevo_api(self, subject: str, body: str, html_body: str = None) -> bool:
        """Send email using Brevo (Sendinblue) HTTP API."""
        if not all([self.brevo_api_key, self.from_email, self.to_emails]):
            error_msg = "Brevo API configuration incomplete"
            print(error_msg)
            self.db.log_email(subject, body, False, error_msg)
            return False

        try:
            url = "https://api.brevo.com/v3/smtp/email"

            headers = {
                "api-key": self.brevo_api_key,
                "Content-Type": "application/json"
            }

            # Extract email from "Name <email>" format if present
            from_email_clean = self.from_email.split('<')[-1].strip('>').strip()

            data = {
                "sender": {"email": from_email_clean, "name": "Harrisburg Weather Agent"},
                "to": [{"email": addr} for addr in self.to_emails],
                "subject": subject,
                "textContent": body
            }

            if html_body:
                data["htmlContent"] = html_body

            print(f"Sending to Brevo API with sender: {from_email_clean}")

            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )

            print(f"Brevo response status: {response.status_code}")
            if response.status_code != 201:
                print(f"Brevo response: {response.text}")

            response.raise_for_status()

            self.db.log_email(subject, body, True, None)
            print(f"Email sent via Brevo API: {subject}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"Failed to send email via Brevo API: {error_msg}")
            self.db.log_email(subject, body, False, error_msg)
            return False

    def _send_via_mailgun(self, subject: str, body: str, html_body: str = None) -> bool:
        """Send email using Mailgun HTTP API."""
        if not all([self.mailgun_api_key, self.mailgun_domain, self.from_email, self.to_emails]):
            error_msg = "Mailgun configuration incomplete"
            print(error_msg)
            self.db.log_email(subject, body, False, error_msg)
            return False

        try:
            url = f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages"

            data = {
                "from": self.from_email,
                "to": ", ".join(self.to_emails),
                "subject": subject,
                "text": body
            }

            if html_body:
                data["html"] = html_body

            response = requests.post(
                url,
                auth=("api", self.mailgun_api_key),
                data=data,
                timeout=30
            )

            response.raise_for_status()

            self.db.log_email(subject, body, True, None)
            print(f"Email sent via Mailgun: {subject}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"Failed to send email via Mailgun: {error_msg}")
            self.db.log_email(subject, body, False, error_msg)
            return False

    def _send_via_smtp(self, subject: str, body: str, html_body: str = None) -> bool:
        """Send email using SMTP (legacy method)."""
        if not all([self.username, self.password, self.from_email, self.to_emails]):
            error_msg = "Email configuration incomplete"
            print(error_msg)
            self.db.log_email(subject, body, False, error_msg)
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)

            # Attach plain text version
            msg.attach(MIMEText(body, 'plain'))

            # Attach HTML version if provided
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_emails, msg.as_string())

            self.db.log_email(subject, body, True, None)
            print(f"Email sent: {subject}")
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"Failed to send email: {error_msg}")
            self.db.log_email(subject, body, False, error_msg)
            return False

    def format_forecast_email(self, forecasts: List[Dict], accuracy_report: Dict = None) -> tuple:
        """Format forecast data into email body (plain and HTML)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")

        # Plain text version
        plain_body = f"""Harrisburg Area Forecast - Harrisburg International Airport
Generated: {timestamp}

"""

        for forecast in forecasts:
            plain_body += self._format_forecast_plain(forecast)

        # Add accuracy report if available
        if accuracy_report and accuracy_report.get('time_periods'):
            plain_body += "\n" + "="*60 + "\n"
            plain_body += "FORECAST ACCURACY TRACKING\n"
            plain_body += "="*60 + "\n\n"

            for period in accuracy_report['time_periods']:
                plain_body += f"\n{period['label']} ({period['sample_count']} forecasts analyzed):\n"
                plain_body += f"  Temperature High Error: {period['avg_temp_high_error']:+.1f}°F\n"
                plain_body += f"  Temperature Low Error:  {period['avg_temp_low_error']:+.1f}°F\n"
                plain_body += f"  Snowfall Error:         {period['avg_snowfall_error']:+.2f} inches\n"
                plain_body += f"  Ice Error:              {period['avg_ice_error']:+.2f} inches\n"
                if period.get('avg_rainfall_error') is not None:
                    plain_body += f"  Rainfall Error:         {period['avg_rainfall_error']:+.2f} inches\n"

            plain_body += "\n(Positive error = forecast was too high, Negative = too low)\n"

        # HTML version
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                .forecast-card {{
                    background: #f8f9fa;
                    border-left: 4px solid #3498db;
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 5px;
                }}
                .winter-alert {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 10px;
                    margin: 10px 0;
                }}
                .adjusted {{ color: #27ae60; font-weight: bold; }}
                .raw {{ color: #7f8c8d; text-decoration: line-through; }}
                .stat-table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
                .stat-table th {{ background: #34495e; color: white; padding: 10px; text-align: left; }}
                .stat-table td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                .stat-table tr:hover {{ background: #f5f5f5; }}
                .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>🌤️ Harrisburg Area Forecast</h1>
            <p class="timestamp">Harrisburg International Airport (KMDT)<br>Generated: {timestamp}</p>
        """

        for forecast in forecasts:
            html_body += self._format_forecast_html(forecast)

        # Add accuracy report
        if accuracy_report and accuracy_report.get('time_periods'):
            html_body += """
            <h2>📊 Forecast Accuracy Tracking</h2>
            <table class="stat-table">
                <tr>
                    <th>Time Range</th>
                    <th>Temp High Error</th>
                    <th>Temp Low Error</th>
                    <th>Snow Error</th>
                    <th>Ice Error</th>
                    <th>Rain Error</th>
                    <th>Samples</th>
                </tr>
            """

            for period in accuracy_report['time_periods']:
                rain_error = period.get('avg_rainfall_error')
                rain_cell = f"{rain_error:+.2f}\"" if rain_error is not None else "—"
                html_body += f"""
                <tr>
                    <td>{period['label']}</td>
                    <td>{period['avg_temp_high_error']:+.1f}°F</td>
                    <td>{period['avg_temp_low_error']:+.1f}°F</td>
                    <td>{period['avg_snowfall_error']:+.2f}"</td>
                    <td>{period['avg_ice_error']:+.2f}"</td>
                    <td>{rain_cell}</td>
                    <td>{period['sample_count']}</td>
                </tr>
                """

            html_body += """
            </table>
            <p style="font-size: 0.9em; color: #7f8c8d; margin-top: 10px;">
                Positive error = forecast too high | Negative = forecast too low
            </p>
            """

        html_body += """
        </body>
        </html>
        """

        return plain_body, html_body

    def _format_forecast_plain(self, forecast: Dict) -> str:
        """Format a single forecast as plain text."""
        text = "="*60 + "\n"
        text += f"Date: {forecast['target_date']} ({forecast.get('days_ahead', 0)} days ahead)\n"
        text += "="*60 + "\n\n"

        # Temperature
        if forecast.get('temperature_high') or forecast.get('temperature_low'):
            text += "TEMPERATURE:\n"
            if forecast.get('temperature_high'):
                high = forecast['temperature_high']
                if forecast.get('adjusted') and forecast.get('temperature_high_raw'):
                    text += f"  High: {high:.0f}°F (adjusted from {forecast['temperature_high_raw']:.0f}°F)\n"
                else:
                    text += f"  High: {high:.0f}°F\n"

            if forecast.get('temperature_low'):
                low = forecast['temperature_low']
                if forecast.get('adjusted') and forecast.get('temperature_low_raw'):
                    text += f"  Low:  {low:.0f}°F (adjusted from {forecast['temperature_low_raw']:.0f}°F)\n"
                else:
                    text += f"  Low:  {low:.0f}°F\n"
            text += "\n"

        # Precipitation
        has_winter = forecast.get('snowfall_inches') or forecast.get('ice_accumulation_inches')
        has_rain = (forecast.get('rainfall_inches') or 0) > 0
        has_thunderstorm = forecast.get('thunderstorm_risk')
        has_flooding = forecast.get('flooding_risk')

        if has_thunderstorm or has_flooding:
            text += "*** SEVERE WEATHER EXPECTED ***\n"
        if has_winter:
            text += "*** WINTER WEATHER EXPECTED ***\n"

        if has_winter or has_rain or has_thunderstorm or has_flooding:
            if forecast.get('snowfall_inches'):
                snow = forecast['snowfall_inches']
                if forecast.get('adjusted') and forecast.get('snowfall_inches_raw'):
                    text += f"  Snow: {snow:.1f} inches (adjusted from {forecast['snowfall_inches_raw']:.1f}\")\n"
                else:
                    text += f"  Snow: {snow:.1f} inches\n"

            if forecast.get('ice_accumulation_inches'):
                ice = forecast['ice_accumulation_inches']
                if forecast.get('adjusted') and forecast.get('ice_accumulation_inches_raw'):
                    text += f"  Ice:  {ice:.2f} inches (adjusted from {forecast['ice_accumulation_inches_raw']:.2f}\")\n"
                else:
                    text += f"  Ice:  {ice:.2f} inches\n"

            if has_rain:
                rain = forecast['rainfall_inches']
                if forecast.get('adjusted') and forecast.get('rainfall_inches_raw'):
                    text += f"  Rain: {rain:.2f} inches (adjusted from {forecast['rainfall_inches_raw']:.2f}\")\n"
                else:
                    text += f"  Rain: {rain:.2f} inches\n"

            if has_thunderstorm:
                text += "  Thunderstorms possible\n"
            if has_flooding:
                text += "  Flooding risk\n"
            text += "\n"

        # Forecast details
        if forecast.get('forecast_text'):
            text += "FORECAST:\n"
            for detail in forecast['forecast_text']:
                if detail:
                    text += f"  {detail}\n"
            text += "\n"

        if forecast.get('adjusted'):
            text += f"(Forecast adjusted based on {forecast.get('adjustment_sample_count', 0)} historical comparisons)\n\n"

        return text

    def _format_forecast_html(self, forecast: Dict) -> str:
        """Format a single forecast as HTML."""
        html = f"""
        <div class="forecast-card">
            <h2>{forecast['target_date']} ({forecast.get('days_ahead', 0)} days ahead)</h2>
        """

        # Temperature
        if forecast.get('temperature_high') or forecast.get('temperature_low'):
            html += "<p><strong>Temperature:</strong><br>"
            if forecast.get('temperature_high'):
                if forecast.get('adjusted') and forecast.get('temperature_high_raw'):
                    html += f"High: <span class='adjusted'>{forecast['temperature_high']:.0f}°F</span> "
                    html += f"<span class='raw'>({forecast['temperature_high_raw']:.0f}°F)</span><br>"
                else:
                    html += f"High: {forecast['temperature_high']:.0f}°F<br>"

            if forecast.get('temperature_low'):
                if forecast.get('adjusted') and forecast.get('temperature_low_raw'):
                    html += f"Low: <span class='adjusted'>{forecast['temperature_low']:.0f}°F</span> "
                    html += f"<span class='raw'>({forecast['temperature_low_raw']:.0f}°F)</span><br>"
                else:
                    html += f"Low: {forecast['temperature_low']:.0f}°F<br>"
            html += "</p>"

        # Precipitation alerts
        has_winter = forecast.get('snowfall_inches') or forecast.get('ice_accumulation_inches')
        has_rain = (forecast.get('rainfall_inches') or 0) > 0
        has_thunderstorm = forecast.get('thunderstorm_risk')
        has_flooding = forecast.get('flooding_risk')

        if has_thunderstorm or has_flooding:
            html += "<div class='winter-alert'><strong>⛈️ SEVERE WEATHER EXPECTED</strong><br>"
            if has_thunderstorm:
                html += "⚡ Thunderstorms possible<br>"
            if has_flooding:
                html += "🌊 Flooding risk<br>"
            html += "</div>"

        if has_winter:
            html += "<div class='winter-alert'><strong>❄️ WINTER WEATHER EXPECTED</strong><br>"

            if forecast.get('snowfall_inches'):
                if forecast.get('adjusted') and forecast.get('snowfall_inches_raw'):
                    html += f"❄️ Snow: <span class='adjusted'>{forecast['snowfall_inches']:.1f}\"</span> "
                    html += f"<span class='raw'>({forecast['snowfall_inches_raw']:.1f}\")</span><br>"
                else:
                    html += f"❄️ Snow: {forecast['snowfall_inches']:.1f} inches<br>"

            if forecast.get('ice_accumulation_inches'):
                if forecast.get('adjusted') and forecast.get('ice_accumulation_inches_raw'):
                    html += f"🧊 Ice: <span class='adjusted'>{forecast['ice_accumulation_inches']:.2f}\"</span> "
                    html += f"<span class='raw'>({forecast['ice_accumulation_inches_raw']:.2f}\")</span><br>"
                else:
                    html += f"🧊 Ice: {forecast['ice_accumulation_inches']:.2f} inches<br>"
            html += "</div>"

        if has_rain:
            html += "<div class='winter-alert'><strong>🌧️ RAIN IN FORECAST</strong><br>"
            if forecast.get('adjusted') and forecast.get('rainfall_inches_raw'):
                html += f"🌧️ Rain: <span class='adjusted'>{forecast['rainfall_inches']:.2f}\"</span> "
                html += f"<span class='raw'>({forecast['rainfall_inches_raw']:.2f}\")</span><br>"
            else:
                html += f"🌧️ Rain: {forecast['rainfall_inches']:.2f} inches<br>"
            html += "</div>"

        # Forecast text
        if forecast.get('forecast_text'):
            html += "<p><strong>Forecast:</strong><br>"
            for detail in forecast['forecast_text']:
                if detail:
                    html += f"{detail}<br>"
            html += "</p>"

        if forecast.get('adjusted'):
            html += f"<p style='font-size: 0.9em; color: #27ae60;'><em>Forecast adjusted based on {forecast.get('adjustment_sample_count', 0)} historical comparisons</em></p>"

        html += "</div>"
        return html

    def send_forecast_email(self, forecasts: List[Dict], accuracy_report: Dict = None) -> bool:
        """Send forecast email."""
        base_subject = f"Harrisburg Area Forecast - {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"

        has_severe_weather = any(
            f.get('thunderstorm_risk') or f.get('flooding_risk')
            for f in forecasts
        )
        has_winter_weather = any(
            f.get('snowfall_inches') or f.get('ice_accumulation_inches')
            for f in forecasts
        )
        has_heavy_rain = any(
            (f.get('rainfall_inches') or 0) > 0.5
            for f in forecasts
        )

        if has_severe_weather:
            subject = "⛈️ " + base_subject + " - SEVERE WEATHER EXPECTED"
        elif has_winter_weather:
            subject = "❄️ " + base_subject + " - WINTER WEATHER EXPECTED"
        elif has_heavy_rain:
            subject = "🌧️ " + base_subject + " - HEAVY RAIN EXPECTED"
        else:
            subject = base_subject

        plain_body, html_body = self.format_forecast_email(forecasts, accuracy_report)
        return self.send_email(subject, plain_body, html_body)

    def send_error_email(self, error_message: str) -> bool:
        """Send error notification email."""
        subject = "Harrisburg Weather Agent - Error"
        body = f"""
An error occurred in the Harrisburg Weather Agent:

{error_message}

Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

Please check the agent logs for more details.
"""
        return self.send_email(subject, body)
