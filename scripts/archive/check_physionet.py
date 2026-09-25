import urllib.request
import re

# Get the database listing page
resp = urllib.request.urlopen('https://physionet.org/about/database/')
html = resp.read().decode('utf-8', errors='ignore')

# Find dataset links
links = re.findall(r'href="(/content/[^"]+)"', html)
print(f'Found {len(links)} dataset links')
for link in links[:30]:
    print(f'  https://physionet.org{link}')