import React, {useEffect, useState} from 'react';

const evidenceLabels = {
  ready: 'Buyer evidence ready',
  delivery_evidence: 'Delivery evidence only',
  unavailable: 'Evidence unavailable',
  stale: 'Evidence needs refresh',
  finance_hold: 'Finance hold',
};

function timeLabel(value) {
  return value?.replace('T', ' ').replace(/(?:\+00:00|Z)$/, ' UTC') || 'Not recorded';
}

async function readProjection(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.detail || 'Offer follow-through request failed');
    error.status = response.status;
    throw error;
  }
  return result;
}

export default function OfferFollowthrough({offerId, onFinance}) {
  const url = `/api/v2/offers/${encodeURIComponent(offerId)}/followthrough`;
  const [projection, setProjection] = useState(null);
  const [requestedTerms, setRequestedTerms] = useState('');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    readProjection(url, {signal: controller.signal, cache: 'no-store'})
      .then(setProjection)
      .catch(error => {
        if (error.name !== 'AbortError') setError(error.message);
      });
    return () => controller.abort();
  }, [url]);

  async function refresh() {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      setProjection(await readProjection(url, {cache: 'no-store'}));
      setNotice('Current Offer evidence refreshed.');
    } catch (error) {
      setError(error.message);
    } finally {
      setWorking(false);
    }
  }

  async function submit(endpoint, fields, successMessage) {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const result = await readProjection(url + endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ...fields,
          expected_evidence_sha: projection.evidence.sha256,
          event_id: crypto.randomUUID(),
        }),
      });
      setProjection(result);
      setNotice(successMessage);
      return true;
    } catch (error) {
      setError(error.message);
      if (error.status === 409) {
        try {
          setProjection(await readProjection(url, {cache: 'no-store'}));
        } catch (refreshError) {
          setError(`${error.message} Evidence refresh failed. ${refreshError.message}`);
        }
      }
      return false;
    } finally {
      setWorking(false);
    }
  }

  const {evidence, proposals, am_actions: amActions} = projection ?? {};

  async function prepareProposal(event) {
    event.preventDefault();
    if (await submit('/proposals', {requested_terms: requestedTerms}, 'BD draft ready for owner review.')) {
      setRequestedTerms('');
    }
  }

  return <>
    {error && <div className="v2-notice error" role="alert">{error}</div>}
    {notice && <div className="v2-notice" role="status">{notice}</div>}
    <section className="v2-panel v2-followthrough-evidence" aria-labelledby="offer-evidence-heading">
      <div className="v2-followthrough-heading">
        <h2 id="offer-evidence-heading">Current Offer evidence</h2>
        <button type="button" onClick={refresh} disabled={working}>Refresh Offer evidence</button>
      </div>
      {evidence ? <>
        <span className={`v2-chip ${evidence.status === 'ready' ? '' : 'warn'}`}>
          {evidenceLabels[evidence.status] || evidence.status}
        </span>
        <p>{evidence.reason}</p>
        <dl>
          <dt>Advertiser / Offer</dt>
          <dd>{evidence.scope.advertiser_id} / {evidence.scope.offer_id}</dd>
          <dt>Channel / Sub ID</dt>
          <dd>{evidence.scope.channel_id} / {evidence.scope.sub_id}</dd>
          <dt>Configuration / release</dt>
          <dd>Version {evidence.config_version ?? 'unknown'} / {evidence.release_id ?? 'pending'}</dd>
          <dt>Batch / buyer feedback</dt>
          <dd>{evidence.batch_id ?? 'Pending'} / {evidence.feedback_id ?? 'pending'}</dd>
          <dt>Delivered / rejected at intake</dt>
          <dd>{evidence.quality?.delivered ?? 'Unknown'} / {evidence.quality?.rejected_at_intake ?? 'unknown'}</dd>
          <dt>Buyer contacts / sales</dt>
          <dd>{evidence.quality?.connected ?? 'Unknown'} / {evidence.quality?.closed_won ?? 'unknown'}</dd>
          <dt>Available channel capacity</dt>
          <dd>{evidence.capacity?.available ?? 'Unknown'} {evidence.capacity?.date_utc && `· ${evidence.capacity.date_utc} UTC`}</dd>
        </dl>
        {evidence.status === 'finance_hold' && (
          <div className="v2-evidence">
            <b>Finance owns the return decision</b>
            <p>Proposal and channel decisions wait for the held buyer evidence. The Finance preview retains the disputed outcome.</p>
            <button type="button" onClick={() => onFinance(evidence.batch_id)}>Open Finance review</button>
          </div>
        )}
        <details>
          <summary>Exact Offer evidence</summary>
          <pre>{JSON.stringify(evidence, null, 2)}</pre>
        </details>
      </> : <p>{error ? 'Refresh to retrieve the Offer evidence.' : 'Loading the Offer evidence…'}</p>}
    </section>
    {evidence && <div className="v2-grid">
      <section className="v2-panel v2-followthrough-records" aria-labelledby="offer-bd-heading">
        <h2 id="offer-bd-heading">BD proposal review</h2>
        <p>Current buyer outcomes and channel capacity inform the review. The draft retains approved synthetic clauses and requested commercial terms separately.</p>
        <form className="v2-form" onSubmit={prepareProposal}>
          <label>
            Requested commercial terms
            <textarea required maxLength={2000} value={requestedTerms} onChange={event => setRequestedTerms(event.target.value)} />
          </label>
          <button className="v2-primary" disabled={working || !evidence.bd_ready || !requestedTerms.trim()}>
            Prepare synthetic proposal
          </button>
        </form>
        {proposals.length ? [...proposals].reverse().map(proposal => (
          <Proposal key={proposal.id} proposal={proposal} ready={evidence.bd_ready} working={working} submit={submit} />
        )) : <p className="v2-muted">No proposal has been prepared for this Offer.</p>}
      </section>
      <section className="v2-panel v2-followthrough-records" aria-labelledby="offer-am-heading">
        <h2 id="offer-am-heading">AM channel follow-through</h2>
        <p>AM owns delivery and buyer outcome issues for this exact placement. Closing an action records the work and schedules a synthetic review after 24 hours.</p>
        <button className="v2-primary" type="button" disabled={working || !evidence.am_ready}
          onClick={() => submit('/am-actions', {}, 'Channel action retained for the current evidence.')}>
          Open channel action
        </button>
        {amActions.length ? [...amActions].reverse().map(action => (
          <ChannelAction key={action.id} action={action} ready={evidence.am_ready} working={working} submit={submit} />
        )) : <p className="v2-muted">No channel action has been opened for this Offer.</p>}
      </section>
    </div>}
  </>;
}

