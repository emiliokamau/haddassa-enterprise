#!/usr/bin/env python3
import json
import sys
import os
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import base64

INPUT_PATH = os.path.join(os.path.dirname(__file__), 'services_input.json')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'services_with_placeholders.json')

# Read input JSON
with open(INPUT_PATH, 'r', encoding='utf-8') as f:
    services = json.load(f)

result = {}

for name, meta in services.items():
    cloud_url = meta.get('cloudinary', '').strip()
    if not cloud_url:
        print(f'[WARN] No cloudinary URL for {name}; skipping')
        result[name] = meta
        continue

    # Build transformed URL: insert transformation after /upload/
    trans = 'w_20,q_10,f_jpg'
    if '/upload/' in cloud_url:
        parts = cloud_url.split('/upload/')
        transformed = parts[0] + '/upload/' + trans + '/' + parts[1]
    else:
        # fallback: append as query param
        transformed = cloud_url

    # Fetch the transformed image
    try:
        req = Request(transformed, headers={'User-Agent': 'python-urllib/3'})
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
            b64 = base64.b64encode(data).decode('ascii')
            mime = 'image/jpeg'
            placeholder = f'data:{mime};base64,{b64}'
            meta_out = dict(meta)
            meta_out['placeholder'] = placeholder
            result[name] = meta_out
            print(f'[OK] Generated placeholder for {name}')
    except Exception as e:
        print(f'[ERROR] Failed to fetch transformed image for {name}: {e}')
        # attempt to fetch original
        try:
            req = Request(cloud_url, headers={'User-Agent': 'python-urllib/3'})
            with urlopen(req, timeout=15) as resp:
                data = resp.read()
                b64 = base64.b64encode(data).decode('ascii')
                # guess mime from url extension
                mime = 'image/jpeg'
                if cloud_url.lower().endswith('.png'):
                    mime = 'image/png'
                placeholder = f'data:{mime};base64,{b64}'
                meta_out = dict(meta)
                meta_out['placeholder'] = placeholder
                result[name] = meta_out
                print(f'[OK] Generated placeholder from original for {name}')
        except Exception as e2:
            print(f'[ERROR] Failed to fetch original image for {name}: {e2}')
            result[name] = meta

# Write output JSON
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2)

print('\nWrote output to:', OUTPUT_PATH)
print('You can copy the contents of this file into SERVICES_JSON or upload as needed.')
