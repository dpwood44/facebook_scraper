"""
Facebook Groups Scraper for Collectible Sales (GI Joe, etc.)
Improved version with better data extraction and save reliability
"""

import asyncio
import json
import csv
import re
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import subprocess

class FacebookGroupScraper:
    def __init__(self, download_images=False):
        self.browser = None
        self.context = None
        self.page = None
        self.posts_data = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create scrapes directory in project root
        scrapes_dir = Path("scrapes")
        scrapes_dir.mkdir(exist_ok=True)
        
        # Put the session folder inside scrapes directory
        self.output_dir = scrapes_dir / f"fb_group_scrape_{self.session_id}"
        self.download_images = download_images
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        if download_images:
            (self.output_dir / "images").mkdir(exist_ok=True)
            print(f"Created folder for images: {self.output_dir}/images/")
    
    async def connect_to_existing_browser(self):
        """Connect to an existing browser session"""
        print("\n🔗 Connecting to existing browser...")
        print("-" * 60)
        
        try:
            self.playwright = await async_playwright().start()
            
            # Try to connect to existing browser
            try:
                # Connect to Chrome DevTools on port 9222
                self.browser = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
                
                # Get existing contexts
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]  # Use first context
                    pages = self.context.pages
                    
                    if pages:
                        # Find Facebook tab or use current tab
                        for page in pages:
                            if 'facebook.com' in page.url:
                                self.page = page
                                print(f"✅ Connected to existing Facebook tab")
                                print(f"🌐 Current URL: {page.url[:100]}")
                                return True
                        
                        # If no Facebook tab, use first tab
                        self.page = pages[0]
                        print(f"✅ Connected to browser (using current tab)")
                        print(f"🌐 Current URL: {self.page.url[:100]}")
                        return True
                else:
                    print("❌ No contexts found in browser")
                    
            except Exception as e:
                print(f"❌ Could not connect to existing browser: {e}")
                print("\nTo use an existing browser session:")
                print("1. Close all Chrome/Edge windows")
                print("2. Start Chrome/Edge with remote debugging:")
                print("\n   For Chrome:")
                print('   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
                print("\n   For Edge:")
                print('   "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222')
                print("\n3. Log into Facebook manually")
                print("4. Navigate to your group")
                print("5. Run this script again")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    ###^ 1- URL NAVIGATION & TRIGGER POSTS
    
    async def navigate_to_group(self, group_id):
        """Navigate to a specific group"""
        try:
            current_url = self.page.url
            target_url = f"https://www.facebook.com/groups/{group_id}"
            
            # Only navigate if not already there
            if group_id not in current_url:
                print(f"\n🌐 Navigating to group {group_id}...")
                await self.page.goto(target_url, wait_until='networkidle')
                await asyncio.sleep(3)
            else:
                print(f"\n✅ Already on group {group_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Navigation error: {e}")
            return False
    
    async def get_real_posts_only(self):
        """Get only real posts, filtering out virtualized placeholders"""
        print("  🔍 Finding real posts (filtering virtualized content)...")
        
        # Get all potential post elements
        all_elements = await self.page.locator('[role="article"]').all()
        print(f"  📋 Total elements found: {len(all_elements)}")
        
        real_posts = []
        virtualized_count = 0
        empty_count = 0
        
        for i, element in enumerate(all_elements):
            try:
                # Check if element is virtualized/hidden
                is_virtualized = await element.get_attribute('data-virtualized')
                is_hidden = await element.locator('div[hidden]').count() > 0
                
                # Check HTML content size (virtualized elements are tiny)
                try:
                    html_content = await element.inner_html()
                    html_size = len(html_content)
                except:
                    html_size = 0
                
                # Check if element has meaningful text content
                try:
                    text_content = await element.text_content(timeout=2000)
                    text_length = len(text_content) if text_content else 0
                except:
                    text_length = 0
                
                print(f"    Element {i+1}: virtualized={is_virtualized}, hidden={is_hidden}, html={html_size}, text={text_length}")
                
                # Skip if virtualized, hidden, or too small
                if (is_virtualized == "true" or 
                    is_hidden or 
                    html_size < 5000 or  # Real posts have substantial HTML
                    text_length < 20):   # Real posts have substantial text
                    
                    if is_virtualized == "true" or is_hidden:
                        virtualized_count += 1
                    else:
                        empty_count += 1
                        
                    print(f"    ❌ Skipping element {i+1}: {'virtualized' if is_virtualized == 'true' or is_hidden else 'too small'}")
                    continue
                
                # This appears to be a real post
                real_posts.append(element)
                print(f"    ✅ Real post found: element {i+1}")
                
            except Exception as e:
                print(f"    ⚠️ Error checking element {i+1}: {str(e)[:50]}")
                continue
        
        print(f"  📊 Results: {len(real_posts)} real posts, {virtualized_count} virtualized, {empty_count} empty")
        return real_posts

    async def trigger_post_loading(self):
        """Trigger loading of virtualized posts by scrolling"""
        print("  🔄 Triggering post loading...")
        
        try:
            # Scroll down to trigger loading of more posts
            for scroll_step in range(3):
                print(f"    📜 Scroll step {scroll_step + 1}/3")
                
                # Scroll to different positions to trigger loading
                scroll_positions = [0.3, 0.6, 1.0]  # 30%, 60%, 100% of page
                for position in scroll_positions:
                    await self.page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {position})')
                    await asyncio.sleep(1.5)  # Wait for content to load
                
                # Check how many real posts we have now
                real_posts = await self.get_real_posts_only()
                if len(real_posts) >= 5:  # If we have enough real posts, stop
                    break
                    
            print(f"  ✅ Post loading complete")
            
        except Exception as e:
            print(f"  ⚠️ Error during post loading: {str(e)[:100]}")
 
 
 
    ###^ 2 - MAIN POST SCRAPING METHODS

    async def process_post_with_complete_thread(self, containers, main_post_index, post_number):
        """Process a main post and ALL its comments with enhanced large thread handling"""
        
        try:
            # Find where this post's comments end
            boundary_index = await self.find_post_boundary(containers, main_post_index)
            
            # Extract the complete thread
            thread_containers = containers[main_post_index:boundary_index]
            thread_size = len(thread_containers)
            
            print(f"    Processing complete thread: containers {main_post_index+1} to {boundary_index} ({thread_size} containers)")
            
            # The first container is the main post
            main_container = thread_containers[0]
            comment_containers = thread_containers[1:]  # Everything else is comments
            
            # Adjust processing strategy based on thread size
            if thread_size > 15:
                print(f"    Large thread detected ({thread_size} containers) - using enhanced processing")
            
            # Force load main post if needed
            try:
                html_size = len(await main_container.inner_html(timeout=3000))
                if html_size < 35000:
                    print(f"    Force loading main post...")
                    await self.force_load_post_content(main_container)
            except Exception as e:
                print(f"    Could not check/load main post size: {str(e)[:50]}")
            
            # Extract main post data with appropriate timeout
            main_post_timeout = 20.0 if thread_size > 15 else 15.0
            post_data = await asyncio.wait_for(
                self.extract_post_data_improved_fixed(main_container, post_number),
                timeout=main_post_timeout
            )
            
            # Process comments if present
            if comment_containers:
                comment_container_info_list = []
                for container in comment_containers:
                    comment_container_info_list.append({'container': container})
                
                # Dynamic comment limit based on thread size
                if thread_size > 25:
                    max_comments = min(50, thread_size)  # Cap at 50 for very large threads
                elif thread_size > 15:
                    max_comments = 75
                else:
                    max_comments = 100
                
                await self.process_complete_comment_thread(
                    post_data, 
                    comment_container_info_list,
                    max_comments=max_comments
                )
            
            return post_data, boundary_index
            
        except asyncio.TimeoutError:
            print(f"    Thread processing timed out for {thread_size} containers")
            # Return partial data if we got the main post
            if 'post_data' in locals():
                return post_data, boundary_index
            return None, boundary_index
            
        except Exception as e:
            print(f"    Error processing thread: {str(e)[:100]}")
            import traceback
            print(f"    Error traceback: {traceback.format_exc()[:200]}...")
            return None, boundary_index

    async def scrape_with_thread_boundary_detection(self, num_posts=10):
        """Scrape posts ensuring complete thread boundaries are respected"""
        print(f"\nScraping {num_posts} posts with thread boundary detection...")
        print("-" * 60)
        
        posts = []
        scroll_attempts = 0
        max_scrolls = 15
        container_position = 0
        
        await self.close_any_modals()
        
        while len(posts) < num_posts and scroll_attempts < max_scrolls:
            try:
                # Get all current containers
                all_containers = await self.page.locator('[role="article"]').all()
                
                # Skip containers we've already processed
                remaining_containers = all_containers[container_position:]
                
                if not remaining_containers:
                    print(f"\n  No new containers, scrolling for more...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    continue
                
                print(f"\n  Examining containers starting from {container_position + 1}")
                
                # Find the next main post in the remaining containers
                next_main_post_index = None
                for i, container in enumerate(remaining_containers[:15]):
                    try:
                        html_content = await container.inner_html(timeout=1500)
                        text_content = await container.text_content(timeout=1200) or ""
                        
                        if self.is_main_post_container(text_content, len(html_content)):
                            next_main_post_index = container_position + i
                            print(f"    Found main post at container {next_main_post_index + 1}")
                            break
                            
                    except Exception:
                        continue
                
                if next_main_post_index is None:
                    print(f"    No main post found in current batch, scrolling...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    container_position += 5
                    continue
                
                # Process this post and its complete comment thread
                post_data, boundary_index = await self.process_post_with_complete_thread(
                    all_containers, 
                    next_main_post_index,
                    len(posts) + 1
                )
                
                if post_data and self.validate_main_post_data(post_data):
                    posts.append(post_data)
                    self.print_post_debug_with_comments(post_data)
                    
                    # CRITICAL: Always update self.posts_data immediately
                    self.posts_data = posts.copy()  # Create a copy to avoid reference issues
                    
                    if len(posts) % 3 == 0:
                        await self.auto_save(posts)
                    
                    print(f"    Success! Total posts: {len(posts)}")
                
                # Move our position to after this complete thread
                container_position = boundary_index
                scroll_attempts = 0
                
            except Exception as e:
                print(f"\nError in boundary detection processing: {str(e)[:100]}")
                scroll_attempts += 1
                container_position += 3
                continue
        
        # FINAL: Ensure posts_data is always set before returning
        self.posts_data = posts
        print(f"\nCompleted boundary-aware scraping: {len(posts)} main posts")
        return posts

    def is_main_post_container(self, text_content, html_size):
        """Enhanced main post detection with sale-context awareness"""
        
        # SALE INDICATORS should override comment signals (highest priority)
        strong_sale_indicators = [
            '$' in text_content and any(word in text_content.lower() for word in ['shipped', 'obo', 'firm', 'sold']),
            any(phrase in text_content.lower() for phrase in ['for sale', 'fs:', 'wts:', 'price drop']),
            text_content.count('$') > 0 and len(text_content) > 80,  # Price with substantial text
        ]
        
        # If it has strong sale indicators, it's definitely a main post regardless of other signals
        if any(strong_sale_indicators):
            print(f"      SALE POST DETECTED: {text_content[:50]}...")
            return True
        
        # STRONG comment indicators (but can be overridden by sale indicators above)
        strong_comment_indicators = [
            text_content.endswith('LikeReply') and '$' not in text_content,  # Only if no price
            text_content.endswith('Reply') and len(text_content) < 100,
            text_content.endswith('Like') and len(text_content) < 50,
            'LikeCommentSend' in text_content and len(text_content) < 150 and '$' not in text_content,
            text_content.startswith('Following.') and 'LikeReply' in text_content,
            
            # Very short responses without sale context
            (len(text_content.split()) < 8 and 
            any(pattern in text_content.lower() for pattern in [
                'nice', 'cool', 'awesome', 'great', 'beautiful', 'sweet', 'yes', 'no',
                'thanks', 'thank you', 'lol', 'haha', 'wow', 'love it', 'agreed'
            ]) and '$' not in text_content)
        ]
        
        # Apply strong comment indicators only if no sale context
        if any(strong_comment_indicators):
            print(f"      STRONG COMMENT SIGNAL: {text_content[:50]}...")
            return False
        
        # Main post indicators
        main_post_indicators = [
            # Size-based indicators
            html_size > 40000,  
            len(text_content) > 150,  
            
            # Facebook-specific patterns
            'Shared with Private group' in text_content,
            any(title in text_content for title in ['All-star contributor', 'Top contributor', 'Rising contributor']),
            
            # Time patterns (but not ending with reply actions)
            (any(pattern in text_content for pattern in ['h ·', 'd ·', 'min ·', 'week ·']) 
            and not any(end in text_content for end in ['LikeReply', 'LikeCommentSend'])),
            
            # Collectible/sale patterns
            any(keyword in text_content.lower() for keyword in [
                'paypal', 'shipping', 'complete', 'loose', 'moc', 'mip', 'iso',
                'condition', 'vintage', 'collection'
            ]),
            
            # Structural complexity
            text_content.count('\n') > 5,
        ]
        
        # Regular comment indicators
        regular_comment_indicators = [
            html_size < 20000 and len(text_content) < 120,
            len(text_content) < 40,
            text_content.count('?') > 0 and len(text_content) < 100,
        ]
        
        # Decision logic
        main_post_score = sum(1 for indicator in main_post_indicators if indicator)
        comment_score = sum(1 for indicator in regular_comment_indicators if indicator)
        
        if main_post_score >= 2:
            return True
        elif comment_score >= 2 and main_post_score == 0:
            return False
        elif html_size > 25000:  # Size-based fallback
            return True
        elif html_size < 15000 and len(text_content) < 80:
            return False
        else:
            return len(text_content) > 60 or html_size > 20000

    async def find_post_boundary(self, containers, start_index):
        """Look ahead to find post boundaries with enhanced handling for long comment threads"""
        
        # Look ahead further for posts that might have long comment threads
        look_ahead_limit = min(len(containers), start_index + 35)  # Increased from 20 to 35
        
        for i in range(start_index + 1, look_ahead_limit):
            try:
                container = containers[i]
                
                # Quick check if this looks like a main post
                try:
                    html_content = await container.inner_html(timeout=800)  # Shorter timeout for boundary detection
                    text_content = await container.text_content(timeout=600) or ""
                    html_size = len(html_content)
                    
                    # Skip tiny placeholders
                    if html_size < 300:
                        continue
                    
                    # If this looks like a main post, we found our boundary
                    if self.is_main_post_container(text_content, html_size):
                        print(f"    Boundary found at container {i+1} (next main post)")
                        return i
                        
                except Exception:
                    # If we can't check a container quickly, continue looking
                    continue
                    
            except Exception:
                continue
        
        # If we didn't find a boundary within our look-ahead limit
        print(f"    No boundary found in look-ahead range (checked {look_ahead_limit - start_index - 1} containers)")
        return look_ahead_limit

    # Alternative: Force load content for hidden elements that might be real posts
    async def force_load_hidden_posts(self):
        """Try to force load content in hidden containers"""
        print("  🔄 Attempting to force load hidden posts...")
        
        all_elements = await self.page.locator('[role="article"]').all()
        loaded_count = 0
        
        for i, element in enumerate(all_elements[:20]):  # Check first 20
            try:
                # Get current state
                html_size = len(await element.inner_html())
                text_length = len(await element.text_content(timeout=2000) or "")
                
                # If it has substantial HTML but no text, try to activate it
                if html_size > 20000 and text_length < 100:
                    print(f"    🔄 Trying to activate element {i+1} (html={html_size}, text={text_length})...")
                    
                    try:
                        # Try scrolling it into view
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                        
                        # Try hovering
                        await element.hover()
                        await asyncio.sleep(1)
                        
                        # Check if content loaded
                        new_text_length = len(await element.text_content(timeout=2000) or "")
                        if new_text_length > text_length:
                            loaded_count += 1
                            print(f"    ✅ Activated! Text length: {text_length} -> {new_text_length}")
                        else:
                            print(f"    ⚠️ No change in text length")
                            
                    except Exception as e:
                        print(f"    ❌ Failed to activate: {str(e)[:50]}")
                        
            except Exception as e:
                continue
        
        print(f"  📊 Force-loaded {loaded_count} hidden posts")
        return loaded_count

    async def force_load_post_content(self, post_element):
        """Enhanced force loading with content preservation and modal detection"""
        try:
            # Get initial state
            initial_html = len(await post_element.inner_html())
            initial_text = len(await post_element.text_content(timeout=1000) or "")
            
            print(f"    Initial state: html={initial_html}, text={initial_text}")
            
            # Skip force loading if content already looks substantial
            if initial_html > 40000 and initial_text > 150:
                print(f"    Content already substantial, skipping force load")
                return True
            
            # Strategy 1: Gentle scrolling and hovering (safest approach)
            try:
                await post_element.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await post_element.hover(timeout=2000)
                await asyncio.sleep(2)
                
                # Check if this helped
                mid_html = len(await post_element.inner_html())
                mid_text = len(await post_element.text_content(timeout=1000) or "")
                
                if mid_html > initial_html * 1.5 or mid_text > initial_text * 2:
                    print(f"    Hover loading successful: html {initial_html}→{mid_html}, text {initial_text}→{mid_text}")
                    return True
                    
            except Exception as e:
                print(f"    Hover strategy failed: {str(e)[:50]}")
            
            # Strategy 2: Very careful "See more" expansion
            try:
                see_more_selectors = [
                    'span:has-text("See more")',
                    'text="See more"'
                ]
                
                for selector in see_more_selectors:
                    try:
                        buttons = await post_element.locator(selector).all()
                        if len(buttons) > 0:
                            button = buttons[0]  # Only try the first button
                            if await button.is_visible(timeout=1000):
                                print(f"    Carefully clicking 'See more' button...")
                                
                                # Store current state in case we need to revert
                                pre_click_html = await post_element.inner_html()
                                
                                await button.click(timeout=2000)
                                await asyncio.sleep(1.5)
                                
                                # Check if a modal opened and close it immediately
                                modal_closed = await self.check_and_close_modal()
                                if modal_closed:
                                    print(f"    Closed modal after expanding")
                                
                                # Verify we didn't lose content
                                post_click_html = len(await post_element.inner_html())
                                post_click_text = len(await post_element.text_content(timeout=1000) or "")
                                
                                if post_click_html < initial_html * 0.8:  # Lost significant HTML
                                    print(f"    Warning: Content may have been lost during expansion")
                                else:
                                    print(f"    See more expansion completed safely")
                                
                                break  # Stop after first successful click
                    except Exception as e:
                        print(f"    See more selector failed: {str(e)[:30]}")
                        continue
                        
            except Exception as e:
                print(f"    See more strategy failed: {str(e)[:50]}")
            
            # Check final state
            final_html = len(await post_element.inner_html())
            final_text = len(await post_element.text_content(timeout=2000) or "")
            
            # Calculate improvements
            html_growth = final_html - initial_html
            text_growth = final_text - initial_text
            
            # Determine success more conservatively
            success = (
                html_growth > 500 or         # Some HTML growth
                text_growth > 20 or          # Some text growth
                final_html > 20000 or        # Already substantial
                final_text > 80              # Already substantial text
            )
            
            if success:
                print(f"    Content loaded: html {initial_html}→{final_html} (+{html_growth}), text {initial_text}→{final_text} (+{text_growth})")
            else:
                print(f"    No significant improvement: html {initial_html}→{final_html}, text {initial_text}→{final_text}")
            
            return success
            
        except Exception as e:
            print(f"    Force load error: {str(e)[:50]}")
            return False


    ###^ 3 - COMMENT SCRAPING

    async def process_complete_comment_thread(self, post_data, comment_containers, max_comments=50):
        """Process complete comment threads with robust error handling for large threads"""
        
        container_count = len(comment_containers)
        print(f"    Processing complete comment thread: {container_count} comment containers")
        
        comments_processed = 0
        sales_keywords = ['sold', 'available', 'claim', 'take it', "i'll take", 'pm me', 'paypal', 'shipped']
        errors_encountered = 0
        max_errors = 5  # Stop processing if too many errors
        
        for i, comment_container_info in enumerate(comment_containers):
            if comments_processed >= max_comments:
                print(f"      Reached max comments limit ({max_comments})")
                break
                
            if errors_encountered >= max_errors:
                print(f"      Too many errors ({max_errors}), stopping comment processing")
                break
                
            try:
                comment_id = f"{post_data['post_id']}_comment_{i+1}"
                
                # Use progressively shorter timeouts for large threads to avoid hanging
                timeout_duration = 8.0 if container_count < 10 else 5.0 if container_count < 20 else 3.0
                
                comment_data = await asyncio.wait_for(
                    self.extract_comment_data_with_images(
                        comment_container_info['container'], 
                        comment_id
                    ),
                    timeout=timeout_duration
                )
                
                if comment_data and comment_data.get('text'):
                    post_data['comments'].append(comment_data)
                    comments_processed += 1
                    
                    # Check for sales-related content
                    comment_text_lower = comment_data['text'].lower()
                    is_sales_comment = any(keyword in comment_text_lower for keyword in sales_keywords)
                    
                    if is_sales_comment:
                        comment_data['is_sales_comment'] = True
                    
                    # Progress update for large threads
                    if container_count > 10 and comments_processed % 5 == 0:
                        print(f"      Processed {comments_processed} comments...")
                    
                    # Show preview for first few comments and sales comments
                    if i < 3 or is_sales_comment or container_count > 15:
                        text_preview = comment_data['text'][:60] + "..." if len(comment_data['text']) > 60 else comment_data['text']
                        image_info = f", {comment_data['image_count']} images" if comment_data['image_count'] > 0 else ""
                        sales_flag = " [SALES]" if is_sales_comment else ""
                        print(f"      Comment {i+1}: {text_preview}{image_info}{sales_flag}")
            
            except asyncio.TimeoutError:
                print(f"      Comment {i+1} timed out, continuing...")
                errors_encountered += 1
                continue
            except Exception as e:
                print(f"      Error processing comment {i+1}: {str(e)[:50]}")
                errors_encountered += 1
                continue
        
        # Update comment counts
        post_data['comment_count'] = len(post_data['comments'])
        sales_comments = [c for c in post_data['comments'] if c.get('is_sales_comment', False)]
        post_data['sales_comment_count'] = len(sales_comments)
        
        if errors_encountered > 0:
            print(f"    Thread complete: {comments_processed} comments processed ({len(sales_comments)} sales-related) with {errors_encountered} errors")
        else:
            print(f"    Thread complete: {comments_processed} comments processed ({len(sales_comments)} sales-related)")

    async def extract_and_associate_comments_with_images(self, main_post_data, comment_containers):
        """Extract comment data with images and associate with main post"""
        
        if not comment_containers:
            return
            
        print(f"    Associating {len(comment_containers)} comments...")
        
        for i, comment_container_info in enumerate(comment_containers):
            try:
                comment_id = f"{main_post_data['post_id']}_comment_{i+1}"
                
                # Extract comprehensive comment data including images
                comment_data = await self.extract_comment_data_with_images(
                    comment_container_info['container'], 
                    comment_id
                )
                
                if comment_data and comment_data.get('text'):
                    main_post_data['comments'].append(comment_data)
                    
                    # Show what we found
                    text_preview = comment_data['text'][:50] + "..." if len(comment_data['text']) > 50 else comment_data['text']
                    image_info = f", {comment_data['image_count']} images" if comment_data['image_count'] > 0 else ""
                    print(f"      Associated comment: {text_preview}{image_info}")
            
            except Exception as e:
                print(f"      Error extracting comment {i+1}: {str(e)[:50]}")
                continue
        
        # Update comment count
        main_post_data['comment_count'] = len(main_post_data['comments'])

    async def extract_comment_data_with_images(self, comment_container, comment_id):
        """Extract comprehensive data from a comment container with proper error handling"""
        try:
            # Extract text content
            try:
                text = await comment_container.text_content(timeout=2000) or ""
            except asyncio.TimeoutError:
                print(f"        Comment text extraction timed out")
                text = ""
            except Exception:
                text = ""
            
            # Clean up comment text
            text = text.replace('LikeReply', '').replace('Reply', '').strip()
            
            # Extract author with proper error handling
            try:
                author = await self.extract_comment_author(comment_container)
            except Exception:
                author = ""
            
            # Extract timestamp with proper error handling
            try:
                time_info = await self.extract_comment_timestamp(comment_container)
            except Exception:
                time_info = ""
            
            # Extract images with proper error handling
            try:
                comment_images = await self.extract_comment_images(comment_container, comment_id)
            except Exception as e:
                print(f"        Comment image extraction error: {str(e)[:30]}")
                comment_images = []
            
            return {
                'text': text,
                'author': author,
                'time': time_info,
                'images': comment_images,
                'image_count': len(comment_images),
                'is_extracted_comment': True,
                'has_price': '$' in text,
                'is_sold': any(word in text.lower() for word in ['sold', 'pending'])
            }
            
        except Exception as e:
            print(f"        Comment extraction error: {str(e)[:50]}")
            return None

    async def extract_comment_author(self, comment_container):
        """Extract author from comment with proper exception handling"""
        author_selectors = [
            'strong',
            'a[href*="/profile/"]', 
            'a[href*="/user/"]',
            'span[dir="auto"] strong',
            'h3 a'
        ]
        
        for selector in author_selectors:
            try:
                author_elem = comment_container.locator(selector).first
                try:
                    author_text = await author_elem.text_content(timeout=1000)  # Reduced timeout
                    if author_text and 2 < len(author_text) < 50:
                        # Filter out obvious non-author text
                        if not any(skip in author_text.lower() for skip in ['like', 'reply', 'comment']):
                            return author_text.strip()
                except asyncio.TimeoutError:
                    # Handle timeout gracefully without logging
                    continue
                except Exception:
                    # Handle any other exceptions gracefully
                    continue
            except Exception:
                # Handle locator creation errors
                continue
        
        return ""

    async def extract_comment_timestamp(self, comment_container):
        """Extract timestamp from comment"""
        time_selectors = [
            'abbr',
            'time', 
            'span[title*="ago"]',
            'a[role="link"] span'
        ]
        
        for selector in time_selectors:
            try:
                time_elements = await comment_container.locator(selector).all()
                for elem in time_elements:
                    try:
                        # Try title attribute first
                        time_text = await elem.get_attribute('title', timeout=1000)
                        if not time_text:
                            time_text = await elem.text_content(timeout=1000)
                        
                        if time_text and any(indicator in time_text.lower() for indicator in 
                                        ['ago', 'min', 'hour', 'day', 'week', 'month']):
                            return time_text
                    except:
                        continue
            except:
                continue
        
        return ""

    async def extract_comment_images(self, comment_container, comment_id):
        """Extract images from comment containers"""
        images = []
        
        try:
            # Get all images in the comment
            img_elements = await comment_container.locator('img').all()
            
            for i, img in enumerate(img_elements[:10]):  # Limit to 10 images per comment
                try:
                    src = await img.get_attribute('src', timeout=2000)
                    
                    # Filter for actual content images (not UI elements)
                    if src and ('scontent' in src or 'fbcdn' in src):
                        alt_text = await img.get_attribute('alt', timeout=1000) or ""
                        
                        image_data = {
                            'image_id': f"{comment_id}_img_{i+1}",
                            'url': src,
                            'alt_text': alt_text,
                            'position': i + 1,
                            'is_comment_image': True
                        }
                        
                        images.append(image_data)
                        
                        # Download image if enabled
                        if self.download_images:
                            await self.download_comment_image(image_data, comment_id)
                            
                except Exception as e:
                    print(f"          Error extracting comment image {i+1}: {str(e)[:30]}")
                    continue
                    
        except Exception as e:
            print(f"        Comment image extraction error: {str(e)[:50]}")
        
        return images

    async def download_comment_image(self, image_data, comment_id):
        """Download images from comments"""
        try:
            import aiohttp
            import aiofiles
            
            # Create comment image folder structure
            comment_folder = self.output_dir / "images" / "comments" / comment_id
            comment_folder.mkdir(parents=True, exist_ok=True)
            
            url = image_data['url']
            filename = comment_folder / f"{image_data['image_id']}.jpg"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        async with aiofiles.open(filename, 'wb') as f:
                            await f.write(await response.read())
                        image_data['local_path'] = str(filename)
                        print(f"          📥 Downloaded comment image {image_data['position']}")
                        
        except Exception as e:
            print(f"          ⚠️ Failed to download comment image: {str(e)[:50]}")



    ###^ 4 - POST PROCESSING & VALIDATION

    async def categorize_containers(self, all_containers):
        """Categorize containers with improved timeout handling"""
        main_posts = []
        comment_containers = []
        
        print(f"  Categorizing {len(all_containers)} containers...")
        
        for i, container in enumerate(all_containers):
            try:
                # Use shorter timeout and handle failures gracefully
                try:
                    html_content = await container.inner_html(timeout=3000)  # Reduced to 3 seconds
                    text_content = await container.text_content(timeout=2000) or ""  # Reduced to 2 seconds
                    html_size = len(html_content)
                    text_size = len(text_content.strip())
                except Exception as e:
                    print(f"    Container {i+1}: Timeout/error getting content ({str(e)[:30]}), skipping")
                    continue
                
                # Skip tiny placeholders
                if html_size < 200 and text_size == 0:
                    continue
                
                # Determine if this is a main post or comment
                is_main_post = self.is_main_post_container(text_content, html_size)
                
                if is_main_post:
                    main_posts.append({
                        'index': i,
                        'container': container,
                        'text': text_content,
                        'html_size': html_size,
                        'comments': []
                    })
                    print(f"    Container {i+1}: MAIN POST (html={html_size}, text={text_size})")
                else:
                    parent_post_idx = self.find_parent_post(main_posts, text_content, i)
                    comment_containers.append({
                        'index': i,
                        'container': container,
                        'text': text_content,
                        'html_size': html_size,
                        'parent_post_idx': parent_post_idx
                    })
                    print(f"    Container {i+1}: COMMENT (html={html_size}, text={text_size}, parent={parent_post_idx})")
                    
            except Exception as e:
                print(f"    Error categorizing container {i+1}: {str(e)[:50]}")
                continue
        
        # Associate comments with their parent posts
        for comment in comment_containers:
            if comment['parent_post_idx'] is not None:
                parent_idx = comment['parent_post_idx']
                if parent_idx < len(main_posts):
                    main_posts[parent_idx]['comments'].append(comment)
        
        print(f"  Result: {len(main_posts)} main posts, {len(comment_containers)} comments")
        return main_posts, comment_containers
    
    def is_main_post_container(self, text_content, html_size):
        """Enhanced main post detection with stronger comment filtering"""
        
        # STRONG comment indicators that should override other signals
        strong_comment_indicators = [
            text_content.endswith('LikeReply'),
            text_content.endswith('Reply'),
            text_content.endswith('Like'),
            'LikeCommentSend' in text_content and len(text_content) < 200,
            text_content.startswith('Following.') and 'LikeReply' in text_content,
            
            # Very short responses typical of comments
            len(text_content.split()) < 10 and any(pattern in text_content.lower() for pattern in [
                'nice', 'cool', 'awesome', 'great', 'beautiful', 'sweet', 'yes', 'no',
                'thanks', 'thank you', 'lol', 'haha', 'wow', 'love it', 'agreed'
            ])
        ]
        
        # If ANY strong comment indicator is present, it's definitely a comment
        if any(strong_comment_indicators):
            print(f"      STRONG COMMENT SIGNAL: {text_content[:50]}...")
            return False
        
        # Strong main post indicators
        main_post_indicators = [
            # Size-based indicators (more reliable)
            html_size > 50000,  
            len(text_content) > 200,  
            
            # Facebook-specific text patterns
            'Shared with Private group' in text_content,
            'All-star contributor' in text_content,
            'Top contributor' in text_content,
            'Rising contributor' in text_content,
            
            # Time patterns that appear in main posts (but not ending with LikeReply)
            any(pattern in text_content for pattern in ['h ·', 'd ·', 'min ·', 'week ·']) and not text_content.endswith('Reply'),
            
            # Sale/collectible indicators
            any(keyword in text_content.lower() for keyword in [
                'for sale', 'selling', 'price drop', 'fs:', 'wts:', 'obo',
                'paypal', 'shipping', 'complete', 'loose', 'moc', 'mip', 'iso'
            ]),
            
            # Multiple price indicators
            text_content.count('$') > 0 and len(text_content) > 100,
            
            # Structural indicators
            text_content.count('\n') > 8,
        ]
        
        # Regular comment indicators (weaker than strong ones above)
        regular_comment_indicators = [
            html_size < 15000 and len(text_content) < 100,
            len(text_content) < 50,  # Very short text likely to be comment
            
            # Comment-like patterns
            text_content.count('?') > 0 and len(text_content) < 150,  # Questions are often comments
        ]
        
        # Calculate confidence scores
        main_post_score = sum(1 for indicator in main_post_indicators if indicator)
        comment_score = sum(1 for indicator in regular_comment_indicators if indicator)
        
        # Decision logic with stronger weighting for main posts
        if main_post_score >= 2:  # Lower threshold for main posts
            return True
        elif comment_score >= 2 and main_post_score == 0:  # Only if no main post signals
            return False
        elif html_size > 30000:  # Size-based fallback (reduced threshold)
            return True
        elif html_size < 20000 and len(text_content) < 100:
            return False
        else:
            # Default: treat substantial content as main post
            return len(text_content) > 80 or html_size > 25000
    
    def find_parent_post(self, main_posts, comment_text, comment_index):
        """Find which main post this comment belongs to"""
        if not main_posts:
            return None
        
        # Simple strategy: associate with the most recent main post
        # (Facebook typically shows comments after their parent posts)
        most_recent_post_idx = None
        for i, post in enumerate(main_posts):
            if post['index'] < comment_index:  # Post comes before comment
                most_recent_post_idx = i
        
        # Advanced strategy: try to match comment content with post content
        if most_recent_post_idx is not None and len(main_posts) > 1:
            # Look for content relationships
            recent_post = main_posts[most_recent_post_idx]
            
            # Check if comment references something specific in the recent post
            comment_lower = comment_text.lower()
            post_text_lower = recent_post['text'].lower()
            
            # Look for shared keywords or references
            shared_keywords = []
            comment_words = set(comment_lower.split())
            post_words = set(post_text_lower.split())
            
            # Find meaningful shared words (filter out common words)
            stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            meaningful_shared = comment_words.intersection(post_words) - stop_words
            
            if len(meaningful_shared) > 0:
                return most_recent_post_idx
        
        return most_recent_post_idx

    async def extract_and_associate_comments(self, main_post_data, comment_containers):
        """Extract comment data and associate it with the main post"""
        
        for comment_container in comment_containers:
            try:
                # Extract comment data
                comment_data = await self.extract_comment_data_with_images(comment_container['container'])
                
                if comment_data and comment_data.get('text'):
                    # Add to main post's comments
                    main_post_data['comments'].append(comment_data)
                    main_post_data['comment_count'] = len(main_post_data['comments'])
                    print(f"      Associated comment: {comment_data['text'][:50]}...")
            
            except Exception as e:
                print(f"      Error extracting comment: {str(e)[:50]}")
                continue

    def validate_main_post_data(self, post_data):
        """Validation specifically for main posts (not comments)"""
        if not post_data:
            return False
        
        # Main posts should have substantial content
        has_text = bool(post_data.get('text', '').strip())
        has_author = bool(post_data.get('author', '').strip())
        has_images = post_data.get('image_count', 0) > 0
        has_substantial_content = len(post_data.get('text', '')) > 50
        
        is_valid = (has_text and has_author) or has_images or has_substantial_content
        
        print(f"   Validation: text={has_text}, author={has_author}, images={has_images}, substantial={has_substantial_content} => Valid={is_valid}")
        
        return is_valid

    # Alternative: Check for loaded content before processing
    async def wait_for_post_content(self, post_element, max_wait=10):
        """Wait for a post element to load real content"""
        print(f"      ⏳ Waiting for content to load...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                # Check if content has loaded
                text_content = await post_element.text_content(timeout=1000)
                html_content = await post_element.inner_html()
                
                if (text_content and len(text_content) > 50 and 
                    html_content and len(html_content) > 10000):
                    print(f"      ✅ Content loaded ({len(text_content)} chars text)")
                    return True
                    
                # Wait a bit more
                await asyncio.sleep(1)
                
            except:
                await asyncio.sleep(1)
                continue
        
        print(f"      ❌ Content didn't load after {max_wait}s")
        return False

    def validate_post_data(self, post_data):
        """Validate that post data contains meaningful content"""
        if not post_data:
            return False
            
        # Check if we have at least some meaningful content
        has_text = bool(post_data.get('text', '').strip())
        has_author = bool(post_data.get('author', '').strip())
        has_images = post_data.get('image_count', 0) > 0
        has_comments = post_data.get('comment_count', 0) > 0
        
        # Post is valid if it has text OR author OR images OR comments
        is_valid = has_text or has_author or has_images or has_comments
        
        print(f"   🔍 Validation: text={has_text}, author={has_author}, images={has_images}, comments={has_comments} => Valid={is_valid}")
        
        return is_valid
    
    def print_post_debug_with_comments(self, post_data):
        """Enhanced debug output showing comment details"""
        text_preview = post_data.get('text', '')[:80] or "[No text]"
        author = post_data.get('author', '') or "[No author]"
        
        print(f"   ✓ Text: {text_preview}{'...' if len(post_data.get('text', '')) > 80 else ''}")
        print(f"   👤 Author: {author}")
        print(f"   🕒 Time: {post_data.get('time', '[No time]')}")
        print(f"   📷 Images: {post_data.get('image_count', 0)}")
        
        # Enhanced comment display
        comment_count = post_data.get('comment_count', 0)
        comment_images = sum(c.get('image_count', 0) for c in post_data.get('comments', []))
        
        if comment_images > 0:
            print(f"   💬 Comments: {comment_count} ({comment_images} comment images)")
        else:
            print(f"   💬 Comments: {comment_count}")
        
        sale_info = post_data.get('sale_info')
        if sale_info:
            if sale_info.get('price'):
                print(f"   💰 Price: {sale_info.get('price')}")
            if sale_info.get('items'):
                print(f"   🎯 Items: {', '.join(sale_info.get('items', [])[:3])}")
    
    async def inspect_post_html(self, post_element, post_num):
        """Inspect the HTML structure of a post to understand why it's failing"""
        print(f"\n🔍 INSPECTING POST {post_num} HTML STRUCTURE")
        print("=" * 60)
        
        try:
            # Get the full HTML of the post
            html_content = await post_element.inner_html()
            
            # Save HTML to file for inspection
            html_file = self.output_dir / f"post_{post_num}_html.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(f"<!-- Post {post_num} HTML Structure -->\n")
                f.write(html_content)
            print(f"📄 Full HTML saved to: {html_file}")
            
            # Show condensed HTML structure
            print(f"\n📋 HTML Preview (first 500 chars):")
            print("-" * 40)
            print(html_content[:500])
            print("..." if len(html_content) > 500 else "")
            
            # Test all our selectors and see what they find
            print(f"\n🧪 TESTING SELECTORS:")
            print("-" * 40)
            
            # Text selectors
            text_selectors = [
                'div[dir="auto"]',
                'span[dir="auto"]', 
                'div[data-ad-preview="message"]',
                '[data-testid="post_message"]',
                'div[lang]',
                'p'
            ]
            
            for selector in text_selectors:
                try:
                    elements = await post_element.locator(selector).all()
                    print(f"📝 {selector}: {len(elements)} elements")
                    
                    # Show first few text samples
                    for i, elem in enumerate(elements[:3]):
                        try:
                            text = await elem.text_content(timeout=1000)
                            if text and len(text.strip()) > 5:
                                print(f"    [{i}] {text[:60]}...")
                        except:
                            print(f"    [{i}] <timeout/error>")
                            
                except Exception as e:
                    print(f"❌ {selector}: ERROR - {str(e)[:50]}")
            
            # Author selectors
            print(f"\n👤 AUTHOR SELECTORS:")
            author_selectors = [
                'strong a',
                'h3 a', 
                'a[role="link"] strong',
                'strong',
                'h3',
                '[data-hovercard-user-id] strong',
                'a[data-hovercard-user-id]'
            ]
            
            for selector in author_selectors:
                try:
                    elements = await post_element.locator(selector).all()
                    print(f"👤 {selector}: {len(elements)} elements")
                    
                    for i, elem in enumerate(elements[:2]):
                        try:
                            text = await elem.text_content(timeout=1000)
                            if text:
                                print(f"    [{i}] {text[:40]}...")
                        except:
                            print(f"    [{i}] <timeout/error>")
                            
                except Exception as e:
                    print(f"❌ {selector}: ERROR - {str(e)[:50]}")
            
            # Image selectors
            print(f"\n📷 IMAGE SELECTORS:")
            try:
                img_elements = await post_element.locator('img').all()
                print(f"📷 img: {len(img_elements)} elements")
                
                for i, img in enumerate(img_elements[:3]):
                    try:
                        src = await img.get_attribute('src', timeout=1000)
                        alt = await img.get_attribute('alt', timeout=1000)
                        print(f"    [{i}] src: {src[:50] if src else 'None'}...")
                        print(f"    [{i}] alt: {alt[:40] if alt else 'None'}...")
                    except:
                        print(f"    [{i}] <timeout/error>")
                        
            except Exception as e:
                print(f"❌ img: ERROR - {str(e)[:50]}")
            
            # Look for any data attributes that might help
            print(f"\n🏷️  DATA ATTRIBUTES:")
            try:
                # Get all attributes of the post element
                all_attrs = await post_element.evaluate('el => Array.from(el.attributes).map(attr => attr.name + "=" + attr.value)')
                for attr in all_attrs[:10]:  # Show first 10 attributes
                    if 'data-' in attr or 'aria-' in attr or 'role' in attr:
                        print(f"    {attr[:80]}...")
            except:
                print("    <Could not get attributes>")
            
            print("=" * 60)
            
        except Exception as e:
            print(f"❌ HTML inspection failed: {str(e)}")

    # Modified extract_post_data_improved function with HTML inspection
    async def extract_post_data_with_debug(self, post_element, post_num):
        """Extract post data with optional HTML debugging"""
        
        # First, inspect the HTML if this is a failing post
        await self.inspect_post_html(post_element, post_num)
        
        # Then try normal extraction
        post_data = await self.extract_post_data_improved_fixed(post_element, post_num)
        
        return post_data

    async def quick_post_diagnosis(self):
        """Quick diagnosis of the first few posts"""
        print("\n=== POST DIAGNOSIS ===")
        
        post_elements = await self.page.locator('[role="article"]').all()
        print(f"Found {len(post_elements)} post elements")
        
        for i, post_element in enumerate(post_elements[:5]):
            print(f"\n--- POST {i+1} ---")
            try:
                # Get all text content
                all_text = await post_element.text_content(timeout=3000)
                print(f"Text length: {len(all_text) if all_text else 0}")
                
                if all_text:
                    lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                    print("First 3 lines:")
                    for j, line in enumerate(lines[:3]):
                        print(f"  {j+1}: {line[:100]}...")
                
                # Test key selectors
                div_auto = await post_element.locator('div[dir="auto"]').count()
                strong = await post_element.locator('strong').count()
                imgs = await post_element.locator('img').count()
                
                print(f"div[dir='auto']: {div_auto}, strong: {strong}, img: {imgs}")
                
            except Exception as e:
                print(f"Error: {str(e)[:100]}")
 
    async def detailed_post_inspection(self):
        """Detailed inspection to understand post structure"""
        print("\n=== DETAILED POST INSPECTION ===")
        
        # Try multiple post selectors
        selectors_to_try = [
            '[role="article"]',
            'div[data-pagelet*="FeedUnit"]', 
            'div[data-pagelet*="GroupFeedUnit"]',
            'div[data-ft*="top_level_post_id"]',
            'div[data-testid*="post"]',
            '.userContentWrapper',
            '._5pcr'  # Old Facebook class
        ]
        
        for selector in selectors_to_try:
            try:
                elements = await self.page.locator(selector).all()
                print(f"\n--- SELECTOR: {selector} ---")
                print(f"Found: {len(elements)} elements")
                
                # Inspect first 3 elements in detail
                for i in range(min(3, len(elements))):
                    print(f"\nElement {i+1}:")
                    try:
                        elem = elements[i]
                        
                        # Get HTML structure preview
                        html = await elem.inner_html()
                        print(f"  HTML length: {len(html)}")
                        print(f"  HTML preview: {html[:200]}...")
                        
                        # Get text content
                        text = await elem.text_content()
                        print(f"  Text length: {len(text) if text else 0}")
                        if text:
                            lines = text.split('\n')[:5]  # First 5 lines
                            for j, line in enumerate(lines):
                                if line.strip():
                                    print(f"    Line {j+1}: {line.strip()[:100]}")
                        
                        # Check for specific elements
                        has_imgs = await elem.locator('img').count()
                        has_divs = await elem.locator('div').count()
                        has_links = await elem.locator('a').count()
                        print(f"  Contains: {has_imgs} imgs, {has_divs} divs, {has_links} links")
                        
                    except Exception as e:
                        print(f"  Error inspecting element {i+1}: {str(e)[:100]}")
                        
            except Exception as e:
                print(f"Selector {selector} failed: {str(e)[:100]}")
        
        # Also check what's actually visible on the page
        print(f"\n--- PAGE CONTENT CHECK ---")
        try:
            page_text = await self.page.text_content()
            print(f"Total page text length: {len(page_text) if page_text else 0}")
            
            if page_text:
                # Look for patterns that suggest posts
                lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                print("Sample visible text lines:")
                for i, line in enumerate(lines[:20]):
                    if len(line) > 20:  # Substantial content
                        print(f"  {i+1}: {line[:100]}")
                        
        except Exception as e:
            print(f"Page content check failed: {str(e)}")

    async def try_alternative_post_finding(self):
        """Try to find posts using different strategies"""
        print("\n=== ALTERNATIVE POST FINDING ===")
        
        strategies = [
            # Strategy 1: Look for text patterns that indicate posts
            ("Text-based search", "xpath=//div[contains(text(), '$') or contains(text(), 'sale') or contains(text(), 'sell')]"),
            
            # Strategy 2: Look for image containers
            ("Image containers", "div:has(img)"),
            
            # Strategy 3: Look for user profile links
            ("Profile links", "a[href*='facebook.com/profile/']"),
            
            # Strategy 4: Look for timestamp patterns  
            ("Timestamp elements", "abbr, time, [title*='ago'], [title*='at']"),
            
            # Strategy 5: Look for reaction buttons
            ("Reaction areas", "div[role='button']:has-text('Like'), div[aria-label*='Like']"),
        ]
        
        for strategy_name, selector in strategies:
            try:
                print(f"\n--- {strategy_name} ---")
                
                if selector.startswith("xpath="):
                    # Handle XPath selectors
                    xpath = selector[6:]  # Remove "xpath=" prefix
                    elements_count = await self.page.evaluate(f'''
                        () => {{
                            const result = document.evaluate("{xpath}", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                            return result.snapshotLength;
                        }}
                    ''')
                    print(f"Found: {elements_count} elements")
                    
                    if elements_count > 0:
                        # Get sample text from first few elements
                        sample_texts = await self.page.evaluate(f'''
                            () => {{
                                const result = document.evaluate("{xpath}", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                                const texts = [];
                                for (let i = 0; i < Math.min(3, result.snapshotLength); i++) {{
                                    const node = result.snapshotItem(i);
                                    if (node && node.textContent) {{
                                        texts.push(node.textContent.trim().substring(0, 100));
                                    }}
                                }}
                                return texts;
                            }}
                        ''')
                        
                        for i, text in enumerate(sample_texts):
                            print(f"  Sample {i+1}: {text}")
                else:
                    # Handle regular CSS selectors
                    elements = await self.page.locator(selector).all()
                    print(f"Found: {len(elements)} elements")
                    
                    # Get sample content from first few
                    for i in range(min(3, len(elements))):
                        try:
                            text = await elements[i].text_content()
                            if text and len(text.strip()) > 10:
                                print(f"  Sample {i+1}: {text.strip()[:100]}")
                        except:
                            print(f"  Sample {i+1}: <error getting text>")
                            
            except Exception as e:
                print(f"{strategy_name} failed: {str(e)[:100]}")

    # Enhanced diagnostic that combines everything
    async def comprehensive_diagnosis(self):
        """Run all diagnostic checks"""
        await self.detailed_post_inspection()
        await self.try_alternative_post_finding()
        
        # Final recommendation
        print(f"\n=== RECOMMENDATIONS ===")
        print("Based on the inspection above:")
        print("1. Check which selector actually found posts with content")
        print("2. Look at the HTML structure to understand the layout") 
        print("3. Try manual browser inspection (F12) to compare")
        print("4. Consider if Facebook has changed their layout recently")
 
    async def check_and_close_modal(self):
        """Check if a modal opened and try to close it"""
        try:
            # Common modal close button selectors
            close_selectors = [
                'div[aria-label="Close"]',
                'div[role="button"][aria-label="Close"]',
                'button[aria-label="Close"]',
                '[aria-label*="close" i]',
                'div[role="dialog"] div[role="button"]',
                'svg[aria-label="Close"]',
                # Facebook-specific close buttons
                'div[data-visualcompletion="ignore-dynamic"]:has-text("×")',
                'div[role="button"]:has-text("×")'
            ]
            
            for selector in close_selectors:
                try:
                    close_button = self.page.locator(selector).first
                    # Short timeout to check if modal is present
                    if await close_button.is_visible(timeout=1000):
                        await close_button.click(timeout=2000)
                        await asyncio.sleep(1)
                        print(f"    Found and closed modal using: {selector}")
                        return True
                except Exception:
                    continue
            
            # Alternative: Press Escape key to close modals
            try:
                await self.page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                print(f"    Pressed Escape to close potential modal")
                return True  # Assume it worked
            except:
                pass
                
            return False
            
        except Exception as e:
            print(f"    Modal close error: {str(e)[:50]}")
            return False
 
    async def close_any_modals(self):
        """Close any open post modals or popups"""
        try:
            # Look for common close buttons with explicit timeout
            close_selectors = [
                'div[aria-label="Close"]',
                'div[role="button"][aria-label="Close"]',
                'div[role="button"]:has-text("X")',
                '[aria-label*="close" i]',
                'div[role="dialog"] div[role="button"]'
            ]
            
            for selector in close_selectors:
                try:
                    close_button = self.page.locator(selector).first
                    if await close_button.is_visible(timeout=1000):  # 1 second timeout
                        await close_button.click(timeout=2000)
                        print("   🔄 Closed modal/popup")
                        await asyncio.sleep(1)
                        return True
                except:
                    continue
                    
            # Alternative: Press Escape key
            await self.page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
            
        except:
            pass
        
        return False
    
    async def extract_post_data_improved_fixed(self, post_element, post_num):
        """Improved post data extraction with better error handling and timeouts"""
        post_data = {
            'post_number': post_num,
            'text': '',
            'author': '',
            'time': '',
            'post_id': f"post_{post_num}_{self.session_id}",
            'scraped_at': datetime.now().isoformat(),
            'images': [],
            'comments': [],  # Initialize as empty - will be populated by thread processing
            'image_count': 0,
            'comment_count': 0  # Will be updated by thread processing
        }
        
        try:
            # IMPROVED TEXT EXTRACTION with timeout handling
            try:
                post_text = await asyncio.wait_for(
                    self.extract_text_improved_fixed(post_element),
                    timeout=5.0  # 5 second timeout for text extraction
                )
                post_data['text'] = post_text
            except asyncio.TimeoutError:
                print(f"      Text extraction timed out")
            except Exception as e:
                print(f"      Text extraction error: {str(e)[:50]}")
            
            # IMPROVED AUTHOR EXTRACTION with timeout handling  
            try:
                author = await asyncio.wait_for(
                    self.extract_author_improved_fixed(post_element),
                    timeout=3.0  # 3 second timeout for author extraction
                )
                post_data['author'] = author
            except asyncio.TimeoutError:
                print(f"      Author extraction timed out")
            except Exception as e:
                print(f"      Author extraction error: {str(e)[:50]}")
            
            # IMPROVED TIME EXTRACTION with timeout handling
            try:
                time_str = await asyncio.wait_for(
                    self.extract_time_improved(post_element),
                    timeout=2.0  # 2 second timeout for time extraction
                )
                post_data['time'] = time_str
            except asyncio.TimeoutError:
                print(f"      Time extraction timed out")
            except Exception as e:
                print(f"      Time extraction error: {str(e)[:50]}")
            
            # Extract images safely with timeout
            try:
                images = await asyncio.wait_for(
                    self.extract_images_safe(post_element, f"post_{post_num}"),
                    timeout=3.0
                )
                post_data['images'] = images
                post_data['image_count'] = len(images)
                
                # Download images if enabled
                if self.download_images and images:
                    await self.download_images_for_post(images, f"post_{post_num}")
            except asyncio.TimeoutError:
                print(f"      Image extraction timed out")
            except Exception as e:
                print(f"      Image extraction error: {str(e)[:50]}")
            
            # REMOVED: Old comment extraction - comments now handled by thread processing
            # This prevents the duplicate comment format issue
            
            # Extract sale info if we have text
            if post_data['text']:
                post_data['sale_info'] = self.extract_collectible_info(post_data)
            else:
                post_data['sale_info'] = None  # Explicitly set to None instead of empty dict
                
        except Exception as e:
            print(f"      Major error in data extraction: {str(e)[:100]}")
        
        return post_data

    async def extract_text_improved_fixed(self, post_element):
        """Improved text extraction with better timeout handling"""
        text_parts = []
        
        # Strategy 1: Use JavaScript to get all text content safely
        try:
            all_text = await post_element.evaluate('''
                (element) => {
                    // Get all text content
                    const allText = element.textContent || '';
                    
                    // Split into lines and filter
                    const lines = allText.split('\\n').map(line => line.trim()).filter(line => line.length > 10);
                    
                    // Filter out UI elements
                    const filteredLines = lines.filter(line => {
                        const lower = line.toLowerCase();
                        return !lower.startsWith('like') && 
                            !lower.startsWith('comment') && 
                            !lower.startsWith('share') &&
                            !lower.startsWith('follow') &&
                            !lower.includes('see more') &&
                            !lower.includes('write a comment');
                    });
                    
                    // Return first 5 substantial lines
                    return filteredLines.slice(0, 5).join(' ');
                }
            ''', timeout=3000)
            
            if all_text and len(all_text.strip()) > 20:
                return all_text.strip()[:2000]
                
        except Exception as e:
            print(f"        JavaScript text extraction failed: {str(e)[:50]}")
        
        # Strategy 2: Fallback to CSS selectors with better timeout handling
        text_selectors = [
            'div[dir="auto"]',
            'span[dir="auto"]', 
            'div[data-ad-preview="message"]',
            'p'
        ]
        
        for selector in text_selectors:
            try:
                elements = await post_element.locator(selector).all()
                for elem in elements[:5]:  # Limit to 5 elements
                    try:
                        text = await elem.text_content(timeout=1000)  # Short timeout
                        if text and len(text.strip()) > 10:
                            # Basic filtering
                            if not any(skip in text.lower()[:20] for skip in [
                                'like', 'comment', 'share', 'write a'
                            ]):
                                text_parts.append(text.strip())
                                
                                # Stop if we have enough content
                                if len(' '.join(text_parts)) > 100:
                                    break
                    except Exception:
                        continue
                        
                # If we found text with this selector, we might have enough
                if text_parts and len(' '.join(text_parts)) > 50:
                    break
                    
            except Exception:
                continue
        
        # Join and clean up the text
        full_text = ' '.join(text_parts)
        full_text = re.sub(r'\s+', ' ', full_text)
        
        return full_text.strip()[:2000] if full_text else ""

    async def extract_author_improved_fixed(self, post_element):
        """Improved author extraction with better timeout handling"""
        
        # Strategy 1: Look for profile links with shorter timeout
        try:
            profile_links = await post_element.locator('a[href*="/profile/"], a[href*="/user/"]').all()
            for link in profile_links[:3]:
                try:
                    author_text = await link.text_content(timeout=1000)  # Reduced timeout
                    if author_text and len(author_text) < 50 and author_text.strip():
                        return author_text.strip()
                except Exception:
                    continue
        except Exception:
            pass
        
        # Strategy 2: Look for any strong/heading text with timeout handling
        try:
            # Use shorter timeout and handle exceptions properly
            headings = await post_element.locator('strong, h1, h2, h3, h4').all()
            for heading in headings[:3]:  # Only try first 3
                try:
                    text = await heading.text_content(timeout=1000)  # Reduced timeout
                    if text and 5 < len(text) < 50:
                        # Filter out obvious non-author text
                        if not any(skip in text.lower() for skip in [
                            'like', 'comment', 'share', 'see more', 'follow'
                        ]):
                            return text.strip()
                except Exception:
                    continue
        except Exception:
            pass
        
        # Strategy 3: JavaScript extraction as last resort
        try:
            author_result = await post_element.evaluate('''
                (element) => {
                    // Look for profile links first
                    const profileLinks = element.querySelectorAll('a[href*="/profile/"], a[href*="/user/"]');
                    for (let link of profileLinks) {
                        if (link.textContent && link.textContent.trim().length > 2 && link.textContent.trim().length < 50) {
                            return link.textContent.trim();
                        }
                    }
                    
                    // Look for strong elements
                    const strongElements = element.querySelectorAll('strong');
                    for (let strong of strongElements) {
                        const text = strong.textContent ? strong.textContent.trim() : '';
                        if (text.length > 2 && text.length < 50 && 
                            !text.toLowerCase().includes('like') &&
                            !text.toLowerCase().includes('comment')) {
                            return text;
                        }
                    }
                    
                    return '';
                }
            ''', timeout=3000)  # 3 second timeout for JavaScript
            
            if author_result and len(author_result.strip()) > 2:
                return author_result.strip()
                
        except Exception:
            pass
        
        return ""

    def is_valid_timestamp(self, text):
        """Check if text looks like a valid timestamp"""
        if not text or len(text) > 50:  # Too long to be a timestamp
            return False
        
        text_lower = text.lower().strip()
        
        # Exclude obvious non-timestamp patterns
        non_timestamp_patterns = [
            'contributor', 'follow', 'member', 'admin', 'moderator', 'author',
            'all-star', 'top', 'rising', 'group', 'expert'
        ]
        
        if any(pattern in text_lower for pattern in non_timestamp_patterns):
            return False
        
        # Valid timestamp patterns
        timestamp_patterns = [
            # Relative times
            r'\d+\s*(min|minute|minutes|m|h|hour|hours|d|day|days|w|week|weeks|y|year|years)\b',
            r'\d+[mhdwy]\b',  # 5m, 2h, 3d, 1w, 2y
            r'(yesterday|today|now)\b',
            r'\d+\s*(min|hour|day|week|month|year)s?\s*(ago)?\b',
            
            # Absolute times  
            r'\d{1,2}:\d{2}\s*(am|pm)?',  # 3:45 PM
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{1,2}',  # Aug 30
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # 8/30/2024
            
            # Facebook-style timestamps
            r'·.*\d+[mhdwy]',  # "· 5h"
            r'\d+[mhdwy]\s*·',  # "5h ·"
        ]
        
        import re
        return any(re.search(pattern, text_lower) for pattern in timestamp_patterns)

    async def extract_time_improved(self, post_element):
        """Fixed time extraction with better fallback handling"""
        
        # Strategy 1: Look for Facebook's specific timestamp patterns
        try:
            # Facebook often uses this pattern: "Author · 5h · Shared with..."
            text_content = await post_element.text_content(timeout=2000) or ""
            
            # Look for timestamp patterns in the full text
            import re
            timestamp_matches = re.findall(r'·\s*(\d+[mhdwy])\s*·', text_content)
            if timestamp_matches:
                return timestamp_matches[0]  # Return first match like "5h"
            
            # Alternative pattern: "5h ·" 
            timestamp_matches = re.findall(r'(\d+[mhdwy])\s*·', text_content)
            if timestamp_matches:
                return timestamp_matches[0]
                
        except Exception:
            pass
        
        # Strategy 2: Look for timestamp-specific elements
        timestamp_selectors = [
            'a[role="link"] span[title]',
            'abbr[title]', 
            'time[datetime]',
            '[data-testid*="timestamp"]',
        ]
        
        for selector in timestamp_selectors:
            try:
                elements = await post_element.locator(selector).all()
                for elem in elements:
                    try:
                        # Check title attribute first
                        title = await elem.get_attribute('title', timeout=500)
                        if title and self.is_valid_timestamp(title):
                            return title.strip()
                        
                        # Check text content
                        text = await elem.text_content(timeout=500)
                        if text and self.is_valid_timestamp(text):
                            return text.strip()
                            
                    except Exception:
                        continue
            except Exception:
                continue
        
        # Strategy 3: Look for time patterns in span/link elements
        try:
            time_elements = await post_element.locator('span, a').all()
            
            for elem in time_elements[:20]:  # Limit to first 20 to avoid timeouts
                try:
                    text = await elem.text_content(timeout=300)
                    if text and len(text) < 20 and self.is_valid_timestamp(text):
                        # Make sure this isn't in an author context
                        try:
                            parent_html = await elem.evaluate('el => el.parentElement ? el.parentElement.outerHTML : ""', timeout=300)
                            if any(author_indicator in parent_html.lower() for author_indicator in [
                                'contributor', 'follow', 'profile', 'user'
                            ]):
                                continue
                        except:
                            pass  # If we can't check parent, still return the timestamp
                        
                        return text.strip()
                        
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return ""

    async def extract_comments_improved(self, post_element):
        """Improved comment extraction"""
        comments = []
        
        try:
            # Look for comment sections with multiple strategies
            comment_selectors = [
                'div[role="article"] div[dir="auto"]',
                'ul[role="list"] div[dir="auto"]',
                'div[data-testid*="comment"] div[dir="auto"]',
                'div[aria-label*="comment" i] div[dir="auto"]'
            ]
            
            for selector in comment_selectors:
                try:
                    comment_elements = await post_element.locator(selector).all()
                    
                    for elem in comment_elements:
                        try:
                            text = await elem.text_content(timeout=2000)
                            
                            if text and len(text.strip()) > 10:
                                # Filter out post text and UI elements
                                if not any(skip in text.lower()[:30] for skip in [
                                    'like', 'reply', 'share', 'write a comment', 
                                    'react', 'view more', 'see more', 'show more'
                                ]):
                                    # Don't add duplicates
                                    text_clean = text.strip()[:500]
                                    if not any(text_clean[:50] in c.get('text', '')[:50] for c in comments):
                                        comments.append({
                                            'text': text_clean,
                                            'order': len(comments) + 1,
                                            'has_price': '$' in text or 'price' in text.lower(),
                                            'is_sold': 'sold' in text.lower() or 'pending' in text.lower()
                                        })
                                        
                                        if len(comments) >= 15:  # Max comments
                                            break
                        except:
                            continue
                            
                    # If we found comments, stop trying other selectors
                    if len(comments) > 3:
                        break
                        
                except:
                    continue
                    
        except Exception as e:
            print(f"        Comment extraction error: {str(e)[:50]}")
        
        return comments
    
    async def extract_images_safe(self, post_element, post_id):
        """Extract images without clicking"""
        images = []
        
        try:
            # Get image URLs with explicit timeout
            img_elements = await post_element.locator('img').all()
            
            for i, img in enumerate(img_elements[:15]):  # Increased limit
                try:
                    src = await img.get_attribute('src', timeout=2000)
                    
                    if src and ('scontent' in src or 'fbcdn' in src):
                        alt_text = await img.get_attribute('alt', timeout=1000) or ""
                        
                        images.append({
                            'image_id': f"{post_id}_img_{i+1}",
                            'url': src,
                            'alt_text': alt_text,
                            'position': i + 1
                        })
                except:
                    continue
                    
        except Exception as e:
            print(f"        Image extraction error: {str(e)[:50]}")
        
        return images
    
    async def download_images_for_post(self, images, post_id):
        """Download images for a specific post"""
        if not images:
            return
        
        try:
            import aiohttp
            import aiofiles
            
            post_folder = self.output_dir / "images" / post_id
            post_folder.mkdir(exist_ok=True)
            
            async with aiohttp.ClientSession() as session:
                for img in images:
                    try:
                        url = img['url']
                        filename = post_folder / f"{img['image_id']}.jpg"
                        
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                async with aiofiles.open(filename, 'wb') as f:
                                    await f.write(await response.read())
                                img['local_path'] = str(filename)
                                print(f"      📥 Downloaded image {img['position']}")
                    except Exception as e:
                        print(f"      ⚠️ Failed to download image {img['position']}: {str(e)[:50]}")
        except ImportError:
            print("      ⚠️ aiohttp/aiofiles not available for image downloads")
    
    def extract_collectible_info(self, post_data):
        """Extract collectible/action figure specific information"""
        sale_info = {}
        
        # Combine post text and comments
        full_text = post_data.get('text', '').lower()
        for comment in post_data.get('comments', []):
            full_text += ' ' + comment.get('text', '').lower()
        
        if not full_text.strip():
            return None
        
        # Price extraction - multiple patterns for collectibles
        price_patterns = [
            r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:each|obo|firm|shipped|plus\s*shipping))?',
            r'[\d,]+\s*(?:dollars?|usd|bucks)',
            r'asking\s*:?\s*\$?[\d,]+',
            r'price\s*:?\s*\$?[\d,]+',
            r'(?:ppd|ppu)\s*\$?[\d,]+',  # Post Paid / Pick Up Pending
        ]
        
        prices_found = []
        for pattern in price_patterns:
            matches = re.findall(pattern, full_text)
            prices_found.extend(matches)
        
        if prices_found:
            sale_info['price'] = prices_found[0]
            sale_info['all_prices'] = list(set(prices_found))
        
        # GI Joe specific item detection
        gi_joe_patterns = {
            'figures': [
                r'(?:snake eyes|storm shadow|duke|cobra commander|destro|scarlett|roadblock|baroness)',
                r'(?:\d{4}\s*)?(?:moc|mip|loose|complete)',  # MOC/MIP = Mint on Card/In Package
                r'(?:v\d+|version\s*\d+)',  # Version numbers
                r'(?:hasbro|takara|funskool)',  # Manufacturer
            ],
            'vehicles': [
                r'(?:hiss tank|skystriker|whale|rattler|moray|mobat|flagg)',
                r'(?:complete|incomplete|parts)',
            ],
            'accessories': [
                r'(?:accessories|weapons|file cards?|stands?|gear)',
                r'(?:original|repro|reproduction|custom)',
            ],
            'years': [
                r'(?:19)?8[2-9]',  # 1982-1989
                r'(?:19)?9[0-4]',  # 1990-1994
                r'arah',  # A Real American Hero line
            ]
        }
        
        # Find mentioned items
        items_found = []
        for category, patterns in gi_joe_patterns.items():
            for pattern in patterns:
                if re.search(pattern, full_text):
                    matches = re.findall(pattern, full_text)
                    items_found.extend(matches[:3])  # Limit to avoid duplicates
        
        if items_found:
            sale_info['items'] = list(set(items_found))[:10]  # Unique items, max 10
        
        # Condition detection for collectibles
        condition_patterns = {
            'mint': ['moc', 'mip', 'mib', 'mint', 'sealed', 'unopened', 'new in box'],
            'complete': ['complete', '100%', 'c-10', 'c-9'],
            'good': ['good condition', 'displayed', 'adult owned', 'smoke free'],
            'incomplete': ['incomplete', 'missing', 'parts', 'for parts', 'broken']
        }
        
        for condition, keywords in condition_patterns.items():
            if any(keyword in full_text for keyword in keywords):
                sale_info['condition'] = condition
                break
        
        # Sale status
        if any(word in full_text for word in ['sold', 'pending', 'ppu', 'spo']):
            sale_info['status'] = 'SOLD/PENDING'
        elif any(word in full_text for word in ['available', 'for sale', 'fs', 'selling']):
            sale_info['status'] = 'AVAILABLE'
        
        # Lot detection (multiple items)
        if any(word in full_text for word in ['lot', 'bundle', 'collection', 'multiple']):
            sale_info['is_lot'] = True
        
        # Shipping info
        if 'shipped' in full_text or 'shipping' in full_text:
            sale_info['shipping_included'] = 'shipped' in full_text or 'free ship' in full_text
        
        return sale_info if sale_info else None
    
    

    ###^ 5- CLEANUP AND SAVE FUNCTIONS
    
    async def auto_save(self, posts_data=None):
        """Auto-save progress to prevent data loss"""
        try:
            data_to_save = posts_data or self.posts_data
            if not data_to_save:
                return
                
            # Save JSON checkpoint
            checkpoint_file = self.output_dir / f"checkpoint_{self.session_id}.json"
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            print(f"   💾 Auto-saved {len(data_to_save)} posts to checkpoint")
            
        except Exception as e:
            print(f"   ⚠️ Auto-save failed: {str(e)[:50]}")
    
    async def save_results_fixed(self):
        """Save scraped data with safe None handling"""
        if not self.posts_data:
            print("\nNo posts to save")
            return
        
        try:
            # Create the output directory if it doesn't exist
            self.output_dir.mkdir(exist_ok=True)
            
            # Save full JSON with error handling
            json_file = self.output_dir / f"group_posts_{self.session_id}.json"
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(self.posts_data, f, indent=2, ensure_ascii=False)
                print(f"\nFull data saved to: {json_file}")
                print(f"   Saved {len(self.posts_data)} posts to JSON")
            except Exception as e:
                print(f"   Failed to save JSON: {str(e)}")
            
            # Create sales summary CSV with safe None handling
            try:
                sales_csv = self.output_dir / f"sales_summary_{self.session_id}.csv"
                sales_data = []
                
                for post in self.posts_data:
                    # Safe handling of potentially None sale_info
                    sale_info = post.get('sale_info')
                    if sale_info and isinstance(sale_info, dict):
                        price = sale_info.get('price', '')
                        items = ', '.join(sale_info.get('items', [])[:5])
                        condition = sale_info.get('condition', '')
                        status = sale_info.get('status', '')
                        is_lot = sale_info.get('is_lot', False)
                    else:
                        price = ''
                        items = ''
                        condition = ''
                        status = ''
                        is_lot = False
                    
                    sales_data.append({
                        'post_number': post.get('post_number', ''),
                        'author': post.get('author', '')[:50],  # Truncate long names
                        'time': post.get('time', ''),
                        'preview': post.get('text', '')[:150],
                        'price': price,
                        'items': items,
                        'condition': condition,
                        'status': status,
                        'is_lot': is_lot,
                        'images': post.get('image_count', 0),
                        'comments': post.get('comment_count', 0),
                        'has_sold_comment': any(c.get('is_sold') for c in post.get('comments', []))
                    })
                
                # Write CSV with proper error handling
                with open(sales_csv, 'w', newline='', encoding='utf-8') as f:
                    if sales_data:  # Make sure we have data
                        writer = csv.DictWriter(f, fieldnames=sales_data[0].keys())
                        writer.writeheader()
                        writer.writerows(sales_data)
                        
                print(f"Sales summary saved to: {sales_csv}")
                print(f"   Saved {len(sales_data)} rows to CSV")
                
            except Exception as e:
                print(f"   Failed to save CSV: {str(e)}")
                # Try to save a simple text backup
                try:
                    backup_file = self.output_dir / f"backup_{self.session_id}.txt"
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        for i, post in enumerate(self.posts_data):
                            f.write(f"POST {i+1}:\n")
                            f.write(f"Author: {post.get('author', '')}\n")
                            f.write(f"Text: {post.get('text', '')[:200]}\n")
                            f.write(f"Images: {post.get('image_count', 0)}\n")
                            f.write("-" * 50 + "\n")
                    print(f"Created text backup: {backup_file}")
                except:
                    print("   Even backup save failed")
            
            # Print summary with safe handling
            self.print_summary_fixed()
            
        except Exception as e:
            print(f"\nSave error: {str(e)}")
            print("Attempting emergency save...")
            
            # Emergency save as plain text
            try:
                emergency_file = self.output_dir / f"emergency_save_{self.session_id}.txt"
                with open(emergency_file, 'w', encoding='utf-8') as f:
                    f.write(f"Emergency save at {datetime.now()}\n")
                    f.write(f"Posts scraped: {len(self.posts_data)}\n\n")
                    for i, post in enumerate(self.posts_data):
                        f.write(f"Post {i+1}: {str(post)}\n\n")
                print(f"Emergency save completed: {emergency_file}")
            except:
                print("Emergency save also failed")
    
    def print_summary_fixed(self):
        """Print scraping summary with safe None handling"""
        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)
        
        total_posts = len(self.posts_data)
        posts_with_text = sum(1 for p in self.posts_data if p.get('text', '').strip())
        posts_with_authors = sum(1 for p in self.posts_data if p.get('author', '').strip())
        
        # Safe handling of sale_info that might be None
        posts_with_prices = 0
        posts_with_items = 0
        for post in self.posts_data:
            sale_info = post.get('sale_info')
            if sale_info and isinstance(sale_info, dict):  # Check it's not None and is a dict
                if sale_info.get('price'):
                    posts_with_prices += 1
                if sale_info.get('items'):
                    posts_with_items += 1
        
        total_images = sum(p.get('image_count', 0) for p in self.posts_data)
        total_comments = sum(p.get('comment_count', 0) for p in self.posts_data)
        
        print(f"Total posts scraped: {total_posts}")
        print(f"Posts with text: {posts_with_text}")
        print(f"Posts with authors: {posts_with_authors}")
        print(f"Posts with prices: {posts_with_prices}")
        print(f"Posts with identified items: {posts_with_items}")
        print(f"Total images found: {total_images}")
        print(f"Total comments: {total_comments}")
        
        # Show sample items found - with safe None handling
        print(f"\nSample Items Found:")
        sample_count = 0
        for post in self.posts_data:
            sale_info = post.get('sale_info')
            if sale_info and isinstance(sale_info, dict) and sale_info.get('items') and sample_count < 5:
                items = sale_info['items']
                price = sale_info.get('price', 'No price')
                print(f"  • {', '.join(items[:3])} - {price}")
                sample_count += 1
        
        if sample_count == 0:
            print("  (No specific items identified)")
        
    async def close(self):
        """Close connections with safer cleanup to avoid recursion"""
        print(f"\nScraping complete - cleaning up...")
        
        try:
            # Don't try to cancel all tasks - just close playwright cleanly
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
                print(f"Playwright closed successfully")
        except Exception as e:
            print(f"Error closing playwright: {str(e)}")
        
        print(f"Cleanup complete - browser left open for your use")