function RecordHeading({title, current, status}) {
  return <div className="v2-followthrough-heading">
    <h3>{title}</h3>
    <span className={`v2-chip ${current ? '' : 'warn'}`}>{current ? status : 'Historical evidence'}</span>
  </div>;
}

function Proposal({proposal, ready, working, submit}) {
  function recordReview(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    submit(`/proposals/${proposal.id}/review`, {
      expected_version: proposal.version,
      note: fields.get('note'),
    }, 'BD owner review recorded for the current evidence.');
  }

  return <article className="v2-followthrough-record" aria-label={`Proposal ${proposal.id}`}>
    <RecordHeading title="Synthetic proposal" current={proposal.current}
      status={proposal.status === 'reviewed' ? 'Reviewed draft' : 'Owner review pending'} />
    <p><strong>Owner</strong> {proposal.owner}</p>
    {!proposal.current && <p className="v2-historical">Prepare a fresh draft and review it against the current evidence.</p>}
    <div className="v2-evidence">
      <b>Approved synthetic clauses</b>
      <p className="v2-followthrough-text">{proposal.approved_clauses}</p>
    </div>
    <div className="v2-evidence v2-requested-terms">
      <b>Requested terms for discussion</b>
      <p className="v2-followthrough-text">{proposal.requested_terms}</p>
    </div>
    {proposal.review && <p className="v2-followthrough-text">
      <strong>Recorded review</strong> {proposal.review.note} · {timeLabel(proposal.review.created_at)}
    </p>}
    {proposal.current && proposal.status === 'pending_review' && <form className="v2-form" onSubmit={recordReview}>
      <label>BD review note<textarea name="note" required maxLength={2000} /></label>
      <button disabled={working || !ready}>Record BD review</button>
    </form>}
    <details><summary>Proposal record and evidence</summary><pre>{JSON.stringify(proposal, null, 2)}</pre></details>
  </article>;
}

function ChannelAction({action, ready, working, submit}) {
  function recordResolution(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    submit(`/am-actions/${action.id}/resolve`, {
      expected_version: action.version,
      note: fields.get('note'),
    }, 'AM resolution recorded and recurring review scheduled.');
  }

  return <article className="v2-followthrough-record" aria-label={`Channel action ${action.id}`}>
    <RecordHeading title="Channel action" current={action.current}
      status={action.status === 'resolved' ? 'Resolved' : 'Open'} />
    <p><strong>Owner</strong> {action.owner}</p>
    <p><strong>Next action</strong> {action.next_action}</p>
    {!action.current && action.status === 'open' && <p className="v2-historical">
      Open the channel action against current evidence before recording a resolution.
    </p>}
    {action.resolution && <p className="v2-followthrough-text">
      <strong>Recorded resolution</strong> {action.resolution.note} · {timeLabel(action.resolution.created_at)}
    </p>}
    {action.next_review_at && <p>
      <strong>{action.review_schedule_active ? 'Next recurring review' : 'Prior recurring review'}</strong>
      {' '}{timeLabel(action.next_review_at)}
      {' '}<span className={`v2-chip ${action.review_due ? 'warn' : ''}`}>
        {!action.review_schedule_active ? 'Historical schedule' : action.review_due ? 'Review due' : 'Scheduled'}
      </span>
    </p>}
    {action.current && action.status === 'open' && <form className="v2-form" onSubmit={recordResolution}>
      <label>AM resolution note<textarea name="note" required maxLength={2000} /></label>
      <button disabled={working || !ready}>Record AM resolution</button>
    </form>}
    <details><summary>Channel action and evidence</summary><pre>{JSON.stringify(action, null, 2)}</pre></details>
  </article>;
}
