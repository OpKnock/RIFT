import urllib.request
import re

for subdir in ['Final', 'midterm_1', 'midterm_2']:
    url = f'https://physionet.org/files/wearable-exam-stress/1.0.0/data/S1/{subdir}/'
    req = urllib.request.Request(url, headers={'Accept': 'text/html'})
    resp = urllib.request.urlopen(req, timeout=30)
    html = resp.read().decode('utf-8', errors='ignore')
    
    files = re.findall(r'href="([^"]+\.(?:csv|txt|edf))"', html)
    print(f'{subdir}: {files}')