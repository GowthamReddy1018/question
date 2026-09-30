import re
from difflib import SequenceMatcher
from indicnlp.tokenize import sentence_tokenize
import nltk
from typing import List, Dict

class TeluguProcessor:
    def __init__(self):
        # Support multiple Indian languages
        self.SUPPORTED_LANGUAGES = {
            'en': {'name': 'English', 'range': None},
            'te': {'name': 'Telugu', 'range': (0x0C00, 0x0C7F)},
            'hi': {'name': 'Hindi', 'range': (0x0900, 0x097F)},
            'ta': {'name': 'Tamil', 'range': (0x0B80, 0x0BFF)},
            'ka': {'name': 'Kannada', 'range': (0x0C80, 0x0CFF)},
            'ml': {'name': 'Malayalam', 'range': (0x0D00, 0x0D7F)},
            'bn': {'name': 'Bengali', 'range': (0x0980, 0x09FF)},
            'gu': {'name': 'Gujarati', 'range': (0x0A80, 0x0AFF)},
            'or': {'name': 'Odia', 'range': (0x0B00, 0x0B7F)},
        }
        
        self.LANG = 'te'  # Default language
        self.QUESTION_TEMPLATES = {
            'en': {'when': 'When did {subject} happen?', 'about': 'What is {subject} about?'},
            'te': {'when': '{subject} ఎప్పుడు?', 'about': '{subject} గురించి ఏమిటి?'},
            'hi': {'when': '{subject} कब हुआ?', 'about': '{subject} के बारे में क्या है?'},
            'ta': {'when': '{subject} எப்போது நடந்தது?', 'about': '{subject} பற்றி என்ன?'},
            'ka': {'when': '{subject} ಯಾವಾಗ ಸಂಭವಿಸಿತು?', 'about': '{subject} ಬಗ್ಗೆ ಏನು?'},
            'ml': {'when': '{subject} എപ്പോൾ നടന്നു?', 'about': '{subject}യെക്കുറിച്ച് എന്താണ്?'},
        }
        
        # Download NLTK data if not already present
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')

    def detect_language(self, text: str) -> str:
        """Detect the Indian language from the input text."""
        if not text:
            return 'te'  # Default to Telugu
        
        # Count characters in each language range
        language_scores = {}
        
        for lang_code, lang_info in self.SUPPORTED_LANGUAGES.items():
            if lang_info['range'] is None:
                continue
            char_range = lang_info['range']
            chars = re.findall(rf'[\u{char_range[0]:04X}-\u{char_range[1]:04X}]', text)
            language_scores[lang_code] = len(chars)
        
        # Return the language with the most characters
        detected_lang = max(language_scores, key=language_scores.get)
        if language_scores[detected_lang] > 0:
            return detected_lang

        return 'en' if re.search(r'[A-Za-z]', text) else 'te'

    def preprocess_text(self, text: str) -> str:
        """Clean and normalize Telugu text."""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize Telugu punctuation
        text = text.replace('॥', '।')  # Normalize double danda to single danda
        
        return text

    def split_into_sentences(self, text: str) -> List[str]:
        """Split Telugu text into sentences using Indic NLP."""
        clean_text = self.preprocess_text(text)
        if not clean_text:
            return []
            
        try:
            sentences = sentence_tokenize.sentence_split(clean_text, self.LANG)
            return [sentence.strip() for sentence in sentences if sentence.strip()]
        except Exception as e:
            # Fallback to simple punctuation-based splitting
            sentences = re.split(r'[।?!\.]+', clean_text)
            return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _normalize_for_dedupe(self, text: str) -> str:
        """Normalize text to catch whitespace and punctuation-only duplicates."""
        if not text:
            return ""

        normalized = re.sub(r'\s+', ' ', text.strip())
        normalized = normalized.replace('।', '.').replace('!', '.').replace('?', '.')
        normalized = re.sub(r'\.+', '.', normalized)
        normalized = re.sub(r'\s*\.\s*', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _is_duplicate_pair(self, left: Dict[str, str], right: Dict[str, str]) -> bool:
        """Check whether two Q&A pairs are effectively the same after normalization."""
        left_question = self._normalize_for_dedupe(left.get("question", ""))
        right_question = self._normalize_for_dedupe(right.get("question", ""))
        left_answer = self._normalize_for_dedupe(left.get("answer", ""))
        right_answer = self._normalize_for_dedupe(right.get("answer", ""))

        if not left_question or not right_question:
            return left_answer == right_answer

        question_similarity = SequenceMatcher(None, left_question, right_question).ratio()
        answer_similarity = SequenceMatcher(None, left_answer, right_answer).ratio()
        same_question = question_similarity >= 0.90
        same_answer = answer_similarity >= 0.90 or left_answer == right_answer

        return same_question and same_answer

    def generate_qa_pairs(self, paragraph: str, language: str = 'auto') -> List[Dict[str, str]]:
        """Generate simple Q&A pairs from an Indian language paragraph using rule-based approach."""
        qna_pairs = []

        # Step 1: Detect language and preprocess
        detected_lang = self.detect_language(paragraph) if language == 'auto' else language
        if detected_lang not in self.QUESTION_TEMPLATES:
            return qna_pairs
        self.LANG = detected_lang
        templates = self.QUESTION_TEMPLATES[detected_lang]
        clean_text = self.preprocess_text(paragraph)
        if not clean_text:
            return qna_pairs

        # Step 2: Sentence splitting
        sentences = self.split_into_sentences(clean_text)

        # Step 3: Rule-based question generation
        for sent in sentences:
            # Rule 1: Year-based questions
            year_match = re.search(r'\d{4}', sent)
            if year_match:
                year = year_match.group()
                # Remove the year from the sentence to form the question
                question_base = re.sub(r'\d{4}', '', sent).strip()
                question_base = re.sub(r'\s+', ' ', question_base)
                if question_base:
                    question = templates['when'].format(subject=question_base)
                    qna_pairs.append({"question": question, "answer": year})

            # Rule 2: Location-based questions (Hyderabad example)
            if detected_lang == 'te' and "హైదరాబాద్" in sent:
                question = "తెలంగాణ రాష్ట్ర రాజధాని ఏది?"
                qna_pairs.append({"question": question, "answer": "హైదరాబాద్"})

            # Rule 3: Person/name-based questions
            name_patterns = [
                r'(\w+) (\w+) చేస్తున్నారు',
                r'(\w+) (\w+) అని',
                r'(\w+) (\w+) గురించి'
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, sent)
                if match:
                    subject = match.group(1)
                    action = match.group(2)
                    question = f"{subject} ఏమి చేస్తున్నారు?"
                    qna_pairs.append({"question": question, "answer": sent})

            # Rule 4: Generic fallback - create questions from important words
            if not any([year_match, detected_lang == 'te' and "హైదరాబాద్" in sent]):
                words = sent.split()
                if len(words) >= 3:
                    # Take first few words as subject
                    subject = " ".join(words[:min(3, len(words))])
                    question = templates['about'].format(subject=subject)
                    qna_pairs.append({"question": question, "answer": sent})

        # Remove duplicates while preserving order, including near-duplicate variants
        unique_pairs = []
        for pair in qna_pairs:
            is_duplicate = False
            for existing in unique_pairs:
                if self._is_duplicate_pair(existing, pair):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_pairs.append(pair)

        return unique_pairs

    def validate_telugu_text(self, text: str, language: str = 'auto') -> Dict[str, any]:
        """Validate Indian language text input."""
        if not text or not text.strip():
            return {"valid": False, "error": "దయచేసి పేరాను నమోదు చేయండి"}

        clean_text = text.strip()
        
        if len(clean_text) < 20:
            return {"valid": False, "error": "పేరా కనీసం 20 అక్షరాలు ఉండాలి"}

        if language != 'auto' and language not in self.QUESTION_TEMPLATES:
            return {"valid": False, "error": "Unsupported language selected"}

        detected_lang = self.detect_language(clean_text) if language == 'auto' else language
        self.LANG = detected_lang

        if detected_lang == 'en':
            english_chars = re.findall(r'[A-Za-z]', clean_text)
            if len(english_chars) / len(clean_text) < 0.3:
                return {"valid": False, "error": "Please enter mainly English text"}
            return {"valid": True, "error": None}
        
        # Check if text contains characters from supported Indian languages
        all_ranges = []
        for lang_code, lang_info in self.SUPPORTED_LANGUAGES.items():
            if lang_code != 'en':
                all_ranges.append(lang_info['range'])
        
        # Build regex pattern for all supported language ranges
        pattern = '|'.join([rf'[\u{r[0]:04X}-\u{r[1]:04X}]' for r in all_ranges])
        indian_lang_chars = re.findall(pattern, clean_text)
        indian_lang_ratio = len(indian_lang_chars) / len(clean_text) if clean_text else 0
        
        if indian_lang_ratio < 0.3:
            return {"valid": False, "error": "Please enter mainly the selected Indian language"}

        return {"valid": True, "error": None}

# Example usage and testing
if __name__ == "__main__":
    processor = TeluguProcessor()
    
    # Test with Telugu sample text
    print("=" * 60)
    print("Telugu Language Test:")
    print("=" * 60)
    telugu_text = "తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. హైదరాబాద్ ఈ రాష్ట్ర రాజధాని."
    print("Input text:", telugu_text)
    print("\nGenerated Q&A pairs:")
    qa_pairs = processor.generate_qa_pairs(telugu_text)
    for i, pair in enumerate(qa_pairs, 1):
        print(f"{i}. Q: {pair['question']}")
        print(f"   A: {pair['answer']}")
    
    # Test with Hindi sample text
    print("\n" + "=" * 60)
    print("Hindi Language Test:")
    print("=" * 60)
    hindi_text = "भारत 2024 में एक महान देश है। दिल्ली भारत की राजधानी है।"
    print("Input text:", hindi_text)
    print("\nGenerated Q&A pairs:")
    qa_pairs = processor.generate_qa_pairs(hindi_text)
    for i, pair in enumerate(qa_pairs, 1):
        print(f"{i}. Q: {pair['question']}")
        print(f"   A: {pair['answer']}")
    
    # Test with Tamil sample text
    print("\n" + "=" * 60)
    print("Tamil Language Test:")
    print("=" * 60)
    tamil_text = "இந்தியா 2024 ஆம் ஆண்டில் மிகச்சிறந்த நாடு. சென்னை தமிழ்நாட்டின் தலைநகரம்."
    print("Input text:", tamil_text)
    print("\nGenerated Q&A pairs:")
    qa_pairs = processor.generate_qa_pairs(tamil_text)
    for i, pair in enumerate(qa_pairs, 1):
        print(f"{i}. Q: {pair['question']}")
        print(f"   A: {pair['answer']}")
    print()
