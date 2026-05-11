import zipfile, json, os

data_dir = r'D:\100_Work\101_Program\Proj\fba\backend\scripts\vocab_data'
for zf_name in ['CET4_3.zip', 'CET6_3.zip', 'KaoYan_3.zip']:
    zf_path = os.path.join(data_dir, zf_name)
    print(f'\n=== {zf_name} ({os.path.getsize(zf_path)} bytes) ===')
    with zipfile.ZipFile(zf_path) as zf:
        names = zf.namelist()
        print(f'  Files: {names}')
        json_files = [n for n in names if n.endswith('.json')]
        if json_files:
            with zf.open(json_files[0]) as f:
                raw = f.read().decode('utf-8')
            lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]
            print(f'  Lines (JSONL): {len(lines)}')
            first = json.loads(lines[0])
            print(f'  Top keys: {list(first.keys())}')
            hw = first.get('headWord', 'N/A')
            print(f'  headWord: {hw}')
            content = first.get('content', {})
            word_data = content.get('word', {})
            word_content = word_data.get('content', {})
            print(f'  word_content keys: {list(word_content.keys())}')
            trans = word_content.get('trans', [])
            if trans:
                print(f'  trans[0]: {json.dumps(trans[0], ensure_ascii=False)}')
            usphone = word_content.get('usphone', '')
            ukphone = word_content.get('ukphone', '')
            print(f'  usphone: {usphone}, ukphone: {ukphone}')
            sentences = word_content.get('sentence', {}).get('sentences', [])
            print(f'  sentences count: {len(sentences)}')
            if sentences:
                print(f'  sentence[0]: {json.dumps(sentences[0], ensure_ascii=False)}')
