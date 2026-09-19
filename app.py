import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import random
import time
import json
from urllib.parse import urljoin, urlparse
import pandas as pd
from io import BytesIO, StringIO
import zipfile
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter

# ============================================================
# SESSION STATE INIT
# ============================================================
defaults = {
    'is_ready': False, 'csv_data': None, 'zip_data': None, 'df_preview': None,
    'failed_urls': [], 'total_rows': 0, 'has_zip': False,
    'batch_index': 0, 'all_final_rows': [], 'all_image_data': {},
    'all_failed': [], 'total_urls': 0, 'is_processing': False, 'all_urls': []
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# CONSTANTS
# ============================================================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0',
]

BATCH_SIZE = 20

SHOPIFY_COLUMNS = [
    'Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
    'Published on online store', 'Status', 'SKU', 'Barcode', 'Option1 name',
    'Option1 value', 'Option1 Linked To', 'Option2 name', 'Option2 value',
    'Option2 Linked To', 'Option3 name', 'Option3 value', 'Option3 Linked To',
    'Price', 'Compare-at price', 'Cost per item', 'Charge tax', 'Tax code',
    'Unit price total measure', 'Unit price total measure unit',
    'Unit price base measure', 'Unit price base measure unit', 'Inventory tracker',
    'Inventory quantity', 'Continue selling when out of stock',
    'Weight value (grams)', 'Weight unit for display', 'Requires shipping',
    'Fulfillment service', 'Product image URL', 'Image position', 'Image alt text',
    'Variant image URL', 'Gift card', 'SEO title', 'SEO description', 'Short description',
    'Additional information',
    'Color (product.metafields.shopify.color-pattern)',
    'Google Shopping / Google product category', 'Google Shopping / Gender',
    'Google Shopping / Age group', 'Google Shopping / Manufacturer part number (MPN)',
    'Google Shopping / Ad group name', 'Google Shopping / Ads labels',
    'Google Shopping / Condition', 'Google Shopping / Custom product',
    'Google Shopping / Custom label 0', 'Google Shopping / Custom label 1',
    'Google Shopping / Custom label 2', 'Google Shopping / Custom label 3',
    'Google Shopping / Custom label 4'
]

WOOCOMMERCE_COLUMNS = [
    'ID', 'Type', 'SKU', 'Name', 'Published', 'Is featured?', 'Visibility in catalog',
    'Short description', 'Description', 'Additional information', 'Date sale price starts', 'Date sale price ends',
    'Tax status', 'Tax class', 'In stock?', 'Stock', 'Low stock amount',
    'Backorders allowed?', 'Sold individually?', 'Weight (kg)', 'Length (cm)',
    'Width (cm)', 'Height (cm)', 'Allow customer reviews?', 'Purchase note',
    'Sale price', 'Regular price', 'Categories', 'Tags', 'Shipping class', 'Images',
    'Download limit', 'Download expiry days', 'Parent', 'Grouped products',
    'Upsells', 'Cross-sells', 'External URL', 'Button text', 'Position',
    'Attribute 1 name', 'Attribute 1 value(s)', 'Attribute 1 visible', 'Attribute 1 global',
    'Attribute 2 name', 'Attribute 2 value(s)', 'Attribute 2 visible', 'Attribute 2 global',
    'Attribute 3 name', 'Attribute 3 value(s)', 'Attribute 3 visible', 'Attribute 3 global',
    'Meta: _yoast_wpseo_title', 'Meta: _yoast_wpseo_metadesc'
]

# ============================================================
# ALL FUNCTIONS DEFINED FIRST
# ============================================================

def test_gemini_api(api_key, model_name):
    """Test Gemini API and return (success, message)"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {"contents": [{"parts": [{"text": "Reply with just: OK"}]}]}
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            try:
                text = r.json()['candidates'][0]['content']['parts'][0]['text']
                return True, f"API working! Response: {text[:50]}"
            except (KeyError, IndexError):
                return False, f"API 200 but unexpected format"
        elif r.status_code == 400:
            return False, f"400 Bad Request: {r.text[:200]}"
        elif r.status_code == 403:
            return False, f"403 Forbidden: {r.text[:200]}"
        elif r.status_code == 404:
            return False, f"404 Model '{model_name}' not found. {r.text[:150]}"
        elif r.status_code == 429:
            return False, f"429 Rate Limit exceeded. Wait 1 min."
        elif r.status_code == 503:
            return False, f"503 Server busy. Wait 1-2 min and retry."
        else:
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.exceptions.Timeout:
        return False, "Timeout (>20s)"
    except Exception as e:
        return False, f"Error: {str(e)[:200]}"


def extract_keywords(title, category, specs_text):
    """Extract primary/secondary/long-tail keywords"""
    combined = f"{title} {category} {specs_text[:800]}".lower()
    words = re.findall(r'\b[a-z][a-z]+\b', combined)
    stopwords = {'the','a','an','and','or','for','with','of','in','to','is','are','this','that','your','our',
                 'from','on','by','it','its','be','as','at','new','made','real','top','best','high','quality',
                 'premium','will','have','has','been','can','may','also','more','most','into','over','while',
                 'such','just','very','only','than','then','when','where','what','which','who','how','all',
                 'but','not','out','up','down','you','they','them','their','was','were','one','two','use','used'}
    words = [w for w in words if w not in stopwords and len(w) > 3]
    freq = {}
    for w in words: freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    title_words = re.findall(r'\b[a-z][a-z]+\b', title.lower())
    title_words = [w for w in title_words if w not in stopwords and len(w) > 3]
    primary = ' '.join(title_words[:3]) if title_words else title.lower()
    secondary = [w for w, c in sorted_words[:10] if w not in primary]
    spec_keywords = []
    for line in specs_text.split('\n')[:10]:
        line = line.strip()
        if ':' in line and len(line) < 80: spec_keywords.append(line)
    return {'primary': primary, 'secondary': secondary[:8], 'long_tail': spec_keywords[:5], 'all': list(set([primary] + secondary[:8]))}


def generate_ai_content(title, specs_text, category, store_context, keywords, api_key, model_name, custom_prompt, max_retries=3):
    """Generate SEO content via Gemini with retry + model fallback"""
    if not api_key or not title:
        return None, "Missing API key or title"
    
    primary_kw = keywords.get('primary', '')
    secondary_kws = ', '.join(keywords.get('secondary', [])[:5])
    long_tail = '\n'.join([f"- {k}" for k in keywords.get('long_tail', [])[:5]])
    custom_block = f"\n\nBRAND VOICE INSTRUCTIONS:\n{custom_prompt}" if custom_prompt else ""
    context_block = f"\nStore Context: {store_context}" if store_context else ""
    
    prompt = f"""You are a world-class editorial e-commerce copywriter for premium brands like Filson, Taylor Stitch, Schott NYC, and Saddleback Leather. You write in a compelling, story-driven, educational style that makes customers feel the craftsmanship and heritage behind each product.

PRODUCT TITLE: {title}
CATEGORY: {category}
RAW SPECIFICATIONS & DETAILS:
{specs_text[:2000]}
{context_block}

PRIMARY KEYWORD: {primary_kw}
SECONDARY KEYWORDS: {secondary_kws}
LONG-TAIL PHRASES:
{long_tail}
{custom_block}

═══════════════════════════════════════════════════════════
WRITING STYLE REQUIREMENTS (Follow religiously):
═══════════════════════════════════════════════════════════

1. **STORIES, NOT SALES PITCHES**: Open with a cultural/historical/emotional hook — like describing a scene, a memory, or a tradition. NOT "This is a great product."

2. **EDUCATE THE CUSTOMER**: Explain WHY premium materials matter using analogies. Example: "Leather is like a roof. You have the wood decking and then the shingles..." — Make complex specs feel intuitive.

3. **SHOW DESIGN THINKING**: Use phrases like "We updated X with two factors in mind..." or "Here's why we chose Y..." — Position every feature as a deliberate decision.

