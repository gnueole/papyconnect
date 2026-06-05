import sqlite3
import json

def parse_flatted(data):
    if not isinstance(data, list):
        return data
    
    resolved = {}
    
    def resolve(val):
        if isinstance(val, str) and val.isdigit():
            idx = int(val)
            if idx < len(data):
                if idx in resolved:
                    return resolved[idx]
                resolved[idx] = "...circular..."
                resolved[idx] = resolve_val(data[idx])
                return resolved[idx]
        return val
        
    def resolve_val(val):
        if isinstance(val, dict):
            return {k: resolve(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [resolve(v) for v in val]
        return val

    return resolve_val(data[0])

try:
    conn = sqlite3.connect('/volume1/docker/n8n/data/n8n_data/database.sqlite')
    cursor = conn.cursor()
    cursor.execute('SELECT executionId, data FROM execution_data ORDER BY executionId DESC LIMIT 1;')
    row = cursor.fetchone()
    if row:
        exec_id = row[0]
        print(f"Checking Execution ID: {exec_id}")
        raw_data = json.loads(row[1])
        parsed = parse_flatted(raw_data)
        run_data = parsed.get('resultData', {}).get('runData', {})
        for node, runs in run_data.items():
            for i, run in enumerate(runs):
                print(f"Node: {node}")
                if run and isinstance(run, dict) and 'error' in run:
                    err = run['error']
                    print(f"  Status: FAILED")
                    print(f"  Error Message: {err.get('message') if isinstance(err, dict) else err}")
                else:
                    print(f"  Status: SUCCESS")
                    # If it succeeded, print some output
                    if run and isinstance(run, dict) and 'data' in run:
                        print(f"  Output: {json.dumps(run['data'], indent=4)}")
except Exception as ex:
    print(f"Exception: {ex}")
