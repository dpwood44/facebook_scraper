"""
Enhanced ML Scraper with 3-layer detection and feedback loop
Integrates: Structural -> DOM ML -> LLM -> Feedback Learning
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from src.dom_ensemble import MLEnsemble

from src.utils import create_scraper_logger, log_method_entry, log_method_exit, log_performance_metric


class MLScraper:
    """ML-enhanced scraper with 3-layer detection and feedback learning"""
    
    def __init__(self, original_scraper, enable_ml: bool = True, 
                 enable_llm: bool = True, training_mode: bool = False, 
                 model_dir: Path = None):
        
        self.scraper = original_scraper
        self.enable_ml = enable_ml
        self.enable_llm = enable_llm
        self.training_mode = training_mode
        
        # CREATE LOGGER WITH RICH CONTEXT - This replaces the old module-level logger
        self.logger = create_scraper_logger(
            session_id=getattr(original_scraper, 'session_id', 'unknown'),
            module_name=__name__,
            scraper_type="MLScraper", 
            enable_ml=enable_ml,
            enable_llm=enable_llm,
            training_mode=training_mode
        )
        
        self.logger.info("MLScraper initialization starting...")
        
        # Initialize DOM ensemble
        self.dom_ensemble = MLEnsemble(model_dir=model_dir)
        
        # Keep reference to existing LLM classifier
        self.llm_classifier = getattr(original_scraper, 'llm_classifier', None)
        
        # Load existing models
        if self.enable_ml:
            if self.dom_ensemble.load_models():
                self.logger.info("Successfully loaded pre-trained DOM ensemble models")
            else:
                self.logger.warning("No pre-trained DOM models found - DOM ML layer will be disabled")
                self.enable_ml = False
        else:
            self.logger.info("DOM ML layer manually disabled")
        
        # Training and feedback data
        self.training_data_collected = []
        self.prediction_results = []  # Store predictions for feedback
        
        # Performance tracking with 3 layers
        self.detection_stats = {
            'structural_only': 0,
            'dom_ml_used': 0, 
            'llm_used': 0,
            'consensus_agreements': 0,
            'total_classifications': 0
        }
        
        # Log final initialization state
        self.logger.info("MLScraper initialization complete")
        self.logger.info(f"DOM ML enabled: {self.enable_ml}")
        self.logger.info(f"LLM enabled: {self.enable_llm}")
        self.logger.info(f"Training mode: {self.training_mode}")

    async def three_layer_detection(self, container, container_index: int) -> Dict[str, Any]:
        """3-layer detection: Structural -> DOM ML -> LLM fallback with enhanced logging"""
        
        # Log method entry with timing
        start_time = asyncio.get_event_loop().time()
        self.logger.info(f"🔍 3-LAYER DETECTION START: Container {container_index+1}")
        
        try:
            # Extract content
            content_data = await self.scraper.get_container_content_with_deep_extraction(
                container, f"enhanced_detection_{container_index}"
            )
            
            html_content = content_data['html_content']
            text_content = content_data['text_content']
            html_size = len(html_content)
            text_length = len(text_content)
            
            # Log extraction results
            self.logger.debug(f"   Content extracted: {text_length} chars text, {html_size:,} bytes HTML")
            
            # Get position data
            position_data = None
            try:
                position_data = await container.bounding_box()
                if position_data:
                    self.logger.debug(f"   Position data: {position_data}")
            except Exception as e:
                self.logger.debug(f"   Could not get position data: {e}")
            
            # LAYER 1: Structural Detection with enhanced logging
            self.logger.info(f"   Layer 1 (Structural): Analyzing container {container_index+1}...")
            structural_start = asyncio.get_event_loop().time()
            
            structural_result = self.scraper._classify_by_structural_patterns(text_content)
            
            structural_duration = (asyncio.get_event_loop().time() - structural_start) * 1000
            self.logger.info(f"   Layer 1 Result: {structural_result['type']} ({structural_result['confidence']}%) - {structural_result['reason']} [{structural_duration:.1f}ms]")
            
            # LAYER 2: DOM ML (if available and uncertain) with enhanced logging
            dom_ml_result = None
            if (self.enable_ml and self.dom_ensemble.is_trained and 
                structural_result['confidence'] < 85):
                
                self.logger.info(f"   Layer 2 (DOM ML): Analyzing uncertain case (structural confidence: {structural_result['confidence']}%)...")
                dom_ml_start = asyncio.get_event_loop().time()
                
                try:
                    dom_ml_result = self.dom_ensemble.predict(html_content, text_content, position_data)
                    dom_ml_duration = (asyncio.get_event_loop().time() - dom_ml_start) * 1000
                    
                    self.detection_stats['dom_ml_used'] += 1
                    confidence_pct = dom_ml_result['confidence'] * 100
                    prediction = 'Main Post' if dom_ml_result['is_main_post'] else 'Comment'
                    
                    self.logger.info(f"   Layer 2 Result: {prediction} ({confidence_pct:.1f}%) - ensemble prediction [{dom_ml_duration:.1f}ms]")
                    
                    # Log individual model predictions for debugging
                    if 'individual_predictions' in dom_ml_result:
                        individual = dom_ml_result['individual_predictions']
                        self.logger.debug(f"   Individual models: RF={individual.get('rf', {}).get('probability', 0):.3f}, XGB={individual.get('xgb', {}).get('probability', 0):.3f}, GBM={individual.get('gbm', {}).get('probability', 0):.3f}, NN={individual.get('nn', {}).get('probability', 0):.3f}")
                    
                except Exception as e:
                    self.logger.error(f"   Layer 2 Error: {e}")
                    dom_ml_result = None
            else:
                # Log why Layer 2 was skipped
                reasons = []
                if not self.enable_ml: 
                    reasons.append("DOM ML disabled")
                if not self.dom_ensemble.is_trained: 
                    reasons.append("no trained models")
                if structural_result['confidence'] >= 85: 
                    reasons.append(f"structural confidence {structural_result['confidence']}% >= 85%")
                
                self.logger.info(f"   Layer 2 (DOM ML): Skipped - {', '.join(reasons)}")
            
            # LAYER 3: LLM Fallback (if available and still uncertain) with enhanced logging
            llm_result = None
            if (self.enable_llm and self.llm_classifier and 
                self._still_uncertain_after_ml(structural_result, dom_ml_result)):
                
                self.logger.info(f"   Layer 3 (LLM): Analyzing uncertain case...")
                llm_start = asyncio.get_event_loop().time()
                
                try:
                    llm_result = await self.scraper.classify_with_llm_fallback(
                        text_content, html_size
                    )
                    llm_duration = (asyncio.get_event_loop().time() - llm_start) * 1000
                    
                    self.detection_stats['llm_used'] += 1
                    self.logger.info(f"   Layer 3 Result: {llm_result['type']} ({llm_result['confidence']}%) - LLM classification [{llm_duration:.1f}ms]")
                    
                    if 'reasoning' in llm_result:
                        self.logger.debug(f"   LLM reasoning: {llm_result['reasoning']}")
                        
                except Exception as e:
                    self.logger.error(f"   Layer 3 Error: {e}")
                    llm_result = None
            else:
                # Log why Layer 3 was skipped
                reasons = []
                if not self.enable_llm: 
                    reasons.append("LLM disabled")
                if not self.llm_classifier: 
                    reasons.append("no LLM classifier")
                if not self._still_uncertain_after_ml(structural_result, dom_ml_result): 
                    reasons.append("sufficient confidence from previous layers")
                
                self.logger.info(f"   Layer 3 (LLM): Skipped - {', '.join(reasons)}")
            
            # Decision fusion with enhanced logging
            fusion_start = asyncio.get_event_loop().time()
            final_result = self._fuse_three_layer_predictions(
                structural_result, dom_ml_result, llm_result, container_index
            )
            fusion_duration = (asyncio.get_event_loop().time() - fusion_start) * 1000
            
            # Enhanced final decision logging with agreement analysis
            decision_summary = f"{'Main Post' if final_result['is_main_post'] else 'Comment'}"
            confidence = final_result['confidence']
            method = final_result['method']
            
            self.logger.info(f"   🎯 FINAL DECISION: {decision_summary} ({confidence:.1f}% confidence via {method}) [{fusion_duration:.1f}ms]")
            
            # Log any disagreements between layers
            predictions = [structural_result['type'] == 'main_post']
            if dom_ml_result: 
                predictions.append(dom_ml_result['is_main_post'])
            if llm_result: 
                predictions.append(llm_result['type'] == 'main_post')
            
            if len(set(predictions)) > 1:
                self.logger.warning(f"   ⚠️ LAYER DISAGREEMENT detected - predictions: {predictions}")
                self.logger.debug(f"   Fusion details: {final_result.get('fusion_details', {})}")
            else:
                self.detection_stats['consensus_agreements'] += 1
                self.logger.debug(f"   ✅ Layer consensus achieved")
            
            # Store prediction for later feedback with enhanced metadata
            prediction_record = {
                'container_index': container_index,
                'html_content': html_content[:3000],  # Truncated for storage
                'text_content': text_content,
                'position_data': position_data,
                'structural_prediction': structural_result,
                'dom_ml_prediction': dom_ml_result,
                'llm_prediction': llm_result,
                'final_prediction': final_result,
                'timestamp': datetime.now().isoformat(),
                'needs_feedback': self._needs_human_feedback(structural_result, dom_ml_result, llm_result),
                'processing_time_ms': (asyncio.get_event_loop().time() - start_time) * 1000
            }
            
            self.prediction_results.append(prediction_record)
            
            # Collect training data if in training mode
            if self.training_mode:
                self._collect_training_data(prediction_record)
            
            self.detection_stats['total_classifications'] += 1
            
            # Log performance metrics
            total_duration = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance_metric(
                "3-layer-detection",
                total_duration,
                container_index=container_index,
                layers_used=final_result.get('layer_used', 1),
                confidence=confidence,
                agreement=len(set(predictions)) == 1
            )
            
            return final_result
            
        except Exception as e:
            total_duration = (asyncio.get_event_loop().time() - start_time) * 1000
            self.logger.error(f"🔍 3-LAYER DETECTION FAILED for container {container_index}: {e} [{total_duration:.1f}ms]")
            
            # Return fallback result
            return {
                'is_main_post': self.scraper._is_likely_main_post_for_boundary(
                    content_data.get('text_content', ''), 
                    content_data.get('html_size', 0)
                ),
                'confidence': 50.0,
                'method': 'fallback_structural',
                'layer_used': 1,
                'error': str(e)
            }

    async def enhanced_scraping_with_three_layers(self, num_posts: int = 10) -> List[Dict]:
        """Enhanced scraping with 3-layer detection and comprehensive logging"""
        
        log_method_entry("enhanced_scraping_with_three_layers", num_posts=num_posts)
        start_time = asyncio.get_event_loop().time()
        
        self.logger.info(f"🚀 STARTING 3-LAYER ENHANCED SCRAPING for {num_posts} posts")
        self.logger.info(f"   DOM ML enabled: {self.enable_ml}")
        self.logger.info(f"   LLM enabled: {self.enable_llm}")
        self.logger.info(f"   Training mode: {self.training_mode}")
        
        posts = []
        container_position = 0
        scroll_attempts = 0
        max_scrolls = 15
        
        await self.scraper.close_any_modals()
        
        while len(posts) < num_posts and scroll_attempts < max_scrolls:
            try:
                all_containers = await self.scraper.page.locator('[role="article"]').all()
                total_containers = len(all_containers)
                
                self.logger.debug(f"📊 Processing containers from position {container_position+1}, total available: {total_containers}")
                
                if container_position >= total_containers:
                    self.logger.info("Reached end of containers, scrolling for more...")
                    await self.scraper.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    continue
                
                found_post = False
                batch_size = 3  # Smaller batches for 3-layer processing
                
                for i in range(container_position, min(container_position + batch_size, total_containers)):
                    container = all_containers[i]
                    
                    # CRITICAL: Use 3-layer detection with enhanced logging
                    self.logger.debug(f"🔍 ANALYZING CONTAINER {i+1} with 3-layer system")
                    detection_result = await self.three_layer_detection(container, i)
                    
                    if detection_result['is_main_post']:
                        confidence = detection_result['confidence']
                        method = detection_result['method']
                        layer_used = detection_result.get('layer_used', 1)
                        
                        self.logger.info(f"✅ MAIN POST DETECTED: Container {i+1} (confidence: {confidence:.1f}%, method: {method}, layer: {layer_used})")
                        
                        # Process the post
                        container_data = {
                            'container': container,
                            'content': await self.scraper.get_container_content_with_deep_extraction(container, "enhanced"),
                            'index': i
                        }
                        
                        self.logger.info(f"📝 Processing main post #{len(posts)+1}")
                        post_data, boundary_index = await self.scraper.process_post_with_stored_content(
                            all_containers, container_data, len(posts) + 1
                        )
                        
                        if post_data and self.scraper.validate_main_post_data(post_data):
                            # Add all detection metadata
                            post_data['detection_result'] = detection_result
                            post_data['layer_used'] = layer_used
                            
                            posts.append(post_data)
                            self.logger.info(f"✅ SUCCESS: Post #{len(posts)} scraped (layer: {layer_used}, confidence: {confidence:.1f}%)")
                            
                            if len(posts) % 3 == 0:
                                await self.scraper.auto_save(posts)
                        else:
                            self.logger.warning(f"❌ Post validation failed for container {i+1}")
                        
                        container_position = i + 1
                        found_post = True
                        scroll_attempts = 0
                        break
                    else:
                        self.logger.debug(f"   Container {i+1}: Not a main post")
                
                if not found_post:
                    container_position = min(container_position + 1, total_containers)
                    self.logger.debug(f"No posts found in batch, advancing to position {container_position}")
                
            except Exception as e:
                self.logger.error(f"Error in 3-layer scraping loop: {str(e)[:100]}")
                scroll_attempts += 1
                container_position += 1
                continue
        
        # Save prediction results for feedback
        self.save_prediction_results()
        
        if self.training_mode:
            self._save_training_data()
        
        # Enhanced stats logging
        self._print_three_layer_stats()
        
        total_duration = (asyncio.get_event_loop().time() - start_time) * 1000
        log_method_exit("enhanced_scraping_with_three_layers", posts, total_duration)
        
        self.logger.info(f"🎉 3-layer enhanced scraping complete: {len(posts)} posts found in {total_duration/1000:.1f}s")
        return posts
    
    def _still_uncertain_after_ml(self, structural_result: Dict, 
                                  dom_ml_result: Optional[Dict]) -> bool:
        """Determine if we should use LLM after DOM ML"""
        
        # Use LLM if structural confidence is low
        if structural_result['confidence'] < 70:
            return True
        
        # Use LLM if DOM ML and structural disagree
        if dom_ml_result:
            structural_is_post = structural_result['type'] == 'main_post'
            ml_is_post = dom_ml_result['is_main_post']
            
            if structural_is_post != ml_is_post:
                return True
        
        return False
    
    def _fuse_three_layer_predictions(self, structural_result: Dict, 
                                     dom_ml_result: Optional[Dict],
                                     llm_result: Optional[Dict],
                                     container_index: int) -> Dict[str, Any]:
        """Intelligently fuse predictions from all three layers"""
        
        structural_is_post = structural_result['type'] == 'main_post'
        structural_confidence = structural_result['confidence']
        
        # If only structural available, use it
        if not dom_ml_result and not llm_result:
            return {
                'is_main_post': structural_is_post,
                'confidence': structural_confidence,
                'method': 'structural_only',
                'layer_used': 1,
                'all_predictions': {
                    'structural': structural_result,
                    'dom_ml': None,
                    'llm': None
                }
            }
        
        # Collect all available predictions
        predictions = []
        weights = []
        
        # Structural prediction (always available)
        predictions.append(structural_is_post)
        weights.append(structural_confidence / 100.0)
        
        # DOM ML prediction (if available)
        if dom_ml_result:
            predictions.append(dom_ml_result['is_main_post'])
            weights.append(dom_ml_result['confidence'])
        
        # LLM prediction (if available) - highest weight due to sophistication
        if llm_result:
            predictions.append(llm_result['type'] == 'main_post')
            weights.append(llm_result['confidence'] / 100.0 * 1.2)  # 20% bonus for LLM
        
        # Weighted majority vote
        weighted_votes = sum(pred * weight for pred, weight in zip(predictions, weights))
        total_weight = sum(weights)
        
        final_confidence = (weighted_votes / total_weight) * 100
        final_prediction = final_confidence > 50
        
        # Determine method used
        if llm_result:
            method = f"three_layer_fusion"
            layer_used = 3
        elif dom_ml_result:
            method = f"two_layer_fusion" 
            layer_used = 2
        else:
            method = "structural_only"
            layer_used = 1
        
        # Check for consensus
        if len(set(predictions)) == 1:  # All agree
            self.detection_stats['consensus_agreements'] += 1
            method += "_consensus"
        
        return {
            'is_main_post': final_prediction,
            'confidence': final_confidence,
            'method': method,
            'layer_used': layer_used,
            'all_predictions': {
                'structural': structural_result,
                'dom_ml': dom_ml_result,
                'llm': llm_result
            },
            'fusion_details': {
                'weighted_votes': weighted_votes,
                'total_weight': total_weight,
                'individual_weights': weights
            }
        }
    
    def _needs_human_feedback(self, structural_result: Dict, 
                             dom_ml_result: Optional[Dict],
                             llm_result: Optional[Dict]) -> bool:
        """Determine if this prediction would benefit from human feedback"""
        
        # Flag if models disagree
        predictions = []
        confidences = []
        
        predictions.append(structural_result['type'] == 'main_post')
        confidences.append(structural_result['confidence'])
        
        if dom_ml_result:
            predictions.append(dom_ml_result['is_main_post'])
            confidences.append(dom_ml_result['confidence'] * 100)
        
        if llm_result:
            predictions.append(llm_result['type'] == 'main_post')
            confidences.append(llm_result['confidence'])
        
        # Flag if there's disagreement among confident predictions
        if len(set(predictions)) > 1 and min(confidences) > 60:
            return True
        
        # Flag if all predictions have low confidence
        if max(confidences) < 65:
            return True
        
        return False
    
    def _collect_training_data(self, prediction_record: Dict):
        """Collect training data from predictions"""
        
        training_example = {
            'container_index': prediction_record['container_index'],
            'html_content': prediction_record['html_content'],
            'text_content': prediction_record['text_content'],
            'position_data': prediction_record['position_data'],
            'all_predictions': prediction_record['final_prediction']['all_predictions'],
            'final_prediction': prediction_record['final_prediction'],
            'timestamp': prediction_record['timestamp'],
            'needs_manual_review': prediction_record['needs_feedback']
        }
        
        self.training_data_collected.append(training_example)
        
        # Periodic save
        if len(self.training_data_collected) % 15 == 0:
            self._save_training_data()
    
    def _save_training_data(self):
        """Save training data"""
        if not self.training_data_collected:
            return
        
        training_file = self.scraper.output_dir / f"enhanced_training_data_{self.scraper.session_id}.json"
        try:
            with open(training_file, 'w', encoding='utf-8') as f:
                json.dump(self.training_data_collected, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved {len(self.training_data_collected)} enhanced training examples")
        except Exception as e:
            self.logger.error(f"Failed to save training data: {e}")
    
    def save_prediction_results(self):
        """Save prediction results for later feedback"""
        if not self.prediction_results:
            return
        
        results_file = self.scraper.output_dir / f"prediction_results_{self.scraper.session_id}.json"
        try:
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.prediction_results, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved {len(self.prediction_results)} prediction results for feedback")
            return str(results_file)
        except Exception as e:
            self.logger.error(f"Failed to save prediction results: {e}")
            return None

    def _print_three_layer_stats(self):
        """Print 3-layer detection statistics"""
        if self.detection_stats['total_classifications'] == 0:
            return
        
        print("\n" + "="*70)
        print("3-LAYER DETECTION PERFORMANCE STATS")
        print("="*70)
    
    def add_manual_labels_and_retrain(self, labeled_examples: List[Dict]):
        """Add manually labeled examples and retrain the DOM ensemble model"""
        self.logger.info(f"Adding {len(labeled_examples)} manual labels and retraining DOM ensemble")
        
        for example in labeled_examples:
            self.dom_ensemble.add_training_example(
                html_content=example['html_content'],
                text_content=example['text_content'],
                is_main_post=example['is_main_post'],
                position_data=example.get('position_data')
            )
        
        # Retrain the DOM ensemble models
        try:
            metrics = self.dom_ensemble.train_models()
            self.logger.info("DOM ensemble retraining completed successfully")
            
            # Enable ML if it wasn't enabled before
            if not self.enable_ml:
                self.enable_ml = True
                self.logger.info("DOM ML predictions now enabled")
            
            # Print performance report
            self.dom_ensemble.print_performance_report()
            
            return metrics
        except Exception as e:
            self.logger.error(f"DOM ensemble retraining failed: {e}")
            return None
        


class FeedbackLearning:
    """System for learning from human feedback on scraping results with enhanced logging"""
    
    def __init__(self, scraper_output_dir: Path, session_id: Optional[str] = None):
        self.output_dir = scraper_output_dir
        self.feedback_dir = self.output_dir / "feedback"
        self.feedback_dir.mkdir(exist_ok=True)
        
        # Create logger with rich context for feedback operations
        self.logger = create_scraper_logger(
            session_id=session_id or 'unknown',
            module_name=__name__,
            component="FeedbackLearning",
            output_dir=str(scraper_output_dir)
        )
        
        self.logger.info("FeedbackLearning system initialized")
        self.logger.info(f"Output directory: {scraper_output_dir}")
        self.logger.info(f"Feedback directory: {self.feedback_dir}")
    
    def create_feedback_interface(self, session_id: str, 
                                scraped_posts: List[Dict], 
                                show_all: bool = True) -> Optional[str]:
        """Create HTML interface for reviewing scraping results and providing feedback"""
        
        log_method_entry("create_feedback_interface", session_id=session_id, posts_count=len(scraped_posts))
        start_time = datetime.now()
        
        self.logger.info(f"Creating feedback interface for session {session_id}")
        self.logger.info(f"Processing {len(scraped_posts)} scraped posts")
        
        # Load prediction results
        results_file = self.output_dir / f"prediction_results_{session_id}.json"
        
        if not results_file.exists():
            self.logger.error(f"No prediction results found: {results_file}")
            self.logger.warning(f"Cannot create feedback interface without prediction data")
            return None
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                prediction_results = json.load(f)
            
            self.logger.info(f"Loaded {len(prediction_results)} prediction results")
            
        except Exception as e:
            self.logger.error(f"Failed to load prediction results from {results_file}: {e}")
            return None
        
        # MODIFIED: Show ALL predictions, not just those needing feedback
        if show_all:
            feedback_candidates = prediction_results  # Show all predictions
            self.logger.info(f"Showing ALL {len(feedback_candidates)} predictions for manual review")
        else:
            # Original behavior - only uncertain predictions
            feedback_candidates = [pred for pred in prediction_results if pred.get('needs_feedback', False)]
            self.logger.info(f"Found {len(feedback_candidates)} predictions needing feedback out of {len(prediction_results)} total")
        
        if not feedback_candidates:
            if show_all:
                self.logger.warning("No predictions available for feedback")
            else:
                self.logger.info("No predictions need feedback - interface creation skipped")
            return None
        
        # Analyze feedback candidates for logging
        high_confidence_cases = 0
        low_confidence_cases = 0
        disagreement_cases = 0
        
        for pred in feedback_candidates:
            final_pred = pred.get('final_prediction', {})
            confidence = final_pred.get('confidence', 100)
            
            if confidence >= 85:
                high_confidence_cases += 1
            elif confidence < 70:
                low_confidence_cases += 1
            
            # Check for layer disagreements
            all_preds = final_pred.get('all_predictions', {})
            if all_preds.get('structural') and all_preds.get('dom_ml'):
                structural_is_post = all_preds['structural']['type'] == 'main_post'
                ml_is_post = all_preds['dom_ml']['is_main_post']
                if structural_is_post != ml_is_post:
                    disagreement_cases += 1
        
        self.logger.info(f"Feedback analysis: {high_confidence_cases} high confidence, {low_confidence_cases} low confidence, {disagreement_cases} disagreements")
        
        # Generate HTML interface (your existing HTML generation code)
        try:
            self.logger.debug("Generating HTML interface...")
            html_content = self._generate_feedback_html(feedback_candidates, scraped_posts, session_id)
            
            # Save HTML file
            html_file = self.feedback_dir / f"feedback_interface_{session_id}.html"
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            file_size = html_file.stat().st_size
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            self.logger.info(f"Created feedback interface: {html_file}")
            self.logger.info(f"Interface file size: {file_size:,} bytes")
            
            log_performance_metric(
                "create_feedback_interface",
                duration,
                candidates_count=len(feedback_candidates),
                file_size=file_size,
                high_confidence_cases=high_confidence_cases,
                disagreement_cases=disagreement_cases
            )
            
            log_method_exit("create_feedback_interface", str(html_file), duration)
            return str(html_file)
            
        except Exception as e:
            self.logger.error(f"Failed to create feedback interface: {e}")
            return None

    def apply_feedback_to_models(self, feedback_file: str, enhanced_scraper) -> bool:
        """Apply human feedback to retrain models with comprehensive logging"""
        
        log_method_entry("apply_feedback_to_models", feedback_file=feedback_file)
        start_time = datetime.now()
        
        self.logger.info(f"Applying feedback from: {feedback_file}")
        
        # Validate feedback file exists
        feedback_path = Path(feedback_file)
        if not feedback_path.exists():
            self.logger.error(f"Feedback file not found: {feedback_file}")
            return False
        
        try:
            # Load feedback data
            with open(feedback_file, 'r') as f:
                feedback_data = json.load(f)
            
            session_id = feedback_data['session_id']
            feedback_dict = feedback_data['feedback']
            metadata = feedback_data.get('metadata', {})
            
            self.logger.info(f"Processing feedback for session: {session_id}")
            self.logger.info(f"Feedback entries: {len(feedback_dict)}")
            self.logger.info(f"Total predictions reviewed: {metadata.get('reviewed_predictions', 'unknown')}")
            self.logger.info(f"Completion percentage: {metadata.get('completion_percentage', 'unknown')}%")
            
            # Load corresponding prediction results
            results_file = self.output_dir / f"prediction_results_{session_id}.json"
            
            if not results_file.exists():
                self.logger.error(f"Prediction results file not found: {results_file}")
                return False
            
            with open(results_file, 'r') as f:
                prediction_results = json.load(f)
            
            self.logger.info(f"Loaded {len(prediction_results)} prediction results for cross-reference")
            
            # Create training examples from feedback
            training_examples = []
            feedback_stats = {'correct': 0, 'incorrect': 0, 'uncertain': 0, 'invalid': 0}
            
            for pred_index_str, feedback_type in feedback_dict.items():
                try:
                    pred_index = int(pred_index_str)
                    feedback_stats[feedback_type] = feedback_stats.get(feedback_type, 0) + 1
                    
                    if pred_index < len(prediction_results) and feedback_type in ['correct', 'incorrect']:
                        pred_result = prediction_results[pred_index]
                        
                        # Determine correct label based on feedback
                        final_pred = pred_result['final_prediction']
                        predicted_is_main_post = final_pred['is_main_post']
                        
                        if feedback_type == 'correct':
                            correct_label = predicted_is_main_post
                            self.logger.debug(f"Prediction {pred_index}: Confirmed as {correct_label}")
                        else:
                            correct_label = not predicted_is_main_post
                            self.logger.debug(f"Prediction {pred_index}: Corrected to {correct_label}")
                        
                        training_examples.append({
                            'html_content': pred_result['html_content'],
                            'text_content': pred_result['text_content'],
                            'position_data': pred_result['position_data'],
                            'is_main_post': correct_label,
                            'feedback_type': feedback_type,
                            'original_prediction': predicted_is_main_post,
                            'prediction_confidence': final_pred.get('confidence', 0)
                        })
                        
                except (ValueError, IndexError) as e:
                    feedback_stats['invalid'] += 1
                    self.logger.warning(f"Invalid feedback entry: {pred_index_str} -> {feedback_type}: {e}")
            
            # Log feedback statistics
            self.logger.info("Feedback statistics:")
            for feedback_type, count in feedback_stats.items():
                self.logger.info(f"  {feedback_type}: {count}")
            
            actionable_examples = len(training_examples)
            self.logger.info(f"Created {actionable_examples} actionable training examples")
            
            if actionable_examples == 0:
                self.logger.warning("No actionable feedback found - cannot retrain models")
                return False
            
            # Analyze correction patterns
            corrections = [ex for ex in training_examples if ex['feedback_type'] == 'incorrect']
            if corrections:
                self.logger.info(f"Model correction analysis:")
                self.logger.info(f"  Total corrections: {len(corrections)}")
                
                # Analyze what types of mistakes were corrected
                false_positives = sum(1 for ex in corrections if ex['original_prediction'] == True)
                false_negatives = sum(1 for ex in corrections if ex['original_prediction'] == False)
                
                self.logger.info(f"  False positives (wrongly called main post): {false_positives}")
                self.logger.info(f"  False negatives (wrongly called comment): {false_negatives}")
                
                # Analyze confidence levels of corrections
                avg_confidence = sum(ex['prediction_confidence'] for ex in corrections) / len(corrections)
                self.logger.info(f"  Average confidence of corrected predictions: {avg_confidence:.1f}%")
            
            # Apply feedback to retrain models
            self.logger.info("Initiating model retraining with feedback...")
            
            try:
                metrics = enhanced_scraper.add_manual_labels_and_retrain(training_examples)
                
                if metrics:
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    
                    self.logger.info("Model retraining completed successfully!")
                    self.logger.info(f"New test accuracy: {metrics['ensemble_test_score']:.3f}")
                    self.logger.info(f"Training examples used: {metrics['training_size']}")
                    self.logger.info(f"Test examples: {metrics['test_size']}")
                    
                    # Log improvement metrics if available
                    if 'individual_models' in metrics:
                        self.logger.info("Individual model performance:")
                        for model_name, scores in metrics['individual_models'].items():
                            self.logger.info(f"  {model_name}: test={scores['test_score']:.3f}")
                    
                    log_performance_metric(
                        "apply_feedback_to_models",
                        duration,
                        training_examples=actionable_examples,
                        corrections=len(corrections),
                        new_accuracy=metrics['ensemble_test_score']
                    )
                    
                    log_method_exit("apply_feedback_to_models", True, duration)
                    return True
                    
                else:
                    self.logger.error("Model retraining failed - no metrics returned")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Model retraining failed with exception: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing feedback file: {e}")
            return False
    
    def _generate_feedback_html(self, predictions: List[Dict], 
                               posts: List[Dict], session_id: str) -> str:
        """Generate HTML for feedback interface with logging"""
        
        self.logger.debug(f"Generating HTML for {len(predictions)} predictions")
        
        # Your existing HTML generation logic here
        # (keeping the same HTML structure but adding some logging)
        
        # Log HTML generation statistics
        total_chars = sum(len(pred.get('text_content', '')) for pred in predictions)
        avg_chars = total_chars / len(predictions) if predictions else 0
        
        self.logger.debug(f"HTML generation stats:")
        self.logger.debug(f"  Total content characters: {total_chars:,}")
        self.logger.debug(f"  Average content length: {avg_chars:.0f} chars")
        self.logger.debug(f"  Posts with layer disagreements: {sum(1 for p in predictions if self._has_layer_disagreement(p))}")
        
        # Your existing HTML generation code would go here
        # For brevity, I'm not repeating the full HTML template
        html = "<!-- Your existing HTML template -->"
        
        return html
    
    def _has_layer_disagreement(self, prediction: Dict) -> bool:
        """Check if prediction has layer disagreements"""
        final_pred = prediction.get('final_prediction', {})
        all_preds = final_pred.get('all_predictions', {})
        
        if not all_preds.get('structural') or not all_preds.get('dom_ml'):
            return False
        
        structural_is_post = all_preds['structural']['type'] == 'main_post'
        ml_is_post = all_preds['dom_ml']['is_main_post']
        
        return structural_is_post != ml_is_post