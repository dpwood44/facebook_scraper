"""
Facebook Groups Scraper for Collectible Sales (GI Joe, etc.)
Improved version with better data extraction and save reliability
"""

import asyncio
import json
import csv
import re
import os
import subprocess
import sys
import time

from datetime import datetime
from loguru import logger
from pathlib import Path

from playwright.async_api import async_playwright
from src.resources.fb_groups import fb_groups
from sold_item_detector import SoldItemDetector
from src.utils import setup_logging

class FacebookGroupScraper:
    def __init__(self, download_images=False, sale_posts_only=False, 
                 include_sold=True, sold_items_only=False, 
                 use_deep_sold_detection=False, visual_highlight=False):
        self.browser = None
        self.context = None
        self.page = None
        self.posts_data = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Post filtering options
        self.sale_posts_only = sale_posts_only
        self.include_sold = include_sold
        self.sold_items_only = sold_items_only  # Option 4: Facebook search
        self.use_deep_sold_detection = use_deep_sold_detection  # Option 5: Deep detection
        self.download_images = download_images
        
        # Create scrapes directory in project root
        scrapes_dir = Path("scrapes")
        scrapes_dir.mkdir(exist_ok=True)
        
        # Put the session folder inside scrapes directory
        self.output_dir = scrapes_dir / f"fb_group_scrape_{self.session_id}"
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # SET UP LOGGING
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"scraper_{self.session_id}.log"
        
        # Initialize logging with both console and file output
        setup_logging(
            log_level="INFO",  # Change to "DEBUG" for more verbose logging
            log_file=str(log_file)
        )
        
        # Initialize sale patterns if any filtering is enabled
        if sale_posts_only or sold_items_only or use_deep_sold_detection:
            self._init_sale_patterns()
        
        # Initialize sold detection for either option 4 or 5
        if sold_items_only or use_deep_sold_detection:
            self.sold_detector = SoldItemDetector()
            if use_deep_sold_detection:
                logger.info("Deep sold detection enabled (posts + comments)")
            else:
                logger.info("Facebook search sold items mode enabled")
        
        # Visual highlighting option
        self.visual_highlight = visual_highlight
        if visual_highlight:
            logger.info("Visual highlighting enabled - containers will be highlighted in browser")
        
        # Track absolute post number across all processing
        self.absolute_post_counter = 0
        
        logger.info(f"FacebookGroupScraper initialized")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Image downloads: {'enabled' if download_images else 'disabled'}")
        logger.info(f"Sale posts only: {sale_posts_only}")
        logger.info(f"Include sold items: {include_sold}")
        logger.info(f"Sold items only: {sold_items_only}")
        
        if download_images:
            (self.output_dir / "images").mkdir(exist_ok=True)
            logger.info(f"Created folder for images: {self.output_dir}/images/")
    
    async def connect_to_existing_browser(self):
        """Connect to an existing browser session - with logging"""
        logger.info("Attempting to connect to existing browser...")
        
        try:
            self.playwright = await async_playwright().start()
            
            try:
                # Connect to Chrome DevTools on port 9222
                self.browser = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
                logger.info("Successfully connected to browser via CDP")
                
                # Get existing contexts
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]
                    pages = self.context.pages
                    logger.info(f"Found {len(pages)} open pages")
                    
                    if pages:
                        # Find Facebook tab or use current tab
                        for page in pages:
                            if 'facebook.com' in page.url:
                                self.page = page
                                logger.success(f"Connected to existing Facebook tab: {page.url[:100]}")
                                return True
                        
                        # If no Facebook tab, use first tab
                        self.page = pages[0]
                        logger.info(f"No Facebook tab found, using current tab: {self.page.url[:100]}")
                        return True
                else:
                    logger.error("No contexts found in browser")
                    
            except Exception as e:
                logger.error(f"Could not connect to existing browser: {e}")
                logger.info("To use an existing browser session:")
                logger.info("1. Close all Chrome/Edge windows")
                logger.info("2. Start Chrome/Edge with remote debugging")
                logger.info("3. Log into Facebook manually")
                logger.info("4. Navigate to your group")
                logger.info("5. Run this script again")
                return False
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    ###^ 1- URL NAVIGATION & TRIGGER POSTS
    
    async def navigate_to_group(self, group_id):
        """Navigate to a specific group with improved timeout handling"""
        try:
            current_url = self.page.url
            
            if self.sold_items_only:
                # Option 4: Use Facebook's search
                target_url = f"https://www.facebook.com/groups/{group_id}/search/?q=sold"
                logger.info(f"Navigating to group {group_id} with 'sold' search")
            elif self.use_deep_sold_detection:
                # Option 5: Stay on regular group page for deep detection
                target_url = f"https://www.facebook.com/groups/{group_id}"
                logger.info(f"Navigating to group {group_id} for deep sold detection")
            elif self.sale_posts_only:
                target_url = f"https://www.facebook.com/groups/{group_id}?filter=sell"
                logger.info(f"Navigating to group {group_id} with sale filter")
            else:
                target_url = f"https://www.facebook.com/groups/{group_id}"
                logger.info(f"Navigating to group {group_id}")
            
            # Only navigate if not already there
            if group_id not in current_url or ('sold' not in current_url and self.sold_items_only):
                try:
                    # Try with networkidle first (with shorter timeout)
                    await self.page.goto(target_url, wait_until='networkidle', timeout=15000)
                    logger.success("Navigation completed with networkidle")
                except Exception as e:
                    logger.warning(f"Networkidle timeout, trying domcontentloaded: {str(e)[:50]}")
                    # Fallback to domcontentloaded
                    await self.page.goto(target_url, wait_until='domcontentloaded', timeout=10000)
                    await asyncio.sleep(5)  # Manual wait for content to load
                    logger.success("Navigation completed with domcontentloaded fallback")
                
                await asyncio.sleep(3)  # Extra wait for search results
                logger.success(f"Successfully navigated to group {group_id}")
            else:
                logger.info(f"Already on appropriate page for group {group_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False


    async def get_real_posts_only(self):
        """Get only real posts, filtering out virtualized placeholders - with logging"""
        logger.info("Finding real posts (filtering virtualized content)")
        
        # Get all potential post elements
        all_elements = await self.page.locator('[role="article"]').all()
        logger.debug(f"Total elements found: {len(all_elements)}")
        
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
                
                logger.debug(f"Element {i+1}: virtualized={is_virtualized}, hidden={is_hidden}, html={html_size}, text={text_length}")
                
                # Skip if virtualized, hidden, or too small
                if (is_virtualized == "true" or 
                    is_hidden or 
                    html_size < 5000 or  # Real posts have substantial HTML
                    text_length < 20):   # Real posts have substantial text
                    
                    if is_virtualized == "true" or is_hidden:
                        virtualized_count += 1
                    else:
                        empty_count += 1
                        
                    logger.debug(f"Skipping element {i+1}: {'virtualized' if is_virtualized == 'true' or is_hidden else 'too small'}")
                    continue
                
                # This appears to be a real post
                real_posts.append(element)
                logger.debug(f"Real post found: element {i+1}")
                
            except Exception as e:
                logger.warning(f"Error checking element {i+1}: {str(e)[:50]}")
                continue
        
        logger.info(f"Results: {len(real_posts)} real posts, {virtualized_count} virtualized, {empty_count} empty")
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
        """Process a main post and ALL its comments - with enhanced logging"""
        
        # Increment absolute counter
        self.absolute_post_counter += 1
        absolute_num = self.absolute_post_counter
        
        # Get preview of post text first
        try:
            main_container = containers[main_post_index]
            preview_text = await main_container.text_content(timeout=2000) or ""
            preview_text = ' '.join(preview_text.split()[:20])  # First 20 words
            if len(preview_text) > 100:
                preview_text = preview_text[:100] + "..."
        except:
            preview_text = "[Could not get preview]"
        
        # Enhanced logging with post number and preview
        logger.info(f"")  # Blank line for clarity
        logger.info(f"{'='*60}")
        logger.info(f"📍 POST #{absolute_num} (container {main_post_index + 1})")
        logger.info(f"📝 Preview: {preview_text}")
        logger.info(f"{'='*60}")
        
        # Visual highlight if enabled
        if self.visual_highlight:
            await self.highlight_element(main_container)
        
        try:
            # Find where this post's comments end
            boundary_index = await self.find_post_boundary(containers, main_post_index)
            
            # Extract the complete thread
            thread_containers = containers[main_post_index:boundary_index]
            thread_size = len(thread_containers)
            
            logger.debug(f"Thread size: {thread_size} containers (post + {thread_size-1} comment containers)")
            
            # The first container is the main post
            main_container = thread_containers[0]
            comment_containers = thread_containers[1:]
            
            # Adjust processing strategy based on thread size
            if thread_size > 15:
                logger.info(f"Large thread detected ({thread_size} containers) - using enhanced processing")
            
            # Force load main post if needed
            try:
                html_size = len(await main_container.inner_html(timeout=3000))
                if html_size < 35000:
                    logger.debug("Force loading main post...")
                    await self.force_load_post_content(main_container)
            except Exception as e:
                logger.warning(f"Could not check/load main post size: {str(e)[:50]}")
            
            # Extract main post data with appropriate timeout
            main_post_timeout = 20.0 if thread_size > 15 else 15.0
            post_data = await asyncio.wait_for(
                self.extract_post_data_improved_fixed(main_container, post_number),
                timeout=main_post_timeout
            )
            
            logger.success(f"Extracted main post data for post {post_number}")
            
            # Process comments if present
            if comment_containers:
                logger.debug(f"Processing {len(comment_containers)} comment containers")
                comment_container_info_list = []
                for container in comment_containers:
                    comment_container_info_list.append({'container': container})
                
                # Dynamic comment limit based on thread size
                if thread_size > 25:
                    max_comments = min(50, thread_size)
                elif thread_size > 15:
                    max_comments = 75
                else:
                    max_comments = 100
                
                logger.debug(f"Max comments for this thread: {max_comments}")
                
                await self.process_complete_comment_thread(
                    post_data, 
                    comment_container_info_list,
                    max_comments=max_comments
                )
            
            return post_data, boundary_index
            
        except asyncio.TimeoutError:
            logger.error(f"Thread processing timed out for {thread_size} containers")
            if 'post_data' in locals():
                return post_data, boundary_index
            return None, boundary_index
            
        except Exception as e:
            logger.error(f"Error processing thread: {str(e)[:100]}")
            return None, boundary_index
        
    async def scrape_with_thread_boundary_detection(self, num_posts=10):
        """Main scraping function - with comprehensive logging"""
        logger.info(f"Starting scraping of {num_posts} posts with thread boundary detection")
        
        # Reset counter for new scraping session
        self.absolute_post_counter = 0
        
        posts = []
        scroll_attempts = 0
        max_scrolls = 15
        container_position = 0
        
        await self.close_any_modals()
        
        while len(posts) < num_posts and scroll_attempts < max_scrolls:
            try:
                all_containers = await self.page.locator('[role="article"]').all()
                remaining_containers = all_containers[container_position:]
                
                if not remaining_containers:
                    logger.debug("No new containers, scrolling for more...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    continue
                
                # Find next main post
                next_main_post_index = None
                for i, container in enumerate(remaining_containers[:15]):
                    try:
                        html_content = await container.inner_html(timeout=1500)
                        text_content = await container.text_content(timeout=1200) or ""
                        
                        if self.is_main_post_container(text_content, len(html_content)):
                            next_main_post_index = container_position + i
                            
                            # Quick preview for debugging
                            preview = ' '.join(text_content.split()[:10])
                            logger.debug(f"Found main post at container {next_main_post_index + 1}: {preview[:50]}...")
                            break
                            
                    except Exception:
                        continue
                
                if next_main_post_index is None:
                    logger.debug("No main post found, scrolling...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    container_position += 5
                    continue
                
                # Process the post
                post_data, boundary_index = await self.process_post_with_complete_thread(
                    all_containers, 
                    next_main_post_index,
                    len(posts) + 1
                )
                
                if post_data and self.validate_main_post_data(post_data):
                    posts.append(post_data)
                    logger.success(f"✅ Successfully scraped post #{self.absolute_post_counter} -> Saved as post {len(posts)}/{num_posts}")
                    
                    # Show key details
                    self.print_enhanced_post_summary(post_data, self.absolute_post_counter)
                    
                    self.posts_data = posts.copy()
                    
                    if len(posts) % 3 == 0:
                        logger.info(f"Auto-saving progress at {len(posts)} posts")
                        await self.auto_save(posts)
                else:
                    logger.warning(f"❌ Post #{self.absolute_post_counter} failed validation, skipping")
                
                # Move to next
                container_position = boundary_index
                scroll_attempts = 0
                
            except Exception as e:
                logger.error(f"Error in scraping: {str(e)[:100]}")
                scroll_attempts += 1
                container_position += 3
                continue
        
        self.posts_data = posts
        logger.info(f"Completed scraping: {len(posts)} valid posts from {self.absolute_post_counter} total processed")
        return posts


    async def scrape_with_sold_detection(self, num_posts=10):
        """Simplified sequential processing - just go through posts 1, 2, 3, 4..."""
        logger.info(f"Starting sequential sold items detection for {num_posts} posts")
        
        posts = []
        current_container = 0
        posts_processed = 0
        scroll_attempts = 0
        max_scrolls = 10
        
        await self.close_any_modals()
        
        while len(posts) < num_posts and posts_processed < num_posts * 3:  # Safety limit
            try:
                # Get all containers
                all_containers = await self.page.locator('[role="article"]').all()
                
                # Check if we need more containers
                if current_container >= len(all_containers):
                    logger.info("Need more containers, scrolling...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    if scroll_attempts >= max_scrolls:
                        logger.warning("Reached max scroll attempts")
                        break
                    continue
                
                # Get the current container
                container = all_containers[current_container]
                posts_processed += 1
                
                try:
                    html_content = await container.inner_html(timeout=2000)
                    text_content = await container.text_content(timeout=1500) or ""
                    
                    # Simple filtering - only skip tiny UI elements
                    is_substantial = (
                        len(html_content) > 5000 and 
                        len(text_content.strip()) > 20 and
                        not text_content.endswith('LikeReply') and 
                        not text_content.endswith('Reply') and
                        not text_content.endswith('Like')
                    )
                    
                    if is_substantial:
                        post_number = posts_processed
                        logger.info(f"📍 Processing post #{post_number} at container {current_container + 1}")
                        
                        # Process this post
                        post_data, boundary_index = await self.process_post_with_sold_detection(
                            all_containers,
                            current_container,
                            post_number
                        )
                        
                        if post_data and self.validate_main_post_data(post_data):
                            sold_analysis = post_data.get('sold_analysis', {})
                            
                            if sold_analysis.get('is_sold', False):
                                posts.append(post_data)
                                confidence = sold_analysis.get('confidence', 0)
                                method = sold_analysis.get('sale_method', 'unknown')
                                
                                logger.success(f"✅ SOLD ITEM #{len(posts)} CONFIRMED: {confidence}% confidence via {method}")
                                self.print_sold_item_debug(post_data)
                                
                                self.posts_data = posts.copy()
                                
                                if len(posts) % 2 == 0:
                                    await self.auto_save(posts)
                            else:
                                confidence = sold_analysis.get('confidence', 0)
                                logger.info(f"Post #{post_number} not sold (confidence: {confidence}%) - continuing to next post")
                        
                        # CRITICAL: Always advance to next container after processing
                        current_container = max(boundary_index, current_container + 1)
                        scroll_attempts = 0  # Reset scroll attempts on successful processing
                    else:
                        logger.debug(f"Skipping container {current_container + 1}: not substantial")
                        current_container += 1
                        
                except Exception as e:
                    logger.warning(f"Error processing container {current_container + 1}: {str(e)[:50]}")
                    current_container += 1
                    continue
                    
            except Exception as e:
                logger.error(f"Major error in sequential processing: {str(e)[:100]}")
                current_container += 1
                continue
        
        self.posts_data = posts
        logger.success(f"🏁 Sequential processing complete: {len(posts)} sold items found from {posts_processed} posts processed")
        return posts


    async def scrape_sold_items_from_search(self, num_posts=10):
        """Scrape posts from the 'sold' search results page - no detection needed"""
        logger.info(f"Scraping {num_posts} posts from 'sold' search results")
        logger.info("All posts on this page should contain 'sold' - scraping sequentially")
        
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
                    logger.debug("No new containers, scrolling for more...")
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    continue
                
                logger.debug(f"Examining containers starting from {container_position + 1}")
                
                # Find the next main post in the remaining containers
                next_main_post_index = None
                for i, container in enumerate(remaining_containers[:15]):
                    try:
                        html_content = await container.inner_html(timeout=1500)
                        text_content = await container.text_content(timeout=1200) or ""
                        
                        # Use the ORIGINAL main post detection (without sale filtering)
                        if self._is_main_post_original_logic(text_content, len(html_content)):
                            next_main_post_index = container_position + i
                            logger.debug(f"Found main post at container {next_main_post_index + 1}")
                            break
                            
                    except Exception:
                        continue
                
                if next_main_post_index is None:
                    logger.debug("No main post found in current batch, scrolling...")
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
                    # Add sold indicator since we know it's from the sold search
                    post_data['from_sold_search'] = True
                    posts.append(post_data)
                    logger.success(f"Successfully scraped sold post {len(posts)}/{num_posts}")
                    self.print_post_debug_with_comments(post_data)
                    
                    # Update self.posts_data immediately
                    self.posts_data = posts.copy()
                    
                    if len(posts) % 3 == 0:
                        logger.info(f"Auto-saving progress at {len(posts)} posts")
                        await self.auto_save(posts)
                
                # Move position to after this complete thread
                container_position = boundary_index
                scroll_attempts = 0
                
            except Exception as e:
                logger.error(f"Error in sold search scraping: {str(e)[:100]}")
                scroll_attempts += 1
                container_position += 3
                continue
        
        # Final update
        self.posts_data = posts
        logger.info(f"Completed sold search scraping: {len(posts)} posts")
        return posts

    async def scrape_with_deep_sold_detection(self, num_posts=10):
        """Deep detection with enhanced logging"""
        logger.info(f"Starting DEEP sold detection for {num_posts} sold items")
        
        # Reset counter
        self.absolute_post_counter = 0
        
        sold_items_found = []
        current_container = 0
        posts_processed = 0
        scroll_attempts = 0
        max_scrolls = 25
        max_posts_to_check = num_posts * 15
        
        await self.close_any_modals()
        
        while len(sold_items_found) < num_posts and posts_processed < max_posts_to_check:
            try:
                all_containers = await self.page.locator('[role="article"]').all()
                
                if current_container >= len(all_containers):
                    logger.info(f"Need more containers (checked {posts_processed} posts, "
                              f"found {len(sold_items_found)}/{num_posts} sold)")
                    
                    if scroll_attempts >= max_scrolls:
                        break
                    
                    await self.page.keyboard.press('End')
                    await asyncio.sleep(3)
                    scroll_attempts += 1
                    continue
                
                container = all_containers[current_container]
                
                try:
                    html_content = await container.inner_html(timeout=2000)
                    text_content = await container.text_content(timeout=1500) or ""
                    
                    if self._is_main_post_original_logic(text_content, len(html_content)):
                        posts_processed += 1
                        self.absolute_post_counter += 1
                        
                        # Get preview
                        preview = ' '.join(text_content.split()[:20])[:100]
                        
                        logger.info(f"")
                        logger.info(f"{'='*60}")
                        logger.info(f"🔍 DEEP SCAN: POST #{self.absolute_post_counter} (container {current_container + 1})")
                        logger.info(f"📝 Preview: {preview}...")
                        logger.info(f"📊 Progress: Found {len(sold_items_found)}/{num_posts} sold items")
                        logger.info(f"{'='*60}")
                        
                        # Visual highlight if enabled
                        if self.visual_highlight:
                            await self.highlight_element(container)
                        
                        # Process with deep analysis
                        post_data, boundary_index = await self.process_post_with_deep_sold_analysis(
                            all_containers,
                            current_container,
                            posts_processed
                        )
                        
                        if post_data:
                            sold_analysis = post_data.get('sold_analysis', {})
                            
                            if sold_analysis.get('is_sold', False):
                                sold_items_found.append(post_data)
                                confidence = sold_analysis.get('confidence', 0)
                                method = sold_analysis.get('sale_method', 'unknown')
                                
                                if sold_analysis.get('would_be_missed_by_search'):
                                    logger.success(f"💎 HIDDEN SOLD ITEM #{len(sold_items_found)} FOUND! "
                                                 f"(Post #{self.absolute_post_counter})")
                                    logger.info(f"   This sale would be MISSED by Facebook search!")
                                else:
                                    logger.success(f"✅ SOLD ITEM #{len(sold_items_found)} FOUND "
                                                 f"(Post #{self.absolute_post_counter})")
                                
                                self.print_enhanced_post_summary(post_data, self.absolute_post_counter)
                                
                                self.posts_data = sold_items_found.copy()
                                
                                if len(sold_items_found) % 2 == 0:
                                    await self.auto_save(sold_items_found)
                            else:
                                confidence = sold_analysis.get('confidence', 0)
                                logger.info(f"   ❌ Not sold (confidence: {confidence}%) - continuing...")
                        
                        current_container = max(boundary_index, current_container + 1)
                        scroll_attempts = 0
                    else:
                        current_container += 1
                        
                except Exception as e:
                    logger.warning(f"Error processing container {current_container + 1}: {str(e)[:50]}")
                    current_container += 1
                    
            except Exception as e:
                logger.error(f"Major error: {str(e)[:100]}")
                current_container += 1
        
        self.posts_data = sold_items_found
        
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.success(f"🏁 Deep detection complete!")
        logger.info(f"📊 Final Stats:")
        logger.info(f"   • Total posts scanned: {self.absolute_post_counter}")
        logger.info(f"   • Sold items found: {len(sold_items_found)}/{num_posts}")
        logger.info(f"{'='*60}")
        
        return sold_items_found

    async def process_post_with_deep_sold_analysis(self, containers, main_post_index, post_number):
        """Process post with DEEP analysis of comments for sale confirmation"""
        
        logger.debug(f"Deep analysis of post {post_number} at index {main_post_index}")
        
        try:
            # First get the complete thread (post + all comments)
            boundary_index = await self.find_post_boundary(containers, main_post_index)
            thread_containers = containers[main_post_index:boundary_index]
            thread_size = len(thread_containers)
            
            logger.debug(f"Complete thread: {thread_size} containers")
            
            # Extract main post data
            main_container = thread_containers[0]
            comment_containers = thread_containers[1:]
            
            # Force load if needed
            try:
                html_size = len(await main_container.inner_html(timeout=3000))
                if html_size < 35000:
                    await self.force_load_post_content(main_container)
            except:
                pass
            
            # Extract main post
            post_data = await asyncio.wait_for(
                self.extract_post_data_improved_fixed(main_container, post_number),
                timeout=15.0
            )
            
            if not post_data:
                return None, boundary_index
            
            # Process ALL comments for deep analysis
            if comment_containers:
                logger.debug(f"Deep-scanning {len(comment_containers)} comment containers")
                comment_container_info_list = []
                for container in comment_containers:
                    comment_container_info_list.append({'container': container})
                
                # For deep detection, we want ALL comments
                await self.process_complete_comment_thread(
                    post_data, 
                    comment_container_info_list,
                    max_comments=100  # High limit for deep analysis
                )
            
            # Call the enhanced analyze_sold_status with deep_mode=True
            sold_analysis = self.sold_detector.analyze_sold_status(post_data, deep_mode=True)
            post_data['sold_analysis'] = sold_analysis
            
            # Enhanced logging for deep detection findings
            if sold_analysis['is_sold']:
                method = sold_analysis['sale_method']
                
                # Special highlighting for sales Facebook would miss
                if sold_analysis.get('would_be_missed_by_search', False):
                    logger.info(f"   💎 HIDDEN SALE FOUND - Facebook search would miss this!")
                    logger.info(f"   This sale was confirmed only in comments, not the main post")
                elif method == 'comments':
                    logger.info(f"   💎 COMMENT-CONFIRMED SALE DETECTED")
                elif method == 'both':
                    logger.info(f"   ✅ Sale confirmed in both post and comments")
                else:
                    logger.info(f"   ✅ Sale confirmed in main post")
                
                # Show what made us detect this as sold
                if sold_analysis.get('sold_indicators'):
                    top_indicators = sold_analysis['sold_indicators'][:3]
                    logger.debug(f"   Key indicators: {', '.join(top_indicators)}")
            
            return post_data, boundary_index
            
        except asyncio.TimeoutError:
            logger.error(f"Deep analysis timed out for post {post_number}")
            return None, boundary_index
        except Exception as e:
            logger.error(f"Error in deep analysis for post {post_number}: {str(e)[:100]}")
            return None, boundary_index


    ###^ 2.1 - FORCE LOADING HELPERS

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


    ###^ 2.2 - BOUNDARY DETECTION & FORCE LOADING HELPERS

    def is_main_post_container(self, text_content, html_size):
        """Enhanced main post detection with optional sale and sold filtering"""
        
        # First, apply your existing main post detection logic
        is_main_post = self._is_main_post_original_logic(text_content, html_size)
        
        if not is_main_post:
            return False
        
        # CRITICAL FIX: When in sold_items_only mode, we're already on the filtered search page
        # So we should NOT apply any additional filtering
        if self.sold_items_only:
            # We're on the "sold" search results page - all posts are already filtered by Facebook
            return is_main_post  # Just return the original detection result
        
        # Apply sale filtering only for sale_posts_only mode (not for sold search)
        if self.sale_posts_only:
            is_sale, details = self.is_sale_post(text_content)
            
            if is_sale:
                logger.debug(f"Sale post detected: {text_content[:50]}...")
                return True
            else:
                logger.debug(f"Non-sale post filtered out: {text_content[:30]}...")
                return False
        
        # If no special filtering, use original result
        return is_main_post

    def _is_main_post_original_logic(self, text_content, html_size):
        """Your original main post detection logic (unchanged)"""
        # SALE INDICATORS should override comment signals (highest priority)
        strong_sale_indicators = [
            '$' in text_content and any(word in text_content.lower() for word in ['shipped', 'obo', 'firm', 'sold']),
            any(phrase in text_content.lower() for phrase in ['for sale', 'fs:', 'wts:', 'price drop']),
            text_content.count('$') > 0 and len(text_content) > 80,  # Price with substantial text
        ]
        
        # If it has strong sale indicators, it's definitely a main post regardless of other signals
        if any(strong_sale_indicators):
            logger.debug(f"SALE POST DETECTED: {text_content[:50]}...")
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
            logger.debug(f"STRONG COMMENT SIGNAL: {text_content[:50]}...")
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



    ###^ 2.3 - SALE POST DETECTION

    def _init_sale_patterns(self):
        """Initialize sale detection patterns"""
        self.sale_keywords = {
            'direct_sale': [
                'for sale', 'fs:', 'wts:', 'want to sell', 'selling',
                'price drop', 'reduced price', 'make offer', 'obo', 'or best offer',
                'firm price', 'firm', 'take it', "i'll take", 'claim it', 'mine', 'pm sent', 'message sent'
            ],
            'collectible_specific': [
                'moc', 'mip', 'mib', 'mint on card', 'mint in package',
                'loose', 'complete', 'incomplete', 'custom', 'vintage', 'rare',
                'htf', 'hard to find', 'grail', 'holy grail'
            ],
            'transaction': [
                'shipped', 'shipping', 'plus shipping', 'free ship',
                'local pickup', 'pick up', 'ppu', 'pending pickup',
                'paypal ready', 'pp ready', 'cash ready', 'available'
            ],
            'status': [
                'sold', 'spo', 'sold pending payment', 'pending',
                'still available', 'available'
            ]
        }
        
        self.price_patterns = [
            r'\$\d+(?:\.\d{2})?',           # $25, $25.00
            r'\d+\s*(?:dollars?|bucks?)',    # 25 dollars, 25 bucks
            r'asking\s*:?\s*\$?\d+',         # asking $25, asking: 25
            r'price\s*:?\s*\$?\d+',          # price $25, price: 25
            r'\d+\s*(?:obo|firm|shipped|each)', # 25 obo, 100 firm
        ]
        
        # Words that indicate NOT a sale post
        self.non_sale_indicators = [
            'iso', 'in search of', 'looking for', 'wtb', 'want to buy',
            'wanted', 'need', 'seeking', 'anyone have', 'does anyone',
            'help me find', 'where can i', 'question', 'advice', 'opinion',
            'thoughts', 'what do you think', 'should i', 'is this worth',
            'just got', 'just arrived', 'mail call', 'collection update',
            'haul', 'found at'
        ]
        
        logger.info(f"Sale detection patterns initialized")

    async def _verify_sale_filter_applied(self):
        """Check if Facebook's sale filter is working"""
        try:
            current_url = self.page.url
            
            if 'filter=sell' in current_url:
                logger.success("Facebook sale filter appears to be active in URL")
                
                # Additional check: look for reduced post count or sale-specific UI
                await asyncio.sleep(2)
                post_count = len(await self.page.locator('[role="article"]').all())
                logger.info(f"Found {post_count} posts with sale filter applied")
                
                return True
            else:
                logger.warning("Facebook sale filter may not be working (URL doesn't show filter)")
                logger.info("Will rely on content-based filtering instead")
                return False
                
        except Exception as e:
            logger.warning(f"Could not verify sale filter status: {e}")
            return False


    def is_sale_post(self, text_content):
        """Determine if a post is a sale post with confidence scoring"""
        if not text_content:
            return False, {'reason': 'No text content', 'score': 0}
        
        text_lower = text_content.lower()
        score = 0
        reasons = []
        
        # Check for prices (highest confidence)
        price_found = False
        for pattern in self.price_patterns:
            if re.search(pattern, text_lower):
                price_found = True
                score += 40
                reasons.append("Price pattern found")
                break
        
        # Check for sale keywords by category
        for category, keywords in self.sale_keywords.items():
            found_keywords = [kw for kw in keywords if kw in text_lower]
            if found_keywords:
                if category == 'direct_sale':
                    score += 30
                    reasons.append(f"Direct sale: {found_keywords[:2]}")
                elif category == 'transaction':
                    score += 20
                    reasons.append(f"Transaction terms: {found_keywords[:2]}")
                elif category == 'collectible_specific':
                    score += 15
                    reasons.append(f"Collectible terms: {found_keywords[:2]}")
                elif category == 'status':
                    score += 10
                    reasons.append(f"Status terms: {found_keywords[:2]}")
        
        # Check for non-sale indicators (reduces confidence)
        non_sale_found = [ind for ind in self.non_sale_indicators if ind in text_lower]
        if non_sale_found:
            score -= 25
            reasons.append(f"Non-sale indicators: {non_sale_found[:2]}")
        
        # Handle sold posts
        if not self.include_sold:
            sold_indicators = ['sold', 'spo', 'sold pending payment', 'pending payment']
            if any(ind in text_lower for ind in sold_indicators):
                reasons.append("Sold post (excluded)")
                return False, {'reasons': reasons, 'score': score}
        
        # Decision logic
        is_sale = (
            score >= 50 or  # High confidence
            (score >= 30 and price_found) or  # Medium confidence with price
            (score >= 25 and len([r for r in reasons if 'sale' in r.lower()]) >= 2)  # Multiple sale indicators
        )
        
        return is_sale, {
            'score': score, 
            'reasons': reasons, 
            'price_found': price_found
        }
    

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
                    src = await img.get_attribute('src', timeout=3000)
                    
                    # Filter for actual content images (not UI elements)
                    if src and ('scontent' in src or 'fbcdn' in src):
                        alt_text = await img.get_attribute('alt', timeout=2000) or ""
                        
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



    ###^ 4 - PROCESSING & VALIDATION

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
    
    async def process_post_with_sold_detection(self, containers, main_post_index, post_number):
        """Process post with sold items detection using existing thread boundary logic"""
        
        logger.debug(f"Processing post {post_number} for sold detection at index {main_post_index}")
        
        try:
            # Use your existing thread boundary detection to get complete post + comments
            post_data, boundary_index = await self.process_post_with_complete_thread(
                containers, main_post_index, post_number
            )
            
            if not post_data:
                logger.debug(f"No post data retrieved for post {post_number}")
                return None, boundary_index
            
            # Analyze for sold status using comments and post content
            sold_analysis = self.sold_detector.analyze_sold_status(post_data)
            post_data['sold_analysis'] = sold_analysis
            
            if sold_analysis['is_sold']:
                confidence = sold_analysis['confidence']
                indicators = sold_analysis['sold_indicators']
                method = sold_analysis['sale_method']
                
                logger.success(f"SOLD ITEM DETECTED: Post {post_number}")
                logger.info(f"  Confidence: {confidence}%")
                logger.info(f"  Method: {method}")
                logger.debug(f"  Indicators: {indicators[:3]}")
                
                return post_data, boundary_index
            else:
                confidence = sold_analysis['confidence']
                logger.debug(f"Item not sold (confidence: {confidence}%), filtering out post {post_number}")
                return None, boundary_index
        
        except asyncio.TimeoutError:
            logger.error(f"Sold detection processing timed out for post {post_number}")
            return None, boundary_index
        except Exception as e:
            logger.error(f"Error in sold detection for post {post_number}: {str(e)[:100]}")
            return None, boundary_index
    

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
    
    async def highlight_element(self, element, duration=2):
        """Visually highlight an element in the browser"""
        if not self.visual_highlight:
            return
            
        try:
            # Scroll element into view first
            await element.scroll_into_view_if_needed()
            
            # Add a red border and yellow background using JavaScript
            await element.evaluate('''
                (element) => {
                    // Store original styles
                    const originalBorder = element.style.border;
                    const originalBackground = element.style.backgroundColor;
                    const originalBoxShadow = element.style.boxShadow;
                    
                    // Apply highlight styles
                    element.style.border = '3px solid red';
                    element.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
                    element.style.boxShadow = '0 0 20px rgba(255, 0, 0, 0.5)';
                    
                    // Remove highlight after duration
                    setTimeout(() => {
                        element.style.border = originalBorder;
                        element.style.backgroundColor = originalBackground;
                        element.style.boxShadow = originalBoxShadow;
                    }, ''' + str(duration * 1000) + ''');
                }
            ''')
            
            # Brief pause to let the highlight be visible
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.debug(f"Could not highlight element: {str(e)[:50]}")

    
    ###^ EXTRACTION METHODS - POST DATA & TEXT    
    
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


    ###^ EXTRACTION METHODS - AUTHOR & TIME

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


    ###^ EXTRACTION METHODS - IMAGES

    async def extract_images_safe(self, post_element, post_id):
        """Extract images without clicking"""
        images = []
        
        try:
            # Get image URLs with explicit timeout
            img_elements = await post_element.locator('img').all()
            
            for i, img in enumerate(img_elements[:15]):  # Increased limit
                try:
                    src = await img.get_attribute('src', timeout=3000)
                    
                    if src and ('scontent' in src or 'fbcdn' in src):
                        alt_text = await img.get_attribute('alt', timeout=2000) or ""
                        
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
    
    
    ###^ EXTRACTION METHODS - COLLECTIBLE INFO
    
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
    
    
    ###^ DIAGNOSICS METHODS
    
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
                        src = await img.get_attribute('src', timeout=3000)
                        alt = await img.get_attribute('alt', timeout=2000)
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

    def print_sold_item_debug(self, post_data):
        """Enhanced debug output for sold items"""
        
        # Your existing debug output
        text_preview = post_data.get('text', '')[:80] or "[No text]"
        author = post_data.get('author', '') or "[No author]"
        
        print(f"   ✅ Text: {text_preview}{'...' if len(post_data.get('text', '')) > 80 else ''}")
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
        
        # NEW: Add sold analysis info
        sold_analysis = post_data.get('sold_analysis', {})
        if sold_analysis:
            confidence = sold_analysis.get('confidence', 0)
            method = sold_analysis.get('sale_method', 'unknown')
            
            print(f"   🏷️ SOLD STATUS: {confidence}% confidence")
            print(f"   💰 Sale Method: {method}")
            
            if sold_analysis.get('buyer_identified'):
                print(f"   🙋 Buyer identified in comments")
            
            if sold_analysis.get('sold_indicators'):
                indicators_str = ', '.join(sold_analysis['sold_indicators'][:3])
                print(f"   📝 Indicators: {indicators_str}")
            
            # Show timeline if available
            timeline = sold_analysis.get('sale_timeline', [])
            if timeline:
                print(f"   ⏰ Sale Timeline: {len(timeline)} interaction(s)")
                for entry in timeline[:2]:  # Show first 2 interactions
                    indicators_str = ', '.join(entry.get('indicators', []))
                    print(f"      - {entry.get('author', 'Unknown')}: {indicators_str}")
        
        # Show sale info if available
        sale_info = post_data.get('sale_info')
        if sale_info:
            if sale_info.get('price'):
                print(f"   💰 Price: {sale_info.get('price')}")
            if sale_info.get('items'):
                print(f"   🎯 Items: {', '.join(sale_info.get('items', [])[:3])}")

    def print_enhanced_post_summary(self, post_data, absolute_num):
        """Print enhanced summary with consistent format"""
        
        # Main post text (first 100 chars)
        text = post_data.get('text', '')[:100]
        if len(post_data.get('text', '')) > 100:
            text += "..."
        
        # Author
        author = post_data.get('author', 'Unknown')[:30]
        
        # Images and comments
        images = post_data.get('image_count', 0)
        comments = post_data.get('comment_count', 0)
        
        # Print formatted summary
        print(f"   📋 Post #{absolute_num} Summary:")
        print(f"   📝 Text: {text}")
        print(f"   👤 Author: {author}")
        print(f"   📷 Images: {images} | 💬 Comments: {comments}")
        
        # If it's a sale post, show price
        sale_info = post_data.get('sale_info')
        if sale_info and sale_info.get('price'):
            print(f"   💰 Price: {sale_info.get('price')}")
        
        # If sold detection is active
        sold_analysis = post_data.get('sold_analysis')
        if sold_analysis and sold_analysis.get('is_sold'):
            confidence = sold_analysis.get('confidence', 0)
            method = sold_analysis.get('sale_method', 'unknown')
            print(f"   🏷️ SOLD: {confidence}% confidence via {method}")
            if sold_analysis.get('would_be_missed_by_search'):
                print(f"   💎 Hidden sale - Facebook search would miss this!")
        
        print("")  # Blank line for readability


    ###^ 5- CLEANUP AND SAVE FUNCTIONS
    
    async def auto_save(self, posts_data=None):
        """Auto-save progress - with logging"""
        try:
            data_to_save = posts_data or self.posts_data
            if not data_to_save:
                logger.warning("No data to auto-save")
                return
                
            # Save JSON checkpoint
            checkpoint_file = self.output_dir / f"checkpoint_{self.session_id}.json"
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            logger.success(f"Auto-saved {len(data_to_save)} posts to checkpoint")
            
        except Exception as e:
            logger.error(f"Auto-save failed: {str(e)[:50]}")

    async def save_results_fixed(self):
        """Save scraped data - with logging"""
        if not self.posts_data:
            logger.warning("No posts to save")
            return
        
        logger.info(f"Saving results for {len(self.posts_data)} posts")
        
        try:
            # Create the output directory if it doesn't exist
            self.output_dir.mkdir(exist_ok=True)
            
            # Save full JSON
            json_file = self.output_dir / f"group_posts_{self.session_id}.json"
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(self.posts_data, f, indent=2, ensure_ascii=False)
                logger.success(f"Full data saved to: {json_file}")
            except Exception as e:
                logger.error(f"Failed to save JSON: {str(e)}")
            
            # Create sales summary CSV
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
                        'author': post.get('author', '')[:50],
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
                
                # Write CSV
                with open(sales_csv, 'w', newline='', encoding='utf-8') as f:
                    if sales_data:
                        writer = csv.DictWriter(f, fieldnames=sales_data[0].keys())
                        writer.writeheader()
                        writer.writerows(sales_data)
                        
                logger.success(f"Sales summary saved to: {sales_csv}")
                
            except Exception as e:
                logger.error(f"Failed to save CSV: {str(e)}")
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
                    logger.success(f"Created text backup: {backup_file}")
                except:
                    logger.error("Even backup save failed")
            
            # Print summary
            self.print_summary_fixed()
            
        except Exception as e:
            logger.error(f"Save error: {str(e)}")
            logger.info("Attempting emergency save...")
            
            # Emergency save as plain text
            try:
                emergency_file = self.output_dir / f"emergency_save_{self.session_id}.txt"
                with open(emergency_file, 'w', encoding='utf-8') as f:
                    f.write(f"Emergency save at {datetime.now()}\n")
                    f.write(f"Posts scraped: {len(self.posts_data)}\n\n")
                    for i, post in enumerate(self.posts_data):
                        f.write(f"Post {i+1}: {str(post)}\n\n")
                logger.success(f"Emergency save completed: {emergency_file}")
            except:
                logger.error("Emergency save also failed")
                
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
        """Close connections - with logging"""
        logger.info("Scraping complete - cleaning up...")
        
        try:
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
                logger.success("Playwright closed successfully")
        except Exception as e:
            logger.error(f"Error closing playwright: {str(e)}")
        
        logger.info("Cleanup complete - browser left open for your use")



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

def prompt_select_groups(groups):
    """
    Show a numbered list of group names and return a list of selected group dicts.
    Accepts: single number (e.g., '2'), comma-separated (e.g., '1,3'), or 'a' for all.
    """
    if not groups:
        print("No Facebook groups configured in resources/fb_groups.py")
        return []

    print("\n📋 Available Facebook Groups:")
    for i, g in enumerate(groups, start=1):
        print(f"  {i}. {g['group_name']}  ({g['group_id']})")

    raw = input("\nChoose group(s) [number, numbers comma-separated, or 'a' for all]: ").strip().lower()
    if raw == "a":
        return groups

    # parse indices
    try:
        idxs = [int(x) for x in raw.split(",") if x.strip()]
        selected = []
        for idx in idxs:
            if 1 <= idx <= len(groups):
                selected.append(groups[idx - 1])
            else:
                print(f"  ⚠️ Skipping out-of-range index: {idx}")
        return selected
    except ValueError:
        print("  ⚠️ Invalid input. Using the first group as default.")
        return [groups[0]]


async def main():
    """Main function with visual highlighting option"""
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
        if not start_browser_with_debugging():
            return
    else:
        print("\n📋 Make sure you have a browser open with remote debugging:")
        print('Chrome: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
        print('Edge: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222')
        print("\nAnd that you're logged into Facebook")
        input("\nPress Enter to continue...")
    
    # Post filtering options with new option 5
    print("\n🏷️ Post Filtering Options:")
    print("1. All posts (default)")
    print("2. Sale posts only")
    print("3. Available sale posts only (exclude sold items)")
    print("4. SOLD ITEMS ONLY (Facebook search - posts marked 'sold')")
    print("5. SOLD ITEMS ONLY (Deep detection - finds sales confirmed in comments)")

    filter_choice = input("\nFiltering choice (1-5): ").strip()

    if filter_choice == '2':
        sale_posts_only = True
        include_sold = True
        sold_items_only = False
        use_deep_sold_detection = False
        print("✅ Will scrape SALE POSTS ONLY (including sold items)")
        
    elif filter_choice == '3':
        sale_posts_only = True
        include_sold = False
        sold_items_only = False
        use_deep_sold_detection = False
        print("✅ Will scrape AVAILABLE SALE POSTS ONLY (excluding sold)")
        
    elif filter_choice == '4':
        # Facebook search already filters for 'sold'
        sale_posts_only = False
        include_sold = True
        sold_items_only = True
        use_deep_sold_detection = False
        print("✅ Will scrape SOLD ITEMS from Facebook search (posts marked 'sold')")
        print("ℹ️ Using Facebook's 'sold' search filter")
        
    elif filter_choice == '5':
        # NEW: Deep detection mode - scan regular feed for comment-confirmed sales
        sale_posts_only = False
        include_sold = True
        sold_items_only = False  # Don't use Facebook search
        use_deep_sold_detection = True
        print("✅ Will use DEEP SOLD DETECTION (analyzes posts + comments)")
        print("🔍 This finds sales confirmed in comments that Facebook search might miss")
        print("📊 Perfect for comprehensive market research")
        
    else:
        sale_posts_only = False
        include_sold = True
        sold_items_only = False
        use_deep_sold_detection = False
        print("ℹ️ Will scrape ALL posts")
    
    # Ask about visual highlighting
    print("\n🎨 Visual Options:")
    highlight = input("Enable visual highlighting of posts being processed? (y/n, default=n): ").strip().lower()
    visual_highlight = highlight == 'y'
    
    if visual_highlight:
        print("✅ Visual highlighting enabled - watch the browser to see posts being processed!")
        print("   Each post will be highlighted with a red border and yellow background")
    else:
        print("ℹ️ Visual highlighting disabled (better performance)")
    
    # Ask about downloading images
    download = input("\n📷 Download images? (y/n, default=y): ").strip().lower()
    download_images = download != 'n'
    
    if download_images:
        print("✅ Will download images to local folder")
        # ... [existing image download setup] ...
    else:
        print("ℹ️ Will only save image URLs (not downloading)")
    
    # Ask about autonomous operation
    autonomous = input("\n🤖 Run autonomously without user prompts? (y/n, default=y): ").strip().lower()
    autonomous_mode = autonomous != 'n'
    
    if autonomous_mode:
        print("✅ Autonomous mode enabled - will run without user interaction")
    else:
        print("ℹ️ Interactive mode - will ask for confirmation if needed")
    
    # Create scraper with all options including visual highlighting
    scraper = FacebookGroupScraper(
        download_images=download_images,
        sale_posts_only=sale_posts_only,
        include_sold=include_sold,
        sold_items_only=sold_items_only,
        use_deep_sold_detection=use_deep_sold_detection if 'use_deep_sold_detection' in locals() else False,
        visual_highlight=visual_highlight  # NEW parameter
    )
    
    try:
        # Connect to browser
        if await scraper.connect_to_existing_browser():
            
            # Ask which group(s) to scrape using the configured list
            selected_groups = prompt_select_groups(fb_groups)
            if not selected_groups:
                print("No groups selected. Exiting.")
                return

            # Navigate to (and later scrape) each selected group in order
            for grp in selected_groups:
                group_id = grp["group_id"]
                print(f"\n🌐 Selected group: {grp['group_name']} ({group_id})")
                await scraper.navigate_to_group(group_id)
            
            # Skip diagnosis for filtering modes to save time
            if filter_choice == '1':  # Only for "all posts" mode
                await scraper.comprehensive_diagnosis()
            
            # How many posts?
            num = input("\nNumber of posts to scrape (default 10): ").strip()
            num_posts = int(num) if num else 10
            
            # Adjust expectations based on filtering mode
            if sold_items_only:
                print(f"\n🏷️ SOLD ITEMS MODE: Scanning for {num_posts} completed sales")
                print("📊 This is perfect for market research - see what actually sells!")
                print("🔍 Will analyze both posts and comments for sale completion evidence")
            elif sale_posts_only:
                print(f"\n🏷️ SALE FILTERING: May need to scan more posts to find {num_posts} sale posts")
            
            print("\n⚠️ Don't click anything in the browser while scraping!")
            print("The script will handle everything automatically.")
            
            if autonomous_mode:
                print("🤖 Running in autonomous mode - no user interaction required.")
            print("Enhanced version with sold items detection.\n")
            
            # Calculate timeout based on mode
            if use_deep_sold_detection:
                # Longest timeout - need to analyze comments deeply
                base_timeout = max(500, num_posts * 50)  # 50 seconds per sold item to find
            elif sold_items_only:
                # Facebook search - simpler
                base_timeout = max(300, num_posts * 30)
            elif sale_posts_only:
                base_timeout = max(300, num_posts * 30)
            else:
                base_timeout = max(240, num_posts * 25)
                        
            # Scraping with appropriate method
            all_posts = []
            attempt = 1
            max_retries = 3 if (sold_items_only or use_deep_sold_detection) else 2
            remaining_posts = num_posts
            
            while len(all_posts) < num_posts and attempt <= max_retries:
                try:
                    if use_deep_sold_detection:
                        # Option 5: Deep detection on regular group feed
                        print(f"🔍 Attempt {attempt}/{max_retries}: Deep-scanning for {remaining_posts} sold items (timeout: {base_timeout}s)")
                        posts = await asyncio.wait_for(
                            scraper.scrape_with_deep_sold_detection(remaining_posts),
                            timeout=base_timeout
                        )
                    elif sold_items_only:
                        # Option 4: Facebook search results
                        print(f"📡 Attempt {attempt}/{max_retries}: Scraping {remaining_posts} posts from Facebook search (timeout: {base_timeout}s)")
                        posts = await asyncio.wait_for(
                            scraper.scrape_sold_items_from_search(remaining_posts),
                            timeout=base_timeout
                        )
                    else:
                        # Options 1, 2, 3: Regular scraping
                        print(f"📡 Attempt {attempt}/{max_retries}: Scraping {remaining_posts} posts (timeout: {base_timeout}s)")
                        posts = await asyncio.wait_for(
                            scraper.scrape_with_thread_boundary_detection(remaining_posts),
                            timeout=base_timeout
                        )
                    
                    if posts:
                        all_posts.extend(posts)
                        if use_deep_sold_detection:
                            print(f"✅ Found {len(posts)} sold items via deep detection in attempt {attempt}")
                            # Show how many were comment-confirmed
                            comment_sales = sum(1 for p in posts 
                                            if p.get('sold_analysis', {}).get('sale_method') in ['comments', 'both'])
                            if comment_sales > 0:
                                print(f"   💎 {comment_sales} were confirmed via comments (Facebook search would miss these!)")
                        elif sold_items_only:
                            print(f"✅ Got {len(posts)} sold posts from Facebook search in attempt {attempt}")
                        else:
                            print(f"✅ Got {len(posts)} posts in attempt {attempt}")
                        break
                    
                except asyncio.TimeoutError:
                    print(f"\n⏱️ Timeout on attempt {attempt}, retrieving partial results...")
                    partial_posts = scraper.posts_data or []
                    if partial_posts:
                        all_posts.extend(partial_posts)
                        print(f"📦 Retrieved {len(partial_posts)} posts from attempt {attempt}")
                    
                    if autonomous_mode and len(all_posts) < num_posts and attempt < max_retries:
                        remaining_posts = num_posts - len(all_posts)
                        print(f"🤖 Autonomous retry: Attempting {remaining_posts} more posts...")
                        attempt += 1
                        base_timeout = max(300, remaining_posts * 40)
                        continue
                    else:
                        break
                
                except Exception as e:
                    print(f"❌ Error on attempt {attempt}: {str(e)[:100]}")
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
            
            # Results handling
            posts = all_posts
            
            if posts and len(posts) > 0:
                scraper.posts_data = posts
                
                try:
                    await scraper.save_results_fixed()
                    
                    if sold_items_only:
                        print(f"\n✅ Successfully found {len(posts)} sold items!")
                        print("📊 Perfect for market research:")
                        print("   - See what items actually sell")
                        print("   - Understand pricing trends")
                        print("   - Identify popular items")
                        
                        # Show sold analysis summary
                        high_confidence = sum(1 for p in posts if p.get('sold_analysis', {}).get('confidence', 0) >= 80)
                        comment_sales = sum(1 for p in posts if p.get('sold_analysis', {}).get('sale_method') in ['comments', 'both'])
                        
                        print(f"   - {high_confidence} high-confidence sales (≥80%)")
                        print(f"   - {comment_sales} sales completed in comments")
                        
                    elif sale_posts_only:
                        print(f"\n✅ Successfully found {len(posts)} sale posts!")
                    else:
                        print(f"\n✅ Successfully scraped {len(posts)} posts!")
                        
                    print(f"📁 Data saved in folder: {scraper.output_dir}/")
                    
                except Exception as e:
                    print(f"⚠️ Error during save: {str(e)[:100]}")
            else:
                if sold_items_only:
                    print(f"\n⚠️ No sold items found after {attempt-1} attempts")
                    print("This could mean:")
                    print("1. No recent sales in this group")
                    print("2. Sales aren't clearly marked as sold")
                    print("3. Try a larger group or different time period")
                else:
                    print(f"\n⚠️ No posts found after {attempt-1} attempts")
        
        else:
            print("\n❌ Could not connect to browser")
            
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
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())