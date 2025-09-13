#!/usr/bin/env python3
"""
Create initial DOM models for Facebook scraper 3-layer system
FIXED VERSION with more training examples
"""

import asyncio
import json
from pathlib import Path
from src.dom_ensemble import MLEnsemble

async def create_initial_models():
    """Create initial DOM models with sample data"""
    
    print("Creating initial DOM models for 3-layer system...")
    
    # Create ensemble
    model_dir = Path("models/dom_ensemble")
    ensemble = MLEnsemble(model_dir=model_dir)
    
    # EXPANDED training data - need at least 20+ examples for proper train/test split
    training_examples = [
        # Main posts (is_main_post=True) - 15 examples
        {
            'html_content': '<div class="main"><div data-testid="story"><div>User Name</div><div>Shared with Private group</div><div>GI Joe lot for sale $50 shipped. All complete figures...</div></div></div>' * 10,
            'text_content': 'User Name · 2d · Shared with Private group\nGI Joe lot for sale $50 shipped. All complete figures with accessories. PayPal ready.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="post"><span>Author Name</span><span>1h</span><div>For sale: Cobra Commander MOC $25 OBO. Mint condition, see more...</div></div>' * 15,
            'text_content': 'Author Name · 1h · Shared with Private group\nFor sale: Cobra Commander MOC $25 OBO. Mint condition, never opened. Ships next day.',
            'is_main_post': True
        },
        {
            'html_content': '<article role="article"><div><h3>Seller Name</h3><time>3d</time><p>Vintage GI Joe collection clearance. Multiple figures available...</p></div></article>' * 12,
            'text_content': 'Seller Name · 3d · Shared with Public\nVintage GI Joe collection clearance. Multiple figures available, prices in comments.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="story"><div>Dealer Name</div><div>Shared with Private group</div><div>New arrivals: classified figures, vehicles, playsets. DM for pricing...</div></div>' * 20,
            'text_content': 'Dealer Name · 6h · Shared with Private group\nNew arrivals: classified figures, vehicles, playsets. DM for pricing. Fast shipping.',
            'is_main_post': True
        },
        {
            'html_content': '<div><span>Collector</span><div>July 15</div><div>Looking to trade my Snake Eyes v2 for Storm Shadow v1. Both MOC condition...</div></div>' * 8,
            'text_content': 'Collector · July 15 · Shared with Private group\nLooking to trade my Snake Eyes v2 for Storm Shadow v1. Both MOC condition.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="post-main"><span>Seller123</span><div>Shared with Private group</div><div>Terrordome playset complete $200 OBO. All original parts included...</div></div>' * 18,
            'text_content': 'Seller123 · 4d · Shared with Private group\nTerrordome playset complete $200 OBO. All original parts included. Pickup or shipping available.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="content"><h3>ActionFigureFan</h3><p>12h</p><div>ISO: Wild Weasel pilot figure from Rattler vehicle. Willing to pay good price...</div></div>' * 14,
            'text_content': 'ActionFigureFan · 12h · Shared with Private group\nISO: Wild Weasel pilot figure from Rattler vehicle. Willing to pay good price for complete figure.',
            'is_main_post': True
        },
        {
            'html_content': '<div><span>VintageDealer</span><div>2d</div><div>Estate sale finds! Multiple 1980s GI Joe figures, vehicles. Photos in comments...</div></div>' * 16,
            'text_content': 'VintageDealer · 2d · Shared with Private group\nEstate sale finds! Multiple 1980s GI Joe figures, vehicles. Photos in comments. Serious buyers only.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="story-container"><div>JoeCollector99</div><div>Shared with Private group</div><div>Custom painted Storm Shadow available $45. High quality work...</div></div>' * 11,
            'text_content': 'JoeCollector99 · 1d · Shared with Private group\nCustom painted Storm Shadow available $45. High quality work, clear coat finish. DM if interested.',
            'is_main_post': True
        },
        {
            'html_content': '<div><span>ToyHunter</span><span>5h</span><div>Found some rare figures at local shop. Selling extras: Shipwreck, Gung-Ho...</div></div>' * 13,
            'text_content': 'ToyHunter · 5h · Shared with Private group\nFound some rare figures at local shop. Selling extras: Shipwreck, Gung-Ho, others. PM for list.',
            'is_main_post': True
        },
        {
            'html_content': '<article><div>RetroToys</div><div>July 20</div><div>Vehicle lot sale: HISS tank, MOBAT, others. All need minor repairs...</div></article>' * 9,
            'text_content': 'RetroToys · July 20 · Shared with Private group\nVehicle lot sale: HISS tank, MOBAT, others. All need minor repairs. $150 for everything.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="main-content"><span>FigureDealer</span><div>Shared with Public</div><div>HUGE collection for sale. Over 200 figures, 50+ vehicles...</div></div>' * 25,
            'text_content': 'FigureDealer · 3d · Shared with Public\nHUGE collection for sale. Over 200 figures, 50+ vehicles. Must sell due to move. Serious offers only.',
            'is_main_post': True
        },
        {
            'html_content': '<div><h3>JoeFan2024</h3><time>1d</time><div>Trading post: Have extra Destro v1, need Baroness v1. Both MOC...</div></div>' * 12,
            'text_content': 'JoeFan2024 · 1d · Shared with Private group\nTrading post: Have extra Destro v1, need Baroness v1. Both MOC condition required.',
            'is_main_post': True
        },
        {
            'html_content': '<div class="story"><div>VintageSeller</div><div>6h</div><div>Clearing out storage unit. GI Joe, Transformers, Star Wars mix...</div></div>' * 17,
            'text_content': 'VintageSeller · 6h · Shared with Private group\nClearing out storage unit. GI Joe, Transformers, Star Wars mix. Good prices, bulk discounts.',
            'is_main_post': True
        },
        {
            'html_content': '<div><span>CobraCollector</span><div>Shared with Private group</div><div>Cobra vehicles for sale: Night Raven, Water Moccasin, Stun...</div></div>' * 19,
            'text_content': 'CobraCollector · 2d · Shared with Private group\nCobra vehicles for sale: Night Raven, Water Moccasin, Stun. All complete with pilots.',
            'is_main_post': True
        },
        
        # Comments (is_main_post=False) - 15 examples  
        {
            'html_content': '<div class="comment"><span>Commenter</span><span>AuthorVery responsive</span><span>2h</span><span>Still available?</span><div>LikeReply</div></div>',
            'text_content': 'Commenter AuthorVery responsive · 2h\nStill available? LikeReply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>User</span><span>1d</span><span>PM sent</span><div>Like</div><div>Reply</div></div>',
            'text_content': 'User · 1d\nPM sent LikeReply',
            'is_main_post': False
        },
        {
            'html_content': '<div class="response"><span>Buyer</span><span>AuthorTop contributor</span><span>4h</span><span>Interested</span></div>',
            'text_content': 'Buyer AuthorTop contributor · 4h\nInterested Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>Member</span><span>AuthorActive poster</span><span>30m</span><span>How much for the lot?</span><div>LikeReply</div></div>',
            'text_content': 'Member AuthorActive poster · 30m\nHow much for the lot? LikeReply',
            'is_main_post': False
        },
        {
            'html_content': '<div class="reply"><span>Fan</span><span>5h</span><span>Mine if still available</span></div>',
            'text_content': 'Fan · 5h\nMine if still available Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>QuickBuyer</span><span>AuthorRegular member</span><span>1h</span><span>I\'ll take it</span><div>Like</div></div>',
            'text_content': 'QuickBuyer AuthorRegular member · 1h\nI\'ll take it Like',
            'is_main_post': False
        },
        {
            'html_content': '<div class="comment-reply"><span>Collector123</span><span>3h</span><span>Do you have the file card?</span><div>Reply</div></div>',
            'text_content': 'Collector123 · 3h\nDo you have the file card? Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>JoeFan</span><span>AuthorContributor</span><span>2d</span><span>Great price!</span><div>LikeReply</div></div>',
            'text_content': 'JoeFan AuthorContributor · 2d\nGreat price! LikeReply',
            'is_main_post': False
        },
        {
            'html_content': '<div class="response"><span>Buyer99</span><span>6h</span><span>Can you do $40 shipped?</span></div>',
            'text_content': 'Buyer99 · 6h\nCan you do $40 shipped? Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>Member456</span><span>AuthorNew member</span><span>1d</span><span>Is this still for sale?</span><div>Like</div></div>',
            'text_content': 'Member456 AuthorNew member · 1d\nIs this still for sale? Like',
            'is_main_post': False
        },
        {
            'html_content': '<div class="comment"><span>FastBuyer</span><span>AuthorActive</span><span>45m</span><span>Next in line</span><div>Reply</div></div>',
            'text_content': 'FastBuyer AuthorActive · 45m\nNext in line Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>Shopper</span><span>2h</span><span>What condition is it in?</span><div>LikeReply</div></div>',
            'text_content': 'Shopper · 2h\nWhat condition is it in? LikeReply',
            'is_main_post': False
        },
        {
            'html_content': '<div class="reply"><span>QuickResponse</span><span>AuthorHelpful</span><span>30m</span><span>Thanks!</span></div>',
            'text_content': 'QuickResponse AuthorHelpful · 30m\nThanks! Like',
            'is_main_post': False
        },
        {
            'html_content': '<div><span>Negotiator</span><span>1d</span><span>Would you consider $80 for the lot?</span><div>Reply</div></div>',
            'text_content': 'Negotiator · 1d\nWould you consider $80 for the lot? Reply',
            'is_main_post': False
        },
        {
            'html_content': '<div class="comment-content"><span>RegularBuyer</span><span>AuthorTrusted</span><span>4h</span><span>Sent you a message</span><div>LikeReply</div></div>',
            'text_content': 'RegularBuyer AuthorTrusted · 4h\nSent you a message LikeReply',
            'is_main_post': False
        }
    ]
    
    # Add training examples
    print(f"Adding {len(training_examples)} training examples...")
    for example in training_examples:
        ensemble.add_training_example(
            html_content=example['html_content'],
            text_content=example['text_content'],
            is_main_post=example['is_main_post']
        )
    
    # Train models with adjusted test size
    print("Training DOM ensemble models...")
    try:
        # Use smaller test size to ensure enough examples in test set
        metrics = ensemble.train_models(test_size=0.3)  # 30% for test, 70% for train
        
        print("\nDOM models created successfully!")
        print(f"   Test accuracy: {metrics['ensemble_test_score']:.3f}")
        print(f"   Training examples: {metrics['training_size']}")
        print(f"   Models saved to: {model_dir}")
        
        # Show feature importance
        if metrics.get('feature_importance'):
            print("\nTop 5 learned features:")
            for i, (feature, importance) in enumerate(list(metrics['feature_importance'].items())[:5]):
                clean_name = feature.replace('_', ' ').title()
                print(f"   {i+1}. {clean_name}: {importance:.3f}")
        
        return True
        
    except Exception as e:
        print(f"Model training failed: {e}")
        return False

