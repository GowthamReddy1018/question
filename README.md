# Telugu NLP Question-Answer Generator

A web application that generates question-answer pairs from input text using Python backend with FastAPI and Indic NLP library. Supports Telugu and other Indian languages.

## Features

- **Multi-Language Support**: Generates Q&A in English, Telugu, Hindi, Tamil, Malayalam, and Kannada
- **Selected Q&A Language**: Automatically translates study material when its detected language differs from the selected output language
- **Live Translation**: Real-time translation of input text to English, Hindi, Telugu, Tamil, Kannada, or Malayalam
- **Text Processing**: Clean and normalize text input for any supported language
- **Sentence Splitting**: Uses Indic NLP library for accurate sentence segmentation across languages
- **Rule-based Q&A Generation**: Creates questions based on patterns like years, locations, and keywords
- **FastAPI Backend**: RESTful API for text processing
- **Responsive Frontend**: Clean web interface with language support
- **Input Validation**: Validates text quality and length

## Project Structure

```
.
├── app.py              # FastAPI backend server
├── telugu_processor.py # Core Telugu NLP processing logic
├── requirements.txt    # Python dependencies
├── index.html         # Frontend HTML
├── style.css          # Frontend styling
├── script.js          # Frontend JavaScript (API integration)
├── test_backend.py    # Backend testing script
└── todo.md            # Implementation progress
```

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Backend Server

```bash
python app.py
```

The server will start on `http://localhost:8000` and serves the web UI itself.

### 3. Open the Frontend

Open `http://localhost:8000` in a web browser. If you serve the files separately, use:

```bash
# Using Python's built-in server
python -m http.server 8080
```

Then navigate to `http://localhost:8080`

### API keys and configuration

The application creates a unique local API key when a user creates an account. The browser stores that key locally and sends it in the `X-API-Key` header for `/generate` requests. To use Google Gemini for multilingual Q&A, set `GOOGLE_API_KEY` on the server. The Google key is never sent to the browser. Without it, the local rule-based generator is used.

Copy `.env.example` to `.env` or set the variables in the shell before starting the server. `TELUGU_QA_ALLOWED_ORIGINS` controls which separately hosted frontends may call the API. Cross-language question generation and the live translation preview use MyMemory first, then fall back to Google's public translation endpoint if MyMemory is unavailable; neither requires a key. `MYMEMORY_EMAIL` is reserved for an optional provider email if higher limits are needed.

Password recovery sends a six-digit one-time code by email. Configure `SMTP_HOST`, `SMTP_FROM`, `SMTP_USERNAME`, and `SMTP_PASSWORD` in the local `.env`; for Gmail, use `smtp.gmail.com`, port 587, and a Google App Password (not your regular account password). Set `SMTP_FROM` and `SMTP_USERNAME` to the same Gmail address. The app reloads `.env` settings when a reset is requested. The recovery form reports when SMTP is missing or cannot send, and the server log includes provider errors. Verification codes expire after 10 minutes and are locked after five failed attempts; a new code can be requested after one minute. A successful reset rotates the account API key. New accounts created in the web UI save a recovery email; older accounts need an `email` value added to their entry in `accounts.json` before they can use password recovery.

## API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /accounts` - Create an account and receive an API key
- `POST /login` - Log in and receive an API key
- `POST /generate` - Generate Q&A pairs in the selected language from study material
- `POST /test` - Test endpoint with sample text

## Usage

1. Choose the Q&A output language, or match the source language with auto-detect
2. Enter text in the textarea (minimum 20 characters)
3. Click "Generate Q&A"
4. View generated question-answer pairs

When a specific Q&A language is selected, study material is translated to that language before questions are generated. If both public translation services are unavailable, the app reports an error rather than generating questions in the wrong language.

## Sample Input

```
తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. హైదరాబాద్ ఈ రాష్ట్ర రాజధాని. రాము ఒక మంచి విద్యార్థి.
```

## Expected Output

```
1. Q: తెలంగాణ రాష్ట్రం ఏర్పడింది ఎప్పుడు?
   A: 2014

2. Q: తెలంగాణ రాష్ట్ర రాజధాని ఏది?
   A: హైదరాబాద్

3. Q: రాము ఒక మంచి గురించి ఏమిటి?
   A: రాము ఒక మంచి విద్యార్థి.
```

## Testing

Run the backend test script:

```bash
python test_backend.py
```

## Dependencies

- **FastAPI**: Web framework for building APIs
- **Uvicorn**: ASGI server for FastAPI
- **indic-nlp-library**: NLP library for Indian languages
- **nltk**: Natural Language Toolkit
- **pydantic**: Data validation

## Development Notes

- The system uses rule-based approach for Q&A generation
- Works with Telugu, Hindi, Tamil, Kannada, and other Indian languages supported by Indic NLP
- Currently supports year-based and location-based question patterns
- Can be extended with more sophisticated NLP models
- Frontend communicates with backend via REST API
- Any language with Indic NLP support can be used

## Future Enhancements

- Add more question templates and patterns for all supported languages
- Integrate machine learning models for better Q&A generation
- Add user authentication and history
- Extend support to more Indian and international languages
- Export functionality for generated Q&A pairs
- Language auto-detection feature