4. **USE SUBHEADINGS**: Long description must have 3-5 bold subheadings like:
   - "Our Full Grain Leather is Key"
   - "Sewn with Strength"
   - "Built to Last Generations"
   - "The Details That Matter"
   - "Heritage You Can Wear"

5. **WEAVE SPECIFIC NUMBERS**: Not "high quality" but "50% Wool, 50% Polyester" or "twice the thickness of most wallets."

6. **CRAFTSMANSHIP REFERENCES**: Mention heritage, origin, artisan techniques, warranty, generational durability.

7. **READER CONNECTION**: Speak TO the customer, like a knowledgeable friend — "Now let me tell you why..." / "Take a look at it."

═══════════════════════════════════════════════════════════
OUTPUT FORMAT (Strict — follow exactly):
═══════════════════════════════════════════════════════════

===SEO TITLE===
[Max 60 chars. Include PRIMARY KEYWORD. Story-driven or heritage-focused.]

===META DESCRIPTION===
[155-160 chars. Include PRIMARY KEYWORD. Emotional hook + key benefit.]

===SHORT DESCRIPTION===
[150-250 words. 2-3 paragraphs. Open with a story/hook, then highlight 2-3 key features. Include PRIMARY KEYWORD 1-2 times. Feel like the opening of an editorial magazine piece.]

===LONG DESCRIPTION===
[700-1000 words in HTML format. MUST include:
- Opening paragraph: Story/cultural/emotional hook (2-3 sentences)
- Then 3-5 sections, each with <h3>Subheading</h3> followed by 1-2 <p> paragraphs
- Each section educates about a feature/material/craftsmanship aspect
- Use <ul><li> for technical feature lists within sections
- One closing paragraph with call-to-action
- Weave PRIMARY KEYWORD naturally 3-4 times
- Include analogies, specific numbers, heritage references]

===ADDITIONAL INFORMATION===
[Extract 8-12 specifications as clean bullet points. Format STRICTLY:
<ul><li><strong>Material:</strong> Value</li><li><strong>Dimensions:</strong> Value</li>...</ul>
Include: Material, Dimensions, Weight, Origin, Fit, Closure, Lining, Hardware, Warranty, SKU (if in specs)]

===TAGS===
[8-10 lowercase tags, comma-separated. Include: product type, material, style, target audience, use case.]

Now write the content:"""
    
    # Model fallback chain
    model_chain = [model_name]
    for fb in ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-2.5-pro"]:
        if fb not in model_chain:
            model_chain.append(fb)
    
    last_error = ""
    
    for current_model in model_chain:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 3000, "topP": 0.95, "topK": 40}
        }
        
        for attempt in range(max_retries):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=90)
                
                if r.status_code == 200:
                    try:
                        text = r.json()['candidates'][0]['content']['parts'][0]['text']
                        return parse_ai_sections(text, title, primary_kw, keywords), None
                    except (KeyError, IndexError):
                        last_error = "Response format unexpected"
                        break
                
                elif r.status_code == 503:
                    wait_time = 2 ** attempt
                    last_error = f"503 (server busy) attempt {attempt+1}/{max_retries}"
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        break
                
                elif r.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    last_error = f"429 (rate limit) attempt {attempt+1}/{max_retries}"
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        break
                
                elif r.status_code == 403:
                    return None, "403 Invalid API Key — check your key"
                elif r.status_code == 400:
                    last_error = f"400 Bad Request: {r.text[:100]}"
                    break
                elif r.status_code == 404:
                    last_error = f"404 Model '{current_model}' not found"
                    break
                else:
                    last_error = f"HTTP {r.status_code}: {r.text[:100]}"
                    break
            
            except requests.exceptions.Timeout:
                last_error = f"Timeout (attempt {attempt+1}/{max_retries})"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    break
            except Exception as e:
                last_error = f"Error: {str(e)[:100]}"
                break
        
        if current_model != model_chain[-1]:
            time.sleep(1)
    
    return None, f"All models failed. Last: {last_error}"


def parse_ai_sections(text, title, primary_kw, keywords):
    """Parse Gemini's structured response"""
    result = {'seo_title': '', 'meta_description': '', 'short_description': '',
              'long_description': '', 'additional_information': '', 'tags': ''}
    markers = {
        '===SEO TITLE===': 'seo_title',
        '===META DESCRIPTION===': 'meta_description',
        '===SHORT DESCRIPTION===': 'short_description',
        '===LONG DESCRIPTION===': 'long_description',
        '===ADDITIONAL INFORMATION===': 'additional_information',
        '===TAGS===': 'tags'
    }
    current_key = None; current_lines = []
    for line in text.split('\n'):
        s = line.strip()
        if s in markers:
            if current_key and current_lines:
                result[current_key] = '\n'.join(current_lines).strip()
            current_key = markers[s]; current_lines = []
        elif current_key:
            current_lines.append(line)
    if current_key and current_lines:
        result[current_key] = '\n'.join(current_lines).strip()
    
    # Fallbacks
    if not result['seo_title']:
        result['seo_title'] = f"{title} - {primary_kw.title()}"[:60]
    if not result['meta_description']:
        result['meta_description'] = f"Premium {title} crafted with quality materials. Order now!"[:160]
    if not result['short_description']:
        result['short_description'] = f"Discover the {title} — premium quality, crafted to last."
    if not result['long_description']:
        result['long_description'] = f"<p>Experience the {title}. Premium quality crafted for those who appreciate {primary_kw}.</p>"
    if not result['tags']:
        result['tags'] = ', '.join(keywords.get('secondary', [])[:5])
    result['tags'] = result['tags'].lower()
    
    return result


# ---------- Local Editorial Fallback ----------
class SmartRewriter:
    def __init__(self):
        self.story_hooks = [
            "If you look closely at the details, you'll understand why this piece stands apart from the rest.",
            "There's a reason some pieces get passed down through generations — and it starts with how they're made.",
            "Craftsmanship isn't just a word. It's a commitment to every stitch, every seam, every detail.",
            "Some things get better with age. This is one of them.",
            "When you hold a piece that's built to last, you can feel the difference immediately.",
        ]
        self.education_blocks = [
            "Here's what most people don't realize: the quality of raw materials determines how a product ages. Cheap alternatives may look the same at first, but they never develop the character that quality materials do over time.",
            "There's a reason premium materials cost more. The difference isn't just in how they look new — it's in how they look after years of use.",
            "Every design decision here was made with intention. From the hardware to the lining, nothing was left to chance.",
        ]
        self.feature_subsections = [
            ("Built to Last", "The construction methods used here are the same ones trusted by craftsmen for generations. Every stitch is reinforced, every seam is finished properly, and every detail is checked by hand."),
            ("Materials That Matter", "We could have used cheaper alternatives. We didn't. The materials here were chosen for one reason: they get better with time, not worse."),
            ("The Details Make the Difference", "It's the small things that separate a good product from a great one. The finishing, the hardware, the lining — every element is considered."),
            ("Heritage & Craftsmanship", "This isn't mass-produced. Every piece carries with it a tradition of quality that's increasingly rare in the modern world."),
            ("Designed for Real Life", "This piece was designed to be used, not just admired. It handles everyday wear with grace and looks better doing it."),
        ]
        self.closings = [
            "A piece like this isn't a purchase — it's an investment. One you'll still be using years from now.",
            "Some things are worth doing right. This is one of them.",
            "When you choose quality, you choose a product that will serve you faithfully for years.",
            "This is what happens when craftsmanship meets purpose. Welcome to better.",
        ]

    def generate_content(self, title, raw_desc, category, store_context, specs_text, keywords):
        primary_kw = keywords.get('primary', title.lower())
        secondary = keywords.get('secondary', [])[:5]
        
        # SEO Title
        seo_title = f"{title} | {primary_kw.title()}"
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + '...'
        
        # Meta Description
        hook_line = random.choice(self.story_hooks)
        meta_desc = f"{hook_line[:100]} Premium {primary_kw} built to last. Order now."
        if len(meta_desc) > 160:
            meta_desc = meta_desc[:157] + '...'
        
        # Short Description
        story = random.choice(self.story_hooks)
        short_desc = f"{story} This {primary_kw} is crafted from quality materials with attention to every detail. A piece designed for those who value substance over flash — and one that grows better with time."
        
        # Long Description
        story_open = random.choice(self.story_hooks)
        education = random.choice(self.education_blocks)
        long_parts = [f"<p>{story_open} This {primary_kw} isn't just another product on a shelf — it's a considered piece built for the long haul.</p>"]
        long_parts.append(f"<p>{education}</p>")
        
        for subhead, subtext in random.sample(self.feature_subsections, 3):
            long_parts.append(f"<h3>{subhead}</h3>")
            long_parts.append(f"<p>{subtext}</p>")
        
        long_parts.append(f"<p>{random.choice(self.closings)}</p>")
        long_desc = ''.join(long_parts)
        
        # Additional Info
        additional_info = ""
        spec_lines = []
        for line in (specs_text or "").split('\n')[:15]:
            line = line.strip()
            if ':' in line and len(line) < 120:
                p = line.split(':', 1)
                key = p[0].strip(); val = p[1].strip()
                if 0 < len(key) < 40 and 0 < len(val) < 100:
                    spec_lines.append(f"<li><strong>{key}:</strong> {val}</li>")
        if spec_lines:
            additional_info = f"<ul>{''.join(spec_lines[:10])}</ul>"
        
        # Tags
        tags = ', '.join(secondary[:8]) if secondary else primary_kw
        
        return {
            'seo_title': seo_title,
            'meta_description': meta_desc,
            'short_description': short_desc,
            'long_description': long_desc,
            'additional_information': additional_info,
            'tags': tags
        }


