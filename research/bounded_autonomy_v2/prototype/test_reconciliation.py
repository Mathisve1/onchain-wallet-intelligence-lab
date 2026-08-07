import unittest
from decimal import Decimal
from reconciliation import ActionJournal, ReconciliationError

class Tests(unittest.TestCase):
    def order(self, risk=True):
        j=ActionJournal()
        r=j.create(action_id='a1',permit_id='p1',action='PLACE_IOC_LIMIT',instrument='BTC',risk_increasing=risk,expected_quantity='0.02')
        return j,r

    def test_new_risk_blocked_from_intent_until_terminal(self):
        j,r=self.order(); self.assertFalse(j.can_issue_new_risk())
        r.transition('POLICY_ALLOWED'); r.transition('PERMIT_ISSUED'); r.transition('PERMIT_CONSUMED'); r.transition('SIGNED'); r.transition('SUBMITTED'); r.transition('ACKNOWLEDGED'); r.record_fill('0.02')
        self.assertTrue(r.terminal); self.assertTrue(j.can_issue_new_risk())

    def test_partial_fill_stays_unresolved(self):
        j,r=self.order(); r.transition('POLICY_ALLOWED'); r.transition('PERMIT_ISSUED'); r.transition('PERMIT_CONSUMED'); r.transition('SIGNED'); r.transition('SUBMITTED'); r.transition('ACKNOWLEDGED'); r.record_fill('0.005')
        self.assertEqual(r.state,'PARTIALLY_FILLED'); self.assertFalse(j.can_issue_new_risk())

    def test_fill_cannot_exceed_expected(self):
        _,r=self.order(); r.transition('POLICY_ALLOWED'); r.transition('PERMIT_ISSUED'); r.transition('PERMIT_CONSUMED'); r.transition('SIGNED'); r.transition('SUBMITTED'); r.transition('ACKNOWLEDGED')
        with self.assertRaises(ReconciliationError): r.record_fill('0.03')

    def test_crash_after_sign_becomes_uncertain(self):
        j,r=self.order(); r.transition('POLICY_ALLOWED'); r.transition('PERMIT_ISSUED'); r.transition('PERMIT_CONSUMED'); r.transition('SIGNED'); j.mark_crash_after_sign_before_ack('a1')
        self.assertTrue(r.uncertain); self.assertFalse(j.can_issue_new_risk())

    def test_uncertain_requires_reconciliation(self):
        j,r=self.order(); r.transition('POLICY_ALLOWED'); r.transition('PERMIT_ISSUED'); r.transition('PERMIT_CONSUMED'); r.transition('SIGNED'); j.mark_crash_after_sign_before_ack('a1'); j.begin_reconciliation('a1'); self.assertEqual(r.state,'RECONCILING')
        r.transition('RECONCILED_NO_ACTION'); self.assertTrue(j.can_issue_new_risk())

    def test_blocked_intent_releases_risk_gate(self):
        j,r=self.order(); r.transition('BLOCKED'); self.assertTrue(r.terminal); self.assertTrue(j.can_issue_new_risk())

    def test_invalid_jump_blocked(self):
        _,r=self.order()
        with self.assertRaises(ReconciliationError): r.transition('SUBMITTED')

    def test_duplicate_permit_blocked(self):
        j,_=self.order()
        with self.assertRaises(ReconciliationError): j.create(action_id='a2',permit_id='p1',action='PLACE_IOC_LIMIT',instrument='ETH',risk_increasing=True,expected_quantity='1')

    def test_cancel_is_nonrisk_and_zero_quantity(self):
        j=ActionJournal(); r=j.create(action_id='c1',permit_id='pc1',action='CANCEL_BY_CLOID',instrument='BTC',risk_increasing=False,expected_quantity='0')
        self.assertTrue(j.can_issue_new_risk()); self.assertEqual(r.expected_quantity,Decimal('0'))

    def test_cancel_cannot_be_marked_risk_increasing(self):
        j=ActionJournal()
        with self.assertRaises(ReconciliationError): j.create(action_id='c1',permit_id='pc1',action='CANCEL_BY_CLOID',instrument='BTC',risk_increasing=True,expected_quantity='0')

    def test_cancel_cannot_have_quantity(self):
        j=ActionJournal()
        with self.assertRaises(ReconciliationError): j.create(action_id='c1',permit_id='pc1',action='CANCEL_BY_CLOID',instrument='BTC',risk_increasing=False,expected_quantity='1')

if __name__=='__main__': unittest.main()
