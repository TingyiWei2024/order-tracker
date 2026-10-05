"""Capture one HTTP lookup and its metric/log/trace backend evidence."""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def get(url, params=None):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('order_id')
    parser.add_argument('output')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    start = time.time_ns()
    url = 'http://localhost:8000/api/orders/' + urllib.parse.quote(args.order_id, safe='')
    try:
        response = urllib.request.urlopen(url, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    body = response.read().decode()
    trace_id = response.headers.get('X-Trace-Id')
    request = dict(url=url, status=response.status, headers=dict(response.headers), body=body, trace_id=trace_id, start_ns=start)
    (out / 'request.json').write_text(json.dumps(request, indent=2)+'\n')
    print(json.dumps(request), flush=True)
    if not trace_id:
        raise RuntimeError('Request did not return X-Trace-Id; cannot claim correlation')
    deadline = time.monotonic() + 60
    metric = logs = trace = None
    errors = []
    while time.monotonic() < deadline:
        try:
            metric = get('http://localhost:9090/api/v1/query', {'query': 'order_lookup_requests_total{http_response_status_code="'+str(response.status)+'"}'})
            logs = get('http://localhost:3100/loki/api/v1/query_range', {'query': '{service_name="order-tracker"} | trace_id="'+trace_id+'"','start':start-1_000_000_000,'end':time.time_ns(),'limit':20})
            trace = get('http://localhost:3200/api/traces/'+trace_id)
            if metric.get('data',{}).get('result') and logs.get('data',{}).get('result') and trace:
                break
        except (urllib.error.URLError, ValueError) as error:
            errors.append(str(error))
        time.sleep(2)
    else:
        raise RuntimeError('Incomplete telemetry: '+repr(errors[-3:]))
    for name, value in [('metric',metric),('logs',logs),('trace',trace)]:
        (out / (name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
    print('Captured metric, log, trace for '+trace_id)


if __name__ == '__main__':
    main()
