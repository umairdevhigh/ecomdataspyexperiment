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
if 'is_ready' not in st.session_state:
    st.session_state.is_ready = False
if 'csv_data' not in st.session_state:
    st.session_state.csv_data = None
if 'zip_data' not in st.session_state:
    st.session_state.zip_data = None
if 'df_preview' not in st.session_state:
    st.session_state.df_preview = None
if 'failed_urls' not in st.session_state:
    st.session_state.failed_urls = []
if 'total_rows' not in st.session_state:
    st.session_state.total_rows = 0
if 'has_zip' not in st.session_state:
    st.session_state.has_zip = False
if 'batch_index' not in st.session_state:
    st.session_state.batch_index = 0
if 'all_final_rows' not in st.session_state:
    st.session_state.all_final_rows = []
if 'all_image_data' not in st.session_state:
    st.session_state.all_image_data = {}
if 'all_failed' not in st.session_state:
    st.session_state.all_failed = []
if 'total_urls' not in st.session_state:
    st.session_state.total_urls = 0
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'all_urls' not in st.session_state:
    st.session_state.all_urls = []
if 'ai_test_result' not in st.session_state:
    st.session_state.ai_test_result = None

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Universal E-commerce Extractor V6.0", page_icon="🛒")
st.title("🛒 UNIVERSAL E-COMMERCE EXTRACTOR V6.0 (AI FIXED)")
st.markdown("**Gemini AI Working | Keyword-Mapped SEO Content | Variable Products Ready**")

st.components.v1.html("""
<script>
    setInterval(function() { console.log("🛡️ Keep-Alive"); }, 2000);
</script>
""", height=0)

