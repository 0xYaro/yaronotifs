# Project Brief: Crypto Intelligence Aggregator & Router

## 1. The High-Level Goal
I am a crypto trader who needs to automate the ingestion of high-signal information. I need a Python application that runs on a cloud server (AWS). 

It acts as a "man-in-the-middle" automation:
1.  **Listens** to specific Telegram channels using a "Burner" user account.
2.  **Processes** the incoming data based on specific business logic (Translation vs. Summarization).
3.  **Forwards** the clean intelligence to my "Main" user account.

## 2. The Constraints & Preferences (Non-Negotiable)
* **Platform:** Must use the **Telegram MTProto API** (e.g., Telethon or Pyrogram) because the bot must act as a User, not a Bot API bot.
* **Cost Efficiency:** This is paramount. We only use LLMs when absolutely necessary.
* **Performance:** High concurrency. Downloading a large PDF must not block the processing of a text message.
* **Infrastructure:** AWS Lightsail (Ubuntu). The code should be production-ready (robust error handling, auto-reconnect).

## 3. The "Tiered" Logic (Business Rules)
I have specific processing rules based on the **Source** of the message. You need to architect a system that routes messages through these specific pipelines:

**Pipeline A: The Translators (Low Cost)**
* **Sources:** "BWEnews" (`-1001279597711`) and "Foresight News" (`-1001526765830`).
* **Task:** These are Chinese news feeds.
* **Requirement:** Detect if Chinese. If so, translate to English using a **free library** (like `deep-translator`). Do **not** use an LLM for this. Forward the result.

**Pipeline B: The Analysts (High Value)**
* **Source:** "DTpapers" (`-1001750561680`).
* **Task:** This channel posts PDF Research Reports with charts, graphs, and token unlock schedules.
* **Requirement:** Download the PDF and send it directly to **Google Gemini API (Flash 1.5 model)** using the **File API (Multimodal capabilities)**. This ensures visual data like charts and graphs are analyzed, not just text.
* **Prompt:** "Analyze this crypto research report. Extract key insights from both text and visual elements (charts, graphs, token unlock schedules). Summarize into bullet points regarding alpha and catalysts."
* **Output:** Forward the AI Summary + the original file.

## 4. The Tech Stack
* **Language:** Python
* **AI Provider:** Google Gemini API or GPT API, require guidance on which is better.
* **Telegram Identity:** I have the `API_ID` and `API_HASH` for the listener account.

## 5. Your Task
**You are the Lead Architect.**
1.  Analyze these requirements.
2.  Design the most efficient, modular Python architecture to handle this.
3.  Decide on the best file structure and async patterns (Queues vs. Event Loops) to ensure the bot doesn't freeze during network requests.
4.  Generate the complete codebase, including a `requirements.txt`, `config.py` (with the IDs above), and a `setup.sh` script for AWS deployment.

**Note:** Please anticipate potential issues with Telegram "Session" files on a cloud server and include a mechanism or instruction to handle the first-time login safely.