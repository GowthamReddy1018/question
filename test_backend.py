#!/usr/bin/env python3
"""
Test script to verify the Telugu Q&A backend works correctly
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telugu_processor import TeluguProcessor

def test_telugu_processor():
    """Test the TeluguProcessor class with sample text"""
    print("Testing Telugu Q&A Processor...")
    print("=" * 50)
    
    processor = TeluguProcessor()
    
    # Test sample text
    sample_texts = [
        "తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. హైదరాబాద్ ఈ రాష్ట్ర రాజధాని.",
        "రాము ఒక మంచి విద్యార్థి. అతను ప్రతిరోజూ పాఠశాలకు వెళ్తాడు.",
        "భారతదేశం ఆసియా ఖండంలో ఉంది. ఢిల్లీ దేశ రాజధాని నగరం."
    ]
    
    for i, text in enumerate(sample_texts, 1):
        print(f"\nTest {i}:")
        print(f"Input: {text}")
        
        # Test preprocessing
        clean_text = processor.preprocess_text(text)
        print(f"Cleaned: {clean_text}")
        
        # Test sentence splitting
        sentences = processor.split_into_sentences(text)
        print(f"Sentences: {sentences}")
        
        # Test Q&A generation
        qa_pairs = processor.generate_qa_pairs(text)
        print(f"Generated {len(qa_pairs)} Q&A pairs:")
        
        for j, pair in enumerate(qa_pairs, 1):
            print(f"  {j}. Q: {pair['question']}")
            print(f"     A: {pair['answer']}")
        
        print("-" * 30)
    
    # Test validation
    print("\nTesting validation:")
    test_cases = [
        "",  # Empty text
        "short",  # Too short
        "This is English text only",  # Not enough Telugu
        sample_texts[0]  # Valid Telugu text
    ]
    
    for test_case in test_cases:
        result = processor.validate_telugu_text(test_case)
        print(f"Text: '{test_case[:30]}...' -> Valid: {result['valid']}, Error: {result['error']}")

    # Regression check for near-duplicate Q&A pairs
    near_duplicate_text = (
        "తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. "
        "తెలంగాణ రాష్ట్రం 2014లో ఏర్పడింది. "
        "హైదరాబాద్ ఈ రాష్ట్ర రాజధాని."
    )
    qa_pairs = processor.generate_qa_pairs(near_duplicate_text)
    questions = [pair['question'] for pair in qa_pairs]
    assert len(qa_pairs) == 2, f"Expected deduplicated Q&A pairs, got {len(qa_pairs)}: {questions}"

if __name__ == "__main__":
    test_telugu_processor()
