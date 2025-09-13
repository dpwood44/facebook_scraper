"""
DOM Ensemble ML system for Facebook post classification
Shortened class names and optimized for production use
"""

import pandas as pd
import numpy as np
import re
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import logging

# ML imports
from sklearn.ensemble import RandomForestClassifier, VotingClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

logger = logging.getLogger(__name__)

class DOMExtractor:
    """Extract comprehensive features from Facebook DOM elements"""
    
    def __init__(self):
        self.feature_names = [
            # Basic counts
            'div_count', 'span_count', 'link_count', 'img_count', 'button_count',
            'text_length', 'word_count', 'sentence_count', 'paragraph_count',
            
            # Facebook-specific patterns
            'has_profile_link', 'has_reaction_buttons', 'has_share_button', 
            'has_comment_section', 'has_timestamp_pattern', 'has_author_label',
            'has_privacy_indicator', 'has_see_more', 'has_shared_with',
            
            # Content patterns
            'has_price_pattern', 'has_sale_keywords', 'has_gi_joe_terms',
            'capitalization_ratio', 'separator_count', 'newline_count',
            'exclamation_count', 'question_count',
            
            # Structure analysis
            'html_size', 'nesting_depth', 'class_diversity', 'id_count',
            'data_attribute_count', 'aria_label_count',
            
            # Visual indicators
            'element_width', 'element_height', 'element_area', 'y_position',
            
            # Complexity metrics
            'text_to_html_ratio', 'unique_words_ratio', 'avg_word_length',
            'css_class_count', 'inline_style_presence',
            
            # Facebook UI patterns
            'ui_element_density', 'interaction_button_count', 'media_element_count',
            'facebook_data_attributes', 'testid_count'
        ]
    
    def extract_features(self, html_content: str, text_content: str, 
                        position_data: Optional[Dict] = None) -> Dict[str, float]:
        """Extract all features from a Facebook DOM element"""
        
        features = {}
        
        # Basic counts
        features['div_count'] = html_content.count('<div')
        features['span_count'] = html_content.count('<span')
        features['link_count'] = html_content.count('<a ')
        features['img_count'] = html_content.count('<img')
        features['button_count'] = html_content.count('<button') + html_content.count('role="button"')
        
        # Text analysis
        features['text_length'] = len(text_content)
        features['word_count'] = len(text_content.split()) if text_content else 0
        features['sentence_count'] = text_content.count('.') + text_content.count('!') + text_content.count('?')
        features['paragraph_count'] = text_content.count('\n') + 1
        
        # Facebook-specific patterns
        features['has_profile_link'] = int('href="/profile' in html_content or 'href="/user' in html_content)
        features['has_reaction_buttons'] = int('aria-label="Like"' in html_content or 'Like' in text_content[-20:])
        features['has_share_button'] = int('Share' in html_content)
        features['has_comment_section'] = int('Write a comment' in html_content or 'Comment' in html_content)
        features['has_timestamp_pattern'] = int(bool(re.search(r'\d+[hmsdwy]', text_content)))
        features['has_author_label'] = int('Author' in text_content)
        features['has_privacy_indicator'] = int('Shared with' in text_content)
        features['has_see_more'] = int('See more' in text_content)
        features['has_shared_with'] = int('Shared with Private group' in text_content or 'Shared with Public' in text_content)
        
        # Content patterns
        features['has_price_pattern'] = int('$' in text_content or re.search(r'\d+\s*obo', text_content.lower()) is not None)
        sale_keywords = ['for sale', 'fs:', 'selling', 'shipped', 'paypal', 'obo', 'firm']
        features['has_sale_keywords'] = sum(1 for kw in sale_keywords if kw in text_content.lower())
        gi_joe_terms = ['gi joe', 'cobra', 'hasbro', 'moc', 'mip', 'vintage', 'loose', 'complete']
        features['has_gi_joe_terms'] = sum(1 for term in gi_joe_terms if term in text_content.lower())
        
        # Text characteristics
        if text_content:
            features['capitalization_ratio'] = sum(1 for c in text_content if c.isupper()) / len(text_content)
        else:
            features['capitalization_ratio'] = 0
        features['separator_count'] = text_content.count('·')
        features['newline_count'] = text_content.count('\n')
        features['exclamation_count'] = text_content.count('!')
        features['question_count'] = text_content.count('?')
        
        # Structure analysis
        features['html_size'] = len(html_content)
        features['nesting_depth'] = self._calculate_nesting_depth(html_content)
        features['class_diversity'] = len(set(re.findall(r'class="([^"]*)"', html_content)))
        features['id_count'] = html_content.count('id="')
        features['data_attribute_count'] = len(re.findall(r'data-[a-zA-Z-]+=', html_content))
        features['aria_label_count'] = html_content.count('aria-label=')
        
        # Visual data (if available)
        if position_data:
            features['element_width'] = position_data.get('width', 0)
            features['element_height'] = position_data.get('height', 0)
            features['element_area'] = features['element_width'] * features['element_height']
            features['y_position'] = position_data.get('y', 0)
        else:
            features['element_width'] = 0
            features['element_height'] = 0
            features['element_area'] = 0
            features['y_position'] = 0
        
        # Complexity metrics
        if features['html_size'] > 0:
            features['text_to_html_ratio'] = features['text_length'] / features['html_size']
        else:
            features['text_to_html_ratio'] = 0
            
        if features['word_count'] > 0:
            unique_words = len(set(text_content.lower().split()))
            features['unique_words_ratio'] = unique_words / features['word_count']
            features['avg_word_length'] = features['text_length'] / features['word_count']
        else:
            features['unique_words_ratio'] = 0
            features['avg_word_length'] = 0
        
        features['css_class_count'] = html_content.count('class=')
        features['inline_style_presence'] = int('style=' in html_content)
        
        # Facebook-specific UI patterns
        ui_elements = ['Like', 'Comment', 'Share', 'Follow', 'See more', 'Reply']
        features['ui_element_density'] = sum(html_content.count(elem) for elem in ui_elements) / max(features['html_size'], 1) * 1000
        
        interaction_buttons = ['role="button"', 'aria-label="Like"', 'aria-label="Comment"']
        features['interaction_button_count'] = sum(html_content.count(pattern) for pattern in interaction_buttons)
        
        media_elements = ['<img', '<video', '<svg']
        features['media_element_count'] = sum(html_content.count(elem) for elem in media_elements)
        
        fb_data_attrs = ['data-ft=', 'data-testid=', 'data-pagelet=', 'data-ad-preview=']
        features['facebook_data_attributes'] = sum(html_content.count(attr) for attr in fb_data_attrs)
        features['testid_count'] = html_content.count('data-testid=')
        
        # Ensure all features are numeric
        for key, value in features.items():
            if isinstance(value, bool):
                features[key] = float(value)
            elif not isinstance(value, (int, float)):
                features[key] = 0.0
        
        return features
    
    def _calculate_nesting_depth(self, html_content: str) -> int:
        """Calculate maximum nesting depth of HTML elements"""
        depth = 0
        max_depth = 0
        
        for char in html_content:
            if char == '<':
                if html_content[html_content.find(char):].startswith('</'):
                    depth -= 1
                else:
                    depth += 1
                    max_depth = max(max_depth, depth)
        
        return max_depth


