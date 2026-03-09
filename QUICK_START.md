# Quick Start Guide

Get your Winter Weather Agent running on Digital Ocean in 10 minutes.

## Step 1: Create Gmail App Password (5 minutes)

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** if not already enabled
3. Go to https://myaccount.google.com/apppasswords
4. Select **Mail** and **Other (Custom name)**
5. Name it "Winter Weather Agent"
6. **Copy the 16-character password** (remove spaces)

## Step 2: Create Digital Ocean Droplet (2 minutes)

1. Log into Digital Ocean
2. Create Droplet:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($6/month)
   - **CPU**: Regular (cheapest option)
   - **Region**: New York (closest to Harrisburg)
3. Click **Create Droplet**
4. **Copy the IP address** when ready

## Step 3: Upload and Deploy (3 minutes)

### Option A: Using SCP (from your Mac)

```bash
# From your Downloads folder
cd ~/Downloads

# Upload files to droplet
scp -r winter-weather-agent root@YOUR_DROPLET_IP:/opt/

# SSH into droplet
ssh root@YOUR_DROPLET_IP

# Run deployment script
cd /opt/winter-weather-agent
chmod +x deploy.sh
./deploy.sh
```

### Option B: Manual Upload

1. SSH into droplet: `ssh root@YOUR_DROPLET_IP`
2. Create directory: `mkdir -p /opt/winter-weather-agent`
3. On your Mac, from Downloads folder:
   ```bash
   cd ~/Downloads/winter-weather-agent
   scp * root@YOUR_DROPLET_IP:/opt/winter-weather-agent/
   ```
4. Back on droplet: `cd /opt/winter-weather-agent && ./deploy.sh`

## Step 4: Configure Email

```bash
nano /opt/winter-weather-agent/.env
```

Edit these lines:
```
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password-here
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=your-email@gmail.com
NWS_USER_AGENT=(WinterWeatherAgent, your-email@gmail.com)
```

Save with `Ctrl+X`, then `Y`, then `Enter`

## Step 5: Test and Start

```bash
# Test run (sends one email)
cd /opt/winter-weather-agent
source venv/bin/activate
python3 weather_agent.py --once

# If that works, start the service
systemctl start winter-weather-agent
systemctl enable winter-weather-agent

# Check it's running
systemctl status winter-weather-agent
```

## Done!

You'll now receive emails every 6 hours with:
- Weather forecasts for next 2 days
- Snowfall and ice predictions
- Accuracy tracking (after a few days of data)

## View Logs

```bash
journalctl -u winter-weather-agent -f
```

Press `Ctrl+C` to exit log view.

## Troubleshooting

**Email not sending?**
- Check app password (no spaces)
- Verify 2FA is enabled
- Try regenerating app password

**No emails received?**
- Check spam folder
- Verify EMAIL_TO address in .env
- Check logs: `journalctl -u winter-weather-agent -n 50`

**Service not starting?**
- Check logs: `journalctl -u winter-weather-agent -n 50`
- Restart: `systemctl restart winter-weather-agent`

## Stop the Service

```bash
systemctl stop winter-weather-agent
```

## That's it!

Your agent is now running 24/7, monitoring winter weather for Harrisburg International Airport.
