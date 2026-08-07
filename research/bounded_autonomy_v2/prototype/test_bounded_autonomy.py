import unittest
from bounded_autonomy import (
    Decision, ExecutionStateMachine, PermitRegistry, PolicyError,
    compile_abstract_action, derive_cloid, evaluate_intent
)

H="a"*64
C="0x"+"b"*32

def envelope():
    return {
        "schema_version":"0.1-design","environment":"TESTNET","venue":"HYPERLIQUID",
        "account_address":"0x"+"1"*40,"policy_hash":H,"effective_from_ms":1000,"expires_at_ms":999999999,
        "allowed_instruments":["BTC","ETH","SOL"],
        "allowed_actions":["PLACE_IOC_LIMIT","REDUCE_ONLY_IOC","CANCEL_BY_CLOID"],
        "max_single_trade_notional_usd":"1000","max_gross_exposure_usd":"3000","max_net_exposure_usd":"3000",
        "max_instrument_exposure_usd":{"BTC":"2000","ETH":"2000","SOL":"2000"},"max_open_positions":3,
        "max_daily_realized_loss_usd":"500","max_daily_total_loss_usd":"700","max_strategy_drawdown_usd":"900",
        "max_slippage_bps":50,"max_signal_age_ms":5000,"max_quote_age_ms":1000,
        "max_unreconciled_actions":0,"min_cancel_action_reserve":100,"ai_critic_mode":"VETO_ONLY_REQUIRED",
        "human_governor_signature_required_for_activation":True
    }

def risk():
    return {
        "execution_state":"ACTIVE_BOUNDED","kill_switch":False,"unreconciled_actions":0,
        "cancel_action_reserve":1000,"gross_exposure_usd":"0","net_exposure_usd":"0",
        "instrument_exposure_usd":{"BTC":"0","ETH":"0","SOL":"0"},"position_quantity":{"BTC":"0","ETH":"0","SOL":"0"},
        "open_positions":0,"daily_realized_loss_usd":"0","daily_total_loss_usd":"0","strategy_drawdown_usd":"0",
        "strategy_orders":{"order-12345678":{"instrument":"BTC","cloid":C,"terminal":False}}
    }

def common(action):
    return {
        "schema_version":"0.2-design","intent_id":"intent-1234567890","strategy_id":"COPY-001",
        "strategy_version_hash":H,"source_signal_id":"signal-123","decision_timestamp_ms":5000,
        "instrument":"BTC","action":action,"expires_at_ms":10000,"model_version_hash":H,
        "policy_version_hash":H,"data_snapshot_hash":H,"risk_snapshot_hash":H,
        "decision_mode":"DETERMINISTIC_PLUS_AI_CRITIC",
        "ai_assessment":{"status":"PASS","confidence_bps":8000,"veto":False,"risk_codes":[]}
    }

def entry():
    x=common("PLACE_IOC_LIMIT"); x.update(side="BUY",reduce_only=False,requested_quantity="0.01",limit_price="50000",max_slippage_bps=25); return x

def reduce():
    x=common("REDUCE_ONLY_IOC"); x.update(side="SELL",reduce_only=True,requested_quantity="0.01",limit_price="50000",max_slippage_bps=25); return x

def cancel():
    x=common("CANCEL_BY_CLOID"); x["target_strategy_order_id"]="order-12345678"; return x

