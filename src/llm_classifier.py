import os
import asyncio
import json
from typing import Dict, Optional
from openai import AsyncOpenAI
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class LLMClassifier:
    def __init__(self, model="gpt-4o-mini", max_retries=2):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.max_retries = max_retries
        self.call_count = 0
        self.total_cost = 0.0
        
        # Pricing for gpt-4o-mini (as of 2024)
        self.input_cost_per_1k = 0.00015  # $0.15 per 1M tokens
        self.output_cost_per_1k = 0.0006   # $0.60 per 1M tokens
        
    async def classify_post_type(self, text_content: str, html_size: int = 0) -> Dict:
        """Classify if content is a main post or comment using LLM"""
        
        # Truncate text to save costs
        truncated_text = text_content[:500] if len(text_content) > 500 else text_content
        
        prompt = f"""Analyze this Facebook content and determine if it's a main post or a comment.

CONTENT: "{truncated_text}"

CONTEXT:
- Main posts are original content (sales, questions, discussions)
- Comments are responses to posts (short replies, "interested", "pm sent")
- Main posts often have prices, detailed descriptions, sale terms
- Comments often end with "LikeReply" or are very brief responses

Respond with JSON only:
{{"type": "main_post" or "comment", "confidence": 0-100, "reasoning": "brief explanation"}}"""

        try:
            self.call_count += 1
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            
            # Calculate approximate cost
            input_tokens = len(prompt) / 4  # Rough estimate
            output_tokens = len(response.choices[0].message.content) / 4
            cost = (input_tokens * self.input_cost_per_1k / 1000) + (output_tokens * self.output_cost_per_1k / 1000)
            self.total_cost += cost
            
            # Parse response
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(result_text)
            
            logger.debug(f"LLM Classification: {result['type']} ({result['confidence']}%) - {result.get('reasoning', '')}")
            logger.debug(f"LLM call #{self.call_count}, estimated cost: ${cost:.6f}")
            
            return {
                'type': result['type'],
                'confidence': int(result['confidence']),
                'reasoning': result.get('reasoning', ''),
                'method': 'llm'
            }
            
        except Exception as e:
            logger.error(f"LLM classification failed: {str(e)[:100]}")
            return {
                'type': 'uncertain',
                'confidence': 0,
                'reasoning': f'LLM error: {str(e)[:50]}',
                'method': 'llm_error'
            }
    
    async def verify_boundary_decision(self, current_content: str, next_content: str) -> Dict:
        """Use LLM to verify if next content is a new main post or continuation"""
        
        current_preview = current_content[:200]
        next_preview = next_content[:300]
        
        prompt = f"""I'm analyzing Facebook content to detect post boundaries.

CURRENT POST: "{current_preview}"

NEXT CONTENT: "{next_preview}"

Is the NEXT CONTENT a new main post or part of the current post's comments?

NEW MAIN POST indicators:
- Original sales/discussion content
- Has price, detailed description
- Author posting something new

COMMENT indicators:
- Response to current post
- Short replies like "interested", "still available?"
- Ends with UI elements like "LikeReply"

Respond with JSON only:
{{"is_new_post": true/false, "confidence": 0-100, "reasoning": "brief explanation"}}"""

        try:
            self.call_count += 1
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(result_text)
            
            logger.debug(f"LLM Boundary Check: {'New Post' if result['is_new_post'] else 'Comment'} ({result['confidence']}%)")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM boundary verification failed: {str(e)[:100]}")
            return {'is_new_post': False, 'confidence': 0, 'reasoning': f'Error: {str(e)[:50]}'}
    
    def get_stats(self):
        """Return usage statistics"""
        return {
            'total_calls': self.call_count,
            'estimated_cost': round(self.total_cost, 6),
            'average_cost_per_call': round(self.total_cost / max(self.call_count, 1), 6)
        }