"""Bounded synthetic page acquisition. No live provider contract is asserted.

An exhausted page sequence is observation, not proof. Only an independently
declared immutable fixture manifest (including exact row content) can qualify
this adapter's result for reconciliation. Attempts never mix pages.
"""
from copy import deepcopy
from decimal import Decimal
from .reconciliation import amount, digest, instant, money

LIMITS = {"max_attempts": 2, "max_pages": 5, "page_retries": 1, "page_size": 2,
          "retry_delays_seconds": [1], "label": "Assumed local fixture limits, not provider SLA"}


def row_digest(rows):
    return digest(sorted(rows, key=lambda r: r['event_id']))


def assess(contract, pages):
    """Assess retained responses against a fixed window/as-of/content contract."""
    problems, rows, expected_page = [], [], 1
    required = {'header', 'as_of', 'snapshot_token', 'ordering', 'controls', 'consistency'}
    if not isinstance(contract, dict) or set(contract) != required:
        return ['invalid_contract'], []
    try:
        header = contract['header']
        if instant(header['window_start']) >= instant(header['window_end']) or instant(contract['as_of']) < instant(header['window_end']):
            raise ValueError('Invalid contract window')
        if contract['ordering'] != 'event_id_ascending':
            problems.append('unsupported_ordering')
        if contract['consistency'] != 'immutable_fixture_manifest' or not contract['snapshot_token']:
            problems.append('upstream_snapshot_not_proven')
        if not isinstance(pages, list) or not 1 <= len(pages) <= LIMITS['max_pages']:
            return problems + ['page_budget_or_missing_pages'], []
        for index, page in enumerate(pages):
            if not isinstance(page, dict) or set(page) != {'page', 'next_page', 'rows', 'contract_sha256', 'snapshot_token'}:
                problems.append('invalid_page_envelope')
                break
            if type(page['page']) is not int or page['page'] != expected_page:
                problems.append('page_sequence_mismatch')
            if page['contract_sha256'] != digest(contract) or page['snapshot_token'] != contract['snapshot_token']:
                problems.append('contract_changed_during_fetch')
            if not isinstance(page['rows'], list) or not 1 <= len(page['rows']) <= LIMITS['page_size']:
                problems.append('invalid_page_rows')
                break
            rows.extend(deepcopy(page['rows']))
            next_page = page['next_page']
            if index == len(pages) - 1:
                if next_page is not None:
                    problems.append('fetch_incomplete_or_page_limit')
            elif type(next_page) is not int or next_page != expected_page + 1:
                problems.append('invalid_next_page')
            expected_page += 1
        ids = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'event_id', 'occurred_at', 'amount', 'status'}:
                raise ValueError('Invalid row schema')
            if not isinstance(row['event_id'], str) or not row['event_id'].strip():
                raise ValueError('Invalid ID')
            money(row['amount'])
            if row['status'] not in ('billable', 'rejected') or (row['status'] == 'rejected' and money(row['amount']) != 0):
                raise ValueError('Invalid status')
            if not instant(header['window_start']) <= instant(row['occurred_at']) < instant(header['window_end']):
                raise ValueError('Invalid row window')
            ids.append(row['event_id'])
        if len(ids) != len(set(ids)):
            problems.append('duplicate_event_ids')
        if ids != sorted(ids):
            problems.append('ordering_changed')
        controls = contract['controls']
        if not isinstance(controls, dict) or set(controls) != {'count', 'amount', 'rows_sha256'}:
            problems.append('authoritative_content_controls_missing')
        elif (type(controls['count']) is not int or controls['count'] != len(rows)
              or money(controls['amount']) != sum((money(r['amount']) for r in rows), Decimal('0'))
              or controls['rows_sha256'] != row_digest(rows)):
            problems.append('content_control_mismatch')
    except (KeyError, TypeError, ValueError, OverflowError):
        problems.append('malformed_contract_or_rows')
    return sorted(set(problems)), rows


def collect(source):
    """source.begin(attempt) / source.page(contract,page,attempt,try) are bounded.

    Live implementations must additionally enforce provider timeouts/deadlines.
    Only TimeoutError is retryable; auth/schema/permanent errors fail closed.
    The fixture records retry delay, without sleeping or contacting a network.
    """
    attempts = []
    for number in range(1, LIMITS['max_attempts'] + 1):
        record = {'number': number, 'contract': None, 'pages': [], 'calls': [], 'problems': []}
        attempts.append(record)
        try:
            contract = source.begin(number)
            record['contract'] = deepcopy(contract)
            for page in range(1, LIMITS['max_pages'] + 1):
                response = None
                for retry in range(LIMITS['page_retries'] + 1):
                    try:
                        response = source.page(contract, page, number, retry)
                        record['calls'].append({'page': page, 'try': retry + 1, 'outcome': 'response'})
                        break
                    except TimeoutError:
                        record['calls'].append({'page': page, 'try': retry + 1, 'outcome': 'timeout',
                                                'retry_delay_seconds': 1 if retry < LIMITS['page_retries'] else None})
                if response is None:
                    record['problems'].append('page_retry_exhausted')
                    break
                record['pages'].append(deepcopy(response))
                if not isinstance(response, dict) or response.get('next_page') is None:
                    break
            reasons, _ = assess(contract, record['pages'])
            record['problems'].extend(reasons)
        except (PermissionError, ValueError, TypeError, KeyError) as exc:
            record['problems'].append('permanent_source_error:' + type(exc).__name__)
            break
        record['problems'] = sorted(set(record['problems']))
        if not record['problems']:
            break
    return {'version': 'synthetic-page-acquisition-v1', 'limits': deepcopy(LIMITS), 'attempts': attempts,
            'classification': 'verified_fixture' if attempts and not attempts[-1]['problems'] else 'partial_or_uncertain',
            'limitations': ['Reaching the last page or repeating identical reads does not prove a consistent snapshot',
                           'Fixture contract is not evidence of a provider snapshot token/content manifest',
                           'No live auth, timeout, quota, watermark or settling contract verified']}


