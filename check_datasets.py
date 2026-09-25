import urllib.request
import re

# Check a few promising datasets for open access
datasets = [
    'chfdb',  # Congestive Heart Failure RR Interval Database
    'bidmc',  # BIDMC Congestive Heart Failure Database
    'apnea-ecg',  # Apnea-ECG Database
    'bidsleep-dataset',  # Already have
    'ecg-arrhythmia',  # ECG Arrhythmia
    'wearable-exam-stress',  # Wearable stress data
    'big-ideas-glycemic-wearable',  # Glucose + wearable
]

for ds in datasets:
    url = f'https://physionet.org/content/{ds}/'
    try:
        req = urllib.request.Request(url, headers={'Accept': 'text/html'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')
        
        # Check for license/access info
        if 'Open Data Commons' in html or 'Public Domain' in html or 'ODC' in html:
            access = 'OPEN'
        elif 'credential' in html.lower() or 'restricted' in html.lower():
            access = 'RESTRICTED'
        else:
            access = 'UNKNOWN'
        
        # Find file listings
        files = re.findall(r'href="([^"]+\.(?:csv|dat|hea|txt|json))"', html)
        print(f'{ds}: {access} - {len(files)} data files')
        if files:
            print(f'  Example: {files[:3]}')
    except Exception as e:
        print(f'{ds}: ERROR - {e}')