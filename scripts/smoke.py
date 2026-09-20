"""Exercise a running, genuinely configured API; never supplies mock answers."""

import argparse
import json
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--question', default='What is Atlas Forge\'s current launch date, and what changed from kickoff?')
    args = parser.parse_args()
    base = args.url.rstrip('/')

    def request(path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)

    try:
        health = request('/api/health')
        if not health['ready']:
            raise RuntimeError('Service is not ready: ' + '; '.join(health.get('warnings', [])))
        result = request('/api/query', {'question': args.question})
        assert result['query_id'] and result['status'] in {'answered', 'partial', 'needs_routing'}
        evidence = {item['chunk_id']: item for item in result['evidence']}
        for claim in result['claims']:
            assert claim['citations'], 'An answer claim has no citations'
            for citation in claim['citations']:
                source = evidence[citation['chunk_id']]
                assert ' '.join(citation['quote'].split()) in ' '.join(source['text'].split()), 'Citation quote does not match source'
                assert source['filename'] and source['locator'], 'Missing source location'
                request('/api/sources/' + source['document_id'])
        persisted = request('/api/query/' + result['query_id'])
        assert persisted == result, 'Stored answer snapshot changed'
        request('/api/review')
        request('/api/outbox')
        request('/api/metrics')
        request('/api/quality')
        print(json.dumps({'status': 'passed', 'query_id': result['query_id'], 'answer_status': result['status'],
                          'claims': len(result['claims']), 'evidence': len(result['evidence'])}, indent=2))
        return 0
    except (urllib.error.URLError, RuntimeError, AssertionError, KeyError) as exc:
        print(f'Smoke test failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