def start_browser_with_debugging():
    """Helper to start browser with remote debugging"""
    print("\n🚀 Starting Browser with Remote Debugging...")
    print("-" * 60)
    
    # Check for Chrome and Edge paths
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    
    browser_path = None
    browser_name = None
    
    # Check which browser is available
    for path in chrome_paths:
        if os.path.exists(path):
            browser_path = path
            browser_name = "Chrome"
            break
    
    if not browser_path:
        for path in edge_paths:
            if os.path.exists(path):
                browser_path = path
                browser_name = "Edge"
                break
    
    if browser_path:
        print(f"✅ Found {browser_name} at: {browser_path}")
        print(f"\n🔌 Starting {browser_name} with remote debugging...")
        
        # Start browser with debugging
        subprocess.Popen([
            browser_path,
            "--remote-debugging-port=9222",
            "--user-data-dir=C:\\temp\\chrome_debug"  # Temporary profile
        ])
        
        print(f"\n✅ {browser_name} started!")
        print("\n📋 Next steps:")
        print("1. Log into Facebook in the browser that just opened")
        print("2. Navigate to your GI Joe group")
        print("3. Come back here and press Enter to start scraping")
        
        input("\nPress Enter when ready...")
        return True
    else:
        print("❌ Could not find Chrome or Edge")
        return False

