from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from email.message import EmailMessage
import hashlib
import json
import logging
import re
import smtplib
import ssl
import time
import uvicorn
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from dotenv import load_dotenv

from telugu_processor import TeluguProcessor

# Initialize FastAPI app
app = FastAPI(
    title="Telugu Q&A Generator API",
    description="API for generating question-answer pairs in a selected language from study material",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip()
allowed_origins = os.getenv(
    "TELUGU_QA_ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8080,http://127.0.0.1:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Telugu processor
processor = TeluguProcessor()
ACCOUNTS_FILE = BASE_DIR / "accounts.json"

# Request/Response models
class TextInput(BaseModel):
    text: str
    language: str = "auto"
    question_count: int = 5
    difficulty: str = "medium"
    question_type: str = "mixed"
    include_answers: bool = True

class TranslationInput(BaseModel):
    text: str
    target_language: str
    source_language: str = "auto"

class AccountInput(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    email: str
    otp: str
    new_password: str

class QAItem(BaseModel):
    question: str
    answer: str
    options: List[str] = []
    question_type: str = "short_answer"
    explanation: str = ""

class AccountResponse(BaseModel):
    success: bool
    username: str
    api_key: str
    message: str = ""

class QAResponse(BaseModel):
    success: bool
    qa_pairs: List[QAItem]
    message: str = ""
    error: str = ""

def load_accounts() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(ACCOUNTS_FILE):
        return {}

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_accounts(accounts: Dict[str, Dict[str, str]]) -> None:
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as file:
        json.dump(accounts, file, indent=2)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

def validate_account_input(username: str, password: str) -> str:
    username = username.strip()
    if len(username) < 3:
        return "Username must be at least 3 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return "Username can only contain letters, numbers, underscores, and hyphens."
    if len(password) < 6:
        return "Password must be at least 6 characters."
    return ""

def normalize_email(email: str) -> Optional[str]:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        return None
    return normalized

def smtp_configuration_error() -> Optional[str]:
    load_dotenv(BASE_DIR / ".env", override=True)
    required_settings = ("SMTP_HOST", "SMTP_FROM", "SMTP_USERNAME", "SMTP_PASSWORD")
    if any(not os.getenv(setting, "").strip() for setting in required_settings):
        return (
            "Email delivery is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_FROM, "
            "SMTP_USERNAME, and SMTP_PASSWORD in the server's .env file."
        )
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        return "SMTP_PORT must be a valid port number."
    if not 1 <= port <= 65535:
        return "SMTP_PORT must be between 1 and 65535."
    if os.getenv("SMTP_HOST", "").strip().lower() == "smtp.gmail.com":
        password = "".join(os.getenv("SMTP_PASSWORD", "").split())
        if len(password) != 16:
            return (
                "Gmail rejected the SMTP login. Set SMTP_PASSWORD to the 16-character "
                "Google App Password for SMTP_USERNAME; do not use your regular Gmail password."
            )
    return None

def smtp_is_configured() -> bool:
    return smtp_configuration_error() is None

def send_password_reset_email(email: str, otp: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = "".join(os.getenv("SMTP_PASSWORD", "").split())
    if not smtp_is_configured():
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = "Your Question Generator password reset code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "We received a request to reset your password. "
        f"Enter this verification code in the app within 10 minutes:\n\n{otp}\n\n"
        "If you did not request this, you can ignore this email."
    )

    context = ssl.create_default_context()
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10, context=context) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls(context=context)
            server.login(username, password)
            server.send_message(message)
    return True

def find_user_by_api_key(api_key: str) -> Optional[str]:
    accounts = load_accounts()
    for username, account in accounts.items():
        if secrets.compare_digest(account.get("api_key", ""), api_key):
            return username
    return None

def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Create an account or log in first.")

    username = find_user_by_api_key(x_api_key)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid API key. Please log in again.")
    return username

def generate_with_google(text: str, language: str, question_count: int, difficulty: str, question_type: str) -> List[Dict[str, Any]]:
    """Generate localized Q&A JSON with Gemini using a server-side API key."""
    language_name = {
        "en": "English", "te": "Telugu", "hi": "Hindi",
        "ta": "Tamil", "ml": "Malayalam", "ka": "Kannada",
    }.get(language, "the input language")
    prompt = (
        f"Create exactly {question_count} unique questions from the text below. "
        f"Difficulty: {difficulty}. Question type: {question_type}. "
        "For MCQ questions include exactly four options. "
        f"Write all questions, answers, options, and explanations primarily in {language_name}, "
        "using its native script when applicable. Keep proper names, numbers, and standard "
        "technical terms as needed, but do not leave the Q&A in the source language. "
        "Return only valid JSON in this exact shape: "
        '{"qa_pairs":[{"question":"...","answer":"..."}]}. '
        f"Text: {text}"
    )
    query = urlencode({"key": GOOGLE_API_KEY})
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode("utf-8")
    request = UrlRequest(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_MODEL}:generateContent?{query}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        generated_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        if generated_text.startswith("```"):
            generated_text = generated_text.replace("```json", "", 1).replace("```", "").strip()
        parsed = json.loads(generated_text)
        pairs = parsed.get("qa_pairs", []) if isinstance(parsed, dict) else parsed
        return [
            {
                "question": str(pair["question"]).strip(),
                "answer": str(pair.get("answer", "")).strip(),
                "options": pair.get("options", []),
                "question_type": pair.get("question_type", "short_answer"),
                "explanation": str(pair.get("explanation", "")).strip(),
            }
            for pair in pairs
            if pair.get("question")
        ]
    except Exception as error:
        raise HTTPException(status_code=502, detail="Google AI could not generate Q&A.") from error


def translate_with_provider(text: str, source_language: str, target_language: str) -> str:
    """Translate text in provider-sized chunks while preserving the original text on same-language requests."""
    if source_language == target_language:
        return text

    provider_codes = {"ka": "kn"}
    source_code = provider_codes.get(source_language, source_language)
    target_code = provider_codes.get(target_language, target_language)
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + 500, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end])
        start = end

    translated_chunks = []
    for chunk in chunks:
        query = urlencode({"q": chunk, "langpair": f"{source_code}|{target_code}"})
        request = UrlRequest(
            f"https://api.mymemory.translated.net/get?{query}",
            headers={"User-Agent": "Telugu-QA-Generator/1.0"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                provider_data = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise HTTPException(status_code=502, detail="Translation provider is unavailable.") from error

        response_data = provider_data.get("responseData") if isinstance(provider_data, dict) else None
        translated_text = (
            response_data.get("translatedText")
            if isinstance(response_data, dict)
            else None
        )
        if not isinstance(translated_text, str):
            raise HTTPException(status_code=502, detail="Translation provider returned no translation.")
        translated_text = translated_text.strip()
        if provider_data.get("responseStatus") != 200 or not translated_text:
            raise HTTPException(status_code=502, detail="Translation provider returned no translation.")
        translated_chunks.append(translated_text)

    return " ".join(translated_chunks)


@app.get("/")
async def root(request: Request):
    """Root endpoint returning HTML frontend for browser or API info for JSON requests"""
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept:
        if (BASE_DIR / "index.html").exists():
            return FileResponse(BASE_DIR / "index.html")
    return {
        "message": "Telugu Q&A Generator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /accounts": "Create account and receive an API key",
            "POST /login": "Log in and receive your API key",
            "POST /password-reset/request": "Email a time-limited password reset code",
            "POST /password-reset/confirm": "Set a new password with an emailed reset code",
            "POST /generate": "Generate Q&A pairs in a selected language from study material",
            "GET /health": "Check API health status"
        }
    }

@app.get("/index.html")
@app.get("/app")
async def serve_frontend():
    """Serve the Web UI directly"""
    return FileResponse(BASE_DIR / "index.html")

@app.get("/style.css")
async def serve_style():
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")

@app.get("/script.js")
async def serve_script():
    return FileResponse(BASE_DIR / "script.js", media_type="application/javascript")

@app.get("/telugu-nlp.js")
async def serve_nlp_script():
    return FileResponse(BASE_DIR / "telugu-nlp.js", media_type="application/javascript")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Telugu Q&A Generator"}

@app.post("/extract")
async def extract_content(file: UploadFile = File(...), username: str = Depends(require_api_key)):
    """Extract text from a PDF or image upload for question generation."""
    filename = (file.filename or "").lower()
    content = await file.read()
    extracted_text = ""

    if filename.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as error:
            raise HTTPException(status_code=400, detail="Could not read this PDF file.") from error
    elif file.content_type and file.content_type.startswith("image/"):
        try:
            from PIL import Image
            import io
            import pytesseract
            extracted_text = pytesseract.image_to_string(Image.open(io.BytesIO(content))).strip()
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail="Image OCR is unavailable. Install Tesseract OCR and try again.",
            ) from error
    else:
        raise HTTPException(status_code=400, detail="Upload a PDF or image file.")

    if not extracted_text:
        raise HTTPException(status_code=422, detail="No readable text was found in this file.")
    return {"success": True, "filename": file.filename, "text": extracted_text}

