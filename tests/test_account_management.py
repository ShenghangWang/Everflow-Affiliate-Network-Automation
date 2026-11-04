from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import app as app_module
from backend.domain import Workflow, parse
from backend.account_management import AccountManagement, StaleAccountAction, settings


class AccountManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'am.sqlite3')
        self.w=Workflow(self.path);self.am=AccountManagement(self.w);self.event=0

    def tearDown(self):self.tmp.cleanup()

    def start(self,lead_id='L001'):
        self.w.reply(lead_id,'I am interested','handoff-'+lead_id)
        return self.am.start(lead_id)['accounts'][0]

    def account(self):return self.am.state()['accounts'][0]

    def apply(self,fixture_id):
        self.event+=1
        return self.am.apply_fixture(self.account()['id'],fixture_id,'AM-E'+str(self.event))

    def decide(self,decision,account=None):
        a=account or self.account()
        return self.am.decide(a['id'],a['version'],decision,'Synthetic owner reviewed current evidence','Fixture hashes, approved terms and sandbox/readback checked')

    def activate(self):
        self.start();self.apply('ready');return self.decide('approve_activation')

    def test_bd_handoff_creates_one_owned_pending_case_and_signature_does_not_activate(self):
        with self.assertRaises(ValueError):self.am.start('L001')
        a=self.start()
        self.assertEqual(a['status'],'pending_activation')
        self.assertEqual(a['next_owner'],'Demo onboarding owner')
        state=self.apply('signed_only')
        self.assertEqual(state['accounts'][0]['status'],'pending_activation')
        self.assertTrue(state['accounts'][0]['readiness_problems'])
        with self.assertRaises(ValueError):self.decide('approve_activation')
        for _ in range(10):self.am.start('L001')
        self.assertEqual(len(self.am.state()['accounts']),1)
        self.assertEqual(self.am.state()['tasks'],[])

    def test_complete_readiness_requires_explicit_version_bound_owner_approval(self):
        self.start();self.apply('ready');prior=self.account()
        self.assertEqual(prior['status'],'pending_activation')
        state=self.decide('approve_activation')
        account=state['accounts'][0]
        self.assertEqual(account['status'],'active')
        self.assertEqual(account['outcome_status'],'unverified')
        self.assertEqual(account['next_owner'],'Demo AM owner')
        self.assertEqual({t['kind'] for t in state['tasks']},{'activation_followthrough','health_review'})
        self.assertEqual((parse(account['next_check_at'])-parse(self.w.state()['now'])).total_seconds()/3600,24)
        with self.assertRaises(StaleAccountAction):self.decide('approve_activation',prior)
        self.assertEqual(len(self.am.state()['outcomes']),1)

    def test_stale_mapping_missing_and_changed_terms_block_activation(self):
        for fixture in ('signed_only','stale_readiness','mapping_regression'):
            with self.subTest(fixture=fixture):
                self.w.reset();self.start();self.apply(fixture)
                with self.assertRaises(ValueError):self.decide('approve_activation')
                self.assertFalse(self.am.state()['tasks'])
        self.w.reset();self.start();self.apply('ready')
        self.w.change_terms('13.00')
        with self.assertRaises(ValueError):self.decide('approve_activation')
        self.assertEqual(self.account()['status'],'pending_activation')

    def test_health_unknown_without_evidence_stale_and_partial_evidence_never_supply_counts(self):
        self.activate()
        self.assertIsNone(self.account()['health']['accepted_outcomes'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        for fixture in ('stale_health','partial_health'):
            state=self.apply(fixture);a=state['accounts'][0]
            self.assertIsNone(a['health']['accepted_outcomes'])
            self.assertEqual(a['next_owner'],'Demo integration owner')
            self.assertIsNone(a['draft'])
            with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.assertEqual(len([i for i in self.am.state()['issues'] if i['kind']=='data_quality']),1)

    def test_low_activation_tracking_repair_first_outcome_and_next_owned_cycle(self):
        core=self.w.state();self.activate();self.apply('low_activation')
        self.assertEqual(self.account()['next_owner'],'Demo AM owner')
        self.assertIn('0 accepted',self.account()['draft']['content'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.apply('tracking_fault')
        self.assertEqual(self.account()['next_owner'],'Demo integration owner')
        task=next(t for t in self.am.state()['tasks'] if t['kind']=='issue_followthrough')
        self.assertEqual(task['owner'],'Demo integration owner')
        self.apply('healthy')
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.apply('tracking_fixed');state=self.decide('verify_outcome')
        self.assertEqual(state['accounts'][0]['outcome_status'],'verified')
        self.assertTrue(all(i['status']=='resolved' for i in state['issues']))
        pending=[t for t in state['tasks'] if t['status']=='scheduled']
        self.assertEqual(len(pending),1)
        self.assertEqual(pending[0]['kind'],'health_review')
        self.assertEqual((parse(pending[0]['due_at'])-parse(self.w.state()['now'])).total_seconds()/3600,168)
        self.assertFalse(state['effects']['external_effects'])
        after=self.w.state()
        for key in ('actions','messages','authorizations','policy','cost'):
            if key!='messages':self.assertEqual(core[key],after[key])
        self.assertEqual(len(after['messages']),1) # Only the injected BD handoff reply.

    def test_first_outcome_due_boundary_and_duplicate_tick_alert_once(self):
        self.activate();self.w.tick(23)
        self.assertEqual(next(t for t in self.am.state()['tasks'] if t['kind']=='activation_followthrough')['status'],'scheduled')
        self.w.tick(1);self.w.tick(0)
        events=[e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due']
        self.assertEqual(len(events),1)
        self.assertEqual(self.account()['next_owner'],'Demo integration owner')
        self.assertIn('missing',self.account()['health']['reason'])
        self.assertFalse(self.w.state()['actions'])

    def test_weekly_health_review_reopens_missing_current_evidence_and_reschedules_after_verification(self):
        self.activate();self.apply('healthy');self.decide('verify_outcome')
        self.w.tick(167)
        self.assertFalse([e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due'])
        self.w.tick(1);self.w.tick(0)
        self.assertEqual(len([e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due']),1)
        self.assertEqual(self.account()['health']['status'],'unknown')
        self.assertEqual(self.account()['outcome_status'],'verified') # Historical outcome is separate.
        self.assertIsNone(self.account()['draft'])
        self.apply('healthy');self.decide('verify_outcome')
        tasks=[t for t in self.am.state()['tasks'] if t['kind']=='health_review' and t['status']=='scheduled']
        self.assertEqual(len(tasks),1)
        self.assertEqual((parse(tasks[0]['due_at'])-parse(self.w.state()['now'])).total_seconds()/3600,168)

    def test_duplicate_evidence_events_and_concurrent_intake_are_idempotent(self):
        self.start();a=self.account()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:self.am.start('L001'),range(10)))
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:self.am.apply_fixture(a['id'],'ready','SAME-EVENT'),range(10)))
        state=self.am.state()
        self.assertEqual(len(state['accounts']),1)
        self.assertEqual(len(state['evidence']),1)
        version=state['accounts'][0]['version']
        self.w.tick(1)
        self.am.apply_fixture(a['id'],'ready','SAME-EVENT')
        self.assertEqual(self.account()['version'],version)
        with self.assertRaises(StaleAccountAction):self.am.apply_fixture(a['id'],'signed_only','SAME-EVENT')
        self.assertEqual(len(self.am.state()['evidence']),1)

    def test_competing_approvals_produce_one_activation_epoch_and_one_set_of_tasks(self):
        self.start();self.apply('ready');a=self.account()
        def approve(_):
            try:self.decide('approve_activation',a);return 'approved'
            except StaleAccountAction:return 'stale'
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(approve,range(10)))
        self.assertEqual(results.count('approved'),1)
        self.assertEqual(len(self.am.state()['tasks']),2)
        self.assertEqual(self.account()['epoch'],1)

    def test_cancel_preserves_history_and_no_due_or_evidence_can_resume_it(self):
        self.activate();old=self.account();self.decide('cancel')
        self.w.tick(168)
        state=self.am.state()
        self.assertEqual(state['accounts'][0]['status'],'cancelled')
        self.assertTrue(all(t['status']=='cancelled' for t in state['tasks']))
        self.assertFalse([e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due'])
        with self.assertRaises(ValueError):self.apply('healthy')
        with self.assertRaises(StaleAccountAction):self.decide('approve_activation',old)
        self.assertEqual(len(self.am.start('L001')['accounts']),1)

    def test_optout_cancels_am_tasks_immediately_and_does_not_restore_bd_authority(self):
        self.activate();self.w.reply('L001','unsubscribe','optout-am')
        self.assertEqual(self.account()['status'],'cancelled')
        self.assertTrue(all(t['status']=='cancelled' for t in self.am.state()['tasks']))
        self.w.tick(168)
        self.assertFalse([e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due'])
        self.assertEqual(self.w.state()['leads'][0]['stage'],'suppressed')

    def test_material_record_terms_and_readiness_changes_cancel_old_tasks_and_require_reapproval(self):
        for change in ('lead','terms','mapping'):
            with self.subTest(change=change):
                self.w.reset();self.activate()
                if change=='lead':self.w.edit('L001',recipient='alex-new@northstar.example')
                elif change=='terms':self.w.change_terms('13.00')
                else:self.apply('mapping_regression')
                self.assertEqual(self.account()['status'],'readiness_review')
                self.assertTrue(all(t['status']=='cancelled' for t in self.am.state()['tasks']))
                self.w.tick(24)
                self.assertFalse([e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due'])
                self.apply('ready');self.decide('approve_activation')
                self.assertEqual(self.account()['status'],'active')
                self.assertEqual(self.account()['outcome_status'],'unverified')

    def test_missing_notes_stale_state_and_unapproved_actions_have_no_effect(self):
        self.start();self.apply('ready');a=self.account()
        with self.assertRaises(ValueError):self.am.decide(a['id'],a['version'],'approve_activation','','reference')
        with self.assertRaises(ValueError):self.am.decide(a['id'],a['version'],'send','note','reference')
        self.apply('signed_only')
        with self.assertRaises(StaleAccountAction):self.decide('approve_activation',a)
        self.assertFalse(self.am.state()['tasks'])

    def test_source_hashes_preserve_immutable_evidence_and_rules_changes_fail_closed(self):
        self.activate();state=self.apply('healthy')
        import hashlib
        for evidence in state['evidence']:
            encoded=json.dumps(evidence['payload'],sort_keys=True,separators=(',',':'))
            self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(),evidence['sha256'])
        data=deepcopy(settings());data['health_review_hours']=72
        with patch('backend.account_management.settings',return_value=data):
            with self.assertRaises(StaleAccountAction):self.decide('verify_outcome')
            self.w.tick(0)
            self.assertEqual(self.account()['status'],'readiness_review')
            self.assertTrue(all(t['status']=='cancelled' for t in self.am.state()['tasks']))

    def test_restart_preserves_pending_active_and_resolved_state_and_explicit_reset(self):
        self.activate();self.apply('tracking_fault');self.w.tick(24)
        before=self.w.state();reopened=Workflow(self.path)
        self.assertEqual(before,reopened.state())
        self.w=reopened;self.am=AccountManagement(reopened)
        self.apply('tracking_fixed');self.decide('verify_outcome')
        before=self.w.state();self.assertEqual(before,Workflow(self.path).state())
        self.w.reset();self.assertEqual(self.am.state()['accounts'],[])
        self.assertEqual(self.am.state()['tasks'],[])

    def test_health_observed_before_activation_is_not_a_first_outcome(self):
        self.start();self.apply('ready');self.apply('healthy');self.w.tick(1);self.decide('approve_activation')
        self.assertIn('predates',self.account()['health']['reason'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.apply('healthy');self.decide('verify_outcome')
        self.assertEqual(self.account()['outcome_status'],'verified')

    def test_same_instant_pre_activation_and_prior_epoch_counts_cannot_verify_new_outcome(self):
        self.start();self.apply('ready');self.apply('healthy')
        self.decide('approve_activation')
        self.assertIsNone(self.account()['health']['accepted_outcomes'])
        self.assertIn('epoch',self.account()['health']['reason'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.apply('healthy');self.decide('verify_outcome')
        self.apply('mapping_regression');self.apply('ready');self.decide('approve_activation')
        self.assertIsNone(self.account()['health']['accepted_outcomes'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')
        self.apply('healthy');self.decide('verify_outcome')
        self.assertEqual(self.account()['outcome_status'],'verified')

    def test_repeated_outcome_review_of_same_evidence_cannot_postpone_due_check(self):
        self.activate();self.apply('healthy');self.decide('verify_outcome')
        original=self.am.state()
        self.w.tick(1)
        before=self.w.state()
        self.decide('verify_outcome')
        self.assertEqual(before,self.w.state())
        self.assertEqual(original['accounts'][0]['next_check_at'],self.account()['next_check_at'])
        self.assertEqual(len(original['outcomes']),len(self.am.state()['outcomes']))

    def test_concurrent_scheduler_ticks_deduplicate_owned_due_tasks(self):
        self.activate()
        with self.w.tx() as c:
            now=parse(self.w._get(c,'now'))+timedelta(hours=24)
            self.w._set(c,'now',now.isoformat())
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:self.w.tick(0),range(10)))
        due=[e for e in self.w.state()['audit'] if e['event']=='am_followthrough_due']
        self.assertEqual(len(due),1)
        self.assertEqual(len([t for t in self.am.state()['tasks'] if t['status']=='due']),1)
        self.assertEqual(len([i for i in self.am.state()['issues'] if i['kind']=='data_quality']),1)

    def test_future_evidence_timestamp_and_config_interval_validation(self):
        self.activate();self.apply('healthy')
        with self.w.tx() as c:
            # Simulate an invalid source clock before using otherwise exact data.
            original=self.w._get(c,'now');self.w._set(c,'now',(parse(original)-timedelta(hours=1)).isoformat())
        self.assertIsNone(self.account()['health']['accepted_outcomes'])
        self.assertIn('future',self.account()['health']['reason'])
        with self.assertRaises(ValueError):self.decide('verify_outcome')

    def test_api_connects_bd_activation_and_review_and_rejects_extra_authority(self):
        app_module.workflow=self.w
        with TestClient(app_module.app) as client:
            self.assertEqual(client.post('/api/am/start',json={'lead_id':'L001'}).status_code,400)
            self.start();a=self.account()
            route=f"/api/am/accounts/{a['id']}"
            self.assertEqual(client.post(route+'/fixture',json={'fixture_id':'../../.env','event_id':'x'}).status_code,400)
            self.assertEqual(client.post(route+'/fixture',json={'fixture_id':'ready','event_id':'x','execute':'live'}).status_code,400)
            state=client.post(route+'/fixture',json={'fixture_id':'ready','event_id':'x'}).json();a=state['accounts'][0]
            body={'expected_version':a['version'],'decision':'approve_activation','note':'Synthetic approval','evidence':'Current fixture gates'}
            self.assertEqual(client.post(route+'/decision',json={**body,'actor':'admin'}).status_code,400)
            self.assertEqual(client.post(route+'/decision',json=body).status_code,200)
            self.assertEqual(client.post(route+'/decision',json=body).status_code,409)
            self.assertFalse(client.get('/api/am').json()['effects']['external_effects'])
            self.assertEqual(client.get('/api/state').json()['account_management']['accounts'][0]['status'],'active')