# ---------- Extractors ----------
def safe_get_offer_price(offers):
    if isinstance(offers, dict): return offers.get('price', '')
    elif isinstance(offers, list) and len(offers) > 0:
        first = offers[0]
        if isinstance(first, dict): return first.get('price', '')
    return ''

def safe_get_sku(sku_data):
    if isinstance(sku_data, str): return sku_data
    elif isinstance(sku_data, list) and len(sku_data) > 0: return str(sku_data[0])
    return ''

def safe_get_brand(brand_data):
    if isinstance(brand_data, str): return brand_data
    if isinstance(brand_data, dict): return brand_data.get('name', '')
    if isinstance(brand_data, list) and brand_data: return safe_get_brand(brand_data[0])
    return ''

def format_category(soup, product_data=None, title=None, default="Uncategorized"):
    product_data = product_data or {}
    title_norm = re.sub(r'[^a-z0-9]', '', (title or '').lower())
    def _is_product_title(name):
        if not title_norm or not name: return False
        name_norm = re.sub(r'[^a-z0-9]', '', str(name).lower())
        if not name_norm: return False
        return name_norm == title_norm or (len(name_norm) > 6 and name_norm in title_norm)
    def _is_home(name):
        if not name: return False
        return str(name).strip().lower() in ('home', 'homepage', 'home page', 'main', 'shop', 'store')
    cat_field = product_data.get('category')
    if isinstance(cat_field, str) and cat_field.strip() and not _is_product_title(cat_field): return cat_field.strip()
    if isinstance(cat_field, list):
        cat_names = [c.strip() for c in cat_field if isinstance(c, str) and c.strip() and not _is_product_title(c)]
        if cat_names: return ' > '.join(cat_names)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                if isinstance(entry, dict) and entry.get('@type') == 'BreadcrumbList':
                    items = sorted(entry.get('itemListElement', []), key=lambda x: x.get('position', 0))
                    names = [it.get('name') or (it.get('item', {}).get('name') if isinstance(it.get('item'), dict) else None) for it in items]
                    names = [n for n in names if n]
                    if names and _is_product_title(names[-1]): names = names[:-1]
                    names = [n for n in names if not _is_home(n)]
                    if names: return ' > '.join(names)
        except Exception: pass
    bread = (soup.find(['ul', 'nav', 'ol'], {'class': re.compile(r'breadcrumb', re.I)}) or soup.find(attrs={'aria-label': re.compile(r'breadcrumb', re.I)}))
    if bread:
        links = bread.find_all('a')
        if links:
            categories = [link.get_text(strip=True) for link in links]
            if categories and _is_product_title(categories[-1]): categories = categories[:-1]
            categories = [c for c in categories if not _is_home(c)]
            if categories: return ' > '.join(categories)
    return default

def generate_handle(title):
    handle = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if len(handle) > 200: handle = handle[:200].rsplit('-', 1)[0]
    return handle

def extract_title(soup, product_data, url):
    title = product_data.get('name')
    if not title:
        itemprop = soup.find(attrs={'itemprop': 'name'})
        if itemprop: title = itemprop.get_text(strip=True)
    if not title and soup.find('h1'): title = soup.find('h1').get_text(strip=True)
    if not title:
        og_title = soup.find('meta', property='og:title')
        title = og_title.get('content') if og_title else None
    if not title and soup.find('title'): title = soup.find('title').get_text(strip=True)
    if not title: title = url.split('/')[-1].replace('-', ' ').replace('_', ' ')
    return title.strip()

def extract_raw_description(soup, product_data):
    raw_desc = product_data.get('description') or ''
    if not raw_desc:
        itemprop = soup.find(attrs={'itemprop': 'description'})
        if itemprop: raw_desc = itemprop.get_text(strip=True)
    if not raw_desc:
        woo = soup.find('div', {'class': re.compile(r'woocommerce-product-details__short-description')})
        if woo: raw_desc = woo.get_text(' ', strip=True)
    if not raw_desc:
        magento = soup.find('div', {'class': re.compile(r'product.*description|description.*value', re.I)})
        if magento: raw_desc = magento.get_text(' ', strip=True)
    if not raw_desc:
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        raw_desc = desc_meta.get('content') if desc_meta else ''
    if not raw_desc or len(raw_desc) < 20:
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'): raw_desc = og_desc.get('content')
    return raw_desc

def extract_price(soup, product_data):
    price = safe_get_offer_price(product_data.get('offers'))
    if price: return price
    price_tag = (soup.find(attrs={'itemprop': 'price'}) or soup.find('meta', property='product:price:amount') or soup.find('meta', attrs={'property': 'og:price:amount'}))
    if price_tag:
        val = price_tag.get('content') or price_tag.get_text(strip=True)
        match = re.search(r'[\d,]+\.?\d*', val or '')
        if match: return match.group()
    price_span = soup.find(['span', 'div', 'ins'], {'class': re.compile(r'price|amount|sale-price|regular-price|product-price|current-price', re.I)})
    if price_span:
        match = re.search(r'[\d,]+\.?\d*', price_span.get_text())
        if match: return match.group()
    return '0'

def extract_sku(soup, product_data):
    sku_raw = safe_get_sku(product_data.get('sku'))
    if sku_raw: return sku_raw
    itemprop = soup.find(attrs={'itemprop': 'sku'})
    if itemprop: return itemprop.get_text(strip=True) or itemprop.get('content', '')
    sku_span = (soup.find(attrs={'data-product-sku': True}) or soup.find(['span', 'div'], {'class': re.compile(r'\bsku\b|model|product-id', re.I)}))
    if sku_span:
        text = sku_span.get('data-product-sku') or sku_span.get_text(strip=True)
        if text: return text
    return f"OLD-{random.randint(1000,9999)}"

def extract_vendor(soup, product_data, default="Imported Vendor"):
    brand = safe_get_brand(product_data.get('brand'))
    if brand: return brand
    itemprop = soup.find(attrs={'itemprop': 'brand'})
    if itemprop:
        text = itemprop.get_text(strip=True)
        if text: return text
    meta_brand = soup.find('meta', property='product:brand') or soup.find('meta', attrs={'name': 'author'})
    if meta_brand and meta_brand.get('content'): return meta_brand.get('content')
    return default

