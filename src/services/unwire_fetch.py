# fetch data from "https://unwire.hk" url 
# get the list of news data today
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import os
import sys

# Add parent directory to path to enable module imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Disable debugging to avoid saving HTML files
DEBUG = False

class UnwireFetcher:
    def __init__(self):
        self.base_url = "https://unwire.hk"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        self.today = datetime.now()
        # Format for URL path: YYYY/MM/DD
        self.today_url_format = self.today.strftime('%Y/%m/%d')
        # Format for comparison: YYYY-MM-DD
        self.today_date = self.today.strftime('%Y-%m-%d')
        
        # Define known categories mapping (from URL path to display name)
        self.categories_map = {
            'ai': 'AI & Artificial Intelligence',
            'fun-tech': 'Tech Lifestyle',
            'mobile': 'Mobile & Communication',
            'notebook': 'Laptops & Computers',
            'game': 'Gaming & E-Sports',
            'entertainment': 'Entertainment & Audio',
            'photography': 'Digital Cameras',
            'review': 'Reviews & Reports',
            'news': 'News Reports',
            'gadgets': 'Digital Products',
            'apps': 'Applications',
            'security-issues': 'Information Security',
            'tips': 'Tutorials & Tips',
            'ios': 'iOS',
            'android': 'Android'
        }
    
    def fetch_news_page(self, date_str=None):
        """
        Fetch news from a specific date or today
        date_str: Date in YYYY-MM-DD or YYYY/MM/DD format
        """
        try:
            if date_str:
                # Convert date string to URL format if needed
                if '-' in date_str:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_url = date_obj.strftime('%Y/%m/%d')
                else:
                    # Assume it's already in the right format
                    date_url = date_str
                
                url = f"{self.base_url}/{date_url}/"
            else:
                # Use today's date
                url = f"{self.base_url}/{self.today_url_format}/"
            
            print(f"Fetching news from URL: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            print(f"Response status: {response.status_code}")
            
            # Debug: Save the HTML content to a file for inspection
            if DEBUG:
                date_for_filename = date_str.replace('/', '-') if date_str else self.today_date
                debug_filename = f"debug_unwire_{date_for_filename}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved HTML content to {debug_filename} for debugging")
            
            # If this is a date-specific URL, return the date we used for display
            if date_str:
                return response.text, date_url
            return response.text
            
        except requests.RequestException as e:
            print(f"Error fetching news: {e}")
            if date_str:
                return None, date_str
            return None
    
    def fetch_recent_news(self, days=7, max_articles=50):
        """
        Fetch news from multiple recent days
        days: Number of days to look back
        max_articles: Maximum number of articles to fetch
        """
        all_news = []
        days_checked = 0
        
        # Try fetching news from today and previous days
        for i in range(days):
            if len(all_news) >= max_articles:
                break
                
            date = self.today - timedelta(days=i)
            date_str = date.strftime('%Y/%m/%d')
            print(f"Checking news for {date_str}")
            
            html_content, _ = self.fetch_news_page(date_str)
            if not html_content:
                continue
                
            news_items = self.parse_news_items(html_content)
            if news_items:
                date_display = date.strftime('%Y-%m-%d')
                for item in news_items:
                    item['date'] = date_display
                all_news.extend(news_items)
                print(f"Found {len(news_items)} articles for {date_str}")
            
            days_checked += 1
            if days_checked >= days:
                break
                
        return all_news
    
    def fetch_article_detail(self, article_url):
        """
        Fetch the detailed content of a specific article
        """
        try:
            # If URL doesn't start with http/https, assume it's relative
            if not article_url.startswith(('http://', 'https://')):
                if article_url.startswith('/'):
                    article_url = f"{self.base_url}{article_url}"
                else:
                    article_url = f"{self.base_url}/{article_url}"
            
            print(f"Fetching article details from: {article_url}")
            response = requests.get(article_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Debug: Save the article HTML content to a file for inspection
            if DEBUG:
                filename_part = article_url.split('/')[-2] if article_url.endswith('/') else article_url.split('/')[-1]
                debug_filename = f"debug_article_{filename_part}.html"
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"Saved article HTML content to {debug_filename} for debugging")
            
            return self.parse_article_detail(response.text, article_url)
        except requests.RequestException as e:
            print(f"Error fetching article details: {e}")
            return None
    
    def extract_category_from_url(self, url):
        """Extract category from article URL"""
        try:
            # URLs typically have format: unwire.hk/YYYY/MM/DD/article-slug/category/
            # or unwire.hk/YYYY/MM/DD/article-slug/category/subcategory/
            
            # Extract the path parts
            url_parts = url.rstrip('/').split('/')
            
            # Check if we have enough parts and the URL is from unwire.hk
            if len(url_parts) >= 6 and ('unwire.hk' in url_parts[2] or url_parts[0] == ''):
                # Category should be the second to last item for single category
                # or last two items for category/subcategory
                idx = -2  # Start with second to last
                
                # Get potential category
                category_slug = url_parts[idx]
                
                # Map to display name if known, otherwise use capitalized version
                category_name = self.categories_map.get(category_slug, category_slug.replace('-', ' ').title())
                
                # Check if there's a subcategory
                if len(url_parts) >= 7:
                    subcategory_slug = url_parts[-1]
                    if subcategory_slug in self.categories_map:
                        subcategory_name = self.categories_map.get(subcategory_slug, subcategory_slug.replace('-', ' ').title())
                        return f"{category_name} / {subcategory_name}"
                
                return category_name
            
            return "Uncategorized"  # Default if we can't determine the category
        except Exception as e:
            print(f"Error extracting category from URL: {e}")
            return "Uncategorized"
    
    def parse_news_items(self, html_content):
        """
        Parse HTML to extract news articles list
        """
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Debug: Print some structure information
        if DEBUG:
            print("\n--- DEBUG: Page Structure Analysis ---")
            
            # Check for main content areas
            print("Checking for main container elements:")
            for container in ['main', '#content', '#primary', '.content-area', '.site-content']:
                elements = soup.select(container)
                print(f"  {container}: {len(elements)} found")
            
            # Check for post/article elements
            print("Checking for article elements:")
            for article_selector in ['article', '.post', '.hentry', '.type-post', '.news-item']:
                articles = soup.select(article_selector)
                print(f"  {article_selector}: {len(articles)} found")
            
            # Check for the first h1/h2 titles
            print("First few heading elements:")
            for heading in soup.find_all(['h1', 'h2'])[:5]:
                print(f"  {heading.name}: {heading.get_text(strip=True)[:50]}")
                
            print("--- End of Structure Analysis ---\n")
        
        # Try different methods to find articles
        
        # Method 1: Standard article elements
        articles = soup.find_all('article')
        if articles:
            print(f"Found {len(articles)} articles using the standard article tag")
        
        # Method 2: If no standard articles found, try common article classes
        if not articles:
            for selector in ['.post', '.type-post', '.hentry', '.news-item']:
                articles = soup.select(selector)
                if articles:
                    print(f"Found {len(articles)} articles using selector: {selector}")
                    break
        
        # Method 3: Look for typical news link patterns
        if not articles:
            print("No standard articles found, looking for news links...")
            # Try to find links to news articles directly in the page
            main_content = soup.select_one('main') or soup.select_one('#content') or soup.select_one('.content-area')
            
            if main_content:
                news_links = []
                # Look for links in the main content that follow Unwire.hk article URL pattern
                for link in main_content.find_all('a', href=True):
                    href = link.get('href')
                    # Check if link seems to be a news article
                    if (self.base_url in href or href.startswith('/')) and re.search(r'/\d{4}/\d{2}/\d{2}/', href):
                        # This looks like an article link
                        parent = link.parent
                        if parent.name in ['h1', 'h2', 'h3', 'h4']:
                            # This is likely a title
                            news_links.append({
                                'title': link.get_text(strip=True),
                                'url': href,
                                'element': link
                            })
                
                if news_links:
                    print(f"Found {len(news_links)} news links by URL pattern")
                    
                    # Convert these links to article-like data structures
                    pseudo_articles = []
                    for news in news_links:
                        # Create a dummy article that our existing parser can handle
                        article = soup.new_tag('div')
                        article['class'] = 'pseudo-article'
                        
                        title = soup.new_tag('h2')
                        title['class'] = 'entry-title'
                        link = soup.new_tag('a', href=news['url'])
                        link.string = news['title']
                        title.append(link)
                        article.append(title)
                        
                        pseudo_articles.append(article)
                    
                    if pseudo_articles:
                        articles = pseudo_articles
        
        # If still no articles found, try one more method with the full HTML
        if not articles:
            print("No articles found with standard methods, trying full page scan...")
            # Look for any links that match the pattern of Unwire.hk articles
            all_links = soup.find_all('a', href=True)
            news_links = []
            
            for link in all_links:
                href = link.get('href')
                # Check if it looks like a news article URL
                if (self.base_url in href or href.startswith('/')) and re.search(r'/\d{4}/\d{2}/\d{2}/', href):
                    news_links.append({
                        'title': link.get_text(strip=True),
                        'url': href
                    })
            
            if news_links:
                print(f"Found {len(news_links)} potential news links from full page scan")
                
                # Filter to remove duplicates and non-title links
                filtered_links = {}
                for link in news_links:
                    url = link['url']
                    title = link['title'].strip()
                    
                    if title and len(title) > 10 and url not in filtered_links:
                        filtered_links[url] = title
                
                # Convert these to pseudo-articles
                pseudo_articles = []
                for url, title in filtered_links.items():
                    article = soup.new_tag('div')
                    article['class'] = 'pseudo-article'
                    
                    title_elem = soup.new_tag('h2')
                    title_elem['class'] = 'entry-title'
                    link = soup.new_tag('a', href=url)
                    link.string = title
                    title_elem.append(link)
                    article.append(title_elem)
                    
                    pseudo_articles.append(article)
                
                articles = pseudo_articles
                print(f"Created {len(articles)} pseudo-articles from links")
        
        if not articles:
            print("Could not find any articles or news links in the page")
            return []
        
        news_items = []
        
        for article in articles:
            try:
                # Extract title and URL
                title_elem = None
                for selector in ['h1.entry-title', 'h2.entry-title', '.entry-title', 'h1 a', 'h2 a', '.title a', 'a']:
                    if selector == 'a' and article.name != 'a':
                        # For the generic 'a' selector, only use it if we haven't found anything yet
                        if not title_elem:
                            elements = article.find_all('a', href=True, limit=1)
                            if elements and len(elements[0].get_text(strip=True)) > 10:
                                title_elem = elements[0]
                    else:
                        if article.select(selector):
                            title_elem = article.select(selector)[0]
                            break
                
                if not title_elem:
                    # Try direct attributes for pseudo-articles
                    if hasattr(article, 'title') and hasattr(article, 'url'):
                        news_items.append({
                            'title': article.title,
                            'url': article.url,
                            'category': getattr(article, 'category', ''),
                            'thumbnail': getattr(article, 'thumbnail', None),
                            'excerpt': getattr(article, 'excerpt', '')
                        })
                        continue
                    else:
                        continue
                
                # Get the title text
                title = title_elem.get_text(strip=True)
                
                # Skip if title is empty or too short
                if not title or len(title) < 5:
                    continue
                
                # Get the URL
                url = None
                if title_elem.name == 'a':
                    url = title_elem.get('href')
                else:
                    # If title element isn't a link, look for a link inside it
                    link = title_elem.find('a')
                    if link:
                        url = link.get('href')
                
                if not url:
                    continue
                
                # Ensure URL is absolute
                if not url.startswith(('http://', 'https://')):
                    if url.startswith('/'):
                        url = f"{self.base_url}{url}"
                    else:
                        url = f"{self.base_url}/{url}"
                
                # Extract category from the URL
                category = self.extract_category_from_url(url)
                
                # If we couldn't extract from URL, try the traditional method
                if category == "Uncategorized":
                    cat_elem = article.select_one('.cat-links')
                    if cat_elem:
                        category = cat_elem.get_text(strip=True)
                
                # Extract thumbnail image
                thumbnail = None
                img = article.select_one('.post-thumbnail img') or article.select_one('img')
                if img:
                    thumbnail = img.get('src') or img.get('data-src')
                
                # Extract excerpt
                excerpt = ""
                excerpt_elem = article.select_one('.entry-summary')
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                
                news_items.append({
                    'title': title,
                    'url': url,
                    'category': category,
                    'thumbnail': thumbnail,
                    'excerpt': excerpt
                })
                
            except Exception as e:
                print(f"Error parsing article: {e}")
                continue
        
        # Debug: final results
        if DEBUG:
            print(f"Final result: Found {len(news_items)} news items")
            for i, item in enumerate(news_items[:5], 1):  # Print first 5 for debugging
                print(f"  {i}. {item['title'][:50]}... - {item['url']} - Category: {item['category']}")
            
            if len(news_items) > 5:
                print(f"  ... and {len(news_items) - 5} more items")
        
        return news_items
    
    def parse_article_detail(self, html_content, url):
        """
        Parse a full article page to extract detailed content
        """
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # Extract title
            title = "Unknown Title"
            title_elem = soup.select_one('h1.entry-title') or soup.select_one('.entry-title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Extract date
            date = "Unknown Date"
            date_elem = soup.select_one('time.entry-date') or soup.select_one('.entry-date')
            if date_elem:
                if date_elem.get('datetime'):
                    date_str = date_elem.get('datetime').split('T')[0]
                    date = date_str
                else:
                    date = date_elem.get_text(strip=True)
            
            # Extract author
            author = "Unwire.HK"
            author_elem = soup.select_one('.author') or soup.select_one('.byline')
            if author_elem:
                author = author_elem.get_text(strip=True)
            
            # Extract categories
            categories = []
            cat_elems = soup.select('.cat-links a')
            for cat in cat_elems:
                categories.append(cat.get_text(strip=True))
            
            # Extract main content
            content_text = ""
            content_elem = soup.select_one('.entry-content')
            if content_elem:
                # Extract paragraphs and headings
                for elem in content_elem.find_all(['p', 'h2', 'h3', 'h4', 'blockquote', 'ul', 'ol']):
                    if elem.name.startswith('h'):
                        content_text += f"\n[{elem.get_text(strip=True)}]\n\n"
                    elif elem.name == 'blockquote':
                        content_text += f"> {elem.get_text(strip=True)}\n\n"
                    elif elem.name in ['ul', 'ol']:
                        for li in elem.find_all('li'):
                            content_text += f"• {li.get_text(strip=True)}\n"
                        content_text += "\n"
                    else:
                        content_text += f"{elem.get_text(strip=True)}\n\n"
            
            # Extract images
            images = []
            if content_elem:
                for img in content_elem.find_all('img'):
                    img_src = img.get('src') or img.get('data-src')
                    if img_src:
                        # Make sure URL is absolute
                        if not img_src.startswith(('http://', 'https://')):
                            if img_src.startswith('/'):
                                img_src = f"{self.base_url}{img_src}"
                            else:
                                img_src = f"{self.base_url}/{img_src}"
                                
                        images.append({
                            'url': img_src,
                            'alt': img.get('alt', '')
                        })
            
            # Extract tags
            tags = []
            tag_elems = soup.select('.tags-links a')
            for tag in tag_elems:
                tags.append(tag.get_text(strip=True))
            
            return {
                'title': title,
                'url': url,
                'date': date,
                'author': author,
                'categories': categories,
                'content': content_text,
                'images': images,
                'tags': tags
            }
        
        except Exception as e:
            print(f"Error parsing article detail: {e}")
            return {
                'title': 'Error parsing article',
                'url': url,
                'content': f"An error occurred while parsing this article: {str(e)}"
            }
    
    def format_news_list(self, news_items, date_str=None):
        """Format news items into readable text"""
        if not news_items:
            if date_str:
                return f"No news found for {date_str}."
            else:
                return f"No news found for today ({self.today_date}). Unwire.hk may not have published any articles today."
        
        title = ""
        if date_str:
            title += f" News for {date_str}"
        else:
            title += f" News for today ({self.today_date})"
        title += "\n\n"
        
        content = title
        
        for i, item in enumerate(news_items, 1):
            if 'url' in item:
                content += f"{i}. {item['title']}\n"
                content += f"{item['url']}\n"
            else:
                content += f"{i}. {item['title']}\n"
            
            if 'excerpt' in item and item['excerpt']:
                content += f"   {item['excerpt'][:150]}...\n"
            content += "\n"
        
        return content
    
    def format_article_detail(self, article):
        """Format article details into readable text"""
        if not article:
            return "Error: Could not fetch or parse the article."
            
        content = f"📱 {article['title']} 📱\n\n"
        
        if 'date' in article:
            content += f"Date: {article['date']}\n"
        
        if 'author' in article:
            content += f"Author: {article['author']}\n"
        
        if 'categories' in article and article['categories']:
            content += f"Categories: {', '.join(article['categories'])}\n"
        
        content += f"Link: {article['url']}\n\n"
        
        content += "📄 Content 📄\n"
        content += "------------------------\n\n"
        content += article['content']
        content += "\n------------------------\n\n"
        
        if 'images' in article and article['images']:
            content += f"Images ({len(article['images'])}):\n"
            for i, img in enumerate(article['images'][:3], 1):  # Limit to first 3 images
                content += f"{i}. {img.get('alt', 'Image')} - {img['url']}\n"
            
            if len(article['images']) > 3:
                content += f"...and {len(article['images']) - 3} more images\n"
            
            content += "\n"
        
        if 'tags' in article and article['tags']:
            content += f"Tags: {', '.join(article['tags'])}"
        
        return content


def fetch_unwire_news(date=None, format_type='text'):
    """Main function to fetch news from Unwire.hk"""
    fetcher = UnwireFetcher()
    
    if date:
        # Fetch news from specific date
        html_content, date_str = fetcher.fetch_news_page(date)
        if html_content:
            news_items = fetcher.parse_news_items(html_content)
            return fetcher.format_news_list(news_items, date_str)
        else:
            return f"Failed to fetch news for date: {date}"
    else:
        # Fetch today's news
        html_content = fetcher.fetch_news_page()
        if html_content:
            news_items = fetcher.parse_news_items(html_content)
            return fetcher.format_news_list(news_items)
        else:
            return "Failed to fetch today's news"

def fetch_unwire_recent(days=7, format_type='text'):
    """Fetch news from recent days"""
    fetcher = UnwireFetcher()
    news_items = fetcher.fetch_recent_news(days=days)
    
    if not news_items:
        return f"No news found in the past {days} days."
    
    # Group articles by date
    articles_by_date = {}
    for item in news_items:
        date = item.get('date', 'Unknown Date')
        if date not in articles_by_date:
            articles_by_date[date] = []
        articles_by_date[date].append(item)
    
    # Format the results by date
    content = f"📰 Unwire.hk Recent News (Past {days} days) 📰\n\n"
    
    for date in sorted(articles_by_date.keys(), reverse=True):
        items = articles_by_date[date]
        content += f"【{date}】- {len(items)} articles\n"
        
        for i, item in enumerate(items, 1):
            if 'url' in item:
                content += f"{i}. <a href=\"{item['url']}\">{item['title']}</a>\n"
            else:
                content += f"{i}. {item['title']}\n"
        
        content += "\n"
    
    return content

def fetch_unwire_article(article_url, format_type='text'):
    """Fetch and format a specific article"""
    fetcher = UnwireFetcher()
    article = fetcher.fetch_article_detail(article_url)
    return fetcher.format_article_detail(article)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        
        # Check if the argument is a URL
        if arg.startswith('http') or 'unwire.hk' in arg:
            print(f"Fetching article: {arg}")
            article_content = fetch_unwire_article(arg)
            print(article_content)
            
        # Check if argument is "recent" or a number (days)
        elif arg == "recent" or arg.isdigit():
            days = 7 if arg == "recent" else int(arg)
            print(f"Fetching news from past {days} days...")
            news_content = fetch_unwire_recent(days=days)
            print(news_content)
            
        # Otherwise assume it's a date
        else:
            print(f"Fetching news for date: {arg}")
            news_content = fetch_unwire_news(date=arg)
            print(news_content)
            
    else:
        # No arguments, fetch today's news
        print("Fetching today's news from Unwire.hk...")
        today_news = fetch_unwire_news()
        print(today_news)