async def main():
    """Main function with autonomous operation support"""
    print("\n" + "=" * 60)
    print("🎯 FACEBOOK GROUP SCRAPER - GI JOE & COLLECTIBLES")
    print("🔌 Uses existing browser session - no login required!")
    print("=" * 60)
    
    # Default GI Joe group
    DEFAULT_GROUP = "132930063463148"
    
    print("\nOptions:")
    print("1. 🔗 Use existing browser (you're already logged in)")
    print("2. 🚀 Start new browser with debugging (I'll help you set it up)")
    
    choice = input("\nChoice (1-2): ").strip()
    
    if choice == '2':
        # Help start browser
        if not start_browser_with_debugging():
            return
    else:
        print("\n📋 Make sure you have a browser open with remote debugging:")
        print('Chrome: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
        print('Edge: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222')
        print("\nAnd that you're logged into Facebook")
        input("\nPress Enter to continue...")
    
    # Ask about downloading images
    download = input("\n📷 Download images? (y/n, default=n): ").strip().lower()
    download_images = download == 'y'
    
    if download_images:
        print("✅ Will download images to local folder")
        # Check for required libraries
        try:
            import aiohttp
            import aiofiles
        except ImportError:
            print("📦 Installing required packages for image downloads...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "aiofiles"])
            print("✅ Packages installed")
    else:
        print("ℹ️ Will only save image URLs (not downloading)")
    
    # Ask about autonomous operation
    autonomous = input("\n🤖 Run autonomously without user prompts? (y/n, default=n): ").strip().lower()
    autonomous_mode = autonomous == 'y'
    
    if autonomous_mode:
        print("✅ Autonomous mode enabled - will run without user interaction")
    else:
        print("ℹ️ Interactive mode - will ask for confirmation if needed")
    
    # Create scraper
    scraper = FacebookGroupScraper(download_images=download_images)
    
    try:
        # Connect to browser
        if await scraper.connect_to_existing_browser():
            
            # Ask which group to scrape
            print(f"\n🌐 Default group: {DEFAULT_GROUP} (GI Joe ARAH)")
            use_default = input("Use default group? (y/n): ").strip().lower()
            
            if use_default == 'y':
                group_id = DEFAULT_GROUP
            else:
                group_id = input("Enter group ID: ").strip() or DEFAULT_GROUP
            
            # Navigate to group
            await scraper.navigate_to_group(group_id)
            
            await scraper.comprehensive_diagnosis()
            
            # How many posts?
            num = input("\nNumber of posts to scrape (default 10): ").strip()
            num_posts = int(num) if num else 10
            
            print("\n⚠️ IMPORTANT: Don't click anything in the browser while scraping!")
            print("The script will handle everything automatically.")
            if autonomous_mode:
                print("🤖 Running in autonomous mode - no user interaction required.")
            print("Improved version with better timeouts and error handling.\n")
            
            # Calculate timeout based on autonomous mode
            if autonomous_mode:
                # Much longer timeout for autonomous operation
                base_timeout = max(300, num_posts * 25)  # 5 minutes minimum, or 25 seconds per post
                max_retries = 3  # Allow multiple attempts
            else:
                # Standard timeout for interactive mode  
                base_timeout = max(120, num_posts * 15)  # 2 minutes minimum, or 15 seconds per post
                max_retries = 2
            
            # Scrape posts with enhanced autonomous handling
            all_posts = []
            attempt = 1
            remaining_posts = num_posts
            
            while len(all_posts) < num_posts and attempt <= max_retries:
                try:
                    print(f"📡 Attempt {attempt}/{max_retries}: Scraping {remaining_posts} posts (timeout: {base_timeout}s)")
                    
                    posts = await asyncio.wait_for(
                        scraper.scrape_with_thread_boundary_detection(remaining_posts),
                        timeout=base_timeout
                    )
                    
                    if posts:
                        all_posts.extend(posts)
                        print(f"✅ Got {len(posts)} posts in attempt {attempt}")
                        break  # Success, exit retry loop
                    
                except asyncio.TimeoutError:
                    print(f"\n⏱️ Timeout on attempt {attempt}, retrieving partial results...")
                    # Get whatever was scraped from scraper.posts_data
                    partial_posts = scraper.posts_data or []
                    if partial_posts:
                        all_posts.extend(partial_posts)
                        print(f"📦 Retrieved {len(partial_posts)} posts from attempt {attempt}")
                    
                    if autonomous_mode and len(all_posts) < num_posts and attempt < max_retries:
                        remaining_posts = num_posts - len(all_posts)
                        print(f"🤖 Autonomous retry: Attempting {remaining_posts} more posts...")
                        attempt += 1
                        # Reduce timeout for subsequent attempts (they should be faster)
                        base_timeout = max(180, remaining_posts * 20)
                        continue
                    else:
                        break  # Exit retry loop
                
                except Exception as e:
                    print(f"❌ Error on attempt {attempt}: {str(e)[:100]}")
                    # Try to get partial results
                    if hasattr(scraper, 'posts_data') and scraper.posts_data:
                        partial_posts = scraper.posts_data or []
                        all_posts.extend(partial_posts)
                        print(f"📦 Retrieved {len(partial_posts)} posts before error")
                    
                    if autonomous_mode and attempt < max_retries:
                        print(f"🤖 Autonomous retry after error...")
                        attempt += 1
                        continue
                    else:
                        break
            
            # Final result handling
            posts = all_posts
            
            # Always try to save results if we have ANY posts
            if posts and len(posts) > 0:
                # Ensure scraper.posts_data is set for save_results_fixed()
                scraper.posts_data = posts
                
                try:
                    await scraper.save_results_fixed()
                    print(f"\n✅ Successfully scraped {len(posts)} posts!")
                    print(f"📁 Data saved in folder: {scraper.output_dir}/")
                    
                    if download_images:
                        total_images = sum(p.get('image_count', 0) for p in posts)
                        total_comment_images = sum(
                            sum(c.get('image_count', 0) for c in p.get('comments', []))
                            for p in posts
                        )
                        print(f"📷 Downloaded {total_images} main images + {total_comment_images} comment images")
                        print(f"   to: {scraper.output_dir}/images/")
                    
                    # Handle incomplete results
                    if len(posts) < num_posts:
                        if autonomous_mode:
                            print(f"🤖 Autonomous mode: Completed with {len(posts)}/{num_posts} posts")
                        else:
                            continue_scraping = input(f"\nOnly got {len(posts)}/{num_posts} posts. Try to get more? (y/n): ").strip().lower()
                            if continue_scraping == 'y':
                                remaining = num_posts - len(posts)
                                print(f"\nAttempting to scrape {remaining} more posts...")
                                
                                try:
                                    more_posts = await asyncio.wait_for(
                                        scraper.scrape_with_thread_boundary_detection(remaining),
                                        timeout=max(120, remaining * 15)
                                    )
                                    
                                    if more_posts:
                                        # Combine with existing posts
                                        all_posts = posts + more_posts
                                        scraper.posts_data = all_posts
                                        await scraper.save_results_fixed()
                                        print(f"✅ Total: {len(all_posts)} posts!")
                                except Exception as e:
                                    print(f"⚠️ Error getting more posts: {str(e)[:100]}")
                    else:
                        print(f"🎯 Target achieved: {len(posts)}/{num_posts} posts!")
                        
                except Exception as e:
                    print(f"⚠️ Error during save: {str(e)[:100]}")
                    # Try emergency save
                    try:
                        emergency_file = scraper.output_dir / f"emergency_save_{scraper.session_id}.json"
                        with open(emergency_file, 'w', encoding='utf-8') as f:
                            json.dump(posts, f, indent=2, ensure_ascii=False)
                        print(f"💾 Emergency save completed: {emergency_file}")
                    except:
                        print("❌ Even emergency save failed")
            else:
                print(f"\n⚠️ No posts found after {attempt-1} attempts")
                print("Debugging info:")
                print(f"  - scraper.posts_data: {len(scraper.posts_data) if hasattr(scraper, 'posts_data') and scraper.posts_data else 'None'}")
                print("Possible issues:")
                print("1. The group might be private and you're not a member")
                print("2. Facebook might have changed their layout")
                print("3. Try refreshing the page and running again")
                print("4. Check that you're actually on a Facebook group page")
        else:
            print("\n❌ Could not connect to browser")
            print("Make sure you started Chrome/Edge with --remote-debugging-port=9222")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user")
        if hasattr(scraper, 'posts_data') and scraper.posts_data:
            try:
                await scraper.save_results_fixed()
                print(f"💾 Saved {len(scraper.posts_data)} posts that were scraped")
            except Exception as e:
                print(f"⚠️ Error saving interrupted data: {str(e)[:100]}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if hasattr(scraper, 'posts_data') and scraper.posts_data:
            print(f"\n💾 Saving {len(scraper.posts_data)} posts that were scraped before error...")
            try:
                await scraper.save_results_fixed()
            except Exception as save_error:
                print(f"⚠️ Error saving data: {str(save_error)[:100]}")
                # Final emergency save attempt
                try:
                    emergency_file = scraper.output_dir / f"emergency_save_{scraper.session_id}.json"
                    with open(emergency_file, 'w', encoding='utf-8') as f:
                        json.dump(scraper.posts_data, f, indent=2, ensure_ascii=False)
                    print(f"💾 Emergency save completed: {emergency_file}")
                except:
                    print("❌ Emergency save also failed")
        
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())