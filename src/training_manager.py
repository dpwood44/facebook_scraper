"""
Training data management for ML-enhanced Facebook scraper
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TrainingManager:
    """Helper class for managing training data collection and labeling"""
    
    def __init__(self, scraper_output_dir: Path):
        self.output_dir = scraper_output_dir
        self.training_dir = self.output_dir / "training_data"
        self.training_dir.mkdir(exist_ok=True)
    
    def load_collected_data(self, session_id: str) -> List[Dict]:
        """Load training data collected during a scraping session"""
        training_file = self.output_dir / f"training_data_{session_id}.json"
        
        if not training_file.exists():
            logger.warning(f"No training data found for session {session_id}")
            return []
        
        try:
            with open(training_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} training examples from {training_file}")
            return data
        except Exception as e:
            logger.error(f"Failed to load training data: {e}")
            return []
    
    def create_labeling_interface(self, collected_data: List[Dict], 
                                max_examples: int = 50) -> Optional[str]:
        """Create a simple HTML interface for manual labeling"""
        
        # Filter to examples that need review
        review_examples = [ex for ex in collected_data if ex.get('needs_manual_review', False)]
        
        # Limit number of examples
        examples_to_label = review_examples[:max_examples]
        
        if not examples_to_label:
            logger.info("No examples need manual review")
            return None
        
        # Generate HTML interface
        html_content = self._generate_labeling_html(examples_to_label)
        
        # Save HTML file
        html_file = self.training_dir / f"labeling_interface_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        try:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Created labeling interface: {html_file}")
            logger.info(f"Open this file in your browser to label {len(examples_to_label)} examples")
            
            return str(html_file)
        except Exception as e:
            logger.error(f"Failed to create labeling interface: {e}")
            return None
    
    def _generate_labeling_html(self, examples: List[Dict]) -> str:
        """Generate HTML for manual labeling interface"""
        
        # Pre-define JavaScript strings with backslashes outside of f-strings
        keyboard_alert = 'alert("💡 Keyboard shortcuts:\\n\\n1 or M = Main Post\\n2 or C = Comment\\n3 or U = Uncertain\\n\\nHover over an example and press the key!");'
        export_alert = 'alert("🎉 Labels exported successfully!\\n\\nNext steps:\\n1. Save the downloaded JSON file\\n2. Use it to train your ML model\\n3. Enjoy improved scraping accuracy!");'
        
        html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Facebook Post Labeling Interface</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: #4267B2; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
            .progress { position: fixed; top: 20px; right: 20px; background: white; border: 2px solid #4267B2; padding: 15px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 1000; }
            .example { background: white; border: 2px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .example.main-post { border-color: #28a745; background: #f8fff9; }
            .example.comment { border-color: #dc3545; background: #fff8f8; }
            .content { background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .predictions { background: #e9ecef; padding: 15px; margin: 15px 0; border-radius: 5px; }
            .buttons { margin: 15px 0; text-align: center; }
            button { margin: 10px; padding: 12px 25px; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
            .btn-main { background-color: #28a745; color: white; }
            .btn-main:hover { background-color: #218838; }
            .btn-comment { background-color: #dc3545; color: white; }
            .btn-comment:hover { background-color: #c82333; }
            .btn-uncertain { background-color: #ffc107; color: #212529; }
            .btn-uncertain:hover { background-color: #e0a800; }
            .result { margin: 15px 0; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
            .instructions { background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .export-btn { background: #007bff; color: white; padding: 15px 30px; font-size: 18px; border-radius: 8px; }
            .export-btn:hover { background: #0056b3; }
            .text-preview { max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: white; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏷️ Facebook Post Labeling Interface</h1>
                <p>Help improve ML model accuracy by labeling these examples</p>
            </div>
            
            <div class="instructions">
                <h3>📋 Instructions:</h3>
                <ul>
                    <li><strong>Main Post:</strong> Original posts by users (sales, questions, announcements, etc.)</li>
                    <li><strong>Comment:</strong> Responses to posts (short interactions, "PM sent", "still available?", etc.)</li>
                    <li><strong>Uncertain:</strong> Use sparingly when you genuinely can't decide</li>
                </ul>
                <p><strong>Look for:</strong> Author info, timestamps, "Shared with" text, content length, and context</p>
            </div>
        
            <div id="examples">
    """
        
        for i, example in enumerate(examples):
            structural_pred = example['structural_prediction']
            ml_pred = example.get('ml_prediction', {})
            
            text_content = example['text_content']
            text_preview = text_content[:400] + "..." if len(text_content) > 400 else text_content
            
            # FIX: Process backslash replacements OUTSIDE the f-string
            text_preview_html = text_preview.replace('\n', '<br>')
            
            # Try to extract key features for display
            has_price = '$' in text_content
            has_shared_with = 'Shared with' in text_content
            has_see_more = 'See more' in text_content
            
            html += f"""
            <div class="example" id="example-{i}">
                <h3>🔍 Example {i+1} of {len(examples)}</h3>
                
                <div class="content">
                    <h4>Content Analysis:</h4>
                    <div class="text-preview">
                        <strong>Text Content:</strong><br>
                        {text_preview_html}
                    </div>
                    <p><strong>Length:</strong> {len(text_content)} characters</p>
                    <p><strong>Key Indicators:</strong> 
                        {"💰 Has price" if has_price else ""} 
                        {"🔒 Privacy indicator" if has_shared_with else ""} 
                        {"📖 Expandable content" if has_see_more else ""}
                    </p>
                </div>
                
                <div class="predictions">
                    <h4>🤖 Current Model Predictions:</h4>
                    <p><strong>Structural Detection:</strong> 
                    <span style="color: {'green' if structural_pred['type'] == 'main_post' else 'red'}">
                        {structural_pred['type'].replace('_', ' ').title()}
                    </span> 
                    ({structural_pred['confidence']:.1f}% confidence)
                    </p>
                    {f'<p><strong>ML Model:</strong> <span style="color: {"green" if ml_pred.get("is_main_post") else "red"}">{"Main Post" if ml_pred.get("is_main_post") else "Comment"}</span> ({ml_pred.get("confidence", 0)*100:.1f}% confidence)</p>' if ml_pred else '<p><strong>ML Model:</strong> Not available</p>'}
                    <p><em>These models disagree - your label will help improve accuracy!</em></p>
                </div>
                
                <div class="buttons">
                    <button class="btn-main" onclick="labelExample({i}, 'main_post')">
                        ✅ Main Post
                    </button>
                    <button class="btn-comment" onclick="labelExample({i}, 'comment')">
                        ❌ Comment
                    </button>
                    <button class="btn-uncertain" onclick="labelExample({i}, 'uncertain')">
                        ❓ Uncertain
                    </button>
                </div>
                
                <div class="result" id="result-{i}"></div>
            </div>
    """
        
        # JavaScript section - using string interpolation for variables, but keeping backslashes outside f-strings
        javascript_section = f"""
            </div>
            
            <div style="text-align: center; margin: 40px 0;">
                <button class="export-btn" onclick="exportLabels()">
                    📤 Export Labels & Train Model
                </button>
                <p style="margin-top: 10px; color: #666;">
                    Export your labels as JSON for model training
                </p>
            </div>
            
            </div>
            
            <div class="progress">
                <h4>📊 Progress</h4>
                <p><strong>Labeled:</strong> <span id="labeled-count">0</span> / {len(examples)}</p>
                <p><strong>Completion:</strong> <span id="completion">0%</span></p>
                <div style="background: #e9ecef; border-radius: 10px; height: 20px; margin: 10px 0;">
                    <div id="progress-bar" style="background: #28a745; height: 100%; border-radius: 10px; width: 0%; transition: width 0.3s;"></div>
                </div>
            </div>

            <script>
                let labels = {{}};
                
                function labelExample(index, label) {{
                    labels[index] = label;
                    
                    const resultDiv = document.getElementById('result-' + index);
                    const labelText = label.replace('_', ' ').toUpperCase();
                    const colorMap = {{
                        'main_post': '#28a745',
                        'comment': '#dc3545', 
                        'uncertain': '#ffc107'
                    }};
                    
                    resultDiv.innerHTML = `<div style="color: ${{colorMap[label]}};">✓ Labeled as: ${{labelText}}</div>`;
                    resultDiv.style.background = colorMap[label] + '20';
                    resultDiv.style.border = '2px solid ' + colorMap[label];
                    
                    const exampleDiv = document.getElementById('example-' + index);
                    exampleDiv.className = 'example ' + label.replace('_', '-');
                    
                    updateProgress();
                    
                    // Auto-scroll to next example
                    const nextExample = document.getElementById('example-' + (index + 1));
                    if (nextExample) {{
                        setTimeout(() => nextExample.scrollIntoView({{ behavior: 'smooth', block: 'center' }}), 500);
                    }}
                }}
                
                function updateProgress() {{
                    const labeledCount = Object.keys(labels).length;
                    const total = {len(examples)};
                    const percentage = Math.round((labeledCount / total) * 100);
                    
                    document.getElementById('labeled-count').textContent = labeledCount;
                    document.getElementById('completion').textContent = percentage + '%';
                    document.getElementById('progress-bar').style.width = percentage + '%';
                }}
                
                function exportLabels() {{
                    const labeledCount = Object.keys(labels).length;
                    const total = {len(examples)};
                    
                    if (labeledCount === 0) {{
                        alert('Please label at least one example before exporting.');
                        return;
                    }}
                    
                    if (labeledCount < total) {{
                        const proceed = confirm(`You've labeled ${{labeledCount}} out of ${{total}} examples. Export anyway?`);
                        if (!proceed) return;
                    }}
                    
                    // Prepare export data
                    const exportData = {{
                        labels: labels,
                        metadata: {{
                            total_examples: total,
                            labeled_examples: labeledCount,
                            completion_percentage: Math.round((labeledCount / total) * 100),
                            export_timestamp: new Date().toISOString(),
                            labeler: 'manual',
                            session_type: 'facebook_post_labeling'
                        }}
                    }};
                    
                    const dataStr = JSON.stringify(exportData, null, 2);
                    const dataBlob = new Blob([dataStr], {{type: 'application/json'}});
                    
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(dataBlob);
                    link.download = 'facebook_training_labels_' + new Date().toISOString().slice(0,19).replace(/:/g, '-') + '.json';
                    link.click();
                    
                    {export_alert}
                }}
                
                // Keyboard shortcuts
                document.addEventListener('keydown', function(e) {{
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                    
                    const activeExample = document.querySelector('.example:hover');
                    if (activeExample) {{
                        const index = parseInt(activeExample.id.split('-')[1]);
                        
                        if (e.key === '1' || e.key === 'm') {{
                            labelExample(index, 'main_post');
                            e.preventDefault();
                        }} else if (e.key === '2' || e.key === 'c') {{
                            labelExample(index, 'comment');
                            e.preventDefault();
                        }} else if (e.key === '3' || e.key === 'u') {{
                            labelExample(index, 'uncertain');
                            e.preventDefault();
                        }}
                    }}
                }});
                
                // Show keyboard shortcuts on load
                setTimeout(() => {{
                    if (Object.keys(labels).length === 0) {{
                        {keyboard_alert}
                    }}
                }}, 2000);
            </script>
        </body>
        </html>
        """
        
        html += javascript_section
        return html

