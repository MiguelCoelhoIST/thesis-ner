import unittest

from src.data.map_role_taxonomy import load_taxonomy, map_label, map_labels


class RoleTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fine_labels, cls.aggregated_mapping = load_taxonomy()

    def map_one(self, label):
        return map_label(
            label,
            "aggregated",
            self.fine_labels,
            self.aggregated_mapping,
        )

    def test_passive_party_mapping(self):
        self.assertEqual(self.map_one("ARGUIDO"), "PASSIVE_PARTY")
        self.assertEqual(self.map_one("REU"), "PASSIVE_PARTY")

    def test_active_party_mapping(self):
        self.assertEqual(self.map_one("AUTOR"), "ACTIVE_PARTY")
        self.assertEqual(self.map_one("REQUERENTE"), "ACTIVE_PARTY")

    def test_multi_label_mapping_preserves_order(self):
        self.assertEqual(
            map_labels(
                ["ARGUIDO", "RECORRENTE"],
                "aggregated",
                self.fine_labels,
                self.aggregated_mapping,
            ),
            ["PASSIVE_PARTY", "APPELLANT"],
        )

    def test_unknown_stays_unknown(self):
        self.assertEqual(self.map_one("UNKNOWN"), "UNKNOWN")

    def test_invalid_label_raises(self):
        with self.assertRaisesRegex(ValueError, "unknown fine label"):
            self.map_one("ADVOGADO")


if __name__ == "__main__":
    unittest.main()
