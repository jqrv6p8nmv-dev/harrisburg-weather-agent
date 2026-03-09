# Winter Weather Agent

An intelligent weather monitoring agent that tracks forecasts from the National Weather Service for Harrisburg International Airport (KMDT), learns from forecast accuracy over time, and sends email updates every 6 hours.

## Features

- Fetches weather forecasts for up to 2 days ahead from NWS API
- Tracks temperature (high/low), snowfall, and ice accumulation
- Stores historical forecasts and actual observations
- Compares forecasts to actual weather to track accuracy
- **Machine learning component** that learns forecast biases and adjusts future predictions
- Sends formatted email reports with forecasts and accuracy statistics
- Runs continuously on Digital Ocean droplet (or any server)
- Updates every 6 hours to match NWS forecast refresh cycle

## How the Learning Works

The agent builds a learning model over time:

1. **Stores every forecast** made for each day
2. **Collects actual observations** from NWS after the day passes
3. **Compares forecasts to reality** to calculate error rates
4. **Groups data by forecast lead time** (0-12h, 12-24h, 24-36h, 36-48h)
5. **Calculates average biases** for temperature, snow, and ice
6. **Applies corrections** to new forecasts based on learned patterns

Example: If NWS consistently forecasts temperatures 2°F too high for 24-36 hour forecasts, the agent will automatically subtract 2°F from those forecasts.

## Installation

### Prerequisites

- Python 3.8 or higher
- A Digital Ocean account (or any Linux server)
- A Gmail account (or other email service)

### Setup on Digital Ocean

1. **Create a droplet** (Basic plan, $6/month is plenty):
   - Ubuntu 22.04 LTS
   - Basic shared CPU
   - Any region

2. **SSH into your droplet**:
   ```bash
   ssh root@your-droplet-ip
   ```

3. **Install Python and dependencies**:
   ```bash
   apt update
   apt install -y python3 python3-pip git
   ```

4. **Clone or upload the agent code**:
   ```bash
   mkdir -p /opt/winter-weather-agent
   cd /opt/winter-weather-agent
   # Upload files here (see deployment section below)
   ```

5. **Install Python packages**:
   ```bash
   pip3 install -r requirements.txt
   ```

## Email Configuration

You have two options for email:

### Option 1: Gmail with App Password (Recommended)

This is the easiest option. Follow these steps:

1. **Enable 2-Factor Authentication** on your Google account:
   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Create an App Password**:
   - Visit https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "Winter Weather Agent"
   - Copy the 16-character password (no spaces)

3. **Configure the .env file**:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   EMAIL_FROM=your-email@gmail.com
   EMAIL_TO=recipient@example.com
   ```

### Option 2: SendGrid (Free tier available)

If Gmail doesn't work from your server:

1. Sign up for SendGrid: https://sendgrid.com/
2. Get an API key
3. Update .env:
   ```
   SMTP_SERVER=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USERNAME=apikey
   SMTP_PASSWORD=your-sendgrid-api-key
   EMAIL_FROM=verified-sender@yourdomain.com
   EMAIL_TO=recipient@example.com
   ```

### Option 3: Mailgun

1. Sign up for Mailgun: https://www.mailgun.com/
2. Get SMTP credentials
3. Update .env with Mailgun SMTP settings

## Configuration

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your settings**:
   ```bash
   nano .env
   ```

   Required settings:
   ```
   # Email - see "Email Configuration" section above
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   EMAIL_FROM=your-email@gmail.com
   EMAIL_TO=your-email@gmail.com

   # NWS Configuration
   NWS_STATION=KMDT
   NWS_USER_AGENT=(WinterWeatherAgent, your-email@example.com)

   # Database
   DB_PATH=/opt/winter-weather-agent/weather_data.db

   # Check every 6 hours
   CHECK_INTERVAL_HOURS=6
   ```

## Running the Agent

### Test Run (Single Execution)

Test the agent before setting it up as a service:

```bash
python3 weather_agent.py --once
```

This will:
- Fetch current forecasts
- Collect yesterday's observations
- Send one email
- Exit

### Run as a Service (Recommended)

Create a systemd service to run the agent automatically:

1. **Create service file**:
   ```bash
   nano /etc/systemd/system/winter-weather-agent.service
   ```

2. **Add this content**:
   ```ini
   [Unit]
   Description=Winter Weather Agent
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/winter-weather-agent
   ExecStart=/usr/bin/python3 /opt/winter-weather-agent/weather_agent.py
   Restart=always
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service**:
   ```bash
   systemctl daemon-reload
   systemctl enable winter-weather-agent
   systemctl start winter-weather-agent
   ```

