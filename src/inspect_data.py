import json
import os

file_path = r"c:\Users\derma\Desktop\‏‏‏‏‏‏الاجدد - نسخة - نسخة - نسخة (3)\price_analysis\بيانات\combined_snapshots_ADAUSDT_20260209162920.json"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"Type: {type(data)}")
        if isinstance(data, dict):
            print(f"Keys: {data.keys()}")
            if 'block16' in data:
                print(f"block16 type: {type(data['block16'])}")
                if isinstance(data['block16'], list):
                    print(f"block16 length: {len(data['block16'])}")
                    # Check timestamps to see if they are sequential
                    timestamps = []
                    for item in data['block16']:
                        if 'timestamp' in item:
                            timestamps.append(item['timestamp'])
                    print(f"Timestamps in block16: {timestamps}")
            if 'last_snapshot' in data:
                print(f"last_snapshot type: {type(data['last_snapshot'])}")
except Exception as e:
    print(f"Error: {e}")