# ============================================================
# BRANDING STUDIO (unchanged)
# ============================================================
st.subheader("🎨 Branding Studio (Optional)")
with st.expander("⚙️ Configure Image Branding", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.checkbox("🖼️ Add Corner Logo (Top-Left)", key="enable_logo", value=False)
        if st.session_state.get("enable_logo", False):
            st.file_uploader("Upload Corner Logo", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
        st.checkbox("🔤 Add Center Watermark", key="enable_watermark", value=False)
        if st.session_state.get("enable_watermark", False):
            st.radio("Watermark Type", ["Text", "Image Logo"], key="watermark_type", horizontal=True)
            st.slider("Watermark Size (%)", 5, 50, 15, key="watermark_size")
            st.slider("Watermark Opacity (%)", 10, 80, 20, key="watermark_opacity")
            if st.session_state.get("watermark_type") == "Text":
                st.text_input("Watermark Text", "YourBrand.com", key="watermark_text")
            else:
                st.file_uploader("Upload Watermark Logo (PNG)", type=['png', 'jpg', 'jpeg'], key="watermark_logo_uploader")
        st.checkbox("🌑 Drop Shadow", key="enable_shadow", value=False)
        st.checkbox("🔄 Rounded Corners", key="enable_rounded", value=False)
        st.checkbox("🔄 Mirror Flip (Anti-Duplicate)", key="enable_flip", value=True)
    with col_b:
        st.checkbox("🖼️ Add Border", key="enable_border", value=False)
        if st.session_state.get("enable_border", False):
            st.color_picker("Border Color", "#000000", key="border_color")
        st.checkbox("🌈 Add Gradient Frame", key="enable_gradient", value=False)
        if st.session_state.get("enable_gradient", False):
            st.color_picker("Gradient Color 1", "#FF5733", key="grad_color_1")
            st.color_picker("Gradient Color 2", "#33FF57", key="grad_color_2")
        st.checkbox("✨ Brightness/Contrast Tweak", key="enable_enhance", value=True)

# ============================================================
# 🔥 AI SETTINGS (REBUILT)
# ============================================================
st.subheader("🤖 AI Content Settings")
with st.expander("⚙️ Configure Gemini AI", expanded=True):
    st.checkbox("🚀 Enable Gemini AI Content Generation", key="ai_enabled", value=False,
                help="ON: AI se SEO-optimized content generate hoga. OFF: Local fallback use hoga.")
    
    if st.session_state.get("ai_enabled", False):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.text_input("🔑 Gemini API Key", type="password", key="gemini_api_key",
                          help="Free key: https://aistudio.google.com/apikey")
        with col2:
            # 🔥 Proven working models
            st.selectbox("Model",
                ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
                key="gemini_model",
                help="3.5-flash-lite = fastest & cheapest. 2.5-pro = best quality.")
        
        # Test button
        if st.button("🧪 Test Gemini API", use_container_width=False):
            if not st.session_state.get("gemini_api_key", "").strip():
                st.error("❌ API key enter karo pehle.")
            else:
                with st.spinner("Testing API connection..."):
                    ok, msg = test_gemini_api(
                        st.session_state.gemini_api_key.strip(),
                        st.session_state.get("gemini_model", "gemini-3.5-flash-lite")
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
        
        st.text_area("✍️ Custom Brand Voice / Prompt (optional)",
                     key="ai_custom_prompt",
                     placeholder="e.g. Write in a luxurious, aspirational tone. Target audience: 25-45 year old urban professionals. Focus on craftsmanship and quality.",
                     height=100,
                     help="Ye instructions Gemini ko bheje jayenge.")
        
        st.caption("⚠️ Free tier: 15 requests/min. Auto-fallback to local rewriter if AI fails.")
    else:
        if 'gemini_api_key' in st.session_state:
            st.session_state.gemini_api_key = ""

# ============================================================
# CONTENT SETTINGS
# ============================================================
st.subheader("📝 Content Settings")
with st.expander("⚙️ Configure Content", expanded=False):
    col_ct1, col_ct2 = st.columns(2)
    with col_ct1:
        st.text_area("🏪 Store / Niche Context", key="ai_store_context",
                     placeholder="e.g. Premium leather jackets, luxury fashion e-commerce",
                     height=80)
        st.checkbox("✨ Auto-Generate Unique Product Title (from specs + material + color)",
                    key="smart_title_enabled", value=True)
    with col_ct2:
        st.slider("🖼️ Max Gallery Images per Product", 3, 20, 10, key="max_gallery_images")

# ============================================================
# MAIN INPUTS
# ============================================================
st.subheader("📥 Input & Controls")
edit_images = st.checkbox("🖌️ Enable Image Editing", value=True)
export_format = st.radio("📦 Export Format", ["🛍️ Shopify CSV", "🛒 WooCommerce CSV"],
                         key="export_format", horizontal=True)
col_inp1, col_inp2 = st.columns([3, 1])
with col_inp1:
    urls_input = st.text_area("🔗 Paste Product URLs (One per line):", height=150)
with col_inp2:
    base_url = st.text_input("🌐 Base URL:", placeholder="https://domain.com/wp-content/uploads/")

BATCH_SIZE = 30

# ============================================================
# CONFIG GETTER
# ============================================================
def get_branding_config():
    corner_logo_bytes = None
    if st.session_state.get("enable_logo", False):
        uploaded = st.session_state.get("logo_uploader", None)
        if uploaded is not None:
            corner_logo_bytes = uploaded.getvalue()
    watermark_logo_bytes = None
    if st.session_state.get("enable_watermark", False) and st.session_state.get("watermark_type") == "Image Logo":
        uploaded = st.session_state.get("watermark_logo_uploader", None)
        if uploaded is not None:
            watermark_logo_bytes = uploaded.getvalue()
    return {
        'edit_images': edit_images,
        'enable_flip': st.session_state.get("enable_flip", True),
        'enable_enhance': st.session_state.get("enable_enhance", True),
        'enable_logo': st.session_state.get("enable_logo", False),
        'corner_logo_bytes': corner_logo_bytes,
        'enable_watermark': st.session_state.get("enable_watermark", False),
        'watermark_type': st.session_state.get("watermark_type", "Text"),
        'watermark_text': st.session_state.get("watermark_text", "YourBrand.com"),
        'watermark_logo_bytes': watermark_logo_bytes,
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
        'gemini_model': st.session_state.get("gemini_model", "gemini-3.5-flash-lite"),
        'ai_custom_prompt': st.session_state.get("ai_custom_prompt", "").strip(),
    }

# ============================================================
# 🔥 GEMINI API - DIRECT TEST FUNCTION
# ============================================================
def test_gemini_api(api_key, model_name):
    """Test Gemini API and return (success, message)"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {"contents": [{"parts": [{"text": "Reply with just the word: OK"}]}]}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            try:
                text = data['candidates'][0]['content']['parts'][0]['text']
                return True, f"API working! Model response: {text[:50]}"
            except (KeyError, IndexError):
                return False, f"API returned 200 but response format unexpected: {str(data)[:200]}"
        elif r.status_code == 400:
            return False, f"400 Bad Request - Model name galat ya invalid request. {r.text[:200]}"
        elif r.status_code == 403:
            return False, f"403 Forbidden - API key invalid ya restricted. {r.text[:200]}"
        elif r.status_code == 404:
            return False, f"404 Not Found - Model '{model_name}' exists nahi karta. Try 'gemini-3.5-flash-lite' or 'gemini-2.5-flash'. {r.text[:200]}"
        elif r.status_code == 429:
            return False, f"429 Rate Limit - Quota exceed. Wait 1 min ya paid plan lein."
        else:
            return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except requests.exceptions.Timeout:
        return False, "Request timeout - Network slow ya Gemini server down."
    except Exception as e:
        return False, f"Connection error: {str(e)[:200]}"

# ============================================================
# 🔥 KEYWORD EXTRACTION ENGINE
# ============================================================
def extract_keywords(title, category, specs_text):
    """Extract primary and secondary keywords from product data"""
    # Combine sources
    combined = f"{title} {category} {specs_text[:500]}".lower()
    
    # Remove punctuation and split
    words = re.findall(r'\b[a-z][a-z]+\b', combined)
    
    # Stopwords
    stopwords = {'the', 'a', 'an', 'and', 'or', 'for', 'with', 'of', 'in', 'to', 'is', 'are',
                 'this', 'that', 'your', 'our', 'from', 'on', 'by', 'it', 'its', 'be', 'as',
                 'at', 'new', 'made', 'real', 'top', 'best', 'high', 'quality', 'premium',
                 'this', 'will', 'have', 'has', 'been', 'can', 'may', 'also', 'more', 'most'}
    
    # Filter
    words = [w for w in words if w not in stopwords and len(w) > 3]
    
    # Count frequencies
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    
    # Sort by frequency
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    
    # Primary keyword = from title (first 3 words combination)
    title_words = re.findall(r'\b[a-z][a-z]+\b', title.lower())
    title_words = [w for w in title_words if w not in stopwords and len(w) > 3]
    primary = ' '.join(title_words[:3]) if title_words else title.lower()
    
    # Secondary keywords = top from combined
    secondary = [w for w, c in sorted_words[:10] if w not in primary]
    
    # Long-tail from specs
    spec_keywords = []
    for line in specs_text.split('\n')[:10]:
        line = line.strip()
        if ':' in line and len(line) < 80:
            spec_keywords.append(line)
    
    return {
        'primary': primary,
        'secondary': secondary[:8],
        'long_tail': spec_keywords[:5],
        'all': list(set([primary] + secondary[:8]))
    }

# ============================================================
# 🔥 GEMINI API - CONTENT GENERATOR (REBUILT)
# ============================================================
def generate_ai_content(title, specs_text, category, store_context, keywords, api_key, model_name, custom_prompt):
    """Generate SEO-optimized content via Gemini API with keyword mapping"""
    if not api_key or not title:
        return None, "Missing API key or title"
    
    primary_kw = keywords.get('primary', '')
    secondary_kws = ', '.join(keywords.get('secondary', [])[:5])
    long_tail = '\n'.join([f"- {k}" for k in keywords.get('long_tail', [])[:5]])
    
    # Custom prompt block
    custom_block = f"\n\nBRAND VOICE INSTRUCTIONS:\n{custom_prompt}" if custom_prompt else ""
    context_block = f"\nStore Context: {store_context}" if store_context else ""
    
    prompt = f"""You are an expert SEO copywriter and e-commerce content specialist. Write HIGH-QUALITY, KEYWORD-OPTIMIZED content for the following product.

PRODUCT: {title}
CATEGORY: {category}
SPECIFICATIONS:
{specs_text[:1500]}
{context_block}

PRIMARY KEYWORD: {primary_kw}
SECONDARY KEYWORDS: {secondary_kws}
LONG-TAIL PHRASES:
{long_tail}
{custom_block}

REQUIREMENTS:
1. PRIMARY KEYWORD must appear naturally in SEO Title, Short Description, Long Description (2-3 times), and Meta Description.
2. SECONDARY KEYWORDS should be woven naturally — no keyword stuffing.
3. Content must be UNIQUE, ENGAGING, PERSUASIVE, and SEO-OPTIMIZED.
4. Follow exact character/word limits.
5. Return ONLY the response in the EXACT format below. No extra text.

===SEO TITLE===
[Max 60 chars. Must include primary keyword. Make it click-worthy.]

===META DESCRIPTION===
[Max 160 chars. Include primary keyword. Compelling call-to-action.]

===SHORT DESCRIPTION===
[100-150 words. Hook + benefits + primary keyword. Persuasive.]

===LONG DESCRIPTION===
[400-600 words in HTML format. Use <h3> for subheadings, <p> for paragraphs, <ul><li> for features. Include: an engaging intro, 4-6 key benefits as bullet points, technical specifications, and a call-to-action. Weave keywords naturally.]

===ADDITIONAL INFORMATION===
[Extract 6-10 key specifications from the details above as bullet points. Format: <ul><li><strong>Spec Name:</strong> Spec Value</li></ul>]

===TAGS===
[5-8 relevant tags separated by commas, lowercase, for search/filtering]

Now generate the content:"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.75,
            "maxOutputTokens": 2500,
            "topP": 0.95,
            "topK": 40
        }
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if r.status_code != 200:
            # Return detailed error
            if r.status_code == 429:
                return None, f"429 Rate Limit exceeded — try again in 60s"
            elif r.status_code == 400:
                return None, f"400 Bad Request — {r.text[:200]}"
            elif r.status_code == 404:
                return None, f"404 Model '{model_name}' not found"
            else:
                return None, f"HTTP {r.status_code}: {r.text[:200]}"
        
        data = r.json()
        try:
            text = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError):
            return None, "Response format unexpected"
        
        # Parse sections
        result = parse_ai_sections(text, title, primary_kw, keywords)
        return result, None
    
    except requests.exceptions.Timeout:
        return None, "Request timeout (>60s)"
    except Exception as e:
        return None, f"Error: {str(e)[:200]}"

def parse_ai_sections(text, title, primary_kw, keywords):
    """Parse Gemini's structured response"""
    result = {
        'seo_title': '',
        'meta_description': '',
        'short_description': '',
        'long_description': '',
        'additional_information': '',
        'tags': ''
    }
    
    # Define section markers
    markers = {
        '===SEO TITLE===': 'seo_title',
        '===META DESCRIPTION===': 'meta_description',
        '===SHORT DESCRIPTION===': 'short_description',
        '===LONG DESCRIPTION===': 'long_description',
        '===ADDITIONAL INFORMATION===': 'additional_information',
        '===TAGS===': 'tags'
    }
    
    # Split by markers
    current_key = None
    current_lines = []
    
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped in markers:
            if current_key and current_lines:
                result[current_key] = '\n'.join(current_lines).strip()
            current_key = markers[stripped]
            current_lines = []
        elif current_key:
            current_lines.append(line)
    
    if current_key and current_lines:
        result[current_key] = '\n'.join(current_lines).strip()
    
    # Validate and add defaults
    if not result['seo_title']:
        result['seo_title'] = f"{title} - {primary_kw.title()}"[:60]
    if not result['meta_description']:
        result['meta_description'] = f"Shop the {title}. Premium quality, fast shipping. Order now!"[:160]
    if not result['short_description']:
        result['short_description'] = f"Discover the {title} — premium quality, keyword optimized for {primary_kw}."
    if not result['long_description']:
        result['long_description'] = f"<p>Experience the {title}. Premium quality crafted for those who appreciate {primary_kw}.</p>"
    if not result['additional_information']:
        result['additional_information'] = ""
    if not result['tags']:
        result['tags'] = ', '.join(keywords.get('secondary', [])[:5])
    
    # Ensure tags are lowercase
    result['tags'] = result['tags'].lower()
    
    return result

# ============================================================
# LOCAL REWRITER (IMPROVED FALLBACK)
# ============================================================
class SmartRewriter:
    def __init__(self):
        self.hooks = [
            "Meet the {title} — a piece that redefines what quality should feel like.",
            "Say hello to the {title}, where craftsmanship meets everyday style.",
            "Introducing the {title}, designed for those who value substance.",
            "The {title} is here — crafted to become your go-to favorite.",
            "Discover the {title}, where premium materials meet thoughtful design.",
            "Experience the {title} — built with care in every detail.",
            "Elevate your everyday with the {title}, made for those who notice the difference.",
        ]
        self.features = [
            "Premium materials chosen for comfort and long-lasting wear",
            "Thoughtful construction that holds its shape use after use",
            "A comfortable, true-to-size fit made for all-day wear",
            "Versatile enough to dress up or down for any occasion",
            "Carefully finished details for a polished, put-together look",
            "Easy to care for so it stays looking great with minimal effort",
            "A timeless design that won't feel out of place next season",
            "Reinforced stitching and finishing where it matters most",
        ]
        self.ctas = [
            "Add it to your cart today — you won't regret it.",
            "Treat yourself to something built to last.",
            "Order now and see the quality for yourself.",
            "A smart upgrade for anyone who values quality.",
        ]
    
    def generate_content(self, title, raw_desc, category, store_context, specs_text, keywords):
        """Generate SEO content locally as fallback"""
        hook = random.choice(self.hooks).format(title=title)
        primary_kw = keywords.get('primary', title.lower())
        secondary = keywords.get('secondary', [])[:4]
        
        # SEO Title with primary keyword
        seo_title = f"{title} - {primary_kw.title()}"
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + '...'
        
        # Meta description with primary keyword
        meta_desc = f"Shop the {title}. Premium {primary_kw} available. Fast shipping, quality guaranteed."
        if len(meta_desc) > 160:
            meta_desc = meta_desc[:157] + '...'
        
        # Short description
        short_desc = f"{hook} Premium quality crafted for {primary_kw}. Shop now."
        
        # Long description (HTML)
        features_html = ''.join([f"<li>{f}</li>" for f in random.sample(self.features, 4)])
        long_desc = f"""<p>{hook}</p>
<p>This premium {primary_kw} is designed with your needs in mind. Whether you're looking for {secondary[0] if secondary else 'quality'} or simply want something that lasts, this product delivers.</p>
<h3>Key Features</h3>
<ul>{features_html}</ul>
<h3>Why Choose This Product</h3>
<p>Crafted from premium materials and built to last, this {primary_kw} offers exceptional value. Perfect for those who appreciate {secondary[0] if secondary else 'quality craftsmanship'}.</p>
<p>{random.choice(self.ctas)}</p>"""
        
        # Additional information (specs)
        additional_info = ""
        spec_lines = []
        for line in (specs_text or "").split('\n')[:10]:
            if ':' in line and len(line) < 100:
                parts = line.split(':', 1)
                spec_lines.append(f"<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>")
        if spec_lines:
            additional_info = f"<ul>{''.join(spec_lines[:8])}</ul>"
        
        # Tags
        tags = ', '.join(secondary[:6]) if secondary else primary_kw
        
        return {
            'seo_title': seo_title,
            'meta_description': meta_desc,
            'short_description': short_desc,
            'long_description': long_desc,
            'additional_information': additional_info,
            'tags': tags
        }

# ============================================================
# EXTRACTORS
# ============================================================
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
    if isinstance(brand_data, list) and brand_data:
        return safe_get_brand(brand_data[0])
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
    if isinstance(cat_field, str) and cat_field.strip() and not _is_product_title(cat_field):
        return cat_field.strip()
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

# ============================================================
# SMART TITLE
# ============================================================
def generate_smart_title(original_title, specs_text, color=None, material=None):
    if not specs_text or not original_title: return original_title
    specs_lower = specs_text.lower()
    materials = ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 'canvas', 'denim', 'wool']
    detected_material = ''
    for mat in materials:
        if mat in specs_lower and mat not in original_title.lower():
            detected_material = mat.capitalize(); break
    finish_types = ['waxed', 'pull-up', 'semi-aniline', 'aniline', 'distressed', 'vintage', 'washed', 'oiled', 'matte', 'glossy']
    detected_finish = ''
    for fin in finish_types:
        if fin in specs_lower and fin not in original_title.lower():
            detected_finish = fin.capitalize(); break
    colors = ['black', 'brown', 'tan', 'maroon', 'red', 'blue', 'green', 'grey', 'white', 'charcoal', 'navy', 'olive']
    detected_color = ''
    for col in colors:
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