async def test_models():
    """Test the created models"""
    print("\nTesting created models...")
    
    model_dir = Path("models/dom_ensemble")
    ensemble = MLEnsemble(model_dir=model_dir)
    
    if ensemble.load_models():
        print("Models loaded successfully")
        
        # Test prediction
        test_post = {
            'html_content': '<div class="post"><span>Test User</span><div>Shared with Private group</div><div>Selling GI Joe figures $20 each</div></div>' * 10,
            'text_content': 'Test User · 1h · Shared with Private group\nSelling GI Joe figures $20 each. PayPal ready.',
        }
        
        result = ensemble.predict(test_post['html_content'], test_post['text_content'])
        print(f"Test prediction: {'Main Post' if result['is_main_post'] else 'Comment'} ({result['confidence']:.1f}% confidence)")
        
        return True
    else:
        print("Failed to load models")
        return False

if __name__ == "__main__":
    asyncio.run(create_initial_models())
    asyncio.run(test_models())
    
    print(f"\nSetup complete! Your 3-layer system should now work:")
    print(f"   Layer 1: Structural detection (always active)")
    print(f"   Layer 2: DOM ML models (now available)")  
    print(f"   Layer 3: LLM (fix OpenAI version)")
    print(f"\nNext steps:")
    print(f"1. Fix OpenAI: pip install openai==1.3.7")
    print(f"2. Run your scraper again")
    print(f"3. Look for '3-layer detection' messages!")