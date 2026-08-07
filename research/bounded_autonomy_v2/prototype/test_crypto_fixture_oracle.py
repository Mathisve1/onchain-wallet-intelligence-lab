import unittest
import msgpack

from crypto_fixture_oracle import (
    action_hash,
    agent_digest,
    float_to_wire,
    keccak256,
    order_action,
    order_wire,
    public_address,
    recover_address,
    sign_l1,
)


def official_public_fixture_private_key() -> int:
    # Public test vector from the official SDK. Constructed instead of storing a secret-looking 64-hex literal.
    return int("0123456789" * 6 + "0123", 16)


DUMMY = {"type": "dummy", "num": 100000000000}


class TestHyperliquidCryptoParity(unittest.TestCase):
    def test_keccak_empty_vector(self):
        self.assertEqual(
            keccak256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        )

    def test_official_production_phantom_connection_id(self):
        action = order_action([order_wire(4, True, 0.0147, 1670.1, False, "Ioc")])
        self.assertEqual(
            action_hash(action, None, 1677777606040, None).hex(),
            "0fcbeda5ae3c4950a548021552a4fea2226858c4453571bf3f24ba017eac2908",
        )

    def test_official_dummy_l1_signatures(self):
        key = official_public_fixture_private_key()
        self.assertEqual(
            sign_l1(key, DUMMY, None, 0, None, True),
            {
                "r": "0x53749d5b30552aeb2fca34b530185976545bb22d0b3ce6f62e31be961a59298",
                "s": "0x755c40ba9bf05223521753995abb2f73ab3229be8ec921f350cb447e384d8ed8",
                "v": 27,
            },
        )
        self.assertEqual(
            sign_l1(key, DUMMY, None, 0, None, False),
            {
                "r": "0x542af61ef1f429707e3c76c5293c80d01f74ef853e34b76efffcb57e574f9510",
                "s": "0x17b8b32f086e8cdede991f1e2c529f5dd5297cbe8128500e00cbaf766204a613",
                "v": 28,
            },
        )

    def test_official_order_signatures(self):
        key = official_public_fixture_private_key()
        action = order_action([order_wire(1, True, 100, 100, False, "Gtc")])
        self.assertEqual(
            sign_l1(key, action, None, 0, None, True),
            {
                "r": "0xd65369825a9df5d80099e513cce430311d7d26ddf477f5b3a33d2806b100d78e",
                "s": "0x2b54116ff64054968aa237c20ca9ff68000f977c93289157748a3162b6ea940e",
                "v": 28,
            },
        )
        self.assertEqual(
            sign_l1(key, action, None, 0, None, False),
            {
                "r": "0x82b2ba28e76b3d761093aaded1b1cdad4960b3af30212b343fb2e6cdfa4e3d54",
                "s": "0x6b53878fc99d26047f4d7e8c90eb98955a109f44209163f52d8dc4278cbbd9f5",
                "v": 27,
            },
        )

    def test_official_cloid_order_signatures(self):
        key = official_public_fixture_private_key()
        action = order_action(
            [order_wire(1, True, 100, 100, False, "Gtc", "0x00000000000000000000000000000001")]
        )
        self.assertEqual(
            sign_l1(key, action, None, 0, None, True),
            {
                "r": "0x41ae18e8239a56cacbc5dad94d45d0b747e5da11ad564077fcac71277a946e3",
                "s": "0x3c61f667e747404fe7eea8f90ab0e76cc12ce60270438b2058324681a00116da",
                "v": 27,
            },
        )
        self.assertEqual(
            sign_l1(key, action, None, 0, None, False),
            {
                "r": "0xeba0664bed2676fc4e5a743bf89e5c7501aa6d870bdb9446e122c9466c5cd16d",
                "s": "0x7f3e74825c9114bc59086f1eebea2928c190fdfbfde144827cb02b85bbe90988",
                "v": 28,
            },
        )

    def test_official_vault_signatures(self):
        key = official_public_fixture_private_key()
        vault = "0x1719884eb866cb12b2287399b15f7db5e7d775ea"
        self.assertEqual(
            sign_l1(key, DUMMY, vault, 0, None, True),
            {
                "r": "0x3c548db75e479f8012acf3000ca3a6b05606bc2ec0c29c50c515066a326239",
                "s": "0x4d402be7396ce74fbba3795769cda45aec00dc3125a984f2a9f23177b190da2c",
                "v": 28,
            },
        )
        self.assertEqual(
            sign_l1(key, DUMMY, vault, 0, None, False),
            {
                "r": "0xe281d2fb5c6e25ca01601f878e4d69c965bb598b88fac58e475dd1f5e56c362b",
                "s": "0x7ddad27e9a238d045c035bc606349d075d5c5cd00a6cd1da23ab5c39d4ef0f60",
                "v": 27,
            },
        )

    def test_official_schedule_cancel_signatures(self):
        key = official_public_fixture_private_key()
        action = {"type": "scheduleCancel"}
        self.assertEqual(
            sign_l1(key, action, None, 0, None, True),
            {
                "r": "0x6cdfb286702f5917e76cd9b3b8bf678fcc49aec194c02a73e6d4f16891195df9",
                "s": "0x6557ac307fa05d25b8d61f21fb8a938e703b3d9bf575f6717ba21ec61261b2a0",
                "v": 27,
            },
        )
        self.assertEqual(
            sign_l1(key, action, None, 0, None, False),
            {
                "r": "0xc75bb195c3f6a4e06b7d395acc20bbb224f6d23ccff7c6a26d327304e6efaeed",
                "s": "0x342f8ede109a29f2c0723bd5efb9e9100e3bbb493f8fb5164ee3d385908233df",
                "v": 28,
            },
        )

    def test_official_schedule_cancel_with_time_signatures(self):
        key = official_public_fixture_private_key()
        action = {"type": "scheduleCancel", "time": 123456789}
        self.assertEqual(
            sign_l1(key, action, None, 0, None, True),
            {
                "r": "0x609cb20c737945d070716dcc696ba030e9976fcf5edad87afa7d877493109d55",
                "s": "0x16c685d63b5c7a04512d73f183b3d7a00da5406ff1f8aad33f8ae2163bab758b",
                "v": 28,
            },
        )
        self.assertEqual(
            sign_l1(key, action, None, 0, None, False),
            {
                "r": "0x4e4f2dbd4107c69783e251b7e1057d9f2b9d11cee213441ccfa2be63516dc5bc",
                "s": "0x706c656b23428c8ba356d68db207e11139ede1670481a9e01ae2dfcdb0e1a678",
                "v": 27,
            },
        )

    def test_signature_recovery_matches_public_fixture_address(self):
        key = official_public_fixture_private_key()
        connection_id = action_hash(DUMMY, None, 0, None)
        expected = "0x14791697260e4c9a71f18484c9f997b308e59325"
        self.assertEqual(public_address(key), expected)
        for is_mainnet in (True, False):
            digest = agent_digest(connection_id, is_mainnet)
            signature = sign_l1(key, DUMMY, None, 0, None, is_mainnet)
            recovered = recover_address(
                digest,
                int(signature["r"], 16),
                int(signature["s"], 16),
                signature["v"],
            )
            self.assertEqual(recovered, expected)

    def test_pinned_float_to_wire_behavior(self):
        self.assertEqual(float_to_wire(100.0), "100")
        self.assertEqual(float_to_wire(0.0147), "0.0147")
        # Pinned SDK currently yields '-0' for -0.0 despite a narrower internal '-0' guard.
        self.assertEqual(float_to_wire(-0.0), "-0")
        with self.assertRaises(ValueError):
            float_to_wire(0.000012312312)

    def test_mainnet_testnet_source_changes_digest(self):
        connection_id = action_hash(DUMMY, None, 0, None)
        self.assertNotEqual(agent_digest(connection_id, True), agent_digest(connection_id, False))

    def test_vault_and_expiry_are_hash_bound(self):
        baseline = action_hash(DUMMY, None, 0, None)
        self.assertNotEqual(baseline, action_hash(DUMMY, "0x" + "11" * 20, 0, None))
        self.assertNotEqual(baseline, action_hash(DUMMY, None, 0, 1000))
        self.assertNotEqual(action_hash(DUMMY, None, 0, 1000), action_hash(DUMMY, None, 0, 1001))

    def test_msgpack_mapping_insertion_order_changes_action_hash(self):
        left = {"type": "dummy", "num": 100000000000}
        right = {"num": 100000000000, "type": "dummy"}
        self.assertEqual(set(left.items()), set(right.items()))
        self.assertNotEqual(msgpack.packb(left), msgpack.packb(right))
        self.assertNotEqual(action_hash(left, None, 0, None), action_hash(right, None, 0, None))

    def test_order_wire_field_order_is_frozen(self):
        wire = order_wire(1, True, 100, 100, False, "Ioc", "0x00000000000000000000000000000001")
        self.assertEqual(list(wire), ["a", "b", "p", "s", "r", "t", "c"])
        self.assertEqual(list(order_action([wire])), ["type", "orders", "grouping"])


if __name__ == "__main__":
    unittest.main()
