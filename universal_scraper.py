#!/usr/bin/env python3
"""
Universal Content Scraper

A truly reusable scraper that works on any website by detecting common patterns
rather than using site-specific selectors. This avoids the trap of building
custom code that only works for one customer.

Key principles:
1. Pattern detection over hardcoded selectors
2. Architecture-aware (static HTML, SPA, server-rendered React, etc.)
3. Content quality scoring to find the best content
4. Universal configuration that works across all sites
"""

import json
import requests
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse, parse_qs
import time
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
import PyPDF2
import io
from markdownify import markdownify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import asyncio
import os
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add PDF processing imports
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT_PYMUPDF = True
except ImportError:
    PDF_SUPPORT_PYMUPDF = False

try:
    import PyPDF2
    PDF_SUPPORT_PYPDF2 = True
except ImportError:
    PDF_SUPPORT_PYPDF2 = False

PDF_SUPPORT = PDF_SUPPORT_PYMUPDF or PDF_SUPPORT_PYPDF2

if not PDF_SUPPORT:
    print("⚠️  PDF processing not available. Install PyPDF2 or PyMuPDF for PDF support.")


@dataclass
class ContentItem:
    """Represents a single piece of content for the knowledgebase"""
    title: str
    content: str
    content_type: str = "blog"
    source_url: str = ""
    author: str = ""
    user_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with consistent field ordering"""
        return {
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "source_url": self.source_url,
            "author": self.author,
            "user_id": self.user_id
        }


class WebsiteArchitectureDetector:
    """Detects what type of website architecture we're dealing with"""
    
    @staticmethod
    def detect_architecture(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Detect website architecture and return strategy info"""
        
        # Check for JavaScript frameworks
        scripts = soup.find_all('script')
        script_content = ' '.join([script.get_text() for script in scripts if script.get_text()])
        
        # Check for common JS framework indicators
        is_react = bool(re.search(r'react|React|\breact\b', script_content, re.IGNORECASE))
        is_vue = bool(re.search(r'vue|Vue|\bvue\b', script_content, re.IGNORECASE))
        is_angular = bool(re.search(r'angular|Angular|\bangular\b', script_content, re.IGNORECASE))
        is_next = bool(re.search(r'next|Next|\bnext\b', script_content, re.IGNORECASE))
        
        # Check for SPA indicators
        has_spa_indicators = bool(
            soup.find(attrs={'id': 'root'}) or 
            soup.find(attrs={'id': 'app'}) or
            soup.find(attrs={'class': re.compile(r'app|root')})
        )
        
        # Check content density
        text_content = soup.get_text()
        content_density = len(text_content.strip()) / max(len(str(soup)), 1)
        
        # Determine strategy
        if content_density < 0.02 or has_spa_indicators:
            strategy = "javascript_heavy"
        elif is_react or is_vue or is_angular or is_next:
            strategy = "framework_based"
        else:
            strategy = "static_html"
        
        return {
            'strategy': strategy,
            'frameworks': {
                'react': is_react,
                'vue': is_vue,
                'angular': is_angular,
                'next': is_next
            },
            'content_density': content_density,
            'needs_js': strategy in ['javascript_heavy', 'framework_based']
        }


class PDFProcessor:
    """Handles PDF content extraction and chunking"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        if not PDF_SUPPORT:
            raise ImportError("PDF support not available. Install PyPDF2 or PyMuPDF: pip install PyPDF2")
        
        # Try PyMuPDF first (more accurate)
        if PDF_SUPPORT_PYMUPDF:
            try:
                doc = fitz.open(pdf_path)
                text = ""
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    # Clean the text immediately after extraction
                    page_text = self._clean_pdf_text(page_text)
                    text += page_text
                    text += "\n\n"  # Add spacing between pages
                
                doc.close()
                return text.strip()
            
            except Exception as e:
                logging.warning(f"PyMuPDF failed, trying PyPDF2: {e}")
        
        # Fallback to PyPDF2
        if PDF_SUPPORT_PYPDF2:
            try:
                text = ""
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        # Clean the text immediately after extraction
                        page_text = self._clean_pdf_text(page_text)
                        text += page_text
                        text += "\n\n"  # Add spacing between pages
                
                return text.strip()
            
            except Exception as e:
                logging.error(f"Error extracting text from PDF {pdf_path}: {e}")
                return ""
        
        return ""
    
    def _clean_pdf_text(self, text: str) -> str:
        """Clean PDF text from formatting artifacts and special characters"""
        import re
        
        # Remove common PDF artifacts and formatting issues
        # Remove strikethrough markers and weird formatting
        text = re.sub(r'[\u0336\u0337\u0338]', '', text)  # Remove strikethrough unicode
        text = re.sub(r'[^\w\s\.,;:!?\-\'"()\[\]{}/@#$%&*+=<>|\n]', ' ', text)  # Keep only basic chars
        
        # Fix common PDF extraction issues
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add space between lowercase-uppercase
        text = re.sub(r'([0-9])([A-Z])', r'\1 \2', text)  # Add space between number-uppercase
        
        # Remove page numbers and headers/footers patterns
        text = re.sub(r'\n\d+\s*\n', '\n', text)  # Standalone page numbers
        text = re.sub(r'\n[A-Z\s]{3,50}\n', '\n', text)  # Headers in all caps
        
        # Fix common word breaks
        text = re.sub(r'\b([a-z])\s+([a-z])\b', r'\1\2', text)  # Fix broken words like "h e l l o"
        text = re.sub(r'([a-z])\s*-\s*([a-z])', r'\1-\2', text)  # Fix hyphenated words
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{3,}', '...', text)  # Multiple dots to ellipsis
        text = re.sub(r'[-]{3,}', '---', text)  # Multiple dashes
        
        return text.strip()
    
    def chunk_text(self, text: str, title: str = "") -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces for processing, trying to respect chapter boundaries"""
        
        # Clean the text
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) <= self.chunk_size:
            return [{
                "title": f"{title} (Complete)" if title else "PDF Content",
                "content": text,
                "content_type": "book",
                "chunk_index": 0,
                "total_chunks": 1
            }]
        
        # First, try to find natural chapter boundaries
        chapter_chunks = self._find_chapter_boundaries(text)
        
        # If we found chapters, use them; otherwise fall back to size-based chunking
        if chapter_chunks:
            return self._process_chapter_chunks(chapter_chunks)
        else:
            return self._size_based_chunking(text, title)
    
    def _find_chapter_boundaries(self, text: str) -> List[Dict[str, str]]:
        """Find natural chapter boundaries in the text"""
        chapters = []
        
        # Look for chapter markers - common patterns in books
        chapter_patterns = [
            r'\bChapter\s+\d+[.\s]',  # "Chapter 1.", "Chapter 2 "
            r'\bCh\s*\d+[.\s]',       # "Ch 1.", "Ch1 "
            r'\bCHAPTER\s+\d+[.\s]',  # "CHAPTER 1."
            r'\bCh\s+\d+\.',          # "Ch 1.", "Ch 2."
            r'\bCh\d+\.',             # "Ch1.", "Ch2."
            r'\b\d+\.\s+[A-Z][^.]{10,}',  # "1. Introduction to Something"
            r'\n\s*\d+\s+[A-Z][^.\n]{10,}',  # Numbered sections
            r'\n\s*Ch\s*\d+[.\s]',    # Ch patterns at line start
        ]
        
        # Try each pattern
        for pattern in chapter_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE))
            
            if len(matches) >= 2:  # Need at least 2 chapters to be useful
                logging.info(f"Found {len(matches)} chapter boundaries using pattern: {pattern}")
                
                # Process all found chapters (no limit)
                max_chapters = len(matches)
                
                for i in range(max_chapters):
                    match = matches[i]
                    start_pos = match.start()
                    
                    # Find the end of this chapter (start of next chapter or end of text)
                    if i + 1 < len(matches):
                        end_pos = matches[i + 1].start()
                    else:
                        end_pos = len(text)
                    
                    chapter_content = text[start_pos:end_pos].strip()
                    
                    # Extract chapter title from the match
                    title_match = text[start_pos:start_pos + 200]  # First 200 chars
                    title_line = title_match.split('\n')[0].strip()
                    
                    # Clean up the title
                    title_clean = re.sub(r'^(Chapter|Ch|CHAPTER)\s*\d+[.\s]*', '', title_line).strip()
                    if not title_clean:
                        title_clean = f"Chapter {i + 1}"
                    
                    chapters.append({
                        'title': title_clean,
                        'content': chapter_content,
                        'index': i
                    })
                
                return chapters  # Return the first successful pattern
        
        return []  # No chapters found
    
    def _process_chapter_chunks(self, chapter_chunks: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Process found chapters into final chunks"""
        final_chunks = []
        
        for i, chapter in enumerate(chapter_chunks):
            content = chapter['content']
            
            # If chapter is too long, split it into sub-chunks
            if len(content) > self.chunk_size * 2:
                sub_chunks = self._split_large_chapter(content, chapter['title'], i)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append({
                    "title": chapter['title'],
                    "content": content,
                    "content_type": "book",
                    "chunk_index": i,
                    "total_chunks": len(chapter_chunks)
                })
        
        # Update total chunks count
        total_chunks = len(final_chunks)
        for chunk in final_chunks:
            chunk["total_chunks"] = total_chunks
        
        return final_chunks
    
    def _split_large_chapter(self, content: str, chapter_title: str, chapter_index: int) -> List[Dict[str, Any]]:
        """Split a large chapter into smaller sub-chunks"""
        sub_chunks = []
        start = 0
        part_index = 1
        
        while start < len(content):
            end = start + self.chunk_size
            
            # Try to find a good breaking point
            if end < len(content):
                # Look for paragraph breaks first
                paragraph_break = content.rfind('\n\n', start, end + 200)
                if paragraph_break > start:
                    end = paragraph_break
                else:
                    # Look for sentence endings
                    for i in range(end - 100, end + 100):
                        if i < len(content) and content[i] in '.!?':
                            if i + 1 < len(content) and content[i + 1] == ' ':
                                end = i + 1
                                break
            
            chunk_content = content[start:end].strip()
            
            if chunk_content:
                sub_title = f"{chapter_title} (Part {part_index})"
                sub_chunks.append({
                    "title": sub_title,
                    "content": chunk_content,
                    "content_type": "book",
                    "chunk_index": chapter_index,
                    "total_chunks": 0  # Will be updated later
                })
                part_index += 1
            
            start = end - self.chunk_overlap
            if start <= 0:
                start = end
        
        return sub_chunks
    
    def _size_based_chunking(self, text: str, title: str) -> List[Dict[str, Any]]:
        """Fallback to size-based chunking when no chapters are found"""
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to find a good breaking point (sentence end)
            if end < len(text):
                # Look for sentence endings within the overlap zone
                for i in range(end - self.chunk_overlap, end + self.chunk_overlap):
                    if i < len(text) and text[i] in '.!?':
                        # Check if it's not an abbreviation
                        if i + 1 < len(text) and text[i + 1] == ' ':
                            end = i + 1
                            break
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Use section-based naming for non-chapter content
                chunk_title = f"Section {chunk_index + 1}"
                
                chunks.append({
                    "title": chunk_title,
                    "content": chunk_text,
                    "content_type": "book",
                    "chunk_index": chunk_index,
                    "total_chunks": 0  # Will be updated after all chunks are created
                })
                
                chunk_index += 1
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start <= 0:
                start = end
        
        # Update total_chunks for all chunks to reflect actual count
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk["total_chunks"] = total_chunks
        
        return chunks
    
    def process_pdf_file(self, pdf_path: str, title: str = "", author: str = "") -> List[Dict[str, Any]]:
        """Process a PDF file and return chunked content"""
        
        logging.info(f"📖 Processing PDF: {pdf_path}")
        
        # Extract text
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text:
            logging.error(f"No text extracted from PDF: {pdf_path}")
            return []
        
        logging.info(f"Extracted {len(text)} characters from PDF")
        
        # Chunk the text
        chunks = self.chunk_text(text, title)
        
        # Add metadata to each chunk
        for chunk in chunks:
            chunk["author"] = author
            chunk["user_id"] = ""
            chunk["source_url"] = f"file://{pdf_path}"
        
        logging.info(f"Created {len(chunks)} chunks from PDF")
        
        return chunks


class UniversalContentDetector:
    """Detects content patterns that work across all websites"""
    
    # Universal patterns for different content types
    ARTICLE_PATTERNS = [
        'article', '[role="article"]', '[role="main"]',
        '.post', '.article', '.content', '.entry',
        'main', '.main-content', '.post-content',
        # Modern framework patterns
        '[class*="post"]', '[class*="article"]', '[class*="blog"]',
        '[class*="card"]', '[class*="item"]', '[class*="entry"]'
    ]
    
    TITLE_PATTERNS = [
        'h1', 'h2', 'h3', '.title', '.post-title', '.entry-title',
        '[role="heading"]', '.headline', 'title',
        # Modern framework patterns
        '[class*="title"]', '[class*="heading"]', '[class*="headline"]'
    ]
    
    NAVIGATION_PATTERNS = [
        '.pagination', '.pager', '.nav', 'nav',
        '[rel="next"]', '[rel="prev"]', '.next', '.previous'
    ]
    
    AUTHOR_PATTERNS = [
        '.author', '.byline', '.by', '[rel="author"]',
        '.post-author', '.entry-author', '.writer'
    ]
    
    def __init__(self):
        self.content_cache = {}
    
    def find_article_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find links to articles using universal patterns"""
        links = set()
        
        # Look for links in common article list patterns
        for pattern in [
            'a[href*="/blog/"]', 'a[href*="/post/"]', 'a[href*="/article/"]',
            'a[href*="/20"]',  # Year-based URLs (2023, 2024, etc.)
            '.post-list a', '.article-list a', '.blog-list a',
            'article a', '.entry a', '.post a'
        ]:
            try:
                elements = soup.select(pattern)
                for element in elements:
                    href = element.get('href')
                    if href:
                        full_url = urljoin(base_url, href)
                        if self._is_likely_article_url(full_url):
                            links.add(full_url)
            except:
                continue
        
        # Also look for any links that seem article-like
        # Method 1: Comprehensive link discovery - find ALL links that could be articles
        self._find_all_potential_article_links(soup, base_url, links)
        
        # Method 4: Modern framework detection - look for clickable elements with article-like content
        self._find_modern_article_elements(soup, base_url, links)
        
        # Method 5: Aggressive detection for article previews/cards
        self._find_article_cards_aggressive(soup, base_url, links)
        
        # Method 6: Scrapy-inspired comprehensive link analysis
        self._find_links_with_scrapy_patterns(soup, base_url, links)
        
        # Method 7: Modern SPA pattern detection for clickable containers
        self._find_spa_clickable_articles(soup, base_url, links)
        
        return list(links)
    
    def _find_all_potential_article_links(self, soup: BeautifulSoup, base_url: str, links: set):
        """Comprehensive discovery of all potential article links on the page"""
        
        # Find ALL links on the page
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            if not href:
                continue
                
            full_url = urljoin(base_url, href)
            
            # Skip if it's the same as base URL or clearly not an article
            if full_url == base_url or full_url == base_url.rstrip('/'):
                continue
            
            # Get link text to help with filtering
            link_text = link.get_text(strip=True)
            
            # Enhanced filtering inspired by Scrapy patterns
            if self._is_likely_article_url(full_url) and self._has_article_context(link, link_text):
                links.add(full_url)
    
    def _find_modern_article_elements(self, soup: BeautifulSoup, base_url: str, links: set):
        """Find articles in modern JavaScript frameworks by looking for clickable content blocks"""
        
        # Look for elements that might be article previews/cards
        potential_articles = []
        
        # Find elements with click handlers or hover effects (common in modern frameworks)
        clickable_selectors = [
            '[style*="cursor:pointer"]',
            '[onclick]',
            'div[class*="hover"]',
            'div[class*="card"]',
            'div[class*="item"]',
            'div[class*="post"]',
            'div[class*="article"]'
        ]
        
        for selector in clickable_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    if self._looks_like_article_preview(element):
                        potential_articles.append(element)
            except:
                continue
        
        # Also look for divs that contain both title-like and description-like text
        all_divs = soup.find_all('div')
        for div in all_divs:
            if self._looks_like_article_preview(div):
                potential_articles.append(div)
        
        # Extract URLs from potential articles
        for article_element in potential_articles:
            # Try to find a link within the element
            link = article_element.find('a', href=True)
            if link:
                full_url = urljoin(base_url, link['href'])
                if self._is_likely_article_url(full_url):
                    links.add(full_url)
            else:
                # For elements without direct links, try to construct URL from text content
                title_element = self._find_title_in_element(article_element)
                if title_element:
                    # This is a heuristic - many modern sites have predictable URL patterns
                    title_text = title_element.get_text(strip=True)
                    potential_url = self._construct_article_url(base_url, title_text)
                    if potential_url:
                        links.add(potential_url)
    
    def _looks_like_article_preview(self, element) -> bool:
        """Check if an element looks like an article preview/card"""
        text = element.get_text(strip=True)
        
        # Must have substantial text
        if len(text) < 50:
            return False
        
        # Look for title-like elements (headings)
        has_title = bool(element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']))
        
        # Look for title-like text patterns in class names
        class_text = ' '.join(element.get('class', [])).lower()
        has_title_class = any(pattern in class_text for pattern in ['title', 'heading', 'headline'])
        
        # Look for description-like text (longer paragraphs)
        paragraphs = element.find_all(['p', 'div'])
        has_description = any(len(p.get_text(strip=True)) > 30 for p in paragraphs)
        
        # Check for date-like text
        has_date = bool(re.search(r'\b(20\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', text))
        
        # Must have at least title + description, or title + date
        return (has_title or has_title_class) and (has_description or has_date)
    
    def _find_title_in_element(self, element):
        """Find the title element within an article preview"""
        # Look for heading tags first
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            title = element.find(tag)
            if title:
                return title
        
        # Look for elements with title-like classes
        for pattern in ['title', 'heading', 'headline']:
            title = element.find(class_=lambda x: x and pattern in x.lower())
            if title:
                return title
        
        return None
    
    def _find_article_cards_aggressive(self, soup: BeautifulSoup, base_url: str, links: set):
        """Aggressively find all article cards/previews on the page"""
        
        # Look for all text blocks that look like article titles
        potential_titles = []
        
        # Find all headings that could be article titles
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            headings = soup.find_all(tag)
            for heading in headings:
                text = heading.get_text(strip=True)
                # Skip if too short or looks like navigation
                if len(text) < 5 or len(text) > 300:
                    continue
                if self._looks_like_article_title(text):
                    potential_titles.append((heading, text))
        
        # Also look for other elements that might contain article titles
        # Look for divs/spans with title-like classes
        for element in soup.find_all(['div', 'span', 'p'], class_=True):
            class_names = ' '.join(element.get('class', [])).lower()
            if any(indicator in class_names for indicator in ['title', 'heading', 'headline', 'name']):
                text = element.get_text(strip=True)
                if 5 <= len(text) <= 300 and self._looks_like_article_title(text):
                    potential_titles.append((element, text))
        
        # For each potential title, try to find or construct an article URL
        for heading_element, title_text in potential_titles:
            # First try to find a link near this heading
            article_url = self._find_link_near_element(heading_element, base_url)
            
            if not article_url:
                # Try to construct URL from title
                article_url = self._construct_article_url(base_url, title_text)
            
            if article_url and article_url not in links:
                # Verify this looks like a real article URL
                if self._is_likely_article_url(article_url):
                    links.add(article_url)
    
    def _looks_like_article_title(self, text: str) -> bool:
        """Check if text looks like an article title"""
        # Skip generic/navigation text
        generic_terms = [
            'home', 'about', 'contact', 'blog', 'news', 'menu', 'search',
            'login', 'register', 'subscribe', 'follow', 'share', 'read more',
            'see all', 'view all', 'more', 'next', 'previous', 'back', 'close'
        ]
        
        text_lower = text.lower()
        if any(term == text_lower or term in text_lower for term in generic_terms):
            return False
        
        # Good indicators of article titles
        # - Contains common article words
        article_indicators = [
            'how to', 'why', 'what is', 'guide', 'tips', 'best', 'top',
            'introduction', 'overview', 'analysis', 'review', 'case study',
            'deep dive', 'understanding', 'exploring', 'building', 'creating',
            'implementing', 'optimizing', 'improving', 'mastering', 'learning'
        ]
        
        # - Has reasonable length and structure
        word_count = len(text.split())
        has_good_length = 2 <= word_count <= 25
        
        # - Contains article-like words or has good structure
        has_article_words = any(indicator in text_lower for indicator in article_indicators)
        
        # - Looks like a proper title (title case, contains meaningful words)
        has_title_structure = any(word[0].isupper() for word in text.split() if len(word) > 2)
        
        return has_good_length and (has_article_words or has_title_structure or word_count >= 3)
    
    def _find_link_near_element(self, element, base_url: str) -> Optional[str]:
        """Find a link near the given element"""
        # Check the element itself
        if element.name == 'a' and element.get('href'):
            return urljoin(base_url, element['href'])
        
        link = element.find('a', href=True)
        if link:
            return urljoin(base_url, link['href'])
        
        # Check parent elements more thoroughly
        parent = element.parent
        for _ in range(5):  # Check up to 5 levels up
            if not parent:
                break
            
            # Check if parent itself is a link
            if parent.name == 'a' and parent.get('href'):
                return urljoin(base_url, parent['href'])
            
            # Check for links within parent
            link = parent.find('a', href=True)
            if link:
                return urljoin(base_url, link['href'])
            
            parent = parent.parent
        
        # Check sibling elements more thoroughly
        if element.parent:
            # Look at all siblings
            for sibling in element.parent.find_all():
                if sibling == element:
                    continue
                if sibling.name == 'a' and sibling.get('href'):
                    return urljoin(base_url, sibling['href'])
                link = sibling.find('a', href=True)
                if link:
                    return urljoin(base_url, link['href'])
        
        # Look for clickable containers (modern frameworks)
        container = element.parent
        for _ in range(3):
            if not container:
                break
            
            # Check if container has click handlers or looks clickable
            container_classes = ' '.join(container.get('class', [])).lower()
            if any(term in container_classes for term in ['card', 'item', 'post', 'article']):
                # Look for any link within this container
                link = container.find('a', href=True)
                if link:
                    return urljoin(base_url, link['href'])
            
            container = container.parent
        
        return None
    
    def _find_links_with_scrapy_patterns(self, soup: BeautifulSoup, base_url: str, links: set):
        """Scrapy-inspired comprehensive link analysis using multiple selector strategies"""
        
        # Strategy 1: Multiple tag types (like Scrapy's flexible tag scanning)
        link_tags = ['a', 'area']  # Scrapy default
        link_attrs = ['href']      # Scrapy default
        
        for tag_name in link_tags:
            for attr_name in link_attrs:
                elements = soup.find_all(tag_name, **{attr_name: True})
                for element in elements:
                    href = element.get(attr_name)
                    if href:
                        full_url = urljoin(base_url, href)
                        link_text = element.get_text(strip=True)
                        
                        # Apply Scrapy-style filtering
                        if (self._scrapy_style_link_filter(full_url, link_text, element, base_url) and
                            full_url not in links):
                            links.add(full_url)
        
        # Strategy 2: XPath-style content area detection
        content_selectors = [
            'main a[href]', 'article a[href]', '[role="main"] a[href]',
            '.content a[href]', '.posts a[href]', '.blog a[href]', 
            '.articles a[href]', '.post-list a[href]', '.entry a[href]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    link_text = element.get_text(strip=True)
                    
                    if (self._scrapy_style_link_filter(full_url, link_text, element, base_url) and
                        full_url not in links):
                        links.add(full_url)
        
        # Strategy 3: Modern framework patterns (clickable cards)
        modern_patterns = [
            '[onclick] a[href]', '[style*="cursor"] a[href]',
            '.card a[href]', '.item a[href]', '.post a[href]',
            '[class*="card"] a[href]', '[class*="item"] a[href]',
            '[class*="post"] a[href]', '[class*="article"] a[href]'
        ]
        
        for pattern in modern_patterns:
            elements = soup.select(pattern)
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(base_url, href)
                    link_text = element.get_text(strip=True)
                    
                    if (self._scrapy_style_link_filter(full_url, link_text, element, base_url) and
                        full_url not in links):
                        links.add(full_url)
    
    def _construct_article_url(self, base_url: str, title: str) -> Optional[str]:
        """Try to construct article URL from title (heuristic)"""
        # This is a fallback heuristic - many sites have predictable patterns
        # Only use for sites that seem to follow common patterns
        
        # Skip date-only titles (these are usually not article titles)
        if re.match(r'^[a-zA-Z]+ \d{1,2}, \d{4}$', title.strip()):
            return None
        
        # Clean title for URL
        clean_title = re.sub(r'[^\w\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        clean_title = re.sub(r'-+', '-', clean_title).strip('-')
        
        # Determine the right pattern based on the base URL
        base_clean = base_url.rstrip('/')
        
        # If we're already on a blog page, don't add /blog again
        if base_clean.endswith('/blog'):
            patterns = [
                f"{base_clean}/{clean_title}",
                f"{base_clean.replace('/blog', '')}/blog/{clean_title}",
                f"{base_clean.replace('/blog', '')}/post/{clean_title}"
            ]
        else:
            patterns = [
                f"{base_clean}/blog/{clean_title}",
                f"{base_clean}/post/{clean_title}",
                f"{base_clean}/article/{clean_title}",
                f"{base_clean}/{clean_title}"
            ]
        
        # Return the most likely pattern
        return patterns[0]
    
    def _is_likely_article_url(self, url: str) -> bool:
        """Check if URL looks like an article"""
        url_lower = url.lower()
        
        # Common article URL patterns
        article_indicators = [
            '/blog/', '/post/', '/article/', '/story/', '/guide/',
            '/tutorial/', '/how-to/', '/tips/', '/news/', '/insights/',
            '/p-', '/post-', '/article-'  # Modern platform patterns
        ]
        
        # Date patterns
        date_pattern = re.search(r'/20\d{2}/', url)
        
        # Modern patterns - URLs with IDs or slugs
        modern_patterns = [
            re.search(r'/p-\d+', url),  # Substack-style
            re.search(r'[a-z]+-[a-z]+-[a-z]+', url),  # Slug patterns
            re.search(r'/\d+/', url)  # Numeric IDs
        ]
        
        # Avoid non-article URLs - enhanced with Scrapy-inspired patterns
        avoid_patterns = [
            '/tag/', '/category/', '/author/', '/page/', '/search/',
            '/login/', '/register/', '/contact/', '/about/', '/api/',
            '.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.xml',
            '/feed', '/rss', '/sitemap', '/book', '/demo', '/pricing',
            '/trial', '/signup', '/calendar', '/schedule', 'cal.com',
            'calendly.com', '/meeting', '/appointment', '/call', '/intro',
            '/consultation', '/support', '/help', '/faq', '/terms',
            '/privacy', '/policy', '/legal', '/careers', '/jobs'
        ]
        
        has_article_indicator = any(indicator in url_lower for indicator in article_indicators)
        has_date = bool(date_pattern)
        has_modern_pattern = any(bool(pattern) for pattern in modern_patterns)
        has_avoid_pattern = any(pattern in url_lower for pattern in avoid_patterns)
        
        # Must have some positive indicator and no negative indicators
        return (has_article_indicator or has_date or has_modern_pattern) and not has_avoid_pattern
    
    def _has_article_context(self, link_element, link_text: str) -> bool:
        """Enhanced article context detection using Scrapy-inspired patterns"""
        
        # Skip if text suggests it's not an article
        non_article_text = [
            'book', 'demo', 'call', 'meeting', 'schedule', 'calendar',
            'contact', 'about', 'login', 'signup', 'register', 'subscribe',
            'download', 'pricing', 'trial', 'free', 'buy', 'purchase'
        ]
        
        text_lower = link_text.lower()
        if any(term in text_lower for term in non_article_text):
            return False
        
        # Look for article-like indicators in the link context
        # Check parent elements for article-like structure
        parent = link_element.parent
        for _ in range(3):  # Check up to 3 levels up
            if not parent:
                break
            
            parent_classes = ' '.join(parent.get('class', [])).lower()
            parent_text = parent.get_text(strip=True).lower()
            
            # Positive indicators for articles
            article_indicators = [
                'post', 'article', 'blog', 'entry', 'content', 'story',
                'news', 'card', 'item', 'link', 'title', 'heading'
            ]
            
            if any(indicator in parent_classes or indicator in parent_text for indicator in article_indicators):
                # Additional check: look for date patterns or author info
                if self._has_article_metadata(parent):
                    return True
            
            parent = parent.parent
        
        # Fallback: if the link text looks like an article title
        return self._looks_like_article_title(link_text)
    
    def _has_article_metadata(self, element) -> bool:
        """Check if element contains article metadata like dates or authors"""
        text = element.get_text(strip=True)
        
        # Look for date patterns
        date_patterns = [
            r'\b\d{4}\b',  # Year
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',  # Month names
            r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',  # Date formats
            r'\b\d{1,2}\s+(minute|hour|day|week|month|year)s?\s+read\b'  # "5 minute read"
        ]
        
        for pattern in date_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Look for author indicators
        author_patterns = [
            r'\bby\s+\w+',
            r'\bauthor',
            r'\bwritten\s+by',
            r'\b\w+\s+\w+\s*·\s*'  # Name with separator
        ]
        
        for pattern in author_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _scrapy_style_link_filter(self, url: str, link_text: str, link_element, base_url: str) -> bool:
        """Scrapy-inspired comprehensive link filtering"""
        
        # Basic URL filtering
        if not self._is_likely_article_url(url):
            return False
        
        # Link text filtering (like Scrapy's restrict_text)
        if not self._is_meaningful_link_text(link_text):
            return False
        
        # Context filtering
        if not self._has_article_context(link_element, link_text):
            return False
        
        # Domain filtering (ensure it's from the same domain or allowed)
        parsed_url = urlparse(url)
        base_parsed = urlparse(base_url)
        
        # Allow same domain or common subdomains
        if parsed_url.netloc != base_parsed.netloc:
            # Allow common subdomains like blog.example.com
            allowed_subdomains = ['blog', 'www', 'news', 'articles']
            if not any(parsed_url.netloc.startswith(f"{sub}.{base_parsed.netloc}") 
                      for sub in allowed_subdomains):
                return False
        
        return True
    
    def _is_meaningful_link_text(self, text: str) -> bool:
        """Check if link text is meaningful for an article"""
        if not text or len(text.strip()) < 5:
            return False
        
        # Avoid generic link text
        generic_text = [
            'read more', 'continue reading', 'click here', 'more info',
            'learn more', 'see more', 'view more', 'full article',
            'read full', 'continue', 'more', 'here', 'link'
        ]
        
        text_lower = text.lower().strip()
        if text_lower in generic_text:
            return False
        
        # Prefer descriptive titles
        return len(text.split()) >= 2  # At least 2 words
    
    def _find_spa_clickable_articles(self, soup: BeautifulSoup, base_url: str, links: set):
        """Find articles in SPAs by looking for actual links in rendered HTML"""
        
        # Strategy 1: Look for actual <a> tags with href attributes first
        # This is the most reliable method for SPAs after JavaScript execution
        actual_links = soup.find_all('a', href=True)
        for link in actual_links:
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                
                # Check if this looks like a blog article URL
                if self._is_likely_article_url(full_url) and full_url not in links:
                    # Additional validation - check if the link has meaningful text
                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) > 5:  # Has meaningful text
                        links.add(full_url)
                        logging.info(f"Found actual article link: {full_url} | {link_text[:50]}...")
        
        # Strategy 2: Look for clickable containers (fallback for complex SPAs)
        # Only use this if we didn't find many actual links
        if len([l for l in links if base_url in l]) < 3:  # If we found fewer than 3 articles
            logging.info("Few actual links found, trying clickable container fallback...")
            
            # Find clickable containers with cursor:pointer
            clickable_containers = soup.find_all(attrs={'style': lambda x: x and 'cursor:pointer' in x})
            
            # Also look for containers with click handlers or interactive classes
            interactive_containers = soup.find_all(attrs={
                'class': lambda x: x and any(term in ' '.join(x).lower() 
                                           for term in ['clickable', 'interactive', 'card', 'item'])
            })
            
            all_containers = clickable_containers + interactive_containers
            logging.info(f"Found {len(all_containers)} potentially clickable containers")
            
            for container in all_containers:
                # Try to find an article title within this container
                title_element = self._find_article_title_in_container(container)
                
                if title_element:
                    title_text = title_element
                    
                    # Skip if we already have this title or it's not article-like
                    if not self._looks_like_article_title(title_text):
                        continue
                    
                    # Try to construct the article URL from the title
                    article_url = self._construct_spa_article_url(base_url, title_text)
                    
                    if article_url and article_url not in links:
                        # Verify this looks like a real article URL
                        if self._is_likely_article_url(article_url):
                            links.add(article_url)
                            logging.info(f"Constructed article URL: {article_url} | {title_text[:50]}...")
        
        logging.info(f"SPA detection found {len([l for l in links if base_url in l])} total articles")
    
    def _find_article_title_in_container(self, container):
        """Extract article title from a clickable container (for SPAs)"""
        
        # Strategy 1: Look for explicit title elements first
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '[class*="title"]', '[class*="heading"]', '[class*="headline"]',
            '.title', '.heading', '.headline'
        ]
        
        for selector in title_selectors:
            title_elem = container.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if self._looks_like_article_title(title):
                    return title
        
        # Strategy 2: Parse mixed content more intelligently
        full_text = container.get_text(strip=True)
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        
        # Remove common non-title content
        filtered_lines = []
        for line in lines:
            line_lower = line.lower()
            
            # Skip dates, categories, and common prefixes
            if re.match(r'^[a-zA-Z]+ \d{1,2}, \d{4}$', line):  # Date format
                continue
            if line_lower in ['product', 'blog', 'news', 'article', 'post']:  # Categories
                continue
            if line.endswith('Read more') or line.endswith('...'):  # Truncated content
                # Extract the part before "Read more" or "..."
                clean_line = re.sub(r'(Read more|\.\.\.|\.\.\.)$', '', line).strip()
                if clean_line and len(clean_line) > 10:
                    filtered_lines.append(clean_line)
                continue
            if len(line) < 10:  # Too short to be a title
                continue
            if len(line) > 200:  # Too long, likely description
                # Try to extract title from the beginning
                sentences = re.split(r'[.!?]', line)
                if sentences and len(sentences[0]) > 10 and len(sentences[0]) < 100:
                    filtered_lines.append(sentences[0].strip())
                continue
                
            filtered_lines.append(line)
        
        # Strategy 3: Find the most title-like line
        for line in filtered_lines:
            # Look for title patterns
            if self._looks_like_article_title(line):
                # Additional cleaning for mixed content
                # Remove category prefixes like "ProductJuly 12, 2024"
                cleaned = re.sub(r'^(Product|Blog|News|Article)\s*[A-Z][a-z]+ \d{1,2}, \d{4}\s*', '', line)
                if cleaned and len(cleaned) > 10:
                    return cleaned.strip()
                return line.strip()
        
        # Strategy 4: Fallback - use the first substantial line
        if filtered_lines:
            return filtered_lines[0]
        
        # Strategy 5: Last resort - use first 100 chars of full text
        if len(full_text) > 10:
            truncated = full_text[:100].strip()
            # Clean up common endings
            truncated = re.sub(r'(Read more|\.\.\.|\.\.\.).*$', '', truncated).strip()
            if len(truncated) > 10:
                return truncated
                
        return None
    
    def _construct_spa_article_url(self, base_url: str, title: str) -> Optional[str]:
        """Construct article URL for SPA applications"""
        
        # Clean title for URL (more aggressive cleaning for SPAs)
        clean_title = title.lower()
        
        # Remove common words and punctuation
        clean_title = re.sub(r'[^\w\s-]', '', clean_title)
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        clean_title = re.sub(r'-+', '-', clean_title).strip('-')
        
        # Remove common stop words that often don't appear in URLs
        stop_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = clean_title.split('-')
        filtered_words = [word for word in words if word not in stop_words or len(words) <= 3]
        clean_title = '-'.join(filtered_words)
        
        # Construct URL based on the base URL pattern
        base_clean = base_url.rstrip('/')
        
        # For blog URLs, the pattern is usually /blog/article-slug
        if '/blog' in base_clean:
            return f"{base_clean}/{clean_title}"
        else:
            return f"{base_clean}/blog/{clean_title}"

    def extract_main_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main content using universal patterns"""
        
        # Try different content extraction strategies
        strategies = [
            self._extract_by_semantic_tags,
            self._extract_by_common_classes,
            self._extract_by_content_density,
            self._extract_by_text_length
        ]
        
        for strategy in strategies:
            content = strategy(soup)
            if content and self._is_quality_content(content):
                return content
        
        return None
    
    def _extract_by_semantic_tags(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract using semantic HTML tags"""
        for tag in ['article', 'main', '[role="main"]']:
            try:
                element = soup.select_one(tag)
                if element:
                    return self._element_to_markdown(element)
            except:
                continue
        return None
    
    def _extract_by_common_classes(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract using common content class patterns"""
        patterns = [
            '.post-content', '.entry-content', '.article-content',
            '.content', '.main-content', '.post-body', '.entry-body'
        ]
        
        for pattern in patterns:
            try:
                element = soup.select_one(pattern)
                if element:
                    return self._element_to_markdown(element)
            except:
                continue
        return None
    
    def _extract_by_content_density(self, soup: BeautifulSoup) -> Optional[str]:
        """Find element with highest content density"""
        candidates = []
        
        # Look at all divs and sections
        for element in soup.find_all(['div', 'section', 'article']):
            if not element.get_text(strip=True):
                continue
            
            text_length = len(element.get_text())
            html_length = len(str(element))
            
            # Skip if too much HTML vs text (likely navigation/ads)
            if html_length > 0 and text_length / html_length < 0.1:
                continue
            
            # Skip if too short
            if text_length < 200:
                continue
            
            candidates.append((element, text_length))
        
        if candidates:
            # Return the element with most text
            best_element = max(candidates, key=lambda x: x[1])[0]
            return self._element_to_markdown(best_element)
        
        return None
    
    def _extract_by_text_length(self, soup: BeautifulSoup) -> Optional[str]:
        """Fallback: find any element with substantial text"""
        for element in soup.find_all(['div', 'section', 'article', 'main']):
            text = element.get_text(strip=True)
            if len(text) > 500:  # Substantial content
                return self._element_to_markdown(element)
        return None
    
    def _element_to_markdown(self, element) -> str:
        """Convert HTML element to clean markdown"""
        try:
            # Clean up the HTML first
            self._clean_element(element)
            html = str(element)
            markdown = markdownify(html, heading_style="ATX")
            return self._clean_markdown(markdown)
        except:
            # Fallback to plain text
            return element.get_text(separator='\n', strip=True)
    
    def _clean_element(self, element):
        """Remove unwanted elements from content"""
        # Remove common non-content elements
        for selector in ['.ad', '.advertisement', '.social', '.share', '.related', '.comments']:
            try:
                for el in element.select(selector):
                    el.decompose()
            except:
                continue
    
    def _clean_markdown(self, markdown: str) -> str:
        """Clean up markdown content"""
        # Remove excessive whitespace
        markdown = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown)
        # Remove empty links
        markdown = re.sub(r'\[\]\([^)]*\)', '', markdown)
        return markdown.strip()
    
    def _is_quality_content(self, content: str) -> bool:
        """Check if content meets quality standards"""
        if not content or len(content.strip()) < 100:
            return False
        
        # Check for reasonable text-to-markup ratio
        text_content = re.sub(r'[#*\[\]()_`-]', '', content)
        ratio = len(text_content) / len(content)
        
        return ratio > 0.5  # At least 50% actual text
    
    def extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title using universal patterns"""
        # Try different title extraction methods in order of preference
        strategies = [
            # Look for main content headings first (most specific)
            lambda: soup.select_one('main h1, article h1, [role="main"] h1'),
            lambda: soup.select_one('main h2, article h2, [role="main"] h2'),
            
            # Look for the largest/most prominent heading
            lambda: self._find_main_heading(soup),
            
            # Look for title classes within content areas
            lambda: soup.select_one('main [class*="title"], article [class*="title"]'),
            
            # Look for any prominent heading
            lambda: soup.find('h1'),
            lambda: soup.find('h2'),
            
            # Look for title classes anywhere
            lambda: soup.select_one('.title, .post-title, .entry-title'),
            
            # Meta tags
            lambda: soup.find(attrs={'property': 'og:title'}),
            
            # Fallback to page title (but clean it up)
            lambda: soup.find('title')
        ]
        
        for strategy in strategies:
            try:
                element = strategy()
                if element:
                    title = element.get_text(strip=True) or element.get('content', '')
                    if title and len(title) > 3:
                        # Skip generic titles
                        if self._is_generic_title(title):
                            continue
                        return title
            except:
                continue
        
        return "Untitled"
    
    def _find_main_heading(self, soup: BeautifulSoup):
        """Find the most prominent heading on the page"""
        # Look for headings and score them by prominence
        headings = []
        
        for tag in ['h1', 'h2', 'h3']:
            elements = soup.find_all(tag)
            for element in elements:
                text = element.get_text(strip=True)
                if len(text) > 10:  # Substantial heading
                    # Score based on tag importance and text length
                    score = (4 - int(tag[1])) * 10 + min(len(text), 100)
                    headings.append((score, element))
        
        if headings:
            # Return the highest scoring heading
            return max(headings, key=lambda x: x[0])[1]
        
        return None
    
    def _is_generic_title(self, title: str) -> bool:
        """Check if title is too generic to be useful"""
        generic_titles = [
            'blog', 'home', 'index', 'main', 'page', 'article', 'post',
            'news', 'updates', 'content', 'site', 'website'
        ]
        return title.lower().strip() in generic_titles
    
    def extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author using universal patterns"""
        strategies = [
            # Traditional patterns
            lambda: soup.select_one('.author, .byline, .by'),
            lambda: soup.find(attrs={'rel': 'author'}),
            lambda: soup.find(attrs={'property': 'article:author'}),
            lambda: soup.find(attrs={'name': 'author'}),
            # Modern patterns - look for text containing author indicators
            lambda: soup.find(string=re.compile(r'\w+\s+\w+\s*·\s*(Co-Founder|Author|Writer|Editor|CEO|CTO)', re.I)),
            lambda: soup.find(string=re.compile(r'By\s+\w+\s+\w+', re.I)),
            lambda: soup.find(string=re.compile(r'\w+\s+\w+\s*-\s*(Co-Founder|Author|Writer|Editor)', re.I)),
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    if hasattr(result, 'get_text'):
                        # It's an element
                        author = result.get_text(strip=True) or result.get('content', '')
                    else:
                        # It's a text node, get the parent element's text
                        author = result.strip()
                        # Clean up the author string - extract just the name part
                        if '·' in author:
                            author = author.split('·')[0].strip()
                        elif '-' in author and any(word in author for word in ['Co-Founder', 'Author', 'Writer', 'Editor', 'CEO', 'CTO']):
                            author = author.split('-')[0].strip()
                        if author.lower().startswith('by '):
                            author = author[3:].strip()
                    
                    if author and len(author) > 2 and not any(skip in author.lower() for skip in ['@', 'http', 'www', 'blog', 'post']):
                        return author
            except Exception as e:
                continue
        
        return ""


class UniversalScraper:
    """Universal scraper that works on any website"""
    
    def __init__(self, base_url: str, config: Dict[str, Any] = None):
        self.base_url = base_url
        self.config = config or {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.driver = None
        self.detector = UniversalContentDetector()
        self.scraped_urls = set()
    
    def scrape(self) -> List[ContentItem]:
        """Main scraping method"""
        logger.info(f"Starting universal scrape of {self.base_url}")
        
        items = []
        
        # First, analyze the main page
        soup = self._fetch_page(self.base_url)
        if not soup:
            logger.error(f"Could not fetch main page: {self.base_url}")
            return items
        
        # Detect website architecture
        architecture = WebsiteArchitectureDetector.detect_architecture(soup, self.base_url)
        logger.info(f"Detected architecture: {architecture['strategy']}")
        
        # If we need JavaScript, refetch with browser
        if architecture['needs_js']:
            logger.info("Refetching with JavaScript support...")
            soup = self._fetch_page(self.base_url, use_js=True)
            if not soup:
                logger.error("Could not fetch page with JavaScript (Selenium failed)")
                logger.info("Attempting Playwright as fallback...")
                soup = self._fetch_with_playwright(self.base_url)
                if not soup:
                    logger.error("Playwright also failed, using requests fallback...")
                    fallback_links = self._fetch_with_requests_fallback(self.base_url)
                    if fallback_links:
                        for link_info in fallback_links:
                            item = ContentItem(
                                title=link_info['title'],
                                content=f"Article preview: {link_info['title']} (Browser-based scraping not available in this environment)",
                                source_url=link_info['url']
                            )
                            items.append(item)
                        logger.info(f"Fallback found {len(items)} articles")
                    return items
                else:
                    logger.info("✅ Playwright successfully fetched the page!")
        
        # Find all article links using traditional pattern matching
        article_links = self.detector.find_article_links(soup, self.base_url)
        logger.info(f"Found {len(article_links)} potential articles using pattern matching")
        
        # Enhanced SPA detection: If we're dealing with a modern SPA and should use click discovery,
        # try the advanced approach to get real URLs instead of constructed ones
        if (architecture['needs_js'] and 
            self._should_use_click_discovery()):
            
            logger.info("Few articles found on detected SPA - attempting click discovery...")
            try:
                click_discovered_articles = self._scrape_with_click_discovery()
                if len(click_discovered_articles) > 0:
                    logger.info(f"✅ Click discovery found {len(click_discovered_articles)} articles with real URLs!")
                    # Use the click discovery results since they have correct URLs
                    return click_discovered_articles
                else:
                    logger.info("Click discovery found no articles, using pattern matching results")
            except Exception as e:
                logger.warning(f"Click discovery failed: {e}, falling back to pattern matching")
        
        # Scrape each article using traditional approach
        max_articles = self.config.get('max_articles', 50)
        total_articles = min(len(article_links), max_articles)
        progress_callback = self.config.get('progress_callback')
        
        for i, url in enumerate(article_links[:max_articles]):
            if url in self.scraped_urls:
                continue
            
            # Send progress update if callback provided
            if progress_callback:
                progress_callback(i + 1, total_articles, url)
            
            logger.info(f"Scraping article {i+1}/{total_articles}: {url}")
            item = self._scrape_article(url, architecture['needs_js'])
            if item:
                items.append(item)
                self.scraped_urls.add(url)
            
            # Be respectful
            time.sleep(self.config.get('delay', 1))
        
        logger.info(f"Successfully scraped {len(items)} articles")
        return items
    
    def _should_use_click_discovery(self) -> bool:
        """Check if we should attempt click discovery based on the URL pattern"""
        # Enable click discovery for known modern blog platforms
        modern_patterns = [
            'quill.co/blog',
            'substack.com',
            'medium.com',
            'ghost.org',
            'notion.site'
        ]
        return any(pattern in self.base_url.lower() for pattern in modern_patterns)
    
    def _scrape_with_click_discovery(self) -> List[ContentItem]:
        """Use Selenium-based click discovery to find articles on modern SPAs"""
        if not self.driver:
            self._init_driver()
        
        if not self.driver:
            logger.error("No WebDriver available for click discovery")
            return []
        
        items = []
        max_articles = self.config.get('max_articles', 50)
        
        try:
            logger.info("🔍 Starting click discovery...")
            self.driver.get(self.base_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Additional wait for dynamic content
            
            # Scroll to load all content
            logger.info("📜 Scrolling to load all content...")
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 5
            
            while scroll_attempts < max_scrolls:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                scroll_attempts += 1
            
            # Find clickable containers with titles
            logger.info("🎯 Looking for clickable article containers...")
            clickable_containers = self.driver.find_elements(By.CSS_SELECTOR, '[style*="cursor:pointer"]')
            
            discovered_urls = []
            processed_titles = set()
            
            # First, collect all titles without clicking
            all_titles = []
            for container in clickable_containers:
                try:
                    h1_elements = container.find_elements(By.TAG_NAME, "h1")
                    if h1_elements:
                        title = h1_elements[0].text.strip()
                        if (title and len(title) >= 15 and 
                            title not in ['Blog', 'Product', 'Docs', 'Home'] and
                            title not in processed_titles):
                            all_titles.append(title)
                            processed_titles.add(title)
                except:
                    continue
            
            logger.info(f"Found {len(all_titles)} potential articles to test")
            
            # Now test each title by finding and clicking fresh elements
            for idx, title in enumerate(all_titles):
                if len(discovered_urls) >= max_articles:
                    break
                    
                logger.info(f"🔍 Testing article {idx+1}/{len(all_titles)}: {title[:50]}...")
                
                try:
                    # Find the container with this specific title (fresh query)
                    containers_with_title = self.driver.find_elements(
                        By.XPATH, 
                        f'//div[contains(@style, "cursor:pointer")]//h1[contains(text(), "{title[:30]}")]/ancestor::div[contains(@style, "cursor:pointer")]'
                    )
                    
                    if not containers_with_title:
                        logger.info(f"  ❌ Could not find container for: {title[:30]}...")
                        continue
                    
                    container = containers_with_title[0]
                    current_url = self.driver.current_url
                    
                    # Click and wait for navigation
                    self.driver.execute_script("arguments[0].click();", container)
                    
                    # Wait for URL change
                    WebDriverWait(self.driver, 5).until(
                        lambda driver: driver.current_url != current_url
                    )
                    
                    new_url = self.driver.current_url
                    if new_url != current_url and new_url not in [item['url'] for item in discovered_urls]:
                        logger.info(f"  ✅ Discovered: {new_url}")
                        discovered_urls.append({
                            'title': title,
                            'url': new_url
                        })
                        
                        # Navigate back
                        self.driver.get(self.base_url)
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)
                        
                        # Re-scroll to ensure all content is loaded
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1)
                        
                    else:
                        logger.info(f"  ❌ No navigation or duplicate URL")
                        
                except Exception as e:
                    logger.warning(f"  ❌ Error testing '{title[:30]}...': {str(e)[:50]}...")
                    # Try to navigate back if needed
                    try:
                        if self.driver.current_url != self.base_url:
                            self.driver.get(self.base_url)
                            time.sleep(2)
                    except:
                        pass
                    continue
            
            logger.info(f"🎯 Discovered {len(discovered_urls)} articles through click discovery")
            
            # Now scrape each discovered article
            progress_callback = self.config.get('progress_callback')
            for i, article_info in enumerate(discovered_urls, 1):
                url = article_info['url']
                
                # Send progress update if callback provided
                if progress_callback:
                    progress_callback(i, len(discovered_urls), url)
                
                logger.info(f"📖 Scraping discovered article {i}/{len(discovered_urls)}: {url}")
                
                try:
                    self.driver.get(url)
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    
                    # Get page source and extract content
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    content = self.detector.extract_main_content(soup)
                    
                    if content and len(content.strip()) >= 100:
                        title = self.detector.extract_title(soup) or article_info['title']
                        author = self.detector.extract_author(soup)
                        
                        item = ContentItem(
                            title=title,
                            content=content,
                            content_type="blog",
                            source_url=url,
                            author=author,
                            user_id=""
                        )
                        items.append(item)
                        logger.info(f"  ✅ Success: {title} ({len(content)} chars)")
                    else:
                        logger.warning(f"  ❌ No content found for {url}")
                        
                except Exception as e:
                    logger.error(f"  ❌ Error scraping {url}: {e}")
                
                time.sleep(self.config.get('delay', 1))
            
            logger.info(f"🎉 Click discovery completed: {len(items)} articles scraped")
            return items
            
        except Exception as e:
            logger.error(f"Click discovery failed: {e}")
            return []
    
    def _fetch_page(self, url: str, use_js: bool = False) -> Optional[BeautifulSoup]:
        """Fetch a page with optional JavaScript support"""
        try:
            if use_js:
                return self._fetch_with_selenium(url)
            else:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_with_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page using Selenium for JavaScript support"""
        if not self.driver:
            self._init_driver()
        
        if not self.driver:
            return None
        
        try:
            self.driver.get(url)
            
            # Wait for content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # Additional wait for dynamic content
                time.sleep(3)
            except:
                pass
            
            return BeautifulSoup(self.driver.page_source, 'html.parser')
        except Exception as e:
            logger.error(f"Selenium error for {url}: {e}")
            return None
    
    def _init_driver(self):
        """Initialize Selenium WebDriver with fallback support for multiple browsers"""
        browsers_to_try = [
            ('Chrome', self._setup_chrome_driver),
            ('Edge', self._setup_edge_driver),
            ('Firefox', self._setup_firefox_driver),
        ]
        
        for browser_name, setup_func in browsers_to_try:
            try:
                logger.info(f"Trying {browser_name} browser...")
                self.driver = setup_func()
                logger.info(f"Successfully initialized {browser_name} WebDriver")
                return
            except Exception as e:
                logger.warning(f"Could not initialize {browser_name}: {e}")
                continue
        
        # If we get here, no browsers worked
        logger.error("Could not initialize any WebDriver")
        logger.error("Please install one of: Chrome, Edge, or Firefox")
        self.driver = None
    
    def _setup_chrome_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver"""
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Try to use system ChromeDriver first if available
        system_chromedriver = shutil.which('chromedriver')
        
        if system_chromedriver:
            logger.info(f"Using system ChromeDriver: {system_chromedriver}")
            service = ChromeService(system_chromedriver)
        else:
            logger.info("Using ChromeDriverManager to download driver")
            try:
                driver_path = ChromeDriverManager().install()
                # Ensure the driver is executable
                import os
                import stat
                os.chmod(driver_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                service = ChromeService(driver_path)
            except Exception as e:
                logger.error(f"ChromeDriverManager failed: {e}")
                raise
        
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def _setup_edge_driver(self) -> webdriver.Edge:
        """Setup Edge WebDriver"""
        try:
            from selenium.webdriver.edge.service import Service as EdgeService
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
        except ImportError:
            raise Exception("Edge WebDriver dependencies not available")
        
        edge_options = EdgeOptions()
        edge_options.add_argument("--headless")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-gpu")
        
        service = EdgeService(EdgeChromiumDriverManager().install())
        return webdriver.Edge(service=service, options=edge_options)
    
    def _setup_firefox_driver(self) -> webdriver.Firefox:
        """Setup Firefox WebDriver"""
        try:
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from webdriver_manager.firefox import GeckoDriverManager
        except ImportError:
            raise Exception("Firefox WebDriver dependencies not available")
        
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--width=1920")
        firefox_options.add_argument("--height=1080")
        
        service = FirefoxService(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=firefox_options)
    
    def _scrape_article(self, url: str, use_js: bool = False) -> Optional[ContentItem]:
        """Scrape a single article"""
        logging.info(f"Attempting to scrape: {url}")
        
        soup = self._fetch_page(url, use_js)
        if not soup:
            logging.warning(f"Failed to fetch page: {url}")
            return None
        
        # Extract content
        content = self.detector.extract_main_content(soup)
        if not content or len(content.strip()) < 100:
            logging.warning(f"No content found for {url}")
            logging.debug(f"Content length: {len(content) if content else 0}")
            return None
        
        # Extract metadata
        title = self.detector.extract_title(soup)
        author = self.detector.extract_author(soup)
        
        # Smart content type detection
        content_type = detect_content_type(url, title, content)
        
        logging.info(f"Successfully extracted content from {url} - Title: '{title}', Content length: {len(content)}, Type: '{content_type}'")
        
        return ContentItem(
            title=title,
            content=content,
            content_type=content_type,
            source_url=url,
            author=author,
            user_id=""
        )
    
    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _fetch_with_requests_fallback(self, url):
        """Enhanced requests-based fallback when browsers aren't available"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find blog post links using multiple selectors
            selectors = [
                'a[href*="blog"]', 'a[href*="post"]', 'a[href*="article"]',
                '.post-title a', '.blog-post a', '.article-title a',
                'h2 a', 'h3 a', '.entry-title a', '.post-link'
            ]
            
            links = []
            for selector in selectors:
                found_links = soup.select(selector)
                for link in found_links:
                    href = link.get('href')
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = urljoin(url, href)
                        elif not href.startswith('http'):
                            href = urljoin(url, href)
                        
                        title = link.get_text(strip=True)
                        if title and len(title) > 10:  # Filter out navigation links
                            links.append({
                                'url': href,
                                'title': title
                            })
            
            # Remove duplicates
            seen = set()
            unique_links = []
            for link in links:
                if link['url'] not in seen:
                    seen.add(link['url'])
                    unique_links.append(link)
            
            logger.info(f"Found {len(unique_links)} potential articles with requests fallback")
            return unique_links[:20]  # Limit to 20 for demo
            
        except Exception as e:
            logger.error(f"Requests fallback failed: {e}")
            return []

    def _init_playwright_driver(self):
        """Initialize Playwright browser as fallback when Selenium fails"""
        try:
            from playwright.sync_api import sync_playwright
            logger.info("Attempting to initialize Playwright browser...")
            
            self.playwright = sync_playwright().start()
            
            try:
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
            except Exception as browser_error:
                if "Executable doesn't exist" in str(browser_error):
                    logger.info("Playwright browsers not found, attempting to install...")
                    import subprocess
                    subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
                    
                    # Try again after installation
                    self.browser = self.playwright.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-features=VizDisplayCompositor'
                        ]
                    )
                else:
                    raise browser_error
            
            self.page = self.browser.new_page()
            logger.info("✅ Playwright browser initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"Could not initialize Playwright: {e}")
            return False

    def _fetch_with_playwright(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page using Playwright"""
        try:
            if not hasattr(self, 'page') or not self.page:
                if not self._init_playwright_driver():
                    return None
            
            logger.info(f"Fetching {url} with Playwright...")
            self.page.goto(url, wait_until='networkidle')
            content = self.page.content()
            
            return BeautifulSoup(content, 'html.parser')
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return None


class UniversalKnowledgebaseScraper:
    """Main orchestrator for universal scraping"""
    
    def __init__(self, team_id: str, customer_name: str):
        self.team_id = team_id
        self.customer_name = customer_name
        self.items = []
    
    def add_source(self, base_url: str, config: Dict[str, Any] = None):
        """Add a source to scrape"""
        logger.info(f"Adding source: {base_url}")
        
        # Handle PDF sources
        if config and config.get('source_type') == 'pdf':
            self._process_pdf_source(base_url, config)
            return
        
        # Handle web sources
        scraper = UniversalScraper(base_url, config)
        try:
            items = scraper.scrape()
            self.items.extend(items)
            logger.info(f"Added {len(items)} items from {base_url}")
        finally:
            scraper.close()
    
    def _process_pdf_source(self, pdf_path: str, config: Dict[str, Any]):
        """Process PDF source using the specific uploaded file"""
        logger.info(f"📖 PDF source detected: {config.get('description', 'PDF content')}")
        
        # Check if PDF support is available
        if not PDF_SUPPORT:
            logger.warning("PDF processing not available. Install PyMuPDF: pip install PyMuPDF")
            return
        
        # Use the specific PDF file path provided (from uploads)
        import os
        
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF file not found: {pdf_path}")
            return
        
        logger.info(f"Processing PDF: {pdf_path}")
        
        processor = PDFProcessor(
            chunk_size=config.get('chunk_size', 1000),
            chunk_overlap=config.get('chunk_overlap', 200)
        )
        
        # Extract title from filename if not provided in config
        title = config.get('title') or config.get('description')
        if not title:
            filename = os.path.basename(pdf_path)
            title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
        
        # Get author from config or use customer name
        author = config.get('author', self.customer_name)
        
        chunks = processor.process_pdf_file(
            pdf_path, 
            title=title,
            author=author
        )
        
        # Convert chunks to ContentItem objects
        for chunk in chunks:
            item = ContentItem(
                title=chunk['title'],
                content=chunk['content'],
                content_type=chunk['content_type'],
                source_url=chunk['source_url'],
                author=chunk['author'],
                user_id=chunk['user_id']
            )
            self.items.append(item)
        
        logger.info(f"Added {len(chunks)} chunks from {os.path.basename(pdf_path)}")
        logger.info(f"PDF processing complete. Total items from PDFs: {len([i for i in self.items if i.content_type == 'book'])}")
    
    def save(self, output_path: str):
        """Save all scraped content"""
        output_data = {
            "team_id": self.team_id,
            "items": [item.to_dict() for item in self.items]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(self.items)} items to {output_path}")


def main():
    """CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Universal Content Scraper')
    parser.add_argument('config', help='Configuration file (JSON)')
    parser.add_argument('-o', '--output', default='knowledgebase.json', help='Output file')
    
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Create scraper
    scraper = UniversalKnowledgebaseScraper(
        team_id=config['team_id'],
        customer_name=config['customer_name']
    )
    
    # Add all sources
    for source in config['sources']:
        scraper.add_source(source['url'], source.get('config', {}))
    
    # Save results
    scraper.save(args.output)


if __name__ == "__main__":
    main()

async def scrape_spa_with_infinite_scroll(base_url, max_articles=50):
    """
    Enhanced SPA scraping with infinite scroll support for sites like Quill.
    Handles lazy loading by scrolling to load all content.
    """
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print(f"🔍 SPA Infinite Scroll: Loading {base_url}")
            
            # Load the main page
            await page.goto(base_url)
            await page.wait_for_load_state('networkidle')
            
            # Scroll to bottom to load all blog posts (SPA behavior)
            print("📜 Scrolling to load all content...")
            previous_height = 0
            max_scrolls = 10  # Prevent infinite loops
            scroll_count = 0
            
            while scroll_count < max_scrolls:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)  # Wait for content to load
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == previous_height:
                    break  # No more content to load
                    
                previous_height = new_height
                scroll_count += 1
                print(f"  Scroll {scroll_count}: Height = {new_height}")
            
            print(f"📜 Finished scrolling after {scroll_count} scrolls")
            
            # Method 1: Look for actual <a> tags with blog URLs
            print("🔗 Looking for traditional <a> links...")
            links = await page.eval_on_selector_all(
                'a[href*="/blog/"]', 
                'elements => elements.map(el => el.href)'
            )
            
            blog_urls = []
            seen = set()
            
            for link in links:
                if link and link not in seen and '/blog/' in link:
                    if not link.endswith('/blog') and not link.endswith('/blog/'):
                        blog_urls.append(link)
                        seen.add(link)
            
            print(f"🔗 Found {len(blog_urls)} traditional blog links")
            
            # Method 2: Handle SPAs like Quill that use clickable containers  
            if len(blog_urls) == 0:
                print("🎯 No traditional links found, trying SPA click discovery...")
                
                # Find clickable containers and discover URLs by simulating clicks
                discovered_urls = []
                seen_urls = set()
                
                # First, get all h1 titles in clickable containers
                clickable_titles = await page.eval_on_selector_all(
                    '[style*="cursor:pointer"] h1',
                    'elements => elements.map(el => el.textContent?.trim()).filter(text => text && text.length > 15)'
                )
                
                print(f"📍 Found {len(clickable_titles)} potential blog posts to test")
                
                # Process each title by finding and clicking its container
                for idx, title in enumerate(clickable_titles):
                    if title in [item['title'] for item in discovered_urls]:
                        continue  # Skip already discovered
                        
                    print(f"🔍 Testing clickable post {idx+1}/{len(clickable_titles)}: {title[:50]}...")
                    
                    try:
                        # Find the specific container with this h1 title
                        container = await page.query_selector(f'[style*="cursor:pointer"]:has(h1:text("{title}"))')
                        
                        if container:
                            # Get current URL
                            current_url = page.url
                            
                            # Click and wait for navigation
                            await container.click()
                            
                            # Wait for URL change or timeout
                            try:
                                await page.wait_for_url(lambda url: url != current_url, timeout=3000)
                                new_url = page.url
                                
                                if new_url != current_url and new_url not in seen_urls:
                                    print(f"  ✅ Discovered: {new_url}")
                                    discovered_urls.append({
                                        'title': title,
                                        'url': new_url
                                    })
                                    seen_urls.add(new_url)
                                    blog_urls.append(new_url)
                                    
                                    # Navigate back to blog page
                                    await page.goto(base_url)
                                    await page.wait_for_load_state('networkidle')
                                    
                                    # Re-scroll to load all content
                                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                    await page.wait_for_timeout(1000)
                                else:
                                    print(f"  ❌ No navigation or duplicate URL")
                                    
                            except:
                                # No navigation occurred within timeout
                                print(f"  ❌ Click did not navigate")
                                
                    except Exception as e:
                        print(f"  ❌ Error testing '{title[:30]}...': {str(e)[:50]}...")
                
                print(f"\n🎯 Discovered {len(discovered_urls)} blog URLs through click navigation:")
                for item in discovered_urls:
                    print(f"  • {item['title'][:50]}... → {item['url']}")
            
            print(f"\n🔗 Total blog URLs to scrape: {len(blog_urls)}")
            
            # Now scrape each blog post
            articles = []
            
            for i, url in enumerate(blog_urls[:max_articles], 1):
                print(f"\n📖 Scraping post {i}/{min(len(blog_urls), max_articles)}: {url}")
                
                try:
                    await page.goto(url)
                    await page.wait_for_load_state('networkidle')
                    
                    # Extract content
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Extract title with improved logic
                    title = ""
                    
                    # First, try to find a meaningful h1 that looks like an article title
                    h1_elements = soup.find_all('h1')
                    for h1 in h1_elements:
                        h1_text = h1.get_text(strip=True)
                        # Look for substantial titles that aren't navigation
                        if (len(h1_text) > 15 and
                            h1_text not in ['Blog', 'Product', 'Docs'] and
                            not h1_text.lower().startswith(('quill', 'home', 'welcome'))):
                            title = h1_text
                            break
                    
                    # Fallback to other title sources if h1 didn't work
                    if not title:
                        for selector in ['title', '[class*="title"]']:
                            title_elem = soup.select_one(selector)
                            if title_elem:
                                title_text = title_elem.get_text(strip=True)
                                # Filter out generic site titles
                                if (len(title_text) > 10 and 
                                    'Quill' not in title_text and
                                    'Platform' not in title_text and
                                    'Dashboard' not in title_text):
                                    title = title_text
                                    break
                    
                    if not title:
                        # Extract from URL as final fallback
                        slug = url.split('/')[-1]
                        title = slug.replace('-', ' ').title()
                    
                    # Extract main content using enhanced detection
                    article_content = ""
                    
                    # Method 1: Traditional semantic selectors
                    traditional_selectors = [
                        'article', 'main', '[class*="content"]', 
                        '[class*="post"]', '[class*="article"]'
                    ]
                    
                    for selector in traditional_selectors:
                        content_elem = soup.select_one(selector)
                        if content_elem:
                            text = content_elem.get_text(separator=' ', strip=True)
                            if len(text) > len(article_content):
                                article_content = text
                    
                    # Method 2: Smart content detection for modern frameworks (Tailwind, etc.)
                    if len(article_content) < 500:  # If traditional methods failed
                        potential_containers = soup.find_all('div')
                        
                        for container in potential_containers:
                            text = container.get_text(separator=' ', strip=True)
                            
                            # Smart criteria for main content:
                            # 1. Has substantial text (> 1000 chars)
                            # 2. Contains meaningful content words
                            # 3. Not navigation/header/footer content
                            # 4. Has reasonable content density
                            
                            if (len(text) > 1000 and
                                len(text) > len(article_content) and
                                not any(nav_word in text.lower() for nav_word in 
                                       ['navigation', 'menu', 'footer', 'header', 'copyright', 'privacy']) and
                                # Check for content-like text patterns
                                (len([word for word in text.split() if len(word) > 3]) / max(len(text.split()), 1) > 0.6)):
                                
                                # Additional quality checks
                                word_count = len(text.split())
                                if (word_count > 200 and  # Substantial word count
                                    text.count('.') > 5 and  # Has sentences
                                    not text.lower().startswith(('cookie', 'privacy', 'terms'))):  # Not legal text
                                    
                                    article_content = text
                    
                    # Clean content
                    article_content = re.sub(r'\s+', ' ', article_content).strip()
                    
                    if len(article_content) > 500:  # Quality threshold
                        articles.append({
                            'title': title,
                            'content': article_content,
                            'url': url,
                            'content_length': len(article_content)
                        })
                        print(f"  ✅ Success: {title} ({len(article_content)} chars)")
                    else:
                        print(f"  ❌ Content too short: {len(article_content)} chars")
                        
                except Exception as e:
                    print(f"  ❌ Error scraping {url}: {e}")
            
            await browser.close()
            
            print(f"\n🎉 Successfully scraped {len(articles)} blog posts!")
            return articles
            
    except ImportError:
        print("❌ Playwright not available. Install with: pip install playwright")
        return []
    except Exception as e:
        print(f"❌ SPA scraping error: {e}")
        return []

def detect_content_type(url: str, title: str = "", content: str = "") -> str:
    """Smart content type detection based on URL, title, and content patterns"""
    url_lower = url.lower()
    title_lower = title.lower()
    content_lower = content.lower()[:500]  # Check first 500 chars
    
    # LinkedIn detection
    if 'linkedin.com' in url_lower:
        if '/posts/' in url_lower or '/feed/update/' in url_lower:
            return 'linkedin_post'
        elif '/pulse/' in url_lower:
            return 'blog'  # LinkedIn articles are more like blogs
        else:
            return 'linkedin_post'  # Default for LinkedIn
    
    # Reddit detection
    if 'reddit.com' in url_lower:
        if '/comments/' in url_lower:
            return 'reddit_comment'
        else:
            return 'reddit_comment'  # Default for Reddit
    
    # Podcast/Audio transcript detection
    podcast_indicators = ['podcast', 'transcript', 'audio', 'episode', 'interview']
    if any(indicator in url_lower for indicator in podcast_indicators):
        return 'podcast_transcript'
    if any(indicator in title_lower for indicator in podcast_indicators):
        return 'podcast_transcript'
    if any(indicator in content_lower for indicator in ['transcript:', 'speaker:', 'host:', '[music]', '[applause]']):
        return 'podcast_transcript'
    
    # Call transcript detection (more specific patterns)
    call_indicators = ['call transcript', 'meeting transcript', 'call notes', 'meeting notes']
    if any(indicator in title_lower for indicator in call_indicators):
        return 'call_transcript'
    if any(indicator in content_lower for indicator in ['attendees:', 'participants:', 'meeting started', 'call ended']):
        return 'call_transcript'
    
    # YouTube detection (could be podcast or blog-style)
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        if any(indicator in title_lower for indicator in ['podcast', 'interview', 'talk', 'discussion']):
            return 'podcast_transcript'
        else:
            return 'blog'  # Video content descriptions are blog-like
    
    # Default to blog for regular websites
    return 'blog'