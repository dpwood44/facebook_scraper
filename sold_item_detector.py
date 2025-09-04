"""
Sold Items Detection System for Facebook Group Scraper
Identifies sold items by analyzing both main posts and comments
"""

import re
from typing import Dict, List, Tuple, Optional
from loguru import logger

class SoldItemDetector:
    """Comprehensive sold item detection system"""
    
    def __init__(self):
        # Main post sold indicators
        self.main_post_sold_patterns = {
            'explicit_sold': [
                r'\bsold\b', r'\bspo\b', r'sold pending',
                r'no longer available', r'taken\b', r'gone\b',
                r'sold to\b', r'pending payment', r'payment pending'
            ],
            'edit_patterns': [
                r'edit:?\s*sold', r'update:?\s*sold',
                r'sold\s*-\s*edit', r'sold\s*\*\*'
            ],
            'crossed_out': [
                r'~~.*sold.*~~', r'~~sold~~',
                r'\*\*sold\*\*'  # Bold sold
            ]
        }
        
        # Comment patterns indicating sale completion
        self.comment_sold_patterns = {
            'buyer_claim': [
                r"i'?ll take it", r"i'?ll take", r"mine\b",
                r"dibs\b", r"claimed?\b", r"call dibs",
                r"i want it", r"interested\b"
            ],
            'seller_confirmation': [
                r"it'?s yours", r"you got it", r"yours\b",
                r"sold to you", r"pm me", r"message me",
                r"pending to you", r"you'?re first"
            ],
            'transaction_terms': [
                r"paypal ready", r"pp ready", r"cash ready",
                r"pending pickup", r"ppu\b", r"pending payment",
                r"payment received", r"shipped to"
            ],
            'final_status': [
                r"sold\b", r"gone\b", r"taken\b",
                r"deal done", r"transaction complete"
            ]
        }
        
        # Negotiation patterns (indicate serious interest)
        self.negotiation_patterns = [
            r"what'?s the lowest", r"would you take",
            r"firm on price", r"negotiate",
            r"best price", r"deal at"
        ]
        
        # Time-sensitive patterns
        self.urgency_patterns = [
            r"first come first served", r"first to respond",
            r"quick sale", r"needs to go"
        ]

    def analyze_sold_status(self, post_data: Dict) -> Dict:
        """
        Analyze if an item was sold based on post content and comments
        
        Args:
            post_data: Complete post data including comments
            
        Returns:
            Dictionary with sold analysis results
        """
        analysis = {
            'is_sold': False,
            'confidence': 0,
            'sold_indicators': [],
            'buyer_identified': False,
            'buyer_info': '',
            'sale_timeline': [],
            'negotiation_detected': False,
            'final_price': None,
            'sale_method': 'unknown'  # 'main_post', 'comments', 'both'
        }
        
        # Analyze main post
        main_post_analysis = self._analyze_main_post_sold(post_data.get('text', ''))
        
        # Analyze comments
        comments_analysis = self._analyze_comments_sold(post_data.get('comments', []))
        
        # Combine analyses
        analysis = self._combine_sold_analysis(analysis, main_post_analysis, comments_analysis)
        
        # Determine final sold status
        analysis['is_sold'] = analysis['confidence'] >= 60  # 60% confidence threshold
        
        logger.debug(f"Sold analysis: confidence={analysis['confidence']}%, sold={analysis['is_sold']}")
        
        return analysis

    def _analyze_main_post_sold(self, post_text: str) -> Dict:
        """Analyze main post for sold indicators"""
        analysis = {
            'main_post_sold': False,
            'main_post_confidence': 0,
            'main_post_indicators': []
        }
        
        if not post_text:
            return analysis
        
        text_lower = post_text.lower()
        
        # Check explicit sold patterns
        for pattern in self.main_post_sold_patterns['explicit_sold']:
            if re.search(pattern, text_lower):
                analysis['main_post_confidence'] += 40
                analysis['main_post_indicators'].append(f"Explicit: {pattern}")
        
        # Check edit patterns (higher confidence)
        for pattern in self.main_post_sold_patterns['edit_patterns']:
            if re.search(pattern, text_lower):
                analysis['main_post_confidence'] += 50
                analysis['main_post_indicators'].append(f"Edit: {pattern}")
        
        # Check formatting indicators
        for pattern in self.main_post_sold_patterns['crossed_out']:
            if re.search(pattern, post_text):  # Don't lowercase for formatting
                analysis['main_post_confidence'] += 45
                analysis['main_post_indicators'].append(f"Formatted: {pattern}")
        
        analysis['main_post_sold'] = analysis['main_post_confidence'] >= 40
        
        return analysis

    def _analyze_comments_sold(self, comments: List[Dict]) -> Dict:
        """Analyze comments for sale completion indicators"""
        analysis = {
            'comments_sold': False,
            'comments_confidence': 0,
            'buyer_claim_found': False,
            'seller_confirm_found': False,
            'transaction_evidence': False,
            'comment_timeline': []
        }
        
        if not comments:
            return analysis
        
        # Get original post author for seller confirmation detection
        post_author = self._get_post_author(comments)
        
        buyer_candidates = []
        seller_confirmations = []
        
        for i, comment in enumerate(comments):
            comment_text = comment.get('text', '').lower()
            comment_author = comment.get('author', '')
            
            # Track timeline
            timeline_entry = {
                'order': i + 1,
                'author': comment_author,
                'text': comment.get('text', '')[:100],
                'indicators': []
            }
            
            # Check for buyer claims
            for pattern in self.comment_sold_patterns['buyer_claim']:
                if re.search(pattern, comment_text):
                    analysis['buyer_claim_found'] = True
                    analysis['comments_confidence'] += 25
                    buyer_candidates.append({
                        'author': comment_author,
                        'comment': comment_text,
                        'position': i + 1
                    })
                    timeline_entry['indicators'].append('buyer_claim')
                    break
            
            # Check for seller confirmations
            for pattern in self.comment_sold_patterns['seller_confirmation']:
                if re.search(pattern, comment_text):
                    # Higher confidence if from original poster
                    confidence_boost = 35 if comment_author == post_author else 20
                    analysis['comments_confidence'] += confidence_boost
                    analysis['seller_confirm_found'] = True
                    seller_confirmations.append({
                        'author': comment_author,
                        'comment': comment_text,
                        'position': i + 1
                    })
                    timeline_entry['indicators'].append('seller_confirm')
                    break
            
            # Check for transaction evidence
            for pattern in self.comment_sold_patterns['transaction_terms']:
                if re.search(pattern, comment_text):
                    analysis['transaction_evidence'] = True
                    analysis['comments_confidence'] += 30
                    timeline_entry['indicators'].append('transaction')
                    break
            
            # Check for final status
            for pattern in self.comment_sold_patterns['final_status']:
                if re.search(pattern, comment_text):
                    analysis['comments_confidence'] += 25
                    timeline_entry['indicators'].append('final_status')
                    break
            
            # Check for negotiation (indicates serious intent)
            for pattern in self.negotiation_patterns:
                if re.search(pattern, comment_text):
                    analysis['comments_confidence'] += 10
                    timeline_entry['indicators'].append('negotiation')
                    break
            
            if timeline_entry['indicators']:
                analysis['comment_timeline'].append(timeline_entry)
        
        # Bonus points for complete buyer-seller interaction
        if analysis['buyer_claim_found'] and analysis['seller_confirm_found']:
            analysis['comments_confidence'] += 20
        
        analysis['comments_sold'] = analysis['comments_confidence'] >= 40
        
        return analysis

    def _combine_sold_analysis(self, base_analysis: Dict, main_analysis: Dict, comments_analysis: Dict) -> Dict:
        """Combine main post and comments analysis"""
        
        # Combine confidence scores
        total_confidence = main_analysis['main_post_confidence'] + comments_analysis['comments_confidence']
        
        # Cap at 100%
        base_analysis['confidence'] = min(100, total_confidence)
        
        # Combine indicators
        base_analysis['sold_indicators'].extend(main_analysis['main_post_indicators'])
        
        # Add comments insights
        if comments_analysis['buyer_claim_found']:
            base_analysis['buyer_identified'] = True
            base_analysis['sold_indicators'].append("Buyer claim in comments")
        
        if comments_analysis['seller_confirm_found']:
            base_analysis['sold_indicators'].append("Seller confirmation in comments")
        
        if comments_analysis['transaction_evidence']:
            base_analysis['sold_indicators'].append("Transaction evidence in comments")
        
        # Determine sale method
        main_sold = main_analysis['main_post_sold']
        comments_sold = comments_analysis['comments_sold']
        
        if main_sold and comments_sold:
            base_analysis['sale_method'] = 'both'
        elif main_sold:
            base_analysis['sale_method'] = 'main_post'
        elif comments_sold:
            base_analysis['sale_method'] = 'comments'
        
        # Add timeline
        base_analysis['sale_timeline'] = comments_analysis['comment_timeline']
        
        return base_analysis

    def _get_post_author(self, comments: List[Dict]) -> str:
        """Try to identify the original post author from comments"""
        # This is a heuristic - the author who replies most or first might be OP
        if not comments:
            return ""
        
        # Simple heuristic: assume first commenter might be OP if they're responding to questions
        authors = [c.get('author', '') for c in comments if c.get('author')]
        if authors:
            return authors[0]  # Could be improved with better logic
        
        return ""