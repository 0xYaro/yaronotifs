# Architecture Overview

## System Design Philosophy

This application is designed with three core principles:

1. **Non-Blocking Concurrency**: Every message is processed independently using `asyncio.create_task()`. A 50MB PDF download never blocks a text message.

2. **Cost Optimization**: Only use AI when necessary. Pipeline A uses free translation; Pipeline B uses the most cost-effective AI model.

3. **Resilience**: Automatic reconnection, exponential backoff retries, and graceful error handling ensure 24/7 operation.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TELEGRAM CHANNELS                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   BWEnews    │  │ Foresight    │  │  DTpapers    │          │
│  │   (Chinese)  │  │ News (CN)    │  │    (PDFs)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                             ▼
          ┌──────────────────────────────────────┐
          │   TELEGRAM CLIENT WRAPPER            │
          │   - Auto-reconnection                │
          │   - Session management               │
          │   - Event registration               │
          └──────────────┬───────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────────────┐
          │   MESSAGE HANDLER (Router)           │
          │   - Routes by channel ID             │
          │   - Creates async tasks              │
          │   - Tracks metrics                   │
          └──────────┬───────────┬───────────────┘
                     │           │
          ┌──────────┘           └──────────┐
          ▼                                  ▼
┌─────────────────────┐          ┌─────────────────────┐
│  PIPELINE A         │          │  PIPELINE B         │
│  Translator         │          │  Analyst            │
│                     │          │                     │
│ 1. Detect Chinese   │          │ 1. Detect PDF       │
│ 2. Translate (FREE) │          │ 2. Download PDF     │
│ 3. Forward result   │          │ 3. Upload to Gemini │
│                     │          │ 4. Multimodal AI    │
│ Cost: $0            │          │ 5. Forward summary  │
└──────────┬──────────┘          │                     │
           │                     │ Cost: ~$0.001/PDF   │
           │                     └──────────┬──────────┘
           │                                │
           └────────────┬───────────────────┘
                        ▼
          ┌──────────────────────────────────────┐
          │   OUTPUT CHANNEL                     │
          │   (Receives processed intelligence)   │
          └──────────────────────────────────────┘
```

## Component Breakdown

### Core Layer (`core/`)

**`telegram_client.py`** - TelegramClientWrapper
- Wraps Telethon's TelegramClient
- Handles authentication and session management
- Auto-reconnection with exponential backoff
- Event handler registration
- Graceful shutdown

**`message_handler.py`** - MessageHandler
- Central routing hub for all messages
- Determines which pipeline to use based on channel ID
- Uses `asyncio.create_task()` for non-blocking processing
- Tracks processing metrics
- Error isolation (one bad message doesn't crash the bot)

### Pipeline Layer (`pipelines/`)

**`base.py`** - BasePipeline
- Abstract base class for all pipelines
- Common forwarding logic
- Source attribution helpers

**`translator.py`** - TranslatorPipeline (Pipeline A)
- Detects Chinese characters using Unicode ranges
- Translates using Google Translate (free, via deep-translator)
- Splits long texts into chunks to avoid rate limits
- Forwards with source attribution

**`analyst.py`** - AnalystPipeline (Pipeline B)
- Downloads PDF attachments from Telegram
- **Key Feature**: Uses Gemini's File API for multimodal analysis
- Analyzes both text AND visual elements:
  - Charts and graphs
  - Token unlock schedules
  - Roadmap timelines
  - Tokenomics breakdowns
- Forwards AI summary + original PDF
- Cleans up temporary files

### Service Layer (`services/`)

**`gemini_service.py`** - GeminiService
- Wraps Google Gemini API
- **Uses File API** for direct PDF upload (multimodal)
- Waits for file processing completion
- Cleans up uploaded files to save quota
- Custom crypto analysis prompt
- Retry logic with exponential backoff

**`pdf_service.py`** - PDFService
- Downloads PDFs from URLs with size limits
- Async download with chunk streaming
- Optional text extraction (fallback capability)
- Cleanup utilities for temporary files

### Utilities Layer (`utils/`)

**`logger.py`**
- Centralized logging configuration
- Console and file handlers
- Structured log format with timestamps

**`helpers.py`**
- `retry_async`: Decorator for automatic retries with backoff
- `detect_chinese`: Unicode-based Chinese detection
- `safe_filename`: Sanitize filenames for security
- Other utility functions

### Configuration Layer (`config/`)

**`settings.py`**
- Centralized configuration management
- Environment variable loading
- Channel routing definitions
- Pipeline mappings
- Validation logic

## Concurrency Model

The bot uses asyncio with task-based concurrency:

```python
# In message_handler.py
async def handle_message(self, message):
    pipeline_type = settings.get_pipeline_for_channel(channel_id)

    if pipeline_type == 'translator':
        # Create independent task - doesn't block
        asyncio.create_task(self._process_translator(message))
    elif pipeline_type == 'analyst':
        # Create independent task - doesn't block
        asyncio.create_task(self._process_analyst(message))
