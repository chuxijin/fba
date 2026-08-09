import re, json

with open("scripts/huatu_page.html", "r", encoding="utf-8") as f:
    html = f.read()

# Normalize encoding - the page is GBK displayed as UTF-8, so Chinese chars are garbled
# We need to work with the raw bytes or re-encode

# Actually, let's try re-reading as GBK
try:
    with open("scripts/huatu_page.html", "r", encoding="gbk") as f:
        html = f.read()
except:
    pass

# Extract all pointid and name pairs
# Pattern: text content followed by pointid in data-options
# The structure is: category name in h2 or div, then sub-items with pointid

# First, let's see what we can extract
# Find all pointid references
pointid_pattern = re.compile(r'pointid":"(\d+)"')
pointids = pointid_pattern.findall(html)
print(f"Total point IDs found: {len(set(pointids))}")

# Try to find category names near pointids
# Look for: <span ... data-options='{"pointid":"..."}'>text</span>
span_pattern = re.compile(r'<span[^>]*data-options=\'[^\']*pointid":"(\d+)"[^\']*\'[^>]*>([^<]+)</span>')
matches = span_pattern.findall(html)
print(f"\nSpan items with pointid:")
for pid, name in matches[:20]:
    print(f"  {pid}: {name.strip()}")

# Also look for h2 elements (category names)
h2_pattern = re.compile(r'<h2[^>]*>([^<]+)</h2>')
h2s = h2_pattern.findall(html)
print(f"\nH2 headers:")
for h in h2s:
    print(f"  {h.strip()}")

# Look for div items that are category headers
div_pattern = re.compile(r'<div[^>]*class="[^"]*spcs_item[^"]*"[^>]*>([^<]+)</div>')
divs = div_pattern.findall(html)
print(f"\nCategory divs:")
for d in divs:
    print(f"  {d.strip()}")

# Let's try to extract the structure more carefully
# The structure seems to be nested divs with specific classes
# Let's look at the raw HTML structure around the knowledge points