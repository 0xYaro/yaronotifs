# Market Intelligence Aggregator & Router

A production-ready modular intelligence bot that monitors multiple information sources (Telegram, RSS, web scrapers, APIs), processes all content through an AI-powered pipeline, and forwards curated intelligence to your Telegram channel.

---

## 📚 Documentation

**🎯 New to this project?** → **[START HERE](START_HERE.md)** (5-minute overview)

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[START_HERE.md](START_HERE.md)** ⭐ | Quick onboarding & overview | First time, need context |
| **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** ⭐ | Copy-paste examples & commands | Daily usage, adding sources |
| **[ADDING_NEW_SOURCES.md](ADDING_NEW_SOURCES.md)** | Detailed source integration guide | Adding RSS/scrapers/APIs |
| **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** | Complete doc navigation | Finding specific info |
| **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** | Legacy → modular migration | Upgrading from old version |
| **[MODULAR_ARCHITECTURE_COMPLETE.md](MODULAR_ARCHITECTURE_COMPLETE.md)** | Technical deep dive | Understanding internals |

**Quick Links:**
- 🚀 [Run the bot](START_HERE.md#quick-start-3-steps)
- ➕ [Add an RSS feed](QUICK_REFERENCE.md#add-rss-feed)
- 🌐 [Add a web scraper](QUICK_REFERENCE.md#add-web-scraper)
- 🔧 [Troubleshooting](QUICK_REFERENCE.md#troubleshooting)

---

## Overview

This bot acts as a "man-in-the-middle" automation system that:

1. **Listens** to any Telegram channels using a burner user account
2. **Processes** incoming data through a **Unified AI Pipeline**:
   - **LLM-powered content routing**: Automatically detects content type and applies appropriate processing
   - **Translation**: Chinese to English for news channels
   - **Analysis**: Deep analysis of PDF research reports (text + visual elements)
   - **Summarization**: Key insights extraction from all content types
3. **Forwards** processed intelligence to your main Telegram account in a consistent format

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

### AI-Powered Intelligence
- **Unified Pipeline**: All messages processed through Gemini Flash 2.5
- **Smart Content Detection**: LLM automatically determines processing needs
- **Consistent Output**: Unified format for all intelligence
- **Cost**: ~$0.0001-0.002 per message depending on complexity

### Resilient Architecture
- Automatic reconnection on network failures
- Exponential backoff retry logic
- Graceful error handling (logs errors, continues operation)
- No crashes from individual message failures

## Architecture

```
yaronotifs/
├── config/              # Configuration management
├── sources/             # Modular source providers (NEW)
│   ├── base.py          # BaseSource interface & SourceMessage
│   ├── registry.py      # SourceRegistry for managing sources
│   ├── telegram_source.py  # Telegram channel source
│   └── examples/        # Example source implementations
│       ├── rss_source.py        # RSS feed source
│       ├── webscraper_source.py # Web scraper source
│       └── api_source.py        # REST API source
├── core/                # Telegram client wrapper
├── pipelines/           # Message processing pipelines
│   ├── base.py          # Base pipeline class
│   └── unified.py       # Unified AI-powered pipeline with SourceMessage support
├── services/            # External service integrations
│   ├── gemini_service.py   # Google Gemini API with intelligent routing
│   └── pdf_service.py      # PDF download & extraction
├── utils/               # Logging, helpers, retry logic
├── scripts/             # Setup and utility scripts
├── main.py              # Modular source architecture entry point
├── main_legacy.py       # Legacy direct Telegram approach (backup)
└── requirements.txt
```

### Modular Source Architecture

The bot now uses a **modular source architecture** that makes it trivial to add new information sources:

```
┌─────────────────────────────────────────────────┐
│         Source Registry                         │
│  (Manages all information sources)              │
└────────┬────────────────────────────────────────┘
         │
         ├─── TelegramSource (Telegram channels)
         ├─── RSSSource (RSS feeds)
         ├─── WebScraperSource (Web scraping)
         ├─── APISource (REST APIs)
         └─── [Your Custom Source]
                     │
                     ▼
         ┌───────────────────────┐
         │   SourceMessage       │
         │  (Standardized)       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   UnifiedPipeline     │
         │  (LLM Processing)     │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Output Channel       │
         │  (Telegram)           │
         └───────────────────────┘
```

**Key Components:**
1. **BaseSource** - Abstract interface all sources implement
2. **SourceMessage** - Standardized message format across all sources
3. **SourceRegistry** - Manages and multiplexes messages from all sources
4. **UnifiedPipeline** - Processes all messages with LLM intelligence

**Benefits:**
- **Modular**: Add new sources without touching existing code
- **Flexible**: Support any data source (feeds, APIs, scrapers, webhooks)
- **Consistent**: All sources processed through same LLM pipeline
- **Maintainable**: Clear separation of concerns
- **Extensible**: Easy for users or AI to add new sources

See [ADDING_NEW_SOURCES.md](ADDING_NEW_SOURCES.md) for complete documentation on adding sources.

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

## Unified Pipeline Processing

The **UnifiedPipeline** intelligently processes all message types:

### Text Messages (e.g., News Channels)

**Default Channels:**
- BWEnews (`-1001279597711`) - Chinese crypto news
- Foresight News (`-1001526765830`) - Chinese crypto news
- Any text-based channel you add

**Processing:**
1. LLM detects language and content type
2. Translates if Chinese (or other non-English languages)
3. Extracts key insights and actionable information
4. Summarizes in professional format
5. Highlights breaking news, price movements, or important data

**Output Format:**
```
[Summarized and/or translated content]

Key Points:
• [Important insight 1]
• [Important insight 2]
• [Important insight 3]

from: [Source Channel](message_link)
```

### Document Messages (e.g., Research Reports)

**Default Channels:**
- DTpapers (`-1001750561680`) - Equity research reports
- Any channel with PDF documents

**Processing:**
1. Downloads document (non-blocking)
2. Uploads to Gemini File API (multimodal analysis)
3. Analyzes BOTH text AND visual elements:
   - Charts, graphs, financial tables
   - Valuation models, price targets
   - Revenue/EPS estimates
4. Provides contextual market analysis
5. Extracts actionable intelligence

**Output Format:**
```
🔴 **NVIDIA - COVERAGE**

**Summary**
[2-3 sentence executive summary of the report and key insight]

**Investment Thesis**
• [Core bull/bear case point 1]
• [Core bull/bear case point 2]
• [Core bull/bear case point 3]

**Key Data & Visual Insights**
• [Critical data point with numbers]
• [Chart insight - story it tells]
• [Valuation metrics]

**Catalysts & Timeline**
• **Near-term (0-3 months):** [Upcoming events]
• **Medium-term (3-12 months):** [Structural changes]

**Risk Factors**
• [Key downside risk 1]
• [Key downside risk 2]

**Sector Context**
[Broader market/sector trends and peer implications]

from: [Source Channel](message_link)

[PDF attached]
```

**Priority Labels:**
- 🔴 = ACTIONABLE (requires immediate attention)
- 🟡 = MONITOR (track developments)
- ⚪ = NOISE (informational only)

**Cost:** ~$0.0001-0.002 per message (varies by complexity)

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

### CRITICAL: Multiple Instance Protection

**Problem:** "Session is being used from another IP address!" or `AuthKeyDuplicatedError`

**What This Means:**
Telegram detected that the same session file is being used from multiple IP addresses simultaneously. This is a **serious issue** that can lead to:
- Telegram account suspension
- IP address bans
- Session invalidation

**Common Causes:**
1. Running the bot on both local machine AND AWS server at the same time
2. Running multiple instances of the bot on different servers
3. Not properly stopping the bot before starting it elsewhere

**Solution:**
1. **Stop ALL instances** of the bot immediately:
   ```bash
   # On AWS server
   sudo systemctl stop yaronotifs

   # On local machine (if running)
   # Press Ctrl+C to stop
   ```

2. **Wait 60 seconds** for Telegram to release the session

3. **Only run ONE instance at a time**
   - If testing locally, don't run on AWS
   - If running on AWS, don't run locally

4. **The bot now includes automatic protection:**
   - Creates a lock file when starting
   - Checks for existing lock file before connecting
   - Prevents accidental multiple instances

5. **If lock file is stuck:**
   ```bash
   rm yaronotifs_session.lock
   ```

**Prevention:**
- Always use `sudo systemctl stop yaronotifs` before running locally
- Never copy the same session file to multiple machines
- Use the systemd service on AWS (it prevents multiple starts)

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

**API Costs (UnifiedPipeline):**
- Text messages: ~$0.0001 each (Gemini Flash)
- PDF documents: ~$0.001-0.002 each (multimodal processing)

**Examples:**
- 1000 text messages/month: ~$0.10
- 100 PDFs/month: ~$0.10-0.20
- Combined typical usage: ~$0.20-0.50/month

**Total:** ~$4-5/month (infrastructure + API)

## Security Best Practices

1. **Use a burner Telegram account** for listening (not your main account)
2. **Keep .env and .session files secure** (never commit to git)
3. **Restrict server access** (use SSH keys, disable password auth)
4. **Rotate API keys periodically**
5. **Monitor logs** for unusual activity

## Adding New Channels

To monitor additional channels:

1. Edit `config/settings.py`
2. Add channel ID to `MONITORED_CHANNELS`:

```python
# All channels are processed through UnifiedPipeline
self.MONITORED_CHANNELS: List[int] = [
    -1001279597711,    # BWEnews
    -1001526765830,    # Foresight News
    -1001750561680,    # DTpapers
    -1001234567890,    # Your new channel
]
```

3. Restart the bot:
```bash
sudo systemctl restart yaronotifs
```

**That's it!** The UnifiedPipeline will automatically:
- Detect the content type (text, PDF, etc.)
- Determine if translation is needed
- Apply appropriate analysis
- Format output consistently

## Extending the Bot

### Adding New Input Sources (RSS, Web Scrapers, APIs, etc.)

The bot now features a **modular source architecture** that makes it incredibly easy to add new information sources alongside Telegram channels.

**📖 See [ADDING_NEW_SOURCES.md](ADDING_NEW_SOURCES.md) for complete documentation**

#### Quick Example: Add an RSS Feed

```python
from sources.examples import RSSSource
from sources import SourceRegistry

# Initialize registry
registry = SourceRegistry()

# Add Telegram (existing)
telegram_source = TelegramSource(monitored_channels=[...])
registry.register(telegram_source)

# Add RSS feed (new!)
rss_source = RSSSource(
    name="TechCrunch",
    feed_url="https://techcrunch.com/feed/",
    poll_interval_minutes=15
)
registry.register(rss_source)

# Start all sources
await registry.start_all()

# Process all messages through unified pipeline
await registry.process_messages(message_handler)
```

**Available Source Templates:**
- ✅ **RSSSource** - Any RSS/Atom feed
- ✅ **WebScraperSource** - Web page scraping with CSS selectors
- ✅ **APISource** - REST API polling
- ✅ **CoinGeckoTrendingSource** - Pre-built trending crypto tracker
- 🔧 **BaseSource** - Create custom sources

All sources are processed through the same LLM-powered UnifiedPipeline with consistent formatting!

### Customizing AI Prompts

Edit `services/gemini_service.py` to customize how the LLM processes messages:

**For text messages:**
```python
def _build_text_processing_prompt(self, text: str, context: dict) -> str:
    # Customize the prompt for text processing
    # Change tone, format, length, etc.
    pass
```

**For documents:**
```python
def _build_document_processing_prompt(self, context: dict) -> str:
    # Customize the prompt for document analysis
    # Change analysis framework, output format, etc.
    pass
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
