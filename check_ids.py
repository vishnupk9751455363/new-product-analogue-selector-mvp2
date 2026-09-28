import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# Check for getElementById references to ensure they exist in index.html
with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))
js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', code))

missing_ids = js_ids - html_ids
print("IDs in JS but missing from HTML:")
for mid in sorted(missing_ids):
    print(" -", mid)

btn_ids = set(re.findall(r'<button[^>]+id=["\']([^"\']+)["\']', html))
missing_btns = {b for b in btn_ids if b not in code}
print("\nButton IDs in HTML not mentioned in JS:")
for mb in sorted(missing_btns):
    print(" -", mb)
if not missing_btns:
    print("ALL HTML BUTTONS CONNECTED IN JS!")
