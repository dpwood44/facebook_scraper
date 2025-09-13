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

    def analyze_sold_status(self, post_data: Dict, deep_mode: bool = False) -> Dict:
        """
        Analyze if an item was sold based on post content and comments
        
        Args:
            post_data: Complete post data including comments
            deep_mode: If True, use stricter analysis for deep detection mode
            
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
            'sale_method': 'unknown',  # 'main_post', 'comments', 'both'
            'would_be_missed_by_search': False  # NEW: for deep detection
        }
        
        # Analyze main post
        main_post_analysis = self._analyze_main_post_sold(post_data.get('text', ''))
        
        # Analyze comments
        comments_analysis = self._analyze_comments_sold(post_data.get('comments', []))
        
        # Combine analyses
        analysis = self._combine_sold_analysis(analysis, main_post_analysis, comments_analysis)
        
        # DEEP MODE ENHANCEMENTS
        if deep_mode:
            # Check if this would be missed by Facebook search
            # (sold only in comments, not in main post)
            if comments_analysis['comments_sold'] and not main_post_analysis['main_post_sold']:
                analysis['would_be_missed_by_search'] = True
                analysis['sold_indicators'].append("💎 Comment-only sale (Facebook search would miss)")
            
            # Look for subtle sale patterns that Facebook might miss
            self._detect_subtle_sale_patterns(post_data, analysis)
            
            # Use different confidence threshold for deep mode
            # More lenient since we want to catch edge cases
            analysis['is_sold'] = analysis['confidence'] >= 50  # Lower than normal 60%
        else:
            # Normal mode - standard threshold
            analysis['is_sold'] = analysis['confidence'] >= 60
        
        logger.debug(f"Sold analysis (deep={deep_mode}): confidence={analysis['confidence']}%, "
                    f"sold={analysis['is_sold']}, method={analysis['sale_method']}")
        
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

    def _analyze_comments_sold_deep(self, comments: List[Dict], post_author: str = '') -> Dict:
        """Enhanced comment analysis for deep detection mode"""
        
        analysis = self._analyze_comments_sold(comments)  # Start with base analysis
        
        if not comments:
            return analysis
        
        # Additional patterns for deep detection
        indirect_sale_patterns = [
            r'check your pm',
            r'messaged you',
            r'sent you a message',
            r'details in pm',
            r'let\'s take this offline',
        ]
        
        # Track conversation flow more carefully
        conversation_flow = []
        last_author = None
        back_and_forth_count = 0
        
        for i, comment in enumerate(comments):
            comment_text = comment.get('text', '').lower()
            comment_author = comment.get('author', '')
            
            # Check for indirect sale indicators
            for pattern in indirect_sale_patterns:
                if re.search(pattern, comment_text):
                    analysis['comments_confidence'] += 15
                    analysis['comment_timeline'].append({
                        'order': i + 1,
                        'author': comment_author,
                        'indicators': ['moved_to_pm']
                    })
            
            # Track back-and-forth (indicates negotiation)
            if comment_author != last_author:
                back_and_forth_count += 1
                last_author = comment_author
        
        # Back-and-forth conversation suggests active negotiation
        if back_and_forth_count >= 3:
            analysis['comments_confidence'] += 15
            analysis['negotiation_detected'] = True
        
        # If conversation suddenly stops after negotiation, likely sold
        if analysis['negotiation_detected'] and len(comments) < 10:
            analysis['comments_confidence'] += 10
            
        return analysis


    def _detect_subtle_sale_patterns(self, post_data: Dict, analysis: Dict):
        """Detect subtle sale patterns that Facebook search might miss"""
        
        # Patterns that indicate a completed sale but might not contain "sold"
        subtle_patterns = {
            'completed_transaction': [
                r'thanks for the quick payment',
                r'enjoy your new',
                r'hope you like it',
                r'shipped today',
                r'tracking number',
                r'should arrive',
            ],
            'buyer_satisfaction': [
                r'perfect condition',
                r'exactly as described',
                r'thanks for the deal',
                r'great transaction',
            ],
            'seller_closing': [
                r'thanks everyone for looking',
                r'more items coming soon',
                r'check my other posts',
            ]
        }
        
        text_to_check = post_data.get('text', '').lower()
        
        # Also check comments
        for comment in post_data.get('comments', []):
            text_to_check += ' ' + comment.get('text', '').lower()
        
        # Look for subtle patterns
        for category, patterns in subtle_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_to_check):
                    analysis['confidence'] += 15
                    analysis['sold_indicators'].append(f"Subtle: {category}")
                    break  # One per category
        
        # Check for price drop followed by silence (often means sold)
        if 'price drop' in text_to_check and len(post_data.get('comments', [])) < 3:
            analysis['confidence'] += 10
            analysis['sold_indicators'].append("Price drop + few comments (likely sold quickly)")
        
        # Multiple interested parties but conversation stops (likely sold offline)
        comments = post_data.get('comments', [])
        if len(comments) > 3:
            interested_count = sum(1 for c in comments 
                                if any(word in c.get('text', '').lower() 
                                    for word in ['interested', 'pm', 'still available']))
            if interested_count >= 2:
                # Multiple people interested but no explicit sold = probably sold offline
                analysis['confidence'] += 20
                analysis['sold_indicators'].append("Multiple interested + conversation stopped")

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
    
    def analyze_sold_status_deep(self, post_data):
        """Enhanced deep analysis that prioritizes comment-based sale confirmations"""
        
        confidence = 0
        sale_method = 'none'
        sold_indicators = []
        buyer_identified = False
        sale_timeline = []
        
        # Analyze main post text
        main_text = (post_data.get('text', '') or '').lower()
        
        # Check if explicitly marked sold in main post
        main_post_sold_patterns = [
            (r'\*\*\*\s*sold\s*\*\*\*', 'Explicit: ***sold***', 40),
            (r'\bsold\b', 'Explicit: sold', 30),
            (r'\bspo\b', 'SPO (sold pending)', 30),
            (r'pending\s*pickup', 'Pending pickup', 25),
            (r'ppu', 'PPU (pending pickup)', 25),
        ]
        
        main_post_confidence = 0
        for pattern, indicator, points in main_post_sold_patterns:
            if re.search(pattern, main_text):
                main_post_confidence += points
                sold_indicators.append(indicator)
        
        # Check for sale listing patterns
        sale_listing_patterns = [
            (r'\$\d+', 'Has price', 10),
            (r'for sale|fs:', 'For sale listing', 10),
            (r'asking|obo|firm', 'Sale terms', 10),
        ]
        
        is_sale_listing = False
        for pattern, indicator, points in sale_listing_patterns:
            if re.search(pattern, main_text):
                is_sale_listing = True
                confidence += points
                sold_indicators.append(indicator)
        
        # DEEP COMMENT ANALYSIS - This is the key part for option 5
        comments = post_data.get('comments', [])
        if comments:
            # Track conversation flow
            claim_patterns = [
                (r"i'll take it", "Buyer: I'll take it", 35),
                (r'claim', 'Buyer: Claim', 35),
                (r'mine|dibs', 'Buyer: Mine/Dibs', 30),
                (r'interested|int', 'Buyer: Interested', 20),
                (r'still available\?', 'Buyer: Asking availability', 15),
                (r'pm|messaged|pm sent', 'Buyer: PM sent', 25),
            ]
            
            seller_confirmation_patterns = [
                (r'sold|spo', 'Seller: Sold confirmation', 40),
                (r'its yours', "Seller: It's yours", 35),
                (r'pending', 'Seller: Pending', 30),
                (r'messaged you|check your messages', 'Seller: PM response', 25),
                (r'thanks|thank you.*sold', 'Seller: Thanks + sold', 35),
            ]
            
            # Analyze each comment
            for i, comment in enumerate(comments):
                comment_text = (comment.get('text', '') or '').lower()
                comment_author = comment.get('author', '').lower()
                
                # Check for buyer claims
                for pattern, indicator, points in claim_patterns:
                    if re.search(pattern, comment_text):
                        confidence += points
                        sold_indicators.append(f"Comment {i+1}: {indicator}")
                        sale_timeline.append({
                            'comment_index': i+1,
                            'author': comment_author,
                            'type': 'claim',
                            'indicators': [indicator]
                        })
                        buyer_identified = True
                
                # Check for seller confirmations
                for pattern, indicator, points in seller_confirmation_patterns:
                    if re.search(pattern, comment_text):
                        confidence += points
                        sold_indicators.append(f"Comment {i+1}: {indicator}")
                        sale_timeline.append({
                            'comment_index': i+1,
                            'author': comment_author,
                            'type': 'confirmation',
                            'indicators': [indicator]
                        })
                
                # Check for explicit sold in comments
                if re.search(r'\bsold\b', comment_text):
                    confidence += 30
                    sold_indicators.append(f"Comment {i+1}: Explicit SOLD")
                    
            # Bonus confidence for conversation patterns
            if buyer_identified and any('confirmation' in event.get('type', '') for event in sale_timeline):
                confidence += 20
                sold_indicators.append("Complete sale conversation detected")
        
        # Determine sale method
        if main_post_confidence >= 30 and len(sale_timeline) > 0:
            sale_method = 'both'
        elif main_post_confidence >= 30:
            sale_method = 'main_post'
        elif len(sale_timeline) > 0 and confidence >= 50:
            sale_method = 'comments'
        
        # Final determination
        is_sold = confidence >= 50  # Lower threshold for deep detection
        
        return {
            'is_sold': is_sold,
            'confidence': min(confidence, 100),
            'sale_method': sale_method,
            'sold_indicators': sold_indicators[:5],  # Top 5 indicators
            'buyer_identified': buyer_identified,
            'sale_timeline': sale_timeline[:5],  # Top 5 timeline events
            'comment_confirmed': sale_method in ['comments', 'both'],
            'would_be_missed_by_search': sale_method == 'comments' and main_post_confidence < 30
        }
        