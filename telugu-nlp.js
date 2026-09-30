// Telugu NLP Utilities for Question-Answer Generation

class TeluguNLP {
    constructor() {
        this.teluguVowels = 'అఆఇఈఉఊఋఌఎఏఐఒఓఔ';
        this.teluguConsonants = 'కఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరఱలళవశషసహ';
        this.teluguDigits = '౦౧౨౩౪౫౬౭౮౯';
        this.teluguSymbols = 'ఁంః';
    }

    // Check if character is Telugu
    isTeluguChar(char) {
        const code = char.charCodeAt(0);
        return (code >= 0x0C00 && code <= 0x0C7F) || 
               (code >= 0x1CD0 && code <= 0x1CFF);
    }

    // Tokenize Telugu text into words
    tokenize(text) {
        // Split by spaces and punctuation, but keep Telugu words intact
        const tokens = text.split(/[\s\u200B-\u200D\uFEFF]+|[,.;!?()'"-]+/);
        return tokens.filter(token => token.trim() !== '');
    }

    // Split Telugu text into sentences
    splitIntoSentences(text) {
        // Telugu sentence boundaries: ।, ?, !, .
        const sentenceDelimiters = /[।?!\.]+/;
        const sentences = text.split(sentenceDelimiters);
        return sentences.filter(sentence => sentence.trim() !== '');
    }

    // Extract keywords from Telugu text
    extractKeywords(text, maxKeywords = 5) {
        const words = this.tokenize(text);
        const wordFrequency = {};
        
        words.forEach(word => {
            if (this.isTeluguWord(word)) {
                wordFrequency[word] = (wordFrequency[word] || 0) + 1;
            }
        });

        // Sort by frequency and get top keywords
        return Object.entries(wordFrequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, maxKeywords)
            .map(entry => entry[0]);
    }

    // Check if word is a Telugu word
    isTeluguWord(word) {
        return word.split('').every(char => this.isTeluguChar(char)) && word.length > 1;
    }

    // Remove stop words from Telugu text
    removeStopWords(text) {
        const teluguStopWords = [
            'మరియు', 'కానీ', 'అయితే', 'కాబట్టి', 'అందువలన', 
            'అప్పటికి', 'ఇప్పుడు', 'అప్పుడు', 'ఇక్కడ', 'అక్కడ',
            'ఈ', 'ఆ', 'అది', 'ఇది', 'వారు', 'మేము', 'నేను', 'అవి'
        ];

        const words = this.tokenize(text);
        return words.filter(word => !teluguStopWords.includes(word)).join(' ');
    }

    // Generate questions from Telugu sentences
    generateQuestionsFromSentence(sentence) {
        const questions = [];
        const words = this.tokenize(sentence);
        
        if (words.length < 3) return questions;

        // Question templates for different sentence types
        const questionTemplates = [
            {
                pattern: /(.+) (.+) చేస్తున్నారు/,
                question: "ఎవరు {1} చేస్తున్నారు?",
                answer: "{2}"
            },
            {
                pattern: /(.+) (.+) లో/,
                question: "ఏది {1} లో?",
                answer: "{2}"
            },
            {
                pattern: /(.+) (.+) కు/,
                question: "ఎవరికి {1}?",
                answer: "{2}"
            },
            {
                pattern: /(.+) (.+) గురించి/,
                question: "ఏమి {1} గురించి?",
                answer: "{2}"
            },
            {
                pattern: /(.+) (.+) అని/,
                question: "ఏమి {1} అని?",
                answer: "{2}"
            }
        ];

        // Try to match sentence with question templates
        for (const template of questionTemplates) {
            const match = sentence.match(template.pattern);
            if (match) {
                let question = template.question;
                let answer = template.answer;
                
                // Replace placeholders with actual words
                for (let i = 1; i < match.length; i++) {
                    question = question.replace(`{${i}}`, match[i]);
                    answer = answer.replace(`{${i}}`, match[i]);
                }
                
                questions.push({
                    question: question,
                    answer: answer,
                    confidence: 0.8
                });
            }
        }

        // Fallback: Generate simple questions based on keywords
        if (questions.length === 0) {
            const keywords = this.extractKeywords(sentence, 2);
            if (keywords.length > 0) {
                questions.push({
                    question: `ఏమి ${keywords[0]} గురించి?`,
                    answer: sentence,
                    confidence: 0.5
                });
            }
        }

        return questions;
    }

    // Generate questions from entire paragraph
    generateQAFromParagraph(paragraph) {
        const sentences = this.splitIntoSentences(paragraph);
        const allQuestions = [];

        sentences.forEach(sentence => {
            const sentenceQuestions = this.generateQuestionsFromSentence(sentence.trim());
            allQuestions.push(...sentenceQuestions);
        });

        // Sort by confidence and remove duplicates
        const uniqueQuestions = [];
        const seenQuestions = new Set();

        allQuestions
            .sort((a, b) => b.confidence - a.confidence)
            .forEach(qa => {
                const key = qa.question + qa.answer;
                if (!seenQuestions.has(key)) {
                    seenQuestions.add(key);
                    uniqueQuestions.push(qa);
                }
            });

        return uniqueQuestions.slice(0, 10); // Return top 10 questions
    }

    // Validate Telugu text input
    validateTeluguText(text) {
        if (!text || text.trim().length === 0) {
            return { valid: false, error: "దయచేసి తెలుగు పేరాను నమోదు చేయండి" };
        }

        if (text.trim().length < 20) {
            return { valid: false, error: "పేరా కనీసం 20 అక్షరాలు ఉండాలి" };
        }

        // Check if text contains Telugu characters
        const teluguChars = text.split('').filter(char => this.isTeluguChar(char));
        if (teluguChars.length / text.length < 0.5) {
            return { valid: false, error: "దయచేసి ప్రధానంగా తెలుగు అక్షరాలు మాత్రమే ఉపయోగించండి" };
        }

        return { valid: true, error: null };
    }
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TeluguNLP;
}
