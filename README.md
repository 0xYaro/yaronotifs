# Crypto Intelligence Aggregator & Router

A production-ready Telegram intelligence bot that monitors crypto channels, processes messages through AI-powered pipelines, and forwards curated intelligence to your main account.

## Overview

This bot acts as a "man-in-the-middle" automation system that:

1. **Listens** to specific Telegram channels using a burner user account
2. **Processes** incoming data through specialized pipelines:
   - **Pipeline A (Translator)**: Chinese news translation (BWEnews, Foresight News)
   - **Pipeline B (Analyst)**: PDF research report analysis (DTpapers)
3. **Forwards** processed intelligence to your main Telegram account

## Key Features

### Non-Blocking Concurrency
- Built with `asyncio` for true concurrent processing
- PDF downloads never block text message processing
- Each message is processed in an independent async task
- Handles multiple channels simultaneously without performance degradation

### Cloud Deployment Ready
- Designed for AWS Lightsail/EC2 Ubuntu servers
- Systemd service integration for auto-start and monitoring
- Session file management for headless operation
- Comprehensive error handling and auto-reconnection

### Cost Optimized
- **Pipeline A**: FREE (uses Google Translate via deep-translator)
- **Pipeline B**: ~$0.001-0.002 per PDF (Gemini Flash 1.5)
- No unnecessary LLM calls
- Efficient resource usage

### Resilient Architecture
- Automatic reconnection on network failures
- Exponential backoff retry logic
- Graceful error handling (logs errors, continues operation)
- No crashes from individual message failures

## Architecture

```
yaronotifs/
├── config/              # Configuration management
├── core/                # Telegram client wrapper & message routing
├── pipelines/           # Message processing pipelines
│   ├── translator.py    # Pipeline A: Chinese translation
│   └── analyst.py       # Pipeline B: PDF analysis
├── services/            # External service integrations
│   ├── gemini_service.py   # Google Gemini API
│   └── pdf_service.py      # PDF download & extraction
├── utils/               # Logging, helpers, retry logic
├── scripts/             # Setup and utility scripts
├── main.py              # Application entry point
└── requirements.txt
```

## Prerequisites

### Local Machine (for session creation)
- Python 3.10+
- Telegram account (burner account recommended)
- Telegram API credentials (api_id, api_hash)

### AWS Server
- Ubuntu 20.04 or newer
- Python 3.10+
- Sudo privileges
- Internet connection