@app.post("/translate")
async def translate_text(input_data: TranslationInput):
    """Proxy the public translation service so browser CORS does not break previews."""
    supported_languages = {"en", "te", "hi", "ta", "ka", "ml"}
    target_language = input_data.target_language.strip().lower()
    text = input_data.text.strip()
    source_language = input_data.source_language.strip().lower()

    if target_language not in supported_languages:
        raise HTTPException(status_code=400, detail="Unsupported translation language.")
    if source_language != "auto" and source_language not in supported_languages:
        raise HTTPException(status_code=400, detail="Unsupported source language.")
    if not text:
        raise HTTPException(status_code=400, detail="Translation text is required.")

    if source_language == "auto":
        source_language = processor.detect_language(text)
    if source_language == target_language:
        return {"success": True, "translated_text": text}

    translated_text = translate_with_provider(text[:500], source_language, target_language)
    return {"success": True, "translated_text": translated_text}

@app.post("/accounts", response_model=AccountResponse)
async def create_account(account_input: AccountInput):
    """Create a local account and return its API key."""
    username = account_input.username.strip()
    password = account_input.password
    email = normalize_email(account_input.email) if account_input.email is not None else ""
    validation_error = validate_account_input(username, password)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
    if account_input.email is not None and not email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    accounts = load_accounts()
    if username in accounts:
        raise HTTPException(status_code=409, detail="Username already exists. Please log in instead.")
    if email and any(account.get("email", "").lower() == email for account in accounts.values()):
        raise HTTPException(status_code=409, detail="Email address is already linked to an account.")

    salt = secrets.token_hex(16)
    api_key = f"tqag_{secrets.token_urlsafe(32)}"
    accounts[username] = {
        "email": email,
        "password_salt": salt,
        "password_hash": hash_password(password, salt),
        "api_key": api_key,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    save_accounts(accounts)

    return AccountResponse(
        success=True,
        username=username,
        api_key=api_key,
        message="Account created. Use this API key in the X-API-Key header."
    )

@app.post("/login", response_model=AccountResponse)
async def login(account_input: AccountInput):
    """Log in to an existing local account and return its API key."""
    username = account_input.username.strip()
    accounts = load_accounts()
    account = accounts.get(username)

    if not account:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    password_hash = hash_password(account_input.password, account["password_salt"])
    if not secrets.compare_digest(password_hash, account["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    return AccountResponse(
        success=True,
        username=username,
        api_key=account["api_key"],
        message="Logged in successfully."
    )

@app.post("/password-reset/request")
async def request_password_reset(reset_request: PasswordResetRequest):
    email = normalize_email(reset_request.email)
    if not email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    configuration_error = smtp_configuration_error()
    if configuration_error:
        raise HTTPException(
            status_code=503,
            detail=configuration_error,
        )

    accounts = load_accounts()
    matching_account = next(
        (account for account in accounts.values() if account.get("email", "").lower() == email),
        None,
    )
    if matching_account:
        last_requested_at = float(matching_account.get("password_reset_requested_at", 0))
        if time.time() - last_requested_at < 60:
            return {
                "success": True,
                "message": "If an account matches and email recovery is configured, a verification code will arrive shortly.",
            }

        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_salt = secrets.token_hex(16)
        matching_account["password_reset_otp_hash"] = hashlib.sha256(
            f"{otp_salt}:{otp}".encode("utf-8")
        ).hexdigest()
        matching_account["password_reset_otp_salt"] = otp_salt
        matching_account["password_reset_expires_at"] = time.time() + 10 * 60
        matching_account["password_reset_attempts"] = 0
        matching_account["password_reset_requested_at"] = time.time()
        save_accounts(accounts)
        delivery_error = (
            "The email server could not send the verification code. Check the SMTP host, "
            "port, sender address, and server log."
        )
        try:
            sent = send_password_reset_email(email, otp)
        except smtplib.SMTPAuthenticationError:
            logging.getLogger(__name__).exception("Gmail rejected password reset SMTP credentials.")
            sent = False
            delivery_error = (
                "Gmail rejected the SMTP login. Set SMTP_USERNAME to the Gmail account that "
                "created the App Password, and set SMTP_PASSWORD to its valid 16-character "
                "Google App Password (not the regular Gmail password)."
            )
        except (smtplib.SMTPException, OSError, ValueError):
            logging.getLogger(__name__).exception("Could not send password reset email.")
            sent = False
        if not sent:
            clear_password_reset(matching_account)
            save_accounts(accounts)
            raise HTTPException(
                status_code=502,
                detail=delivery_error,
            )

    return {
        "success": True,
        "message": "If an account matches and email recovery is configured, a verification code will arrive shortly.",
    }

@app.post("/password-reset/confirm")
async def confirm_password_reset(reset: PasswordResetConfirm):
    if len(reset.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not re.fullmatch(r"\d{6}", reset.otp):
        raise HTTPException(status_code=400, detail="Enter the six-digit verification code.")

    email = normalize_email(reset.email)
    if not email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    accounts = load_accounts()
    matching_username = next(
        (username for username, account in accounts.items()
         if account.get("email", "").lower() == email),
        None,
    )
    matching_account = accounts.get(matching_username) if matching_username else None
    if matching_account:
        expires_at = float(matching_account.get("password_reset_expires_at", 0))
        attempts = int(matching_account.get("password_reset_attempts", 0))
        otp_salt = matching_account.get("password_reset_otp_salt", "")
        expected_hash = matching_account.get("password_reset_otp_hash", "")
        supplied_hash = hashlib.sha256(f"{otp_salt}:{reset.otp}".encode("utf-8")).hexdigest()
        if expires_at > time.time() and attempts < 5 and secrets.compare_digest(expected_hash, supplied_hash):
            salt = secrets.token_hex(16)
            matching_account["password_salt"] = salt
            matching_account["password_hash"] = hash_password(reset.new_password, salt)
            matching_account["api_key"] = f"tqag_{secrets.token_urlsafe(32)}"
            clear_password_reset(matching_account)
            save_accounts(accounts)
            return {"success": True, "message": "Your password has been updated."}

        if expires_at > time.time() and attempts < 5:
            matching_account["password_reset_attempts"] = attempts + 1
            if attempts + 1 >= 5:
                clear_password_reset(matching_account)
            save_accounts(accounts)

    raise HTTPException(status_code=400, detail="The verification code is invalid or has expired.")


def clear_password_reset(account: Dict[str, Any]) -> None:
    for key in (
        "password_reset_otp_hash",
        "password_reset_otp_salt",
        "password_reset_expires_at",
        "password_reset_attempts",
        "password_reset_requested_at",
    ):
        account.pop(key, None)
    account.pop("password_reset_token_hash", None)

@app.post("/generate", response_model=QAResponse)
async def generate_qa(input_data: TextInput, username: str = Depends(require_api_key)):
    """
    Generate question-answer pairs in the selected language from study material.
    
    Args:
        input_data: TextInput containing source text and the desired Q&A language.
        
    Returns:
        QAResponse with generated Q&A pairs or error message
    """
    try:
        # Validate input text
        source_language = processor.detect_language(input_data.text)
        validation = processor.validate_telugu_text(input_data.text, source_language)
        if not validation["valid"]:
            return QAResponse(
                success=False,
                qa_pairs=[],
                error=validation["error"]
            )

        selected_language = input_data.language
        if selected_language == "auto":
            selected_language = source_language
        elif selected_language not in processor.QUESTION_TEMPLATES:
            return QAResponse(
                success=False,
                qa_pairs=[],
                error="Unsupported output language selected",
            )
        prepared_text = translate_with_provider(
            input_data.text,
            source_language,
            selected_language,
        )

        # Use Gemini when configured; retain the local generator as a development fallback.
        if GOOGLE_API_KEY:
            qa_pairs = generate_with_google(
                prepared_text,
                selected_language,
                input_data.question_count,
                input_data.difficulty,
                input_data.question_type,
            )
        else:
            qa_pairs = processor.generate_qa_pairs(prepared_text, selected_language)
            qa_pairs = qa_pairs[:input_data.question_count]
        
        if not qa_pairs:
            return QAResponse(
                success=False,
                qa_pairs=[],
                error="ప్రశ్నలను జనరేట్ చేయడంలో విఫలమైంది. దయచేసి వేరే పేరాను ప్రయత్నించండి."
            )
        
        # Convert to QAItem objects
        qa_items = [QAItem(
            question=pair["question"],
            answer=pair.get("answer", ""),
            options=pair.get("options", []),
            question_type=pair.get("question_type", "short_answer"),
            explanation=pair.get("explanation", ""),
        ) for pair in qa_pairs]
        
        return QAResponse(
            success=True,
            qa_pairs=qa_items,
            message=f"విజయవంతంగా {len(qa_items)} ప్రశ్నలు జనరేట్ చేయబడ్డాయి"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ప్రాసెస్ చేయడంలో లోపం ఏర్పడింది: {str(e)}"
        )

@app.post("/test")
async def test_endpoint():
    """Test endpoint with sample Telugu text"""
    sample_text = "తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. హైదరాబాద్ ఈ రాష్ట్ర రాజధాని. రాము ఒక మంచి విద్యార్థి."
    
    try:
        qa_pairs = processor.generate_qa_pairs(sample_text)
        qa_items = [QAItem(question=pair["question"], answer=pair["answer"]) for pair in qa_pairs]
        
        return {
            "input_text": sample_text,
            "qa_pairs": qa_items,
            "total_questions": len(qa_items)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )

if __name__ == "__main__":
    # Run the FastAPI application
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes for development
    )
