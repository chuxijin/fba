import urllib.request
import re

url = "https://v.huatu.com/tiku/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req)
raw = resp.read()

# Try to decode as GBK
try:
    html = raw.decode("gbk")
except:
    html = raw.decode("utf-8", errors="replace")

# Save decoded HTML
with open("scripts/huatu_decoded.html", "w", encoding="utf-8") as f:
    f.write(html)

# Extract the knowledge point structure
# Pattern: div with class containing spcs_item, then point data
# The structure is nested

# Find all major category divs (spcs_item)
# <div class="spcs_item [active]">name</div>
cat_pattern = re.compile(r'<div[^>]*class="spcs_item[^"]*"[^>]*>\s*<i[^>]*></i>\s*([^<]+?)\s*</div>')
cats = cat_pattern.findall(html)
print("=== Major Categories ===")
for c in cats:
    print(f"  {c.strip()}")

# Find sub-category spans with pointid
# <span ... data-options='{"pointid":"123"}' ...>name</span>
sub_pattern = re.compile(r'<span[^>]*data-options=\'[^\']*pointid":"(\d+)"[^\']*\'[^>]*>([^<]+?)</span>')
subs = sub_pattern.findall(html)
print(f"\n=== Sub-categories ({len(subs)}) ===")
for pid, name in subs:
    print(f"  {pid}: {name.strip()}")

# Find "随机来10道" buttons (these are mid-level categories)
mid_pattern = re.compile(r'<span[^>]*class="[^"]*tiku_practice_btn_noborder[^"]*"[^>]*data-options=\'[^\']*pointid":"(\d+)"[^\']*\'[^>]*>([^<]+?)<i')
mids = mid_pattern.findall(html)
print(f"\n=== Mid-level categories ({len(mids)}) ===")
for pid, name in mids:
    print(f"  {pid}: {name.strip()}")

# Output the structure as JSON for further processing
print("\n\nFull mids list:")
for pid, name in mids:
    print(json.dumps({"id": pid, "name": name.strip()}, ensure_ascii=False) + ",")