4. **Check status**:
   ```bash
   systemctl status winter-weather-agent
   ```

5. **View logs**:
   ```bash
   journalctl -u winter-weather-agent -f
   ```

## What You'll Receive

Every 6 hours, you'll receive an email with:

1. **Weather Forecast** for the next 2 days including:
   - High/Low temperatures
   - Snowfall accumulation (if any)
   - Ice accumulation (if any)
   - Detailed forecast text
   - **Adjusted forecasts** based on learned accuracy patterns

2. **Forecast Accuracy Report** showing:
   - Historical error rates by time range
   - How accurate NWS forecasts have been
   - Number of forecasts analyzed
   - Separate stats for 0-12h, 12-24h, 24-36h, 36-48h predictions

3. **Winter Weather Alerts** in the subject line when snow/ice is expected

## Database

The agent stores all data in a SQLite database (`weather_data.db`) including:

- All forecasts made (with timestamps)
- Actual observations collected
- Forecast accuracy comparisons
- Learned adjustment factors
- Email send logs

You can query this database directly or backup regularly:

```bash
# Backup database
cp /opt/winter-weather-agent/weather_data.db ~/weather_backup_$(date +%Y%m%d).db

# View statistics
sqlite3 /opt/winter-weather-agent/weather_data.db "SELECT * FROM forecast_accuracy ORDER BY created_at DESC LIMIT 10;"
```

## Troubleshooting

### Email not sending

1. **Check email configuration**:
   ```bash
   cat .env | grep EMAIL
   ```

2. **Test Gmail app password**:
   - Make sure 2FA is enabled
   - Regenerate app password if needed
   - No spaces in the password

3. **Check logs**:
   ```bash
   journalctl -u winter-weather-agent -n 50
   ```

4. **Try SendGrid** as alternative (see Email Configuration section)

### No forecasts received

1. **Check NWS API access**:
   ```bash
   curl -A "(TestApp, test@example.com)" "https://api.weather.gov/stations/KMDT/observations/latest"
   ```

2. **Check service status**:
   ```bash
   systemctl status winter-weather-agent
   ```

3. **Restart service**:
   ```bash
   systemctl restart winter-weather-agent
   ```

### Database issues

```bash
# Check if database exists and is writable
ls -la /opt/winter-weather-agent/weather_data.db

# Reset database (WARNING: deletes all historical data)
rm /opt/winter-weather-agent/weather_data.db
systemctl restart winter-weather-agent
```

## Manual Operations

### Run a single forecast check:
```bash
cd /opt/winter-weather-agent
python3 weather_agent.py --once
```

### Force collect yesterday's observations:
```bash
python3 -c "from weather_agent import WinterWeatherAgent; agent = WinterWeatherAgent(); agent.collect_observations()"
```

### View accuracy report:
```bash
python3 -c "from weather_agent import WinterWeatherAgent; agent = WinterWeatherAgent(); print(agent.analyzer.get_accuracy_report())"
```

## Maintenance

- **Database grows over time** - consider archiving old data periodically
- **Monitor email sending** - check email_log table if issues arise
- **Update NWS user agent** - keep your contact info current in .env
- **Backup database** - schedule weekly backups of weather_data.db

## Stopping the Agent

```bash
systemctl stop winter-weather-agent
systemctl disable winter-weather-agent  # Prevent auto-start on boot
```

## Cost

Running on Digital Ocean:
- Basic Droplet: $6/month (plenty of resources)
- Email (Gmail): Free
- Total: ~$6/month

## Data Sources

- Weather data: National Weather Service API (api.weather.gov)
- Station: KMDT (Harrisburg International Airport)
- No API key required (NWS API is free and public)

## Support

For issues or questions:
1. Check the logs: `journalctl -u winter-weather-agent -f`
2. Test email configuration
3. Verify NWS API access
4. Check database permissions

## License

Free to use and modify.