class MLEnsemble:
    """Ensemble classifier for Facebook post detection using multiple ML models"""
    
    def __init__(self, model_dir: Path = None):
        self.feature_extractor = DOMExtractor()
        self.models = {}
        self.ensemble = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Model directory setup
        self.model_dir = model_dir or Path("models/dom_ensemble")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Training data storage
        self.training_data = []
        self.training_labels = []
        
        # Performance metrics
        self.metrics = {}
        
        logger.info(f"ML Ensemble initialized. Model directory: {self.model_dir}")
    
    def _create_models(self):
        """Create the ensemble of ML models"""
        self.models = {
            'rf': RandomForestClassifier(
                n_estimators=200,
                max_depth=15,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            ),
            'xgb': xgb.XGBClassifier(
                n_estimators=200,
                max_depth=10,
                learning_rate=0.1,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss'
            ),
            'gbm': GradientBoostingClassifier(
                n_estimators=150,
                max_depth=8,
                learning_rate=0.1,
                random_state=42
            ),
            'nn': MLPClassifier(
                hidden_layer_sizes=(100, 50, 25),
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
        }
        
        # Create voting ensemble
        self.ensemble = VotingClassifier(
            estimators=[(name, model) for name, model in self.models.items()],
            voting='soft'
        )
    
    def add_training_example(self, html_content: str, text_content: str, 
                           is_main_post: bool, position_data: Optional[Dict] = None):
        """Add a training example to the dataset"""
        features = self.feature_extractor.extract_features(html_content, text_content, position_data)
        self.training_data.append(features)
        self.training_labels.append(1 if is_main_post else 0)
        
        logger.debug(f"Added training example: is_main_post={is_main_post}, features_count={len(features)}")
    
    def train_models(self, test_size: float = 0.2, save_models: bool = True) -> Dict[str, float]:
        """Train all models in the ensemble"""
        if len(self.training_data) < 10:
            raise ValueError(f"Need at least 10 training examples, got {len(self.training_data)}")
        
        logger.info(f"Training ensemble on {len(self.training_data)} examples")
        
        # Convert to DataFrame
        df = pd.DataFrame(self.training_data)
        y = np.array(self.training_labels)
        
        # Handle missing values
        df = df.fillna(0)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            df, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Create and train models
        self._create_models()
        
        # Train individual models
        individual_scores = {}
        
        for name, model in self.models.items():
            logger.info(f"Training {name}...")
            
            if name == 'nn':
                model.fit(X_train_scaled, y_train)
                train_score = model.score(X_train_scaled, y_train)
                test_score = model.score(X_test_scaled, y_test)
            else:
                model.fit(X_train, y_train)
                train_score = model.score(X_train, y_train)
                test_score = model.score(X_test, y_test)
            
            individual_scores[name] = {
                'train_score': train_score,
                'test_score': test_score
            }
            
            logger.info(f"{name} - Train: {train_score:.3f}, Test: {test_score:.3f}")
        
        # Train ensemble
        logger.info("Training ensemble...")
        self.ensemble.fit(X_train, y_train)
        
        ensemble_train_score = self.ensemble.score(X_train, y_train)
        ensemble_test_score = self.ensemble.score(X_test, y_test)
        
        logger.info(f"Ensemble - Train: {ensemble_train_score:.3f}, Test: {ensemble_test_score:.3f}")
        
        # Generate evaluation metrics
        y_pred = self.ensemble.predict(X_test)
        
        self.metrics = {
            'individual_models': individual_scores,
            'ensemble_train_score': ensemble_train_score,
            'ensemble_test_score': ensemble_test_score,
            'classification_report': classification_report(y_test, y_pred, output_dict=True),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'feature_importance': self._get_feature_importance(X_train.columns),
            'training_size': len(self.training_data),
            'test_size': len(X_test)
        }
        
        self.is_trained = True
        
        if save_models:
            self.save_models()
        
        return self.metrics
    
    def _get_feature_importance(self, feature_names) -> Dict[str, float]:
        """Get feature importance from random forest model"""
        if 'rf' in self.models:
            importance_dict = {}
            importances = self.models['rf'].feature_importances_
            for name, importance in zip(feature_names, importances):
                importance_dict[name] = float(importance)
            
            return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
        return {}
    
    def predict(self, html_content: str, text_content: str, 
                position_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Predict if content is a main post using the ensemble"""
        if not self.is_trained:
            raise ValueError("Models must be trained before prediction")
        
        # Extract features
        features = self.feature_extractor.extract_features(html_content, text_content, position_data)
        
        # Convert to DataFrame
        feature_df = pd.DataFrame([features])
        feature_df = feature_df.fillna(0)
        
        # Make prediction
        prediction = self.ensemble.predict(feature_df)[0]
        probabilities = self.ensemble.predict_proba(feature_df)[0]
        
        # Get individual model predictions
        individual_predictions = {}
        for name, model in self.models.items():
            if name == 'nn':
                scaled_features = self.scaler.transform(feature_df)
                pred = model.predict(scaled_features)[0]
                prob = model.predict_proba(scaled_features)[0]
            else:
                pred = model.predict(feature_df)[0]
                prob = model.predict_proba(feature_df)[0]
            
            individual_predictions[name] = {
                'prediction': int(pred),
                'probability': float(prob[1])
            }
        
        return {
            'is_main_post': bool(prediction),
            'confidence': float(probabilities[1]),
            'ensemble_probabilities': [float(p) for p in probabilities],
            'individual_predictions': individual_predictions,
            'features_extracted': len(features)
        }
    
    def save_models(self):
        """Save trained models to disk"""
        if not self.is_trained:
            logger.warning("No trained models to save")
            return
        
        # Save ensemble model
        model_file = self.model_dir / "ensemble_model.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(self.ensemble, f)
        
        # Save scaler
        scaler_file = self.model_dir / "scaler.pkl"
        with open(scaler_file, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        # Save metrics
        metrics_file = self.model_dir / "training_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        # Save training data
        training_file = self.model_dir / "training_data.pkl"
        with open(training_file, 'wb') as f:
            pickle.dump({
                'data': self.training_data,
                'labels': self.training_labels
            }, f)
        
        logger.info(f"Models saved to {self.model_dir}")
    
    def load_models(self) -> bool:
        """Load trained models from disk"""
        try:
            model_file = self.model_dir / "ensemble_model.pkl"
            scaler_file = self.model_dir / "scaler.pkl"
            
            if not model_file.exists() or not scaler_file.exists():
                logger.info("No saved models found")
                return False
            
            # Load ensemble
            with open(model_file, 'rb') as f:
                self.ensemble = pickle.load(f)
            
            # Load scaler
            with open(scaler_file, 'rb') as f:
                self.scaler = pickle.load(f)
            
            # Load metrics if available
            metrics_file = self.model_dir / "training_metrics.json"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    self.metrics = json.load(f)
            
            # Load training data if available
            training_file = self.model_dir / "training_data.pkl"
            if training_file.exists():
                with open(training_file, 'rb') as f:
                    training_data_dict = pickle.load(f)
                    self.training_data = training_data_dict['data']
                    self.training_labels = training_data_dict['labels']
            
            self.is_trained = True
            logger.info(f"Models loaded from {self.model_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return False
    
    def get_training_stats(self) -> Dict[str, Any]:
        """Get statistics about training data"""
        if not self.training_data:
            return {'message': 'No training data available'}
        
        positive_examples = sum(self.training_labels)
        total_examples = len(self.training_labels)
        
        return {
            'total_examples': total_examples,
            'positive_examples': positive_examples,
            'negative_examples': total_examples - positive_examples,
            'positive_ratio': positive_examples / total_examples if total_examples > 0 else 0,
            'is_trained': self.is_trained,
            'last_metrics': self.metrics
        }
    
    def print_performance_report(self):
        """Print detailed performance report"""
        if not self.metrics:
            print("No metrics available. Train the model first.")
            return
        
        print("\n" + "="*60)
        print("ML ENSEMBLE PERFORMANCE REPORT")
        print("="*60)
        
        print(f"\nTraining Data: {self.metrics['training_size']} examples")
        print(f"Test Data: {self.metrics['test_size']} examples")
        
        print(f"\nEnsemble Performance:")
        print(f"  Train Accuracy: {self.metrics['ensemble_train_score']:.3f}")
        print(f"  Test Accuracy:  {self.metrics['ensemble_test_score']:.3f}")
        
        print(f"\nIndividual Model Performance:")
        for name, scores in self.metrics['individual_models'].items():
            print(f"  {name:4}: Train={scores['train_score']:.3f}, Test={scores['test_score']:.3f}")
        
        if self.metrics['feature_importance']:
            print(f"\nTop 10 Most Important Features:")
            for i, (feature, importance) in enumerate(list(self.metrics['feature_importance'].items())[:10]):
                print(f"  {i+1:2}. {feature:25}: {importance:.4f}")
        
        print("="*60)