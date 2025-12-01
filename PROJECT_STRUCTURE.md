# Project Structure

```
yaronotifs/
│
├── config/                      # Configuration Management
│   ├── __init__.py
│   └── settings.py              # Centralized settings, channel routing
│
├── core/                        # Core Application Logic
│   ├── __init__.py
│   ├── telegram_client.py       # Telegram client wrapper with auto-reconnect
│   └── message_handler.py       # Message routing and orchestration
│
├── pipelines/                   # Message Processing Pipelines
│   ├── __init__.py
│   ├── base.py                  # Abstract base pipeline class
│   ├── translator.py            # Pipeline A: Chinese→English translation
│   └── analyst.py               # Pipeline B: PDF multimodal analysis
│
├── services/                    # External Service Integrations
│   ├── __init__.py
│   ├── gemini_service.py        # Google Gemini File API (multimodal)
│   └── pdf_service.py           # PDF download and optional extraction
│
├── utils/                       # Utility Functions
│   ├── __init__.py
│   ├── logger.py                # Logging setup and configuration
│   └── helpers.py               # Retry decorator, Chinese detection, etc.
│
├── scripts/                     # Deployment and Utility Scripts
│   ├── create_session.py        # Local 2FA session creation helper
│   └── setup.sh                 # AWS Ubuntu server setup script
│
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
│
├── .env.example                 # Example environment configuration
├── .gitignore                   # Git ignore rules
│
├── README.md                    # Complete user documentation
├── ARCHITECTURE.md              # Detailed architecture documentation
├── DEPLOYMENT_CHECKLIST.md      # Step-by-step deployment guide
└── PROJECT_STRUCTURE.md         # This file

Generated at runtime:
├── temp/                        # Temporary PDF storage (auto-cleanup)
├── logs/                        # Application logs
│   ├── bot.log                  # Main application log
│   └── bot_error.log            # Error log
├── .env                         # Your environment variables (DO NOT COMMIT)
└── *.session                    # Telegram session file (DO NOT COMMIT)
```

## File Descriptions

### Configuration (`config/`)

- **`settings.py`**: Single source of truth for all configuration
  - Environment variable loading
  - Channel ID to pipeline routing
  - API keys and credentials
  - File size limits, timeouts, retry settings

### Core (`core/`)

- **`telegram_client.py`**: Telegram client lifecycle management
  - Session authentication
  - Auto-reconnection on network failures
  - Event handler registration
  - Graceful shutdown

- **`message_handler.py`**: Message routing orchestration
  - Receives messages from all monitored channels
  - Routes to appropriate pipeline based on channel ID
  - Creates async tasks for non-blocking processing
  - Tracks processing metrics

### Pipelines (`pipelines/`)

- **`base.py`**: Abstract base class
  - Common forwarding logic
  - Source attribution helpers
  - Shared utilities

- **`translator.py`**: Chinese translation (Pipeline A)
  - Chinese character detection
  - Free Google Translate integration
  - Chunk handling for long texts
  - Cost: $0

- **`analyst.py`**: PDF multimodal analysis (Pipeline B)
  - PDF download from Telegram
  - Upload to Gemini File API
  - Multimodal analysis (text + visual elements)
  - Summary + original PDF forwarding
  - Cost: ~$0.001-0.002 per PDF

### Services (`services/`)

- **`gemini_service.py`**: Google Gemini integration
  - **File API upload** for multimodal processing
  - Processing state management
  - Custom crypto analysis prompts
  - Automatic file cleanup
  - Retry logic

- **`pdf_service.py`**: PDF operations
  - Async download with streaming
  - File size validation
  - Optional text extraction (fallback)
  - Temporary file management

### Utilities (`utils/`)

- **`logger.py`**: Logging infrastructure
  - Console and file handlers
  - Structured log format
  - Log level configuration

- **`helpers.py`**: Common utilities
  - `@retry_async`: Exponential backoff decorator
  - `detect_chinese()`: Unicode-based detection
  - `safe_filename()`: Security sanitization
  - File size formatting
  - Text truncation

