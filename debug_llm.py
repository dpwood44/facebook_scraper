# Create a debug script to find and fix the LLM classifier issue

# debug_llm.py
import sys
from pathlib import Path

def find_llm_classifier_issue():
    """Find the LLM classifier initialization issue"""
    
    llm_file = Path("src/llm_classifier.py")
    
    if not llm_file.exists():
        print("LLM classifier file not found. Let's create a simple one.")
        create_simple_llm_classifier()
        return
    
    # Read the file
    with open(llm_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the problematic proxies parameter
    if 'proxies=' in content:
        print("Found 'proxies=' parameter in LLM classifier")
        print("This is causing the initialization error")
        
        # Show the problematic line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'proxies=' in line:
                print(f"Line {i+1}: {line.strip()}")
        
        # Create fixed version
        fix_llm_classifier(content)
    else:
        print("No 'proxies=' parameter found. The issue might be elsewhere.")
        print("Let's create a simple working LLM classifier.")
        create_simple_llm_classifier()

def fix_llm_classifier(content):
    """Fix the LLM classifier by removing proxies parameter"""
    
    # Remove proxies parameter
    fixed_content = content.replace('proxies=', '#proxies=')
    
    # Also remove any other problematic parameters
    problematic_patterns = [
        'proxies=None',
        'proxies={}',
        'proxies=self.proxies',
    ]
    
    for pattern in problematic_patterns:
        fixed_content = fixed_content.replace(pattern, f'#{pattern}')
    
    # Backup original
    backup_file = Path("src/llm_classifier.py.backup")
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created backup: {backup_file}")
    
    # Write fixed version
    with open("src/llm_classifier.py", 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    print("Fixed LLM classifier by commenting out proxies parameter")

def create_simple_llm_classifier():
    """Create a simple working LLM classifier"""
    
    llm_content = '''"""
Simple LLM Classifier for Facebook post detection
Compatible with OpenAI 1.3.7
"""

import os
import asyncio
from typing import Dict, Any
import openai
from openai import AsyncOpenAI

class LLMClassifier:
    """Simple LLM classifier for Facebook post detection"""
    
    def __init__(self):
        """Initialize the LLM classifier"""
        
        # Get API key from environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Initialize OpenAI client (no proxies parameter)
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Stats tracking
        self.stats = {
            'total_calls': 0,
            'estimated_cost': 0.0,
            'average_cost_per_call': 0.0
        }
    
    async def classify_post_type(self, text_content: str, html_size: int = 0) -> Dict[str, Any]:
        """Classify if content is a main post or comment"""
        
        try:
            self.stats['total_calls'] += 1
            
            # Simple prompt for classification
            prompt = f"""
Analyze this Facebook content and determine if it's a MAIN POST or COMMENT.

Content: "{text_content[:500]}"
HTML size: {html_size} bytes

MAIN POST indicators:
- Original posts by users (sales, announcements, questions)
- Contains "Shared with Private group" or similar
- Has substantial content (150+ characters)
- Contains sale prices, product descriptions

COMMENT indicators:  
- Short responses ("PM sent", "still available?", "interested")
- Ends with "LikeReply" or similar UI elements
- Brief interactions with existing posts

Respond with just: MAIN_POST or COMMENT
"""
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            # Estimate cost (rough calculation)
            tokens_used = len(prompt.split()) + 5
            estimated_cost = tokens_used * 0.000001  # Rough estimate
            self.stats['estimated_cost'] += estimated_cost
            
            if self.stats['total_calls'] > 0:
                self.stats['average_cost_per_call'] = self.stats['estimated_cost'] / self.stats['total_calls']
            
            # Parse result
            if 'MAIN_POST' in result:
                return {
                    'type': 'main_post',
                    'confidence': 80,
                    'reasoning': 'LLM classified as main post'
                }
            else:
                return {
                    'type': 'comment', 
                    'confidence': 80,
                    'reasoning': 'LLM classified as comment'
                }
                
        except Exception as e:
            print(f"LLM classification error: {e}")
            return {
                'type': 'uncertain',
                'confidence': 50,
                'reasoning': f'LLM error: {str(e)[:100]}'
            }
    
    async def verify_boundary_decision(self, main_content: str, potential_content: str) -> Dict[str, Any]:
        """Verify if potential content is a new main post"""
        
        try:
            prompt = f"""
Two Facebook content pieces:

FIRST: "{main_content[:200]}"
SECOND: "{potential_content[:200]}"

Is the SECOND content a separate MAIN POST or a COMMENT/continuation of the first?

Respond: NEW_POST or COMMENT
"""
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            return {
                'is_new_post': 'NEW_POST' in result,
                'confidence': 75
            }
            
        except Exception as e:
            return {
                'is_new_post': False,
                'confidence': 50
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return self.stats.copy()
'''
    
    # Create src directory if it doesn't exist
    src_dir = Path("src")
    src_dir.mkdir(exist_ok=True)
    
    # Write the simple LLM classifier
    with open("src/llm_classifier.py", 'w', encoding='utf-8') as f:
        f.write(llm_content)
    
    print("Created simple LLM classifier (no proxies parameter)")

if __name__ == "__main__":
    find_llm_classifier_issue()