def materialize(proof):
    """Produce a report whose partial classification cannot pass check_report."""
    last = proof['attempts'][-1]
    reasons, rows = assess(last['contract'], last['pages'])
    header = deepcopy(last['contract']['header'])
    proven = proof['classification'] == 'verified_fixture' and not reasons and not last['problems']
    header.update(rows=rows, observed_at=last['contract']['as_of'],
                  snapshot={'kind': 'paginated_fixture', 'id': 'PAGES-' + digest(proof)[:24], 'complete': proven,
                            'control_count': len(rows), 'control_amount': amount(sum((money(r['amount']) for r in rows), Decimal('0')))},
                  acquisition=deepcopy(proof))
    return header


def acquisition_matches(report):
    """Reproduce exact content from all retained attempts, never from a success flag."""
    try:
        proof = report['acquisition']
        if proof['version'] != 'synthetic-page-acquisition-v1' or proof['limits'] != LIMITS:
            return False
        attempts = proof['attempts']
        if not 1 <= len(attempts) <= LIMITS['max_attempts'] or proof['classification'] != 'verified_fixture':
            return False
        for index, attempt in enumerate(attempts, 1):
            if attempt['number'] != index or len(attempt['calls']) > LIMITS['max_pages'] * (1 + LIMITS['page_retries']):
                return False
        reasons, _ = assess(attempts[-1]['contract'], attempts[-1]['pages'])
        return not reasons and not attempts[-1]['problems'] and digest(materialize(proof)) == digest(report)
    except (KeyError, TypeError, ValueError, OverflowError, IndexError):
        return False


class FixturePageSource:
    """Controlled upstream mutations, not a claim about Everflow's behavior."""
    def __init__(self, report, scenario='stable'):
        self.report, self.scenario = deepcopy(report), scenario

    def begin(self, attempt):
        if self.scenario == 'forbidden':
            raise PermissionError('Fixture forbidden')
        rows = self.report['rows']
        return {'header': {k: v for k, v in self.report.items() if k not in ('rows', 'snapshot', 'observed_at')},
                'as_of': self.report['observed_at'], 'ordering': 'event_id_ascending',
                'snapshot_token': 'FIXTURE-' + digest(self.report) if self.scenario != 'unproven' else None,
                'consistency': 'immutable_fixture_manifest' if self.scenario != 'unproven' else 'unverified',
                'controls': {'count': len(rows), 'amount': self.report['snapshot']['control_amount'], 'rows_sha256': row_digest(rows)}}

    def page(self, contract, page, attempt, retry):
        if self.scenario == 'timeout' or (self.scenario == 'transient' and page == 2 and retry == 0):
            raise TimeoutError('Fixture timeout')
        rows = deepcopy(self.report['rows'])
        mutation = self.scenario if self.scenario != 'settles' or attempt == 1 else 'stable'
        if page > 1:
            if mutation in ('insert', 'settles'): rows.insert(0, {**rows[0], 'event_id': 'DEMO-E000'})
            elif mutation == 'remove': rows.pop(0)
            elif mutation == 'reorder': rows.reverse()
            elif mutation == 'same_total_change':
                rows[2]['amount'], rows[3]['amount'] = '10.00', '15.00'
            elif mutation == 'correction': rows[2]['amount'] = '9.00'
            elif mutation == 'duplicate': rows[2] = deepcopy(rows[0])
            elif mutation == 'missing': rows.pop()
        size = LIMITS['page_size']
        selected = rows[(page - 1) * size:page * size]
        next_page = page + 1 if page * size < len(rows) else None
        if self.scenario == 'loop': next_page = page
        token = contract['snapshot_token']
        if self.scenario == 'token_change' and page > 1: token = 'NEW-TOKEN'
        return {'page': page, 'next_page': next_page, 'rows': selected,
                'snapshot_token': token, 'contract_sha256': digest(contract)}


def fixture_report(report, scenario):
    return materialize(collect(FixturePageSource(report, scenario)))