# ============================================================
# GALLERY IMAGES
# ============================================================
def strip_size_suffix(url):
    try:
        clean = url.split('?')[0]
        query = url[len(clean):]
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

# ============================================================
# IMAGE EDITOR
# ============================================================
def edit_image(img_data, filename, config):
    try:
        img = Image.open(BytesIO(img_data))
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        width, height = img.size
        final_img = img
        if config.get('enable_flip', True): final_img = final_img.transpose(Image.FLIP_LEFT_RIGHT)
        if config.get('enable_enhance', True):
            final_img = ImageEnhance.Brightness(final_img).enhance(random.uniform(0.92, 1.08))
            final_img = ImageEnhance.Contrast(final_img).enhance(random.uniform(0.95, 1.05))
        if config.get('enable_rounded', False):
            mask = Image.new('L', final_img.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=30, fill=255)
            final_img.putalpha(mask)
            bg = Image.new('RGB', final_img.size, (255, 255, 255))
            bg.paste(final_img, mask=final_img.split()[-1]); final_img = bg
        if config.get('enable_shadow', False):
            so, sb = 10, 15
            shadow = Image.new('RGBA', (width + so*2, height + so*2), (0,0,0,0))
            ImageDraw.Draw(shadow).rectangle((so, so, width + so, height + so), fill=(0,0,0,30))
            shadow = shadow.filter(ImageFilter.GaussianBlur(sb))
            bg = Image.new('RGBA', (width + so*2, height + so*2), (255,255,255,0))
            bg.paste(shadow, (0,0), shadow); bg.paste(final_img, (so, so)); final_img = bg.convert('RGB')
        if config.get('enable_logo', False):
            logo_bytes = config.get('corner_logo_bytes')
            if logo_bytes:
                try:
                    logo = Image.open(BytesIO(logo_bytes))
                    logo.thumbnail((int(width * 0.15), int(height * 0.15)), Image.LANCZOS)
                    final_img.paste(logo, (20, 20), logo if logo.mode == 'RGBA' else None)
                except: pass
        if config.get('enable_watermark', False):
            opacity = config.get('watermark_opacity', 20) / 100
            wm_type = config.get('watermark_type', 'Text')
            wm_size = config.get('watermark_size', 15)
            if final_img.mode != 'RGBA': final_img = final_img.convert('RGBA')
            wm_layer = Image.new('RGBA', final_img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(wm_layer)
            if wm_type == 'Text':
                txt = config.get('watermark_text', 'Brand')
                font_size = int(min(width, height) * (wm_size / 100))
                try:
                    from PIL import ImageFont
                    font = ImageFont.truetype("arial.ttf", font_size)
                except: font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), txt, font=font)
                pos = ((width - (bbox[2]-bbox[0])) // 2, (height - (bbox[3]-bbox[1])) // 2)
                draw.text(pos, txt, font=font, fill=(255, 255, 255, int(255 * opacity)))
            else:
                wm_logo_bytes = config.get('watermark_logo_bytes')
                if wm_logo_bytes:
                    try:
                        wm_logo = Image.open(BytesIO(wm_logo_bytes))
                        tw = int(width * (wm_size / 100))
                        th = int(wm_logo.height * (tw / wm_logo.width))
                        wm_logo = wm_logo.resize((tw, th), Image.LANCZOS)
                        if wm_logo.mode != 'RGBA': wm_logo = wm_logo.convert('RGBA')
                        alpha = wm_logo.split()[3].point(lambda p: int(p * opacity))
                        wm_logo.putalpha(alpha)
                        wm_layer.paste(wm_logo, ((width - tw) // 2, (height - th) // 2), wm_logo)
                    except: pass
            final_img = Image.alpha_composite(final_img, wm_layer).convert('RGB')
        if config.get('enable_border', False):
            final_img = ImageOps.expand(final_img, border=10, fill=config.get('border_color', '#000000'))
            width, height = final_img.size
        if config.get('enable_gradient', False):
            c1 = config.get('grad_color_1', '#FF5733').lstrip('#')
            c2 = config.get('grad_color_2', '#33FF57').lstrip('#')
            c1_rgb = tuple(int(c1[i:i+2], 16) for i in (0, 2, 4))
            c2_rgb = tuple(int(c2[i:i+2], 16) for i in (0, 2, 4))
            fh = int(height * 0.1)
            strip = Image.new('RGB', (width, fh))
            for x in range(width):
                r = x / width
                strip.paste(tuple(int(c1_rgb[i] + (c2_rgb[i] - c1_rgb[i]) * r) for i in range(3)), (x, 0, x+1, fh))
            final_img.paste(strip, (0, height - fh))
        new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
        if not new_filename.lower().endswith(('.jpg', '.jpeg')): new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
        buffer = BytesIO()
        final_img.save(buffer, format='JPEG', quality=70, optimize=True)
        buffer.seek(0)
        return new_filename, buffer.getvalue()
    except Exception:
        try:
            new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
            if not new_filename.lower().endswith(('.jpg', '.jpeg')): new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
            return new_filename, img_data
        except: return None, None

# ============================================================
# VARIATION EXTRACTION
# ============================================================
def extract_variations(product_data, soup, base_url_domain, price):
    variations = []
    seen_attrs = set()
    offers = product_data.get('offers')
    if isinstance(offers, list) and len(offers) > 1:
        for offer in offers:
            if not isinstance(offer, dict): continue
            var_attrs = {}
            if 'size' in offer: var_attrs['Size'] = offer['size']
            if 'color' in offer: var_attrs['Color'] = offer['color']
            if 'material' in offer: var_attrs['Material'] = offer['material']
            if not var_attrs: var_attrs['Option'] = f'Variant {len(variations)+1}'
            attrs_key = tuple(sorted(var_attrs.items()))
            if attrs_key not in seen_attrs:
                seen_attrs.add(attrs_key)
                variations.append({'sku': offer.get('sku', ''), 'price': offer.get('price', price), 'attrs': var_attrs, 'image': offer.get('image', '')})
    if not variations:
        size_select = soup.find('select', {'class': re.compile(r'size|variant', re.I)})
        if size_select:
            for opt in size_select.find_all('option'):
                val = opt.get('value', '').strip()
                if val and val.lower() not in ('', 'select', 'choose'):
                    var_attrs = {'Size': val}
                    attrs_key = tuple(sorted(var_attrs.items()))
                    if attrs_key not in seen_attrs:
                        seen_attrs.add(attrs_key)
                        variations.append({'sku': '', 'price': price, 'attrs': var_attrs, 'image': ''})
    seen = set(); unique = []
    for v in variations:
        key = tuple(sorted(v['attrs'].items()))
        if key not in seen:
            seen.add(key); unique.append(v)
    return unique

# ============================================================
# MAIN SCRAPER
# ============================================================
def scrape_product(url, session, config, ai_status_placeholder=None):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for attempt in range(2):
        try:
            resp = session.get(url, headers=headers, timeout=20)
            resp.raise_for_status(); break
        except:
            if attempt == 0: time.sleep(5)
            else: return None, None, f"Failed"
    soup = BeautifulSoup(resp.text, 'lxml')
    base_url_domain = f"{resp.url.split('/')[0]}//{resp.url.split('/')[2]}"
    product_data = {}
    def is_product_type(data_type):
        if isinstance(data_type, str): return data_type == 'Product'
        if isinstance(data_type, list): return 'Product' in data_type
        return False
    for script in soup.find_all('script', type='application/ld+json'):
        try: data = json.loads(script.string)
        except: continue
        if isinstance(data, dict):
            if is_product_type(data.get('@type')): product_data = data; break
            if '@graph' in data:
                for entry in data['@graph']:
                    if isinstance(entry, dict) and is_product_type(entry.get('@type')):
                        product_data = data; break
                if product_data: break
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and is_product_type(entry.get('@type')):
                    product_data = entry; break
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
    # Extract keywords
    keywords = extract_keywords(original_title, category_str, specs_text)
    color = ''
    material = ''
    color_match = re.search(r'color[:\s]+([a-zA-Z]+)', raw_desc, re.I)
    if color_match: color = color_match.group(1).capitalize()
    for mat in ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 'canvas', 'denim', 'wool']:
        if mat in raw_desc.lower(): material = mat.capitalize(); break
    if config.get('smart_title_enabled', True):
        title = generate_smart_title(original_title, specs_text, color, material)
    else:
        title = original_title
    # Content generation
    ai_content = None
    ai_error = None
    if config.get('ai_enabled', False) and config.get('gemini_api_key'):
        ai_content, ai_error = generate_ai_content(
            title, specs_text, category_str, config.get('store_context', ''),
            keywords, config.get('gemini_api_key'),
            config.get('gemini_model', 'gemini-3.5-flash-lite'),
            config.get('ai_custom_prompt', '')
        )
        if ai_error and ai_status_placeholder:
            ai_status_placeholder.warning(f"⚠️ AI failed for '{title[:30]}...': {ai_error} — Using local fallback.")
    rewriter = SmartRewriter()
    if ai_content:
        content = ai_content
    else:
        content = rewriter.generate_content(title, raw_desc, category_str, config.get('store_context', ''), specs_text, keywords)
    seo_title = content.get('seo_title', title)
    meta_desc = content.get('meta_description', '')
    short_desc = content.get('short_description', '')
    long_desc = content.get('long_description', '')
    additional_info = content.get('additional_information', '')
    tags = content.get('tags', 'Imported')
    # SKU
    rand_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    parent_sku = f"CUSTOM-{rand_suffix}-{sku_raw}"
    # Images
    max_images = config.get('max_gallery_images', 10)
    raw_image_urls = collect_gallery_images(url, soup, base_url_domain, session, headers, product_data, max_images)
    image_zip_data = {}
    processed_image_urls = []
    if config.get('edit_images', False):
        for img_url in raw_image_urls:
            try:
                img_resp = session.get(img_url, timeout=15)
                if img_resp.status_code == 200:
                    new_name, edited_data = edit_image(img_resp.content, img_url, config)
                    if new_name and edited_data:
                        image_zip_data[new_name] = edited_data
                        processed_image_urls.append(new_name)
                    else: processed_image_urls.append(img_url)
                else: processed_image_urls.append(img_url)
            except: processed_image_urls.append(img_url)
    else: processed_image_urls = raw_image_urls
    main_image = processed_image_urls[0] if processed_image_urls else ''
    additional_images = processed_image_urls[1:] if len(processed_image_urls) > 1 else []
    handle = generate_handle(title)
    # Variations
    variations_data = extract_variations(product_data, soup, base_url_domain, price)
    is_variable = len(variations_data) > 1
    opt1_name = opt2_name = opt3_name = ''
    if variations_data:
        attr_names = set()
        for v in variations_data: attr_names.update(v['attrs'].keys())
        attr_names = sorted(list(attr_names))
        if len(attr_names) > 0: opt1_name = attr_names[0]
        if len(attr_names) > 1: opt2_name = attr_names[1]
        if len(attr_names) > 2: opt3_name = attr_names[2]
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
    for idx, img_url in enumerate(additional_images, start=2):
        img_row = {col: '' for col in SHOPIFY_COLUMNS}
        img_row['URL handle'] = handle
        img_row['Product image URL'] = img_url
        img_row['Image position'] = str(idx)
        image_rows.append(img_row)
    variant_rows = []
    if variations_data and is_variable:
        for idx, var in enumerate(variations_data):
            var_sku = var.get('sku', '') or f"{parent_sku}-V{idx+1}"
            var_price = var.get('price', price)
            var_attrs = var['attrs']
            attr1_val = list(var_attrs.values())[0] if len(var_attrs) > 0 else ''
            attr2_val = list(var_attrs.values())[1] if len(var_attrs) > 1 else ''
            attr3_val = list(var_attrs.values())[2] if len(var_attrs) > 2 else ''
            variant_row = {
                'Title': '', 'URL handle': handle, 'Description': '', 'Vendor': '', 'Product category': '',
                'Type': '', 'Tags': '', 'Published on online store': 'TRUE', 'Status': 'active',
                'SKU': var_sku, 'Barcode': random.randint(1000000000, 9999999999),
                'Option1 name': '', 'Option1 value': attr1_val, 'Option1 Linked To': '',
                'Option2 name': '', 'Option2 value': attr2_val, 'Option2 Linked To': '',
                'Option3 name': '', 'Option3 value': attr3_val, 'Option3 Linked To': '',
                'Price': var_price, 'Compare-at price': '', 'Cost per item': '', 'Charge tax': 'TRUE', 'Tax code': '',
                'Unit price total measure': '', 'Unit price total measure unit': '', 'Unit price base measure': '', 'Unit price base measure unit': '',
                'Inventory tracker': 'shopify', 'Inventory quantity': 10, 'Continue selling when out of stock': 'DENY',
                'Weight value (grams)': 150, 'Weight unit for display': 'g', 'Requires shipping': 'TRUE',
                'Fulfillment service': 'manual', 'Product image URL': '', 'Image position': '',
                'Image alt text': '', 'Variant image URL': var.get('image', ''), 'Gift card': 'FALSE',
                'SEO title': '', 'SEO description': '', 'Short description': '', 'Additional information': '',
                'Color (product.metafields.shopify.color-pattern)': attr2_val if opt2_name.lower() == 'color' else attr1_val if opt1_name.lower() == 'color' else '',
                'Google Shopping / Google product category': '', 'Google Shopping / Gender': '',
                'Google Shopping / Age group': '', 'Google Shopping / Manufacturer part number (MPN)': f'MPN-{var_sku}',
                'Google Shopping / Ad group name': '', 'Google Shopping / Ads labels': '',
                'Google Shopping / Condition': 'New', 'Google Shopping / Custom product': '',
                'Google Shopping / Custom label 0': '', 'Google Shopping / Custom label 1': '',
                'Google Shopping / Custom label 2': '', 'Google Shopping / Custom label 3': '', 'Google Shopping / Custom label 4': ''
            }
            variant_rows.append(variant_row)
    if not variations_data:
        parent_row['SKU'] = parent_sku
        parent_row['Price'] = price
        parent_row['Inventory tracker'] = 'shopify'
        parent_row['Inventory quantity'] = 10
        parent_row['Continue selling when out of stock'] = 'DENY'
        parent_row['Weight value (grams)'] = 150
        parent_row['Weight unit for display'] = 'g'
        parent_row['Fulfillment service'] = 'manual'
        parent_row['Barcode'] = random.randint(1000000000, 9999999999)
    final_rows = [parent_row] + image_rows + variant_rows
    return final_rows, image_zip_data, None

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0',
]

# ============================================================
# COLUMNS (Added "Additional information")
# ============================================================
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
    parent = product_rows[0]
    handle = parent.get('URL handle', '')
    images = [parent.get('Product image URL', '')] if parent.get('Product image URL') else []
    variant_rows_src = []
    for r in product_rows[1:]:
        if not r.get('SKU') and r.get('Product image URL'): images.append(r['Product image URL'])
        elif r.get('SKU'): variant_rows_src.append(r)
    images_str = ', '.join([img for img in images if img])
    has_variants = len(variant_rows_src) > 0
    attr1_name = parent.get('Option1 name', '')
    attr2_name = parent.get('Option2 name', '')
    attr3_name = parent.get('Option3 name', '')
    attr1_vals = sorted({r['Option1 value'] for r in variant_rows_src if r.get('Option1 value')}) if attr1_name else []
    attr2_vals = sorted({r['Option2 value'] for r in variant_rows_src if r.get('Option2 value')}) if attr2_name else []
    attr3_vals = sorted({r['Option3 value'] for r in variant_rows_src if r.get('Option3 value')}) if attr3_name else []
    woo_parent = {col: '' for col in WOOCOMMERCE_COLUMNS}
    woo_parent.update({
        'Type': 'variable' if has_variants else 'simple',
        'SKU': parent.get('SKU', ''),
        'Name': parent.get('Title', ''),
        'Published': '1' if parent.get('Published on online store') == 'TRUE' else '0',
        'Is featured?': '0', 'Visibility in catalog': 'visible',
        'Short description': parent.get('Short description', ''),
        'Description': parent.get('Description', ''),
        'Additional information': parent.get('Additional information', ''),
        'Tax status': 'taxable' if parent.get('Charge tax') == 'TRUE' else 'none',
        'In stock?': '1', 'Stock': parent.get('Inventory quantity', ''),
        'Backorders allowed?': '0' if parent.get('Continue selling when out of stock') == 'DENY' else '1',
        'Weight (kg)': parent.get('Weight value (grams)', ''),
        'Allow customer reviews?': '1',
        'Regular price': '' if has_variants else parent.get('Price', ''),
        'Categories': parent.get('Product category', ''),
        'Tags': parent.get('Tags', ''),
        'Images': images_str,
        'Attribute 1 name': attr1_name, 'Attribute 1 value(s)': ', '.join(attr1_vals),
        'Attribute 1 visible': '1' if attr1_name else '', 'Attribute 1 global': '0',
        'Attribute 2 name': attr2_name, 'Attribute 2 value(s)': ', '.join(attr2_vals),
        'Attribute 2 visible': '1' if attr2_name else '', 'Attribute 2 global': '0',
        'Attribute 3 name': attr3_name, 'Attribute 3 value(s)': ', '.join(attr3_vals),
        'Attribute 3 visible': '1' if attr3_name else '', 'Attribute 3 global': '0',
        'Meta: _yoast_wpseo_title': parent.get('SEO title', ''),
        'Meta: _yoast_wpseo_metadesc': parent.get('SEO description', ''),
    })
    rows = [woo_parent]
    if has_variants:
        for r in variant_rows_src:
            woo_var = {col: '' for col in WOOCOMMERCE_COLUMNS}
            woo_var.update({
                'Type': 'variation', 'SKU': r.get('SKU', ''),
                'Name': f"{parent.get('Title', '')} - Variation",
                'Published': '1', 'Visibility in catalog': 'visible',
                'Tax status': 'taxable' if r.get('Charge tax') == 'TRUE' else 'none',
                'In stock?': '1', 'Stock': r.get('Inventory quantity', ''),
                'Backorders allowed?': '0' if r.get('Continue selling when out of stock') == 'DENY' else '1',
                'Weight (kg)': r.get('Weight value (grams)', ''),
                'Regular price': r.get('Price', ''),
                'Images': r.get('Variant image URL', ''),
                'Parent': handle,
                'Attribute 1 name': attr1_name, 'Attribute 1 value(s)': r.get('Option1 value', ''),
                'Attribute 2 name': attr2_name, 'Attribute 2 value(s)': r.get('Option2 value', ''),
                'Attribute 3 name': attr3_name, 'Attribute 3 value(s)': r.get('Option3 value', ''),
            })
            rows.append(woo_var)
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
# MAIN FLOW
# ============================================================
if st.button("🚀 Generate CSV + ZIP (Batch Mode)", type="primary") or st.session_state.is_processing:
    if not st.session_state.is_processing and urls_input.strip():
        urls_list = [u.strip() for u in re.split(r'[,\s]+', urls_input) if u.strip().startswith('http')]
        if not urls_list:
            st.error("❌ Valid URL nahi mili.")
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
        urls_list = st.session_state.all_urls
        batch_idx = st.session_state.batch_index
        total = st.session_state.total_urls
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        current_batch = urls_list[start:end]
        if start < total:
            status_text = st.empty()
            progress_bar = st.progress(0)
            ai_status = st.empty()
            status_text.info(f"⏳ Processing Batch {batch_idx+1}/{(total // BATCH_SIZE) + 1} ({start+1} to {end} of {total})...")
            config = get_branding_config()
            session = requests.Session()
            batch_rows, batch_images, batch_failed = process_batch(current_batch, config, session, ai_status)
            st.session_state.all_final_rows.extend(batch_rows)
            st.session_state.all_image_data.update(batch_images)
            st.session_state.all_failed.extend(batch_failed)
            st.session_state.batch_index += 1
            progress_bar.progress(1.0)
            status_text.success(f"✅ Batch {batch_idx+1} complete. Total rows: {len(st.session_state.all_final_rows)}")
            if st.session_state.batch_index * BATCH_SIZE < total:
                time.sleep(2); st.rerun()
            else:
                st.session_state.is_processing = False
                if base_url:
                    for row in st.session_state.all_final_rows:
                        for col in ['Product image URL', 'Variant image URL']:
                            img_col = row.get(col, '')
                            if img_col:
                                imgs = img_col.split(', ')
                                new_imgs = []
                                for img in imgs:
                                    if not img.startswith('http'):
                                        new_imgs.append(f"{base_url.rstrip('/')}/{img.lstrip('/')}")
                                    else: new_imgs.append(img)
                                row[col] = ', '.join(new_imgs)
                config = get_branding_config()
                if config.get('export_format') == 'woocommerce':
                    product_groups = group_rows_by_product(st.session_state.all_final_rows)
                    woo_rows = []
                    for group in product_groups:
                        woo_rows.extend(build_woocommerce_rows(group, config))
                    df = pd.DataFrame(woo_rows, columns=WOOCOMMERCE_COLUMNS)
                    for col in WOOCOMMERCE_COLUMNS:
                        if col not in df.columns: df[col] = ''
                    df = df[WOOCOMMERCE_COLUMNS]
                else:
                    df = pd.DataFrame(st.session_state.all_final_rows, columns=SHOPIFY_COLUMNS)
                    for col in SHOPIFY_COLUMNS:
                        if col not in df.columns: df[col] = ''
                    df = df[SHOPIFY_COLUMNS]
                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.session_state.csv_data = csv_buffer.getvalue()
                st.session_state.df_preview = df
                st.session_state.failed_urls = st.session_state.all_failed
                st.session_state.total_rows = len(st.session_state.all_final_rows)
                st.session_state.is_ready = True
                st.session_state.has_zip = False
                st.session_state.zip_data = None
                st.rerun()
        else:
            st.session_state.is_processing = False

# ============================================================
# DOWNLOAD SECTION
# ============================================================
if st.session_state.is_ready:
    st.success(f"🎯 {st.session_state.total_rows} rows generated! {len(st.session_state.failed_urls)} failed.")
    if st.session_state.failed_urls:
        with st.expander(f"⚠️ Failed URLs ({len(st.session_state.failed_urls)})"):
            st.write('\n'.join(st.session_state.failed_urls))
    st.subheader("📊 Preview (First 10 rows)")
    st.dataframe(st.session_state.df_preview.head(10))
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        is_woo = st.session_state.get("export_format", "🛍️ Shopify CSV").startswith("🛒")
        st.download_button(
            label=f"⬇️ Download {'WooCommerce' if is_woo else 'Shopify'} CSV",
            data=st.session_state.csv_data,
            file_name=f"{'woocommerce' if is_woo else 'shopify'}_import_{int(time.time())}.csv",
            mime="text/csv", use_container_width=True, key="csv_download"
        )
    with col_b:
        if st.session_state.has_zip and st.session_state.zip_data:
            zip_mb = len(st.session_state.zip_data) / (1024 * 1024)
            st.download_button(
                label=f"⬇️ Download Images ZIP ({zip_mb:.1f} MB)",
                data=st.session_state.zip_data,
                file_name=f"branded_images_{int(time.time())}.zip",
                mime="application/zip", use_container_width=True, key="zip_download"
            )
        else:
            if st.button("🔄 Generate ZIP (Images)", use_container_width=True):
                with st.spinner("📦 Compressing..."):
                    pb = st.progress(0); stxt = st.empty()
                    for i in range(101):
                        if i % 20 == 0: stxt.text(f"Compressing... {i}%")
                        pb.progress(i / 100); time.sleep(0.05)
                    zbuf = BytesIO()
                    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for fname, fdata in st.session_state.all_image_data.items():
                            zf.writestr(fname, fdata)
                    zbuf.seek(0)
                    zr = zbuf.getvalue()
                    zm = len(zr) / (1024 * 1024)
                    if zm > 1000:
                        st.error(f"❌ ZIP {zm:.1f} MB > 1000 MB limit. Process ≤400 URLs.")
                    else:
                        st.session_state.zip_data = zr
                        st.session_state.has_zip = True
                        st.rerun()
            st.info("ℹ️ Click 'Generate ZIP'")
    with col_c:
        if st.button("🔄 Reset & New Batch", use_container_width=True):
            for key in ['is_ready', 'csv_data', 'zip_data', 'df_preview', 'failed_urls', 'total_rows', 'has_zip',
                        'batch_index', 'all_final_rows', 'all_image_data', 'all_failed', 'total_urls', 'is_processing', 'all_urls']:
                if key in st.session_state:
                    if key in ['total_rows', 'batch_index', 'total_urls']: st.session_state[key] = 0
                    elif key in ['failed_urls', 'all_failed']: st.session_state[key] = []
                    elif key == 'all_image_data': st.session_state[key] = {}
                    elif key == 'all_final_rows': st.session_state[key] = []
                    elif key in ['is_ready', 'has_zip', 'is_processing']: st.session_state[key] = False
                    else: st.session_state[key] = None
            st.rerun()

st.caption("🛒 V6.0 | AI Fixed | Keyword-Mapped SEO | Additional Information | Variable Products")