### Scripts (`scripts/`)

- **`create_session.py`**: Local session creator
  - Interactive 2FA authentication
  - Generates .session file
  - Run on your local machine only
  - Upload result to AWS server

- **`setup.sh`**: AWS deployment automation
  - System package installation
  - Python virtual environment setup
  - Systemd service creation
  - Directory structure creation

### Main Application

- **`main.py`**: Entry point
  - Health checks (config, session, Gemini API)
  - Client initialization
  - Handler registration
  - Graceful shutdown handling
  - Metrics reporting

### Documentation

- **`README.md`**: Complete user guide
  - Quick start
  - Configuration
  - Deployment instructions
  - Troubleshooting
  - API reference

- **`ARCHITECTURE.md`**: Technical deep dive
  - System design philosophy
  - Component breakdown
  - Concurrency model
  - Data flow diagrams
  - Error handling strategy

- **`DEPLOYMENT_CHECKLIST.md`**: Step-by-step deployment
  - Pre-deployment checklist
  - AWS setup steps
  - Testing procedures
  - Verification commands

## Dependency Graph

```
main.py
  ├─→ config.settings
  ├─→ core.TelegramClientWrapper
  │     └─→ telethon.TelegramClient
  ├─→ core.MessageHandler
  │     ├─→ pipelines.TranslatorPipeline
  │     │     ├─→ pipelines.BasePipeline
  │     │     └─→ deep_translator.GoogleTranslator
  │     └─→ pipelines.AnalystPipeline
  │           ├─→ pipelines.BasePipeline
  │           ├─→ services.GeminiService
  │           │     └─→ google.generativeai (File API)
  │           └─→ services.PDFService
  │                 └─→ aiohttp, PyPDF2
  └─→ utils (logger, helpers)
```

## Data Flow

```
Telegram Channels
      ↓
TelegramClientWrapper (receives messages)
      ↓
MessageHandler (routes by channel ID)
      ↓
   ┌──┴──┐
   ↓     ↓
Pipeline A  Pipeline B
   ↓          ↓
Translate   Analyze PDF
(FREE)      (Gemini File API)
   ↓          ↓
   └──┬───────┘
      ↓
Target User Account
```

## Configuration Flow

```
.env file
    ↓
config/settings.py (loads & validates)
    ↓
Used by all modules
    ├─→ main.py
    ├─→ core/*
    ├─→ pipelines/*
    └─→ services/*
```

## Session Flow

```
Local Machine:
  create_session.py
      ↓
  2FA Authentication
      ↓
  .session file generated
      ↓
  Upload to AWS
      ↓
AWS Server:
  main.py loads session
      ↓
  Authenticated Telegram client
```

## Key Files to Configure

1. **`.env`** - Add your credentials:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `TELEGRAM_PHONE`
   - `OUTPUT_CHANNEL_ID` (channel for intelligence)
   - `STATUS_DESTINATION_ID` (optional - for bot metrics)
   - `GEMINI_API_KEY`

2. **`*.session`** - Generate locally:
   - Run `python scripts/create_session.py`
   - Upload to project root on AWS

3. **`config/settings.py`** - To add channels:
   - Edit `TRANSLATOR_CHANNELS` list
   - Edit `ANALYST_CHANNELS` list

## Files NOT to Modify (Unless Extending)

- `main.py` - Entry point (stable)
- `core/*.py` - Core logic (stable)
- `utils/*.py` - Utilities (stable)
- `scripts/setup.sh` - Deployment (stable)

## Files to Customize (For Extensions)

- `config/settings.py` - Add new channels or configuration
- `pipelines/*.py` - Add new processing pipelines
- `services/gemini_service.py` - Customize AI prompts

## Security-Sensitive Files

**NEVER COMMIT TO GIT:**
- `.env` (API keys, credentials)
- `*.session` (Telegram authentication)
- `temp/*` (Downloaded PDFs)
- `logs/*` (May contain sensitive data)

**Protected by `.gitignore`**