def generate_smart_title(original_title, specs_text, color=None, material=None):
    if not specs_text or not original_title: return original_title
    specs_lower = specs_text.lower()
    detected_material = ''
    for mat in ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 'canvas', 'denim', 'wool']:
        if mat in specs_lower and mat not in original_title.lower():
            detected_material = mat.capitalize(); break
    detected_finish = ''
    for fin in ['waxed', 'pull-up', 'semi-aniline', 'aniline', 'distressed', 'vintage', 'washed', 'oiled', 'matte', 'glossy']:
        if fin in specs_lower and fin not in original_title.lower():
            detected_finish = fin.capitalize(); break
    detected_color = ''
    for col in ['black', 'brown', 'tan', 'maroon', 'red', 'blue', 'green', 'grey', 'white', 'charcoal', 'navy', 'olive']:
        if col in specs_lower and col not in original_title.lower():
            detected_color = col.capitalize(); break
    parts = []
    if detected_finish: parts.append(detected_finish)
    if detected_material: parts.append(detected_material)
    parts.append(original_title)
    if detected_color and detected_color not in ' '.join(parts): parts.append(detected_color)
    new_title = ' - '.join(parts)
    new_title = re.sub(r'\s+', ' ', new_title).strip()
    new_title = re.sub(r'-\s*-\s*', '-', new_title)
    if len(new_title) > 80 or len(new_title) < len(original_title) - 5: return original_title
    return new_title

def strip_size_suffix(url):
    try:
        clean = url.split('?')[0]; query = url[len(clean):]
        clean = re.sub(r'(_\d{2,4}x\d{0,4})(@\d+x)?(\.[a-zA-Z]{3,4})$', r'\3', clean)
        clean = re.sub(r'(_(?:small|medium|large|thumb|thumbnail|grande|compact))(\.[a-zA-Z]{3,4})$', r'\2', clean, flags=re.I)
        return clean + query
    except Exception: return url

def try_get_shopify_json_images(url, session, headers):
    urls = []
    try:
        clean_url = url.split('?')[0].rstrip('/')
        json_url = clean_url + '.json' if not clean_url.endswith('.json') else clean_url
        r = session.get(json_url, headers=headers, timeout=15)
        if r.status_code == 200 and 'json' in r.headers.get('Content-Type', ''):
            data = r.json()
            for img in data.get('product', {}).get('images', []) or []:
                if img.get('src'): urls.append(img['src'])
    except Exception: pass
    return urls

def extract_gallery_images_html(soup, base_url_domain):
    skip_words = ['logo', 'icon-', 'sprite', 'placeholder', 'payment', 'visa', 'mastercard', 'paypal', 'spinner', 'avatar']
    attrs_to_check = ['data-zoom-image', 'data-large_image', 'data-original', 'data-lazy-src', 'data-src', 'data-srcset', 'srcset', 'src']
    def collect_from(tags):
        found = []
        for tag in tags:
            for attr in attrs_to_check:
                val = tag.get(attr)
                if not val: continue
                if attr in ('srcset', 'data-srcset'):
                    candidates = [p.strip().split(' ')[0] for p in val.split(',') if p.strip()]
                    val = candidates[-1] if candidates else None
                if not val: continue
                if val.startswith('//'): val = 'https:' + val
                full = urljoin(base_url_domain, val)
                if not full.startswith('http') or full.lower().endswith('.svg'): continue
                if any(word in full.lower() for word in skip_words): continue
                full = strip_size_suffix(full)
                if full not in found: found.append(full)
        return found
    gallery_selectors = [
        {'class': re.compile(r'woocommerce-product-gallery', re.I)},
        {'class': re.compile(r'flex-control-thumbs', re.I)},
        {'class': re.compile(r'fotorama|gallery-placeholder', re.I)},
        {'class': re.compile(r'product[-_]?(gallery|images|media|slider|carousel)', re.I)},
        {'class': re.compile(r'swiper-wrapper|slick-track|splide__track', re.I)},
    ]
    gallery_urls = []
    for sel in gallery_selectors:
        for container in soup.find_all(['div', 'ul', 'section'], sel):
            gallery_urls.extend(collect_from(container.find_all(['img', 'source', 'a'])))
    page_urls = collect_from(soup.find_all(['img', 'source', 'a']))
    combined = []
    for url in gallery_urls + page_urls:
        if url not in combined: combined.append(url)
    return combined

def collect_gallery_images(url, soup, base_url_domain, session, headers, product_data, max_images):
    combined = []
    if product_data.get('image'):
        img_field = product_data['image']
        combined.extend(img_field if isinstance(img_field, list) else [img_field])
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'): combined.append(og_img.get('content'))
    combined.extend(try_get_shopify_json_images(url, session, headers))
    combined.extend(extract_gallery_images_html(soup, base_url_domain))
    seen = set(); final = []
    for img in combined:
        if not img or not img.startswith('http'): continue
        cleaned = strip_size_suffix(img)
        key = cleaned.split('?')[0]
        if key not in seen:
            seen.add(key); final.append(cleaned)
        if len(final) >= max_images: break
    return final