class Tests(unittest.TestCase):
    def ev(self,i=None,e=None,r=None,now=6000,qt=5900):
        return evaluate_intent(i or entry(),e or envelope(),r or risk(),now_ms=now,quote_timestamp_ms=qt,current_policy_hash=H)

    def test_allow_entry(self): self.assertEqual(self.ev(),Decision(True,"ALLOW"))
    def test_size_cap(self):
        i=entry(); i["requested_quantity"]="0.03"; self.assertEqual(self.ev(i=i).code,"BLOCK_TRADE_NOTIONAL")
    def test_slippage(self):
        i=entry(); i["max_slippage_bps"]=51; self.assertEqual(self.ev(i=i).code,"BLOCK_SLIPPAGE")
    def test_veto(self):
        i=entry(); i["ai_assessment"]["status"]="VETO"; i["ai_assessment"]["veto"]=True; self.assertEqual(self.ev(i=i).code,"BLOCK_AI_VETO")
    def test_ai_timeout_required(self):
        i=entry(); i["ai_assessment"]["status"]="TIMEOUT"; self.assertEqual(self.ev(i=i).code,"SKIP_AI_REQUIRED")
    def test_expired(self): self.assertEqual(self.ev(now=11001,qt=11000).code,"BLOCK_EXPIRED")
    def test_policy_hash(self):
        i=entry(); i["policy_version_hash"]="b"*64; self.assertEqual(self.ev(i=i).code,"BLOCK_POLICY_HASH")
    def test_unreconciled(self):
        r=risk(); r["unreconciled_actions"]=1; self.assertEqual(self.ev(r=r).code,"BLOCK_UNRECONCILED")
    def test_kill(self):
        r=risk(); r["kill_switch"]=True; self.assertEqual(self.ev(r=r).code,"BLOCK_KILL_SWITCH")

    def test_cancel_without_economic_dummy_fields(self):
        self.assertEqual(self.ev(i=cancel()).code,"ALLOW_CANCEL")
    def test_cancel_unknown_order(self):
        i=cancel(); i["target_strategy_order_id"]="order-unknown1"; self.assertEqual(self.ev(i=i).code,"BLOCK_CANCEL_NOT_OWNED")
    def test_cancel_still_allowed_when_loss_cap_hit(self):
        r=risk(); r["daily_total_loss_usd"]="700"; self.assertEqual(self.ev(i=cancel(),r=r).code,"ALLOW_CANCEL")
    def test_cancel_compile_uses_owned_target_cloid(self):
        i=cancel(); a=compile_abstract_action(i,owned_orders=risk()["strategy_orders"])
        self.assertEqual(a["target_cloid"],C)

    def test_reduce_long(self):
        r=risk(); r["position_quantity"]["BTC"]="0.02"; r["instrument_exposure_usd"]["BTC"]="1000"; r["gross_exposure_usd"]="1000"; r["net_exposure_usd"]="1000"; r["open_positions"]=1
        self.assertEqual(self.ev(i=reduce(),r=r).code,"ALLOW_REDUCE_ONLY")
    def test_reduce_allowed_when_loss_cap_hit(self):
        r=risk(); r["position_quantity"]["BTC"]="0.02"; r["daily_total_loss_usd"]="700"
        self.assertEqual(self.ev(i=reduce(),r=r).code,"ALLOW_REDUCE_ONLY")
    def test_reduce_wrong_side(self):
        r=risk(); r["position_quantity"]["BTC"]="0.02"; i=reduce(); i["side"]="BUY"
        self.assertEqual(self.ev(i=i,r=r).code,"BLOCK_REDUCE_WRONG_SIDE")
    def test_reduce_exceeds_position(self):
        r=risk(); r["position_quantity"]["BTC"]="0.005"; self.assertEqual(self.ev(i=reduce(),r=r).code,"BLOCK_REDUCE_EXCEEDS_POSITION")

    def test_cloid_deterministic(self):
        a=derive_cloid("COPY-001","permit-123456789",1,"TESTNET"); b=derive_cloid("COPY-001","permit-123456789",1,"TESTNET"); self.assertEqual(a,b); self.assertEqual(len(a),34)
    def test_compile_entry_only_ioc(self):
        i=entry(); c=derive_cloid("COPY-001","permit-123456789",1,"TESTNET"); a=compile_abstract_action(i,new_order_cloid=c); self.assertEqual(a["order_type"],{"limit":{"tif":"Ioc"}})
    def test_permit_replay(self):
        p=PermitRegistry(); p.consume("permit-x")
        with self.assertRaises(PolicyError): p.consume("permit-x")
    def test_state_no_auto_promotion(self):
        s=ExecutionStateMachine("RESEARCH_ONLY")
        with self.assertRaises(PolicyError): s.automated_promote("SHADOW_ONLY")
    def test_state_human_sequential(self):
        s=ExecutionStateMachine("RESEARCH_ONLY"); s.human_promote("SHADOW_ONLY"); self.assertEqual(s.state,"SHADOW_ONLY")

if __name__=="__main__": unittest.main()