class FeedbackLearning:
    """System for learning from human feedback on scraping results"""
    
    def __init__(self, scraper_output_dir: Path, session_id: Optional[str] = None):  # ADD session_id parameter
        self.output_dir = scraper_output_dir
        self.feedback_dir = self.output_dir / "feedback"
        self.feedback_dir.mkdir(exist_ok=True)
        
        # If you have enhanced logging, add this:
        if session_id:
            try:
                from src.utils import create_scraper_logger
                self.logger = create_scraper_logger(
                    session_id=session_id,
                    module_name=__name__,
                    component="FeedbackLearning",
                    output_dir=str(scraper_output_dir)
                )
                self.logger.info("FeedbackLearning system initialized with enhanced logging")
            except ImportError:
                # Fallback to basic logging if enhanced logging not available
                import logging
                self.logger = logging.getLogger(__name__)
                self.logger.info("FeedbackLearning system initialized")
        else:
            import logging
            self.logger = logging.getLogger(__name__)
            self.logger.info("FeedbackLearning system initialized")
        
        self.logger.info(f"Output directory: {scraper_output_dir}")
        self.logger.info(f"Feedback directory: {self.feedback_dir}")

    def create_feedback_interface(self, session_id: str, 
                                scraped_posts: List[Dict]) -> Optional[str]:
        """Create HTML interface for reviewing scraping results and providing feedback"""
        
        # Load prediction results
        results_file = self.output_dir / f"prediction_results_{session_id}.json"
        
        if not results_file.exists():
            print(f"No prediction results found for session {session_id}")
            return None
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                prediction_results = json.load(f)
        except Exception as e:
            print(f"Failed to load prediction results: {e}")
            return None
        
        # SHOW ALL PREDICTIONS, not just those needing feedback
        feedback_candidates = prediction_results  # Changed from filtering by needs_feedback
        
        if not feedback_candidates:
            print("No predictions available for feedback")
            return None
        
        print(f"Creating feedback interface for {len(feedback_candidates)} predictions")
        
        # Generate HTML interface (your existing HTML generation code)
        html_content = self._generate_feedback_html(feedback_candidates, scraped_posts, session_id)
        
        # Save HTML file
        html_file = self.feedback_dir / f"feedback_interface_{session_id}.html"
        
        try:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"Created feedback interface: {html_file}")
            return str(html_file)
        except Exception as e:
            print(f"Failed to create feedback interface: {e}")
            return None    

    def _generate_feedback_html(self, predictions: List[Dict], 
                               posts: List[Dict], session_id: str) -> str:
        """Generate HTML for feedback interface"""
        
        # Define the alert message with newlines outside the f-string
        alert_message = 'alert("🎉 Feedback exported successfully!\\n\\nThis feedback will be used to improve future scraping accuracy.\\nUse the apply_feedback() method to retrain your models.");'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Scraping Results Feedback - Session {session_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }}
        .prediction {{ background: white; border: 2px solid #ddd; margin: 25px 0; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .prediction.correct {{ border-color: #28a745; background: #f8fff9; }}
        .prediction.incorrect {{ border-color: #dc3545; background: #fff8f8; }}
        .content {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 5px solid #007bff; }}
        .predictions-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }}
        .pred-card {{ background: #e9ecef; padding: 15px; border-radius: 8px; text-align: center; }}
        .buttons {{ text-align: center; margin: 25px 0; }}
        button {{ margin: 10px; padding: 15px 30px; font-size: 16px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }}
        .btn-correct {{ background: #28a745; color: white; }}
        .btn-incorrect {{ background: #dc3545; color: white; }}
        .btn-uncertain {{ background: #ffc107; color: #212529; }}
        .feedback-section {{ margin-top: 20px; padding: 20px; background: #e3f2fd; border-radius: 8px; }}
        .export-section {{ position: fixed; top: 20px; right: 20px; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Scraping Results Feedback</h1>
        <p>Session: {session_id} | Help improve future accuracy by reviewing these predictions</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>{len(posts)}</h3>
            <p>Posts Scraped</p>
        </div>
        <div class="stat-card">
            <h3>{len(predictions)}</h3>
            <p>Predictions to Review</p>
        </div>
        <div class="stat-card">
            <h3>0</h3>
            <p>Feedback Given</p>
        </div>
    </div>
    
    <div class="export-section">
        <h4>📊 Progress</h4>
        <p><strong>Reviewed:</strong> <span id="reviewed-count">0</span> / {len(predictions)}</p>
        <button onclick="exportFeedback()" style="background: #007bff; color: white; padding: 10px 20px; border-radius: 5px;">
            💾 Export Feedback
        </button>
    </div>
    
    <div id="predictions">
"""
        
        for i, pred in enumerate(predictions):
            text_preview = pred['text_content'][:300] + "..." if len(pred['text_content']) > 300 else pred['text_content']
            
            final_pred = pred['final_prediction']
            all_preds = final_pred['all_predictions']
            
            html += f"""
        <div class="prediction" id="prediction-{i}">
            <h3>🤔 Prediction #{i+1} - Container {pred['container_index']+1}</h3>
            
            <div class="content">
                <h4>📄 Content:</h4>
                <p style="max-height: 150px; overflow-y: auto; padding: 10px; background: white; border-radius: 5px;">{text_preview.replace(chr(10), '<br>')}</p>
                <p><strong>Length:</strong> {len(pred['text_content'])} characters</p>
            </div>
            
            <div class="predictions-grid">
                <div class="pred-card">
                    <h5>🔧 Structural</h5>
                    <p><strong>{all_preds['structural']['type'].replace('_', ' ').title()}</strong></p>
                    <p>{all_preds['structural']['confidence']:.1f}% confidence</p>
                </div>
                
                {"<div class='pred-card'><h5>🤖 DOM ML</h5><p><strong>" + ("Main Post" if all_preds['dom_ml']['is_main_post'] else "Comment") + "</strong></p><p>" + f"{all_preds['dom_ml']['confidence']*100:.1f}% confidence</p></div>" if all_preds.get('dom_ml') else ""}
                
                {"<div class='pred-card'><h5>🧠 LLM</h5><p><strong>" + all_preds['llm']['type'].replace('_', ' ').title() + "</strong></p><p>" + f"{all_preds['llm']['confidence']:.1f}% confidence</p></div>" if all_preds.get('llm') else ""}
                
                <div class="pred-card" style="background: #fff3cd; border: 2px solid #ffeaa7;">
                    <h5>⚡ Final Decision</h5>
                    <p><strong>{"Main Post" if final_pred['is_main_post'] else "Comment"}</strong></p>
                    <p>{final_pred['confidence']:.1f}% confidence</p>
                    <p><em>{final_pred['method']}</em></p>
                </div>
            </div>
            
            <div class="feedback-section">
                <h4>🎯 Your Feedback: Was this prediction correct?</h4>
                <p><em>Based on the content above, should this have been classified as a <strong>Main Post</strong> or <strong>Comment</strong>?</em></p>
            </div>
            
            <div class="buttons">
                <button class="btn-correct" onclick="giveFeedback({i}, 'correct')">
                    ✅ Prediction was CORRECT
                </button>
                <button class="btn-incorrect" onclick="giveFeedback({i}, 'incorrect')">
                    ❌ Prediction was WRONG
                </button>
                <button class="btn-uncertain" onclick="giveFeedback({i}, 'uncertain')">
                    🤷 I'm not sure
                </button>
            </div>
            
            <div id="feedback-result-{i}" style="margin-top: 15px; text-align: center;"></div>
        </div>
"""
        
        # Now add the JavaScript section - using string concatenation to avoid f-string issues
        javascript_section = """
    </div>
    
    <script>
        let feedback = {};
        
        function giveFeedback(index, feedbackType) {
            feedback[index] = feedbackType;
            
            const predictionDiv = document.getElementById('prediction-' + index);
            const resultDiv = document.getElementById('feedback-result-' + index);
            
            if (feedbackType === 'correct') {
                predictionDiv.className = 'prediction correct';
                resultDiv.innerHTML = '<div style="color: #28a745; font-weight: bold; padding: 10px; background: #d4edda; border-radius: 5px;">✅ Marked as CORRECT - this will reinforce the model</div>';
            } else if (feedbackType === 'incorrect') {
                predictionDiv.className = 'prediction incorrect';
                resultDiv.innerHTML = '<div style="color: #dc3545; font-weight: bold; padding: 10px; background: #f8d7da; border-radius: 5px;">❌ Marked as WRONG - this will help correct the model</div>';
            } else {
                predictionDiv.className = 'prediction';
                resultDiv.innerHTML = '<div style="color: #856404; font-weight: bold; padding: 10px; background: #fff3cd; border-radius: 5px;">🤷 Marked as UNCERTAIN - this will be flagged for additional review</div>';
            }
            
            updateProgress();
            
            // Scroll to next prediction
            const nextPred = document.getElementById('prediction-' + (index + 1));
            if (nextPred) {
                setTimeout(() => nextPred.scrollIntoView({ behavior: 'smooth', block: 'center' }), 1000);
            }
        }
        
        function updateProgress() {
            const reviewedCount = Object.keys(feedback).length;
            document.getElementById('reviewed-count').textContent = reviewedCount;
            
            // Update stats card
            const statsCards = document.querySelectorAll('.stat-card h3');
            if (statsCards.length >= 3) {
                statsCards[2].textContent = reviewedCount;
            }
        }
        
        function exportFeedback() {
            const reviewedCount = Object.keys(feedback).length;
            
            if (reviewedCount === 0) {
                alert('Please provide feedback on at least one prediction before exporting.');
                return;
            }
            
            const exportData = {
                session_id: '""" + session_id + """',
                feedback: feedback,
                metadata: {
                    total_predictions: """ + str(len(predictions)) + """,
                    reviewed_predictions: reviewedCount,
                    export_timestamp: new Date().toISOString(),
                    feedback_type: 'scraping_results_review'
                }
            };
            
            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            
            const link = document.createElement('a');
            link.href = URL.createObjectURL(dataBlob);
            link.download = 'scraping_feedback_""" + session_id + """_' + new Date().toISOString().slice(0,19).replace(/:/g, '-') + '.json';
            link.click();
            
            """ + alert_message + """
        }
    </script>
</body>
</html>
"""
        
        html += javascript_section
        return html
    
    def apply_feedback_to_models(self, feedback_file: str, enhanced_scraper) -> bool:
        """Apply human feedback to retrain models"""
        
        try:
            with open(feedback_file, 'r') as f:
                feedback_data = json.load(f)
            
            session_id = feedback_data['session_id']
            feedback_dict = feedback_data['feedback']
            
            # Load the corresponding prediction results
            results_file = self.output_dir / f"prediction_results_{session_id}.json"
            
            with open(results_file, 'r') as f:
                prediction_results = json.load(f)
            
            # Create training examples from feedback
            training_examples = []
            
            for pred_index_str, feedback_type in feedback_dict.items():
                pred_index = int(pred_index_str)
                
                if pred_index < len(prediction_results):
                    pred_result = prediction_results[pred_index]
                    
                    if feedback_type in ['correct', 'incorrect']:
                        # Determine correct label based on feedback
                        final_pred = pred_result['final_prediction']
                        predicted_is_main_post = final_pred['is_main_post']
                        
                        if feedback_type == 'correct':
                            # Prediction was right
                            correct_label = predicted_is_main_post
                        else:
                            # Prediction was wrong, so correct label is opposite
                            correct_label = not predicted_is_main_post
                        
                        training_examples.append({
                            'html_content': pred_result['html_content'],
                            'text_content': pred_result['text_content'],
                            'position_data': pred_result['position_data'],
                            'is_main_post': correct_label
                        })
            
            if training_examples:
                print(f"📄 Applying feedback: {len(training_examples)} corrective examples")
                
                # Retrain the DOM ensemble with feedback
                metrics = enhanced_scraper.add_manual_labels_and_retrain(training_examples)
                
                if metrics:
                    print("🎉 Feedback successfully applied to models!")
                    print(f"   New test accuracy: {metrics['ensemble_test_score']:.3f}")
                    return True
                else:
                    print("❌ Failed to apply feedback")
                    return False
            else:
                print("⚠️ No actionable feedback found")
                return False
                
        except Exception as e:
            logger.error(f"Error applying feedback: {e}")
            return False