def edit_image(img_data, filename, config):
    try:
        img = Image.open(BytesIO(img_data))
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        width, height = img.size; final_img = img
        if config.get('enable_flip', True): final_img = final_img.transpose(Image.FLIP_LEFT_RIGHT)
        if config.get('enable_enhance', True):
            final_img = ImageEnhance.Brightness(final_img).enhance(random.uniform(0.92, 1.08))
            final_img = ImageEnhance.Contrast(final_img).enhance(random.uniform(0.95, 1.05))
        if config.get('enable_rounded', False):
            mask = Image.new('L', final_img.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=30, fill=255)
            final_img.putalpha(mask); bg = Image.new('RGB', final_img.size, (255, 255, 255))
            bg.paste(final_img, mask=final_img.split()[-1]); final_img = bg
        if config.get('enable_shadow', False):
            so, sb = 10, 15
            shadow = Image.new('RGBA', (width + so*2, height + so*2), (0,0,0,0))
            ImageDraw.Draw(shadow).rectangle((so, so, width + so, height + so), fill=(0,0,0,30))
            shadow = shadow.filter(ImageFilter.GaussianBlur(sb))
            bg = Image.new('RGBA', (width + so*2, height + so*2), (255,255,255,0))
            bg.paste(shadow, (0,0), shadow); bg.paste(final_img, (so, so)); final_img = bg.convert('RGB')
        if config.get('enable_logo', False):
            lb = config.get('corner_logo_bytes')
            if lb:
                try:
                    logo = Image.open(BytesIO(lb)); logo.thumbnail((int(width * 0.15), int(height * 0.15)), Image.LANCZOS)
                    final_img.paste(logo, (20, 20), logo if logo.mode == 'RGBA' else None)
                except: pass
        if config.get('enable_watermark', False):
            opacity = config.get('watermark_opacity', 20) / 100
            wm_type = config.get('watermark_type', 'Text')
            wm_size = config.get('watermark_size', 15)
            if final_img.mode != 'RGBA': final_img = final_img.convert('RGBA')
            wm_layer = Image.new('RGBA', final_img.size, (0, 0, 0, 0)); draw = ImageDraw.Draw(wm_layer)
            if wm_type == 'Text':
                txt = config.get('watermark_text', 'Brand')
                fs = int(min(width, height) * (wm_size / 100))
                try:
                    from PIL import ImageFont; font = ImageFont.truetype("arial.ttf", fs)
                except: font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), txt, font=font)
                pos = ((width - (bbox[2]-bbox[0])) // 2, (height - (bbox[3]-bbox[1])) // 2)
                draw.text(pos, txt, font=font, fill=(255, 255, 255, int(255 * opacity)))
            else:
                wlb = config.get('watermark_logo_bytes')
                if wlb:
                    try:
                        wl = Image.open(BytesIO(wlb)); tw = int(width * (wm_size / 100)); th = int(wl.height * (tw / wl.width))
                        wl = wl.resize((tw, th), Image.LANCZOS)
                        if wl.mode != 'RGBA': wl = wl.convert('RGBA')
                        alpha = wl.split()[3].point(lambda p: int(p * opacity)); wl.putalpha(alpha)
                        wm_layer.paste(wl, ((width - tw) // 2, (height - th) // 2), wl)
                    except: pass
            final_img = Image.alpha_composite(final_img, wm_layer).convert('RGB')
        if config.get('enable_border', False):
            final_img = ImageOps.expand(final_img, border=10, fill=config.get('border_color', '#000000'))
            width, height = final_img.size
        if config.get('enable_gradient', False):
            c1 = config.get('grad_color_1', '#FF5733').lstrip('#')
            c2 = config.get('grad_color_2', '#33FF57').lstrip('#')
            c1_rgb = tuple(int(c1[i:i+2], 16) for i in (0, 2, 4)); c2_rgb = tuple(int(c2[i:i+2], 16) for i in (0, 2, 4))
            fh = int(height * 0.1); strip = Image.new('RGB', (width, fh))
            for x in range(width):
                r = x / width
                strip.paste(tuple(int(c1_rgb[i] + (c2_rgb[i] - c1_rgb[i]) * r) for i in range(3)), (x, 0, x+1, fh))
            final_img.paste(strip, (0, height - fh))
        new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
        if not new_filename.lower().endswith(('.jpg', '.jpeg')): new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
        buffer = BytesIO(); final_img.save(buffer, format='JPEG', quality=70, optimize=True); buffer.seek(0)
        return new_filename, buffer.getvalue()
    except Exception:
        try:
            new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
            if not new_filename.lower().endswith(('.jpg', '.jpeg')): new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
            return new_filename, img_data
        except: return None, None

def extract_variations(product_data, soup, base_url_domain, price):
    variations = []; seen_attrs = set()
    offers = product_data.get('offers')
    if isinstance(offers, list) and len(offers) > 1:
        for offer in offers:
            if not isinstance(offer, dict): continue
            var_attrs = {}
            if 'size' in offer: var_attrs['Size'] = offer['size']
            if 'color' in offer: var_attrs['Color'] = offer['color']
            if 'material' in offer: var_attrs['Material'] = offer['material']
            if not var_attrs: var_attrs['Option'] = f'Variant {len(variations)+1}'
            k = tuple(sorted(var_attrs.items()))
            if k not in seen_attrs:
                seen_attrs.add(k)
                variations.append({'sku': offer.get('sku', ''), 'price': offer.get('price', price), 'attrs': var_attrs, 'image': offer.get('image', '')})
    if not variations:
        size_select = soup.find('select', {'class': re.compile(r'size|variant', re.I)})
        if size_select:
            for opt in size_select.find_all('option'):
                val = opt.get('value', '').strip()
                if val and val.lower() not in ('', 'select', 'choose'):
                    var_attrs = {'Size': val}
                    k = tuple(sorted(var_attrs.items()))
                    if k not in seen_attrs:
                        seen_attrs.add(k)
                        variations.append({'sku': '', 'price': price, 'attrs': var_attrs, 'image': ''})
    seen = set(); unique = []
    for v in variations:
        k = tuple(sorted(v['attrs'].items()))
        if k not in seen: seen.add(k); unique.append(v)
    return unique

def scrape_product(url, session, config, ai_status_placeholder=None):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for attempt in range(2):
        try:
            resp = session.get(url, headers=headers, timeout=25); resp.raise_for_status(); break
        except:
            if attempt == 0: time.sleep(5)
            else: return None, None, f"Failed"
    soup = BeautifulSoup(resp.text, 'lxml')
    base_url_domain = f"{resp.url.split('/')[0]}//{resp.url.split('/')[2]}"
    product_data = {}
    def is_product_type(dt):
        if isinstance(dt, str): return dt == 'Product'
        if isinstance(dt, list): return 'Product' in dt
        return False
    for script in soup.find_all('script', type='application/ld+json'):
        try: data = json.loads(script.string)
        except: continue
        if isinstance(data, dict):
            if is_product_type(data.get('@type')): product_data = data; break
            if '@graph' in data:
                for e in data['@graph']:
                    if isinstance(e, dict) and is_product_type(e.get('@type')): product_data = data; break
                if product_data: break
        if isinstance(data, list):
            for e in data:
                if isinstance(e, dict) and is_product_type(e.get('@type')): product_data = e; break
            if product_data: break
    original_title = extract_title(soup, product_data, url)
    raw_desc = extract_raw_description(soup, product_data) or original_title
    category_str = format_category(soup, product_data, original_title)
    price = extract_price(soup, product_data)
    sku_raw = extract_sku(soup, product_data)
    vendor = extract_vendor(soup, product_data)
    specs_text = raw_desc
    specs_section = soup.find(['div', 'ul', 'table'], {'class': re.compile(r'spec|attribute|detail|features', re.I)})
    if specs_section: specs_text = specs_section.get_text('\n', strip=True)
    keywords = extract_keywords(original_title, category_str, specs_text)
    color = ''; material = ''
    cm = re.search(r'color[:\s]+([a-zA-Z]+)', raw_desc, re.I)
    if cm: color = cm.group(1).capitalize()
    for mat in ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 'canvas', 'denim', 'wool']:
        if mat in raw_desc.lower(): material = mat.capitalize(); break
    if config.get('smart_title_enabled', True): title = generate_smart_title(original_title, specs_text, color, material)
    else: title = original_title
    
    ai_content = None; ai_error = None
    if config.get('ai_enabled', False) and config.get('gemini_api_key'):
        ai_content, ai_error = generate_ai_content(
            title, specs_text, category_str, config.get('store_context', ''),
            keywords, config.get('gemini_api_key'),
            config.get('gemini_model', 'gemini-2.5-flash'),
            config.get('ai_custom_prompt', '')
        )
        if ai_content:
            time.sleep(1.5)  # Inter-request delay
        elif ai_error and ai_status_placeholder:
            ai_status_placeholder.warning(f"⚠️ AI failed for '{title[:30]}...': {ai_error} — Using local fallback.")
            time.sleep(0.5)
    
    rewriter = SmartRewriter()
    content = ai_content if ai_content else rewriter.generate_content(title, raw_desc, category_str, config.get('store_context', ''), specs_text, keywords)
    seo_title = content.get('seo_title', title)
    meta_desc = content.get('meta_description', '')
    short_desc = content.get('short_description', '')
    long_desc = content.get('long_description', '')
    additional_info = content.get('additional_information', '')
    tags = content.get('tags', 'Imported')
    rand_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    parent_sku = f"CUSTOM-{rand_suffix}-{sku_raw}"
    max_images = config.get('max_gallery_images', 10)
    raw_image_urls = collect_gallery_images(url, soup, base_url_domain, session, headers, product_data, max_images)
    image_zip_data = {}; processed_image_urls = []
    if config.get('edit_images', False):
        for img_url in raw_image_urls:
            try:
                ir = session.get(img_url, timeout=15)
                if ir.status_code == 200:
                    nn, ed = edit_image(ir.content, img_url, config)
                    if nn and ed: image_zip_data[nn] = ed; processed_image_urls.append(nn)
                    else: processed_image_urls.append(img_url)
                else: processed_image_urls.append(img_url)
            except: processed_image_urls.append(img_url)
    else: processed_image_urls = raw_image_urls
    main_image = processed_image_urls[0] if processed_image_urls else ''
    additional_images = processed_image_urls[1:] if len(processed_image_urls) > 1 else []
    handle = generate_handle(title)
    variations_data = extract_variations(product_data, soup, base_url_domain, price)
    is_variable = len(variations_data) > 1
    opt1_name = opt2_name = opt3_name = ''
    if variations_data:
        an = set()
        for v in variations_data: an.update(v['attrs'].keys())
        an = sorted(list(an))
        if len(an) > 0: opt1_name = an[0]
        if len(an) > 1: opt2_name = an[1]
        if len(an) > 2: opt3_name = an[2]
    parent_row = {
        'Title': title, 'URL handle': handle, 'Description': long_desc, 'Vendor': vendor,
        'Product category': category_str,
        'Type': category_str.split('>')[-1].strip() if category_str and category_str != 'Uncategorized' else '',
        'Tags': tags, 'Published on online store': 'TRUE', 'Status': 'active',
        'SKU': '' if is_variable else parent_sku,
        'Barcode': '' if is_variable else random.randint(1000000000, 9999999999),
        'Option1 name': opt1_name, 'Option1 value': '', 'Option1 Linked To': 'Option1 name' if opt1_name else '',
        'Option2 name': opt2_name, 'Option2 value': '', 'Option2 Linked To': 'Option2 name' if opt2_name else '',
        'Option3 name': opt3_name, 'Option3 value': '', 'Option3 Linked To': 'Option3 name' if opt3_name else '',
        'Price': '' if is_variable else price, 'Compare-at price': '', 'Cost per item': '',
        'Charge tax': 'TRUE', 'Tax code': '',
        'Unit price total measure': '', 'Unit price total measure unit': '',
        'Unit price base measure': '', 'Unit price base measure unit': '',
        'Inventory tracker': '' if is_variable else 'shopify',
        'Inventory quantity': '' if is_variable else 10,
        'Continue selling when out of stock': '' if is_variable else 'DENY',
        'Weight value (grams)': '' if is_variable else 150, 'Weight unit for display': '' if is_variable else 'g',
        'Requires shipping': 'TRUE', 'Fulfillment service': 'manual' if not is_variable else '',
        'Product image URL': main_image, 'Image position': '1', 'Image alt text': title,
        'Variant image URL': '', 'Gift card': 'FALSE',
        'SEO title': seo_title, 'SEO description': meta_desc,
        'Short description': short_desc, 'Additional information': additional_info,
        'Color (product.metafields.shopify.color-pattern)': '',
        'Google Shopping / Google product category': category_str,
        'Google Shopping / Gender': '', 'Google Shopping / Age group': '',
        'Google Shopping / Manufacturer part number (MPN)': '',
        'Google Shopping / Ad group name': '', 'Google Shopping / Ads labels': '',
        'Google Shopping / Condition': '', 'Google Shopping / Custom product': '',
        'Google Shopping / Custom label 0': '', 'Google Shopping / Custom label 1': '',
        'Google Shopping / Custom label 2': '', 'Google Shopping / Custom label 3': '',
        'Google Shopping / Custom label 4': ''
    }
    image_rows = []
    for idx, iu in enumerate(additional_images, start=2):
        ir = {c: '' for c in SHOPIFY_COLUMNS}
        ir['URL handle'] = handle; ir['Product image URL'] = iu; ir['Image position'] = str(idx)
        image_rows.append(ir)
    variant_rows = []
    if variations_data and is_variable:
        for idx, var in enumerate(variations_data):
            vs = var.get('sku', '') or f"{parent_sku}-V{idx+1}"
            vp = var.get('price', price); va = var['attrs']
            a1 = list(va.values())[0] if len(va) > 0 else ''
            a2 = list(va.values())[1] if len(va) > 1 else ''
            a3 = list(va.values())[2] if len(va) > 2 else ''
            vr = {
                'Title': '', 'URL handle': handle, 'Description': '', 'Vendor': '', 'Product category': '',
                'Type': '', 'Tags': '', 'Published on online store': 'TRUE', 'Status': 'active',
                'SKU': vs, 'Barcode': random.randint(1000000000, 9999999999),
                'Option1 name': '', 'Option1 value': a1, 'Option1 Linked To': '',
                'Option2 name': '', 'Option2 value': a2, 'Option2 Linked To': '',
                'Option3 name': '', 'Option3 value': a3, 'Option3 Linked To': '',
                'Price': vp, 'Compare-at price': '', 'Cost per item': '', 'Charge tax': 'TRUE', 'Tax code': '',
                'Unit price total measure': '', 'Unit price total measure unit': '', 'Unit price base measure': '', 'Unit price base measure unit': '',
                'Inventory tracker': 'shopify', 'Inventory quantity': 10, 'Continue selling when out of stock': 'DENY',
                'Weight value (grams)': 150, 'Weight unit for display': 'g', 'Requires shipping': 'TRUE',
                'Fulfillment service': 'manual', 'Product image URL': '', 'Image position': '',
                'Image alt text': '', 'Variant image URL': var.get('image', ''), 'Gift card': 'FALSE',
                'SEO title': '', 'SEO description': '', 'Short description': '', 'Additional information': '',
                'Color (product.metafields.shopify.color-pattern)': a2 if opt2_name.lower() == 'color' else a1 if opt1_name.lower() == 'color' else '',
                'Google Shopping / Google product category': '', 'Google Shopping / Gender': '',
                'Google Shopping / Age group': '', 'Google Shopping / Manufacturer part number (MPN)': f'MPN-{vs}',
                'Google Shopping / Ad group name': '', 'Google Shopping / Ads labels': '',
                'Google Shopping / Condition': 'New', 'Google Shopping / Custom product': '',
                'Google Shopping / Custom label 0': '', 'Google Shopping / Custom label 1': '',
                'Google Shopping / Custom label 2': '', 'Google Shopping / Custom label 3': '', 'Google Shopping / Custom label 4': ''
            }
            variant_rows.append(vr)
    if not variations_data:
        parent_row['SKU'] = parent_sku; parent_row['Price'] = price
        parent_row['Inventory tracker'] = 'shopify'; parent_row['Inventory quantity'] = 10
        parent_row['Continue selling when out of stock'] = 'DENY'
        parent_row['Weight value (grams)'] = 150; parent_row['Weight unit for display'] = 'g'
        parent_row['Fulfillment service'] = 'manual'; parent_row['Barcode'] = random.randint(1000000000, 9999999999)
    final_rows = [parent_row] + image_rows + variant_rows
    return final_rows, image_zip_data, None

def group_rows_by_product(all_rows):
    groups = []; current = []
    for row in all_rows:
        if row.get('Title'):
            if current: groups.append(current)
            current = [row]
        else:
            if current: current.append(row)
    if current: groups.append(current)
    return groups

def build_woocommerce_rows(product_rows, config):
    if not product_rows: return []
    parent = product_rows[0]; handle = parent.get('URL handle', '')
    images = [parent.get('Product image URL', '')] if parent.get('Product image URL') else []
    vrs = []
    for r in product_rows[1:]:
        if not r.get('SKU') and r.get('Product image URL'): images.append(r['Product image URL'])
        elif r.get('SKU'): vrs.append(r)
    images_str = ', '.join([i for i in images if i])
    has_v = len(vrs) > 0
    a1n = parent.get('Option1 name', ''); a2n = parent.get('Option2 name', ''); a3n = parent.get('Option3 name', '')
    a1v = sorted({r['Option1 value'] for r in vrs if r.get('Option1 value')}) if a1n else []
    a2v = sorted({r['Option2 value'] for r in vrs if r.get('Option2 value')}) if a2n else []
    a3v = sorted({r['Option3 value'] for r in vrs if r.get('Option3 value')}) if a3n else []
    wp = {c: '' for c in WOOCOMMERCE_COLUMNS}
    wp.update({
        'Type': 'variable' if has_v else 'simple', 'SKU': parent.get('SKU', ''),
        'Name': parent.get('Title', ''), 'Published': '1' if parent.get('Published on online store') == 'TRUE' else '0',
        'Is featured?': '0', 'Visibility in catalog': 'visible',
        'Short description': parent.get('Short description', ''),
        'Description': parent.get('Description', ''),
        'Additional information': parent.get('Additional information', ''),
        'Tax status': 'taxable' if parent.get('Charge tax') == 'TRUE' else 'none',
        'In stock?': '1', 'Stock': parent.get('Inventory quantity', ''),
        'Backorders allowed?': '0' if parent.get('Continue selling when out of stock') == 'DENY' else '1',
        'Weight (kg)': parent.get('Weight value (grams)', ''), 'Allow customer reviews?': '1',
        'Regular price': '' if has_v else parent.get('Price', ''),
        'Categories': parent.get('Product category', ''), 'Tags': parent.get('Tags', ''),
        'Images': images_str,
        'Attribute 1 name': a1n, 'Attribute 1 value(s)': ', '.join(a1v), 'Attribute 1 visible': '1' if a1n else '', 'Attribute 1 global': '0',
        'Attribute 2 name': a2n, 'Attribute 2 value(s)': ', '.join(a2v), 'Attribute 2 visible': '1' if a2n else '', 'Attribute 2 global': '0',
        'Attribute 3 name': a3n, 'Attribute 3 value(s)': ', '.join(a3v), 'Attribute 3 visible': '1' if a3n else '', 'Attribute 3 global': '0',
        'Meta: _yoast_wpseo_title': parent.get('SEO title', ''),
        'Meta: _yoast_wpseo_metadesc': parent.get('SEO description', ''),
    })
    rows = [wp]
    if has_v:
        for r in vrs:
            wv = {c: '' for c in WOOCOMMERCE_COLUMNS}
            wv.update({
                'Type': 'variation', 'SKU': r.get('SKU', ''),
                'Name': f"{parent.get('Title', '')} - Variation", 'Published': '1',
                'Visibility in catalog': 'visible',
                'Tax status': 'taxable' if r.get('Charge tax') == 'TRUE' else 'none',
                'In stock?': '1', 'Stock': r.get('Inventory quantity', ''),
                'Backorders allowed?': '0' if r.get('Continue selling when out of stock') == 'DENY' else '1',
                'Weight (kg)': r.get('Weight value (grams)', ''),
                'Regular price': r.get('Price', ''),
                'Images': r.get('Variant image URL', ''), 'Parent': handle,
                'Attribute 1 name': a1n, 'Attribute 1 value(s)': r.get('Option1 value', ''),
                'Attribute 2 name': a2n, 'Attribute 2 value(s)': r.get('Option2 value', ''),
                'Attribute 3 name': a3n, 'Attribute 3 value(s)': r.get('Option3 value', ''),
            })
            rows.append(wv)
    return rows

def process_batch(urls, config, session, ai_status):
    all_rows = []; image_data = {}; failed = []
    for url in urls:
        results, img_data, error = scrape_product(url, session, config, ai_status)
        if results:
            all_rows.extend(results)
            if img_data: image_data.update(img_data)
        else: failed.append(url)
    return all_rows, image_data, failed

# ============================================================
# NOW THE UI
# ============================================================
st.set_page_config(page_title="Universal Extractor V6.2", page_icon="🛒")
st.title("🛒 UNIVERSAL EXTRACTOR V6.2 (EDITORIAL QUALITY)")
st.markdown("**Gemini AI | Editorial Style | Keyword-Mapped SEO | Variable Products**")

st.components.v1.html("""<script>setInterval(function(){console.log("🛡️");},2000);</script>""", height=0)

# ---------- AI Settings ----------
st.subheader("🤖 AI Content Settings")
with st.expander("⚙️ Configure Gemini AI", expanded=True):
    st.checkbox("🚀 Enable Gemini AI Content Generation", key="ai_enabled", value=False)
    if st.session_state.get("ai_enabled", False):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.text_input("🔑 Gemini API Key", type="password", key="gemini_api_key")
        with c2:
            st.selectbox("Model", ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-pro"], key="gemini_model")
        if st.button("🧪 Test Gemini API"):
            k = st.session_state.get("gemini_api_key", "").strip()
            if not k: st.error("❌ API key daalo pehle.")
            else:
                with st.spinner("Testing..."):
                    ok, msg = test_gemini_api(k, st.session_state.get("gemini_model", "gemini-2.5-flash"))
                    if ok: st.success(f"✅ {msg}")
                    else: st.error(f"❌ {msg}")
        st.text_area("✍️ Custom Brand Voice / Prompt (optional)", key="ai_custom_prompt",
                     placeholder="e.g. Write in luxurious, aspirational tone. Focus on craftsmanship and heritage.",
                     height=100)
        st.caption("⚠️ Free tier: 15 req/min. Tool retries 503/429 automatically + falls back to next model.")
    else:
        if 'gemini_api_key' in st.session_state: st.session_state.gemini_api_key = ""

# ---------- Branding Studio ----------
st.subheader("🎨 Branding Studio (Optional)")
with st.expander("⚙️ Configure Image Branding", expanded=False):
    ca, cb = st.columns(2)
    with ca:
        st.checkbox("🖼️ Add Corner Logo", key="enable_logo", value=False)
        if st.session_state.get("enable_logo", False):
            st.file_uploader("Upload Logo", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
        st.checkbox("🔤 Add Watermark", key="enable_watermark", value=False)
        if st.session_state.get("enable_watermark", False):
            st.radio("Type", ["Text", "Image Logo"], key="watermark_type", horizontal=True)
            st.slider("Size (%)", 5, 50, 15, key="watermark_size")
            st.slider("Opacity (%)", 10, 80, 20, key="watermark_opacity")
            if st.session_state.get("watermark_type") == "Text":
                st.text_input("Watermark Text", "YourBrand.com", key="watermark_text")
            else:
                st.file_uploader("Upload WM Logo", type=['png', 'jpg', 'jpeg'], key="watermark_logo_uploader")
        st.checkbox("🌑 Drop Shadow", key="enable_shadow", value=False)
        st.checkbox("🔄 Rounded Corners", key="enable_rounded", value=False)
        st.checkbox("🔄 Mirror Flip", key="enable_flip", value=True)
    with cb:
        st.checkbox("🖼️ Add Border", key="enable_border", value=False)
        if st.session_state.get("enable_border", False): st.color_picker("Border Color", "#000000", key="border_color")
        st.checkbox("🌈 Add Gradient Frame", key="enable_gradient", value=False)
        if st.session_state.get("enable_gradient", False):
            st.color_picker("Gradient 1", "#FF5733", key="grad_color_1")
            st.color_picker("Gradient 2", "#33FF57", key="grad_color_2")
        st.checkbox("✨ Brightness/Contrast", key="enable_enhance", value=True)

# ---------- Content Settings ----------
st.subheader("📝 Content Settings")
with st.expander("⚙️ Configure Content", expanded=False):
    cc1, cc2 = st.columns(2)
    with cc1:
        st.text_area("🏪 Store / Niche Context", key="ai_store_context",
                     placeholder="e.g. Premium leather jackets, heritage fashion",
                     height=80)
        st.checkbox("✨ Auto-Generate Unique Product Title", key="smart_title_enabled", value=True)
    with cc2:
        st.slider("🖼️ Max Gallery Images", 3, 20, 10, key="max_gallery_images")

# ---------- Inputs ----------
st.subheader("📥 Input & Controls")
edit_images = st.checkbox("🖌️ Enable Image Editing", value=True)
export_format = st.radio("📦 Export Format", ["🛍️ Shopify CSV", "🛒 WooCommerce CSV"],
                         key="export_format", horizontal=True)
ci1, ci2 = st.columns([3, 1])
with ci1: urls_input = st.text_area("🔗 Product URLs (one per line):", height=150)
with ci2: base_url = st.text_input("🌐 Base URL:", placeholder="https://domain.com/wp-content/uploads/")

# ---------- Config Getter ----------
def get_branding_config():
    clb = None
    if st.session_state.get("enable_logo", False):
        u = st.session_state.get("logo_uploader", None)
        if u is not None: clb = u.getvalue()
    wlb = None
    if st.session_state.get("enable_watermark", False) and st.session_state.get("watermark_type") == "Image Logo":
        u = st.session_state.get("watermark_logo_uploader", None)
        if u is not None: wlb = u.getvalue()
    return {
        'edit_images': edit_images,
        'enable_flip': st.session_state.get("enable_flip", True),
        'enable_enhance': st.session_state.get("enable_enhance", True),
        'enable_logo': st.session_state.get("enable_logo", False),
        'corner_logo_bytes': clb,
        'enable_watermark': st.session_state.get("enable_watermark", False),
        'watermark_type': st.session_state.get("watermark_type", "Text"),
        'watermark_text': st.session_state.get("watermark_text", "YourBrand.com"),
        'watermark_logo_bytes': wlb,
        'watermark_size': st.session_state.get("watermark_size", 15),
        'watermark_opacity': st.session_state.get("watermark_opacity", 20),
        'enable_border': st.session_state.get("enable_border", False),
        'border_color': st.session_state.get("border_color", "#000000"),
        'enable_gradient': st.session_state.get("enable_gradient", False),
        'grad_color_1': st.session_state.get("grad_color_1", "#FF5733"),
        'grad_color_2': st.session_state.get("grad_color_2", "#33FF57"),
        'enable_shadow': st.session_state.get("enable_shadow", False),
        'enable_rounded': st.session_state.get("enable_rounded", False),
        'max_gallery_images': st.session_state.get("max_gallery_images", 10),
        'store_context': st.session_state.get("ai_store_context", ""),
        'export_format': 'woocommerce' if st.session_state.get("export_format", "🛍️ Shopify CSV").startswith("🛒") else 'shopify',
        'smart_title_enabled': st.session_state.get("smart_title_enabled", True),
        'ai_enabled': st.session_state.get("ai_enabled", False),
        'gemini_api_key': st.session_state.get("gemini_api_key", "").strip(),
        'gemini_model': st.session_state.get("gemini_model", "gemini-2.5-flash"),
        'ai_custom_prompt': st.session_state.get("ai_custom_prompt", "").strip(),
    }

# ---------- Main Processing ----------
if st.button("🚀 Generate CSV + ZIP (Batch Mode)", type="primary") or st.session_state.is_processing:
    if not st.session_state.is_processing and urls_input.strip():
        urls_list = [u.strip() for u in re.split(r'[,\s]+', urls_input) if u.strip().startswith('http')]
        if not urls_list: st.error("❌ Valid URL nahi mili.")
        else:
            st.session_state.total_urls = len(urls_list)
            st.session_state.all_urls = urls_list
            st.session_state.batch_index = 0
            st.session_state.all_final_rows = []
            st.session_state.all_image_data = {}
            st.session_state.all_failed = []
            st.session_state.is_processing = True
            st.rerun()
    if st.session_state.is_processing:
        ul = st.session_state.all_urls
        bi = st.session_state.batch_index
        tt = st.session_state.total_urls
        s = bi * BATCH_SIZE
        e = min(s + BATCH_SIZE, tt)
        cb = ul[s:e]
        if s < tt:
            st_text = st.empty(); pb = st.progress(0); ai_status = st.empty()
            st_text.info(f"⏳ Batch {bi+1}/{(tt // BATCH_SIZE) + 1} ({s+1}-{e}/{tt})...")
            config = get_branding_config(); session = requests.Session()
            br, bimg, bf = process_batch(cb, config, session, ai_status)
            st.session_state.all_final_rows.extend(br)
            st.session_state.all_image_data.update(bimg)
            st.session_state.all_failed.extend(bf)
            st.session_state.batch_index += 1
            pb.progress(1.0)
            st_text.success(f"✅ Batch {bi+1} done. Total: {len(st.session_state.all_final_rows)}")
            if st.session_state.batch_index * BATCH_SIZE < tt:
                time.sleep(2); st.rerun()
            else:
                st.session_state.is_processing = False
                if base_url:
                    for row in st.session_state.all_final_rows:
                        for col in ['Product image URL', 'Variant image URL']:
                            ic = row.get(col, '')
                            if ic:
                                imgs = ic.split(', '); ni = []
                                for im in imgs:
                                    ni.append(f"{base_url.rstrip('/')}/{im.lstrip('/')}" if not im.startswith('http') else im)
                                row[col] = ', '.join(ni)
                config = get_branding_config()
                if config.get('export_format') == 'woocommerce':
                    pg = group_rows_by_product(st.session_state.all_final_rows)
                    wr = []
                    for g in pg: wr.extend(build_woocommerce_rows(g, config))
                    df = pd.DataFrame(wr, columns=WOOCOMMERCE_COLUMNS)
                    for c in WOOCOMMERCE_COLUMNS:
                        if c not in df.columns: df[c] = ''
                    df = df[WOOCOMMERCE_COLUMNS]
                else:
                    df = pd.DataFrame(st.session_state.all_final_rows, columns=SHOPIFY_COLUMNS)
                    for c in SHOPIFY_COLUMNS:
                        if c not in df.columns: df[c] = ''
                    df = df[SHOPIFY_COLUMNS]
                buf = StringIO(); df.to_csv(buf, index=False, encoding='utf-8-sig')
                st.session_state.csv_data = buf.getvalue()
                st.session_state.df_preview = df
                st.session_state.failed_urls = st.session_state.all_failed
                st.session_state.total_rows = len(st.session_state.all_final_rows)
                st.session_state.is_ready = True
                st.session_state.has_zip = False
                st.session_state.zip_data = None
                st.rerun()
        else:
            st.session_state.is_processing = False

# ---------- Download Section ----------
if st.session_state.is_ready:
    st.success(f"🎯 {st.session_state.total_rows} rows! {len(st.session_state.failed_urls)} failed.")
    if st.session_state.failed_urls:
        with st.expander(f"⚠️ Failed URLs ({len(st.session_state.failed_urls)})"):
            st.write('\n'.join(st.session_state.failed_urls))
    st.subheader("📊 Preview (First 10)")
    st.dataframe(st.session_state.df_preview.head(10))
    ca, cb, cc = st.columns([2, 2, 1])
    with ca:
        is_woo = st.session_state.get("export_format", "🛍️ Shopify CSV").startswith("🛒")
        st.download_button(
            label=f"⬇️ Download {'WooCommerce' if is_woo else 'Shopify'} CSV",
            data=st.session_state.csv_data,
            file_name=f"{'woocommerce' if is_woo else 'shopify'}_import_{int(time.time())}.csv",
            mime="text/csv", use_container_width=True, key="csv_download")
    with cb:
        if st.session_state.has_zip and st.session_state.zip_data:
            zm = len(st.session_state.zip_data) / (1024 * 1024)
            st.download_button(
                label=f"⬇️ Download Images ZIP ({zm:.1f} MB)",
                data=st.session_state.zip_data,
                file_name=f"branded_images_{int(time.time())}.zip",
                mime="application/zip", use_container_width=True, key="zip_download")
        else:
            if st.button("🔄 Generate ZIP (Images)", use_container_width=True):
                with st.spinner("📦 Compressing..."):
                    pb = st.progress(0); stxt = st.empty()
                    for i in range(101):
                        if i % 20 == 0: stxt.text(f"Compressing... {i}%")
                        pb.progress(i / 100); time.sleep(0.05)
                    zb = BytesIO()
                    with zipfile.ZipFile(zb, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for fn, fd in st.session_state.all_image_data.items(): zf.writestr(fn, fd)
                    zb.seek(0); zr = zb.getvalue(); zm = len(zr) / (1024 * 1024)
                    if zm > 1000: st.error(f"❌ ZIP {zm:.1f} MB > 1000 MB.")
                    else:
                        st.session_state.zip_data = zr; st.session_state.has_zip = True
                        st.rerun()
            st.info("ℹ️ Click 'Generate ZIP'")
    with cc:
        if st.button("🔄 Reset", use_container_width=True):
            for k in ['is_ready', 'csv_data', 'zip_data', 'df_preview', 'failed_urls', 'total_rows', 'has_zip',
                      'batch_index', 'all_final_rows', 'all_image_data', 'all_failed', 'total_urls', 'is_processing', 'all_urls']:
                if k in st.session_state:
                    if k in ['total_rows', 'batch_index', 'total_urls']: st.session_state[k] = 0
                    elif k in ['failed_urls', 'all_failed']: st.session_state[k] = []
                    elif k == 'all_image_data': st.session_state[k] = {}
                    elif k == 'all_final_rows': st.session_state[k] = []
                    elif k in ['is_ready', 'has_zip', 'is_processing']: st.session_state[k] = False
                    else: st.session_state[k] = None
            st.rerun()

st.caption("🛒 V6.2 | Editorial Quality | AI Retry + Fallback | Variable Products | Additional Info")