### API Keys Required
1. **Telegram API** (get from https://my.telegram.org)
   - `api_id`
   - `api_hash`
2. **Google Gemini API** (get from https://aistudio.google.com/app/apikey)
   - Free tier: 15 requests/minute
3. **Output Channel ID** (your Telegram channel for receiving intelligence)
   - Create a channel or use an existing one
   - Add your listener account (@yaronotifs) as Administrator with full permissions
   - Forward any message from the channel to @userinfobot
   - The bot will show the channel ID (format: -1001234567890)
4. **Status Destination ID** (optional - for bot metrics)
   - Can be a user ID or channel ID
   - Leave empty to disable status reports

## Quick Start Guide

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd yaronotifs
```

### Step 2: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required configuration:
```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+1234567890
OUTPUT_CHANNEL_ID=-1001234567890
STATUS_DESTINATION_ID=  # Optional: for bot metrics
GEMINI_API_KEY=your_gemini_api_key_here
```

### Important: Channel Administrator Permissions

⚠️ **Critical Requirement**: The listener account (@yaronotifs or your burner account) MUST be added as an **Administrator** to the output channel with **full admin permissions**. Without proper permissions, the bot cannot post messages.

**To add the account as admin:**
1. Open your output channel in Telegram
2. Go to Channel Info → Administrators
3. Click "Add Administrator"
4. Search for your listener account username
5. Grant **full administrator permissions** (recommended)
   - At minimum: "Post Messages" is required
   - For best functionality: Enable all admin permissions

**Why full admin access?**
- Ensures the bot can post messages reliably
- Allows message editing if you need to correct errors
- Enables message deletion for cleanup
- Future-proofs the bot for additional features

**Optional: Status Reports Channel**
If you configure `STATUS_DESTINATION_ID` to point to a different channel for bot metrics, the listener account must also be an admin there.
```

### Step 3: Create Session File (LOCAL MACHINE)

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run the session creation script
python scripts/create_session.py
```

This will:
1. Prompt for your phone number
2. Send a Telegram verification code
3. Handle 2FA if enabled
4. Generate a `.session` file

### Step 4: Deploy to AWS Server

```bash
# Upload project files to your server
scp -r yaronotifs/ user@your-server:~/

# Upload the session file
scp yaronotifs_session.session user@your-server:~/yaronotifs/

# SSH into your server
ssh user@your-server
cd ~/yaronotifs

# Run the setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:
- Install system dependencies
- Create a Python virtual environment
- Install Python packages
- Create a systemd service
- Set up logging directories

### Step 5: Start the Bot

#### Manual Start (for testing)

```bash
source venv/bin/activate
python main.py
```

You should see:
```
✓ Connected as: YourName (@username)
✓ BOT IS RUNNING
Monitoring 3 channels:
  • Translator Pipeline: 2 channels
  • Analyst Pipeline: 1 channels
```

#### Production Start (systemd service)

```bash
# Enable auto-start on boot
sudo systemctl enable yaronotifs

# Start the service
sudo systemctl start yaronotifs

# Check status
sudo systemctl status yaronotifs

# View logs
tail -f logs/bot.log
```

## Pipeline Details

### Pipeline A: Chinese News Translation

**Channels:**
- BWEnews (`-1001279597711`)
- Foresight News (`-1001526765830`)

**Processing:**
1. Detect Chinese characters in message
2. Translate to English using Google Translate (free)
3. Forward with source attribution

**Output Format:**
```
📰 BWEnews

[Translated English text]

---
Original (CN): [First 200 chars of Chinese text]
```

**Cost:** FREE

### Pipeline B: PDF Research Analysis

**Channel:**
- DTpapers (`-1001750561680`)

**Processing:**
1. Detect PDF document in message
2. Download PDF (non-blocking)
3. Upload PDF directly to Gemini File API (multimodal)
4. Gemini analyzes BOTH text AND visual elements (charts, graphs, token unlock schedules)
5. Forward AI summary + original PDF

**Analysis Includes:**
- Executive summary
- Key alpha opportunities (from text and charts)
- Catalysts & timeline (including dates from visual roadmaps)
- Visual data insights (token economics, unlock schedules, market data)
- Risks & considerations

**Why Multimodal?**
Traditional text extraction would miss crucial visual data like:
- Token unlock schedules (charts)
- Price targets (graphs)
- Tokenomics breakdowns (pie charts)
- Roadmap timelines (visual timelines)

**Output Format:**
```
📊 Research Report Analysis

Source: DTpapers
Report: crypto_report.pdf

---

## Executive Summary
...

## Key Alpha Opportunities
- [Insights from both text and charts]
- [Token unlock schedules from visual data]

## Catalysts & Timeline
- [Dates extracted from roadmap charts]

## Visual Data Insights
- [Analysis of charts, graphs, tables]
- [Token economics from pie charts]

## Risks & Considerations
...

[PDF attached]
```

**Cost:** ~$0.001-0.002 per report

**Note:** Uses Gemini's File API with multimodal capabilities to analyze the entire PDF including visual elements.

## Managing the Service

### View Logs

```bash
# Application logs
tail -f logs/bot.log

# Error logs
tail -f logs/bot_error.log

# Systemd logs
sudo journalctl -u yaronotifs -f
```

### Control the Service

```bash
# Start
sudo systemctl start yaronotifs

# Stop
sudo systemctl stop yaronotifs

# Restart
sudo systemctl restart yaronotifs

# Status
sudo systemctl status yaronotifs

# Disable auto-start
sudo systemctl disable yaronotifs
```

### Update the Bot

```bash
# Stop the service
sudo systemctl stop yaronotifs

# Pull latest changes
git pull

# Activate venv and update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart the service
sudo systemctl restart yaronotifs
```

## Troubleshooting

### Session File Issues

**Problem:** "Session file not found"

**Solution:**
```bash
# Run create_session.py on your LOCAL machine
python scripts/create_session.py

# Upload to server
scp yaronotifs_session.session user@server:~/yaronotifs/
```

### Authentication Errors

**Problem:** "User is not authorized"

**Solution:**
1. Delete the session file
2. Run `create_session.py` again locally
3. Upload new session file to server

### Gemini API Errors

**Problem:** "Empty response from Gemini API"

**Solutions:**
- Check API key is valid
- Verify you haven't exceeded rate limits (15 req/min free tier)
- Check logs/bot_error.log for details

### Bot Not Posting to Channel

**Problem:** Messages processed but not appearing in channel

**Solutions:**
1. Verify channel ID is correct (should start with -100)
2. Ensure listener account is added as Administrator
3. Check admin permissions include "Post Messages"
4. Verify channel is not deleted or archived
5. Check logs for "Failed to forward to output channel" errors

### Bot Not Processing Messages

**Checklist:**
1. Is the service running? `sudo systemctl status yaronotifs`
2. Are you monitoring the correct channels? Check logs
3. Is the output channel ID correct? Verify in .env
4. Check logs: `tail -f logs/bot.log`

### Connection Issues

The bot automatically reconnects on network failures. Check logs for:
```
Client disconnected: [error]
Attempting to reconnect in 5s...
✓ Reconnected successfully
```

## Performance Considerations

### Concurrency Model

The bot uses `asyncio.create_task()` for message processing:

```python
# Each message is processed independently
asyncio.create_task(self._process_translator(message))
asyncio.create_task(self._process_analyst(message))
```

This means:
- A 50MB PDF download won't block a text message
- Multiple channels can be processed simultaneously
- No message is ever blocked waiting for another

### Resource Usage

Typical resource usage on AWS Lightsail:
- **RAM:** 200-500MB
- **CPU:** <5% (spikes during PDF processing)
- **Disk:** Minimal (PDFs are deleted after processing)
- **Network:** Depends on PDF volume

### Rate Limits

**Gemini API (Free Tier):**
- 15 requests per minute
- 1,500 requests per day

**Telegram:**
- No hard limits for user accounts
- Flood protection applies (auto-handled by bot)

## Cost Analysis

### Monthly Costs (Estimated)

**Infrastructure:**
- AWS Lightsail (1GB RAM): $3.50/month
- Or AWS EC2 t2.micro: $8.50/month

**API Costs:**
- Pipeline A (Translation): $0
- Pipeline B (Gemini):
  - 100 PDFs/month: ~$0.10-0.20
  - 500 PDFs/month: ~$0.50-1.00

**Total:** ~$4-10/month depending on volume

## Security Best Practices

1. **Use a burner Telegram account** for listening (not your main account)
2. **Keep .env and .session files secure** (never commit to git)
3. **Restrict server access** (use SSH keys, disable password auth)
4. **Rotate API keys periodically**
5. **Monitor logs** for unusual activity

## Adding New Channels

To monitor additional channels:

1. Edit `config/settings.py`
2. Add channel ID to appropriate pipeline:

```python
# For translation
self.TRANSLATOR_CHANNELS: List[int] = [
    -1001279597711,
    -1001526765830,
    -1001234567890,  # New channel
]

# For analysis
self.ANALYST_CHANNELS: List[int] = [
    -1001750561680,
    -1001234567890,  # New channel
]
```

3. Restart the bot:
```bash
sudo systemctl restart yaronotifs
```

## Extending the Bot

### Adding a New Pipeline

1. Create a new pipeline class in `pipelines/`:

```python
from .base import BasePipeline

class CustomPipeline(BasePipeline):
    async def process(self, message: Message) -> bool:
        # Your processing logic
        pass
```

2. Update `core/message_handler.py` to route messages

3. Update `config/settings.py` with channel mappings

### Customizing AI Prompts

Edit `services/gemini_service.py`:

```python
def _build_crypto_analysis_prompt(self, text: str) -> str:
    return f"""Your custom prompt here...

    {text}
    """
```

## API Reference

### Gemini vs GPT Comparison

| Feature | Gemini Flash 1.5 | GPT-3.5-turbo | GPT-4 |
|---------|------------------|---------------|-------|
| **Cost** | $0.001/report | $0.002/report | $0.03/report |
| **Speed** | Fast | Fast | Slower |
| **Quality** | Good | Good | Excellent |
| **Free Tier** | Yes (15/min) | No | No |

**Recommendation:** Gemini Flash 1.5 (best cost/quality ratio)

## License

[Your License Here]

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `logs/bot.log` and `logs/bot_error.log`
3. Open an issue on GitHub

## Acknowledgments

- Built with [Telethon](https://docs.telethon.dev/)
- AI powered by [Google Gemini](https://ai.google.dev/)
- Translation by [deep-translator](https://github.com/nidhaloff/deep-translator)
