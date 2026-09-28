import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

buttons = re.findall(r'<button[^>]*>.*?</button>', html, re.DOTALL)
print(f'Total buttons found in HTML: {len(buttons)}')
import sys
sys.stdout.reconfigure(encoding='utf-8')

for b in buttons:
    tag = b.split('>')[0]
    id_m = re.search(r'id=["\']([^"\']+)["\']', tag)
    class_m = re.search(r'class=["\']([^"\']+)["\']', tag)
    bid = id_m.group(1) if id_m else "None"
    bcls = class_m.group(1) if class_m else ''
    text = re.sub(r'<[^>]+>', '', b).strip().replace('\n', ' ')
    print(f'ID: {bid:25} | Text: {text[:25]:25} | Class: {bcls[:30]}')