```

**Why This Works:**
- Each message gets its own async task
- PDF download (I/O-bound) runs concurrently
- Text translation (I/O-bound) runs concurrently
- Gemini API calls (I/O-bound) run concurrently
- No message ever blocks another

**Example Timeline:**
```
T+0.0s: Message 1 (PDF) arrives → Task 1 starts downloading (50MB)
T+0.1s: Message 2 (text) arrives → Task 2 translates immediately
T+0.3s: Message 2 complete, forwarded to user
T+5.0s: Message 1 download complete, uploading to Gemini
T+8.0s: Message 1 analysis complete, forwarded to user
```

## Data Flow

### Pipeline A (Translation)
```
Chinese Message
    ↓
Detect Chinese (regex)
    ↓
Split into chunks if needed
    ↓
Google Translate API (free)
    ↓
Format with source attribution
    ↓
Forward to target user
```

### Pipeline B (PDF Analysis)
```
PDF Message
    ↓
Download PDF via Telethon
    ↓
Upload to Gemini File API
    ↓
Wait for processing (if needed)
    ↓
Send to Gemini with analysis prompt
    ↓
Receive multimodal analysis:
  - Text content
  - Charts & graphs
  - Token unlock schedules
  - Roadmaps
    ↓
Format summary
    ↓
Forward summary + PDF to target user
    ↓
Cleanup (delete temp file, delete from Gemini)
```

## Error Handling Strategy

### Network Errors
- Automatic reconnection with exponential backoff
- Max retry attempts: 3
- Initial delay: 2s, multiplier: 2x

### API Errors
- Retry decorator on all external API calls
- Graceful degradation (log error, skip message)
- Never crash the entire bot

### File Processing Errors
- Try multiple PDF extraction libraries
- Timeout after 60s for file processing
- Always cleanup temp files (even on error)

### Telegram Errors
- FloodWaitError: Auto-sleep for required duration
- SessionPasswordNeededError: Handled in session creation
- Connection errors: Auto-reconnect

## Security Considerations

1. **Session File**: Contains authentication tokens
   - Created locally (with 2FA)
   - Uploaded to server
   - Not committed to git (.gitignore)

2. **Environment Variables**: Stored in `.env`
   - API keys
   - User IDs
   - Phone numbers
   - Not committed to git

3. **File Handling**:
   - Filename sanitization
   - Size limits (50MB default)
   - Automatic cleanup

4. **API Keys**:
   - Loaded from environment
   - Never logged or printed
   - Validated on startup

## Deployment Model

### Local (Session Creation)
```
Your Machine
    ↓
Run create_session.py
    ↓
2FA Authentication
    ↓
Generate .session file
    ↓
Upload to AWS
```

### Production (AWS Server)
```
AWS Ubuntu Server
    ↓
Install dependencies (setup.sh)
    ↓
Load .env and .session
    ↓
Start systemd service
    ↓
Run indefinitely with auto-restart
```

## Monitoring & Observability

### Logs
- Application logs: `logs/bot.log`
- Error logs: `logs/bot_error.log`
- Systemd journal: `journalctl -u yaronotifs`

### Metrics
- Total messages processed
- Messages per pipeline
- Error count
- Available via `message_handler.get_metrics()`

### Health Checks
- Telegram connection status
- Gemini API health check
- Configuration validation

## Scalability Considerations

### Current Limits
- Gemini Free Tier: 15 requests/minute, 1,500/day
- Telegram: No hard user limits (flood protection applies)

### Scaling Options
1. **Vertical**: Upgrade to paid Gemini tier for higher limits
2. **Horizontal**: Run multiple instances with different accounts
3. **Queue-based**: Add Redis queue for rate limiting

## Cost Breakdown

### Fixed Costs (Monthly)
- AWS Lightsail (1GB): $3.50/month
- Or AWS EC2 t2.micro: $8.50/month

### Variable Costs
- Pipeline A (Translation): **$0** (free Google Translate)
- Pipeline B (Gemini File API):
  - Per PDF: ~$0.001-0.002
  - 100 PDFs/month: ~$0.10-0.20
  - 500 PDFs/month: ~$0.50-1.00

### Total Monthly Cost
- Light usage (100 PDFs): **~$3.60-$3.70**
- Medium usage (500 PDFs): **~$4.00-$4.50**

## Future Enhancements

Potential improvements:
1. Add more pipelines (e.g., video summarization)
2. Database for message history
3. Web dashboard for monitoring
4. Multiple target users
5. Customizable prompts per channel
6. Sentiment analysis pipeline
7. Alert system for high-priority messages

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Telegram | Telethon | MTProto API client |
| AI/ML | Google Gemini Flash 1.5 | Multimodal PDF analysis |
| Translation | deep-translator | Free Chinese→English |
| PDF Processing | Gemini File API | Multimodal (text + visual) |
| Async Runtime | asyncio | Non-blocking concurrency |
| Config | python-dotenv | Environment management |
| Logging | Python logging | Structured logs |
| Deployment | systemd | Service management |
| Server | Ubuntu 20.04+ | Production environment |

## Key Design Decisions

1. **Telethon over Pyrogram**: More mature, better documentation
2. **Gemini over GPT**: Better cost/performance ratio, multimodal capabilities
3. **Task-based concurrency**: Simpler than queues, sufficient for workload
4. **File API over text extraction**: Captures visual data (critical for crypto reports)
5. **Systemd over Docker**: Simpler deployment for single-server use case
6. **Free translation**: Google Translate quality sufficient for news
7. **Local session creation**: Security best practice for 2FA
