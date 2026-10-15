import json
from pathlib import Path
import re
import sys
import unittest

import numpy as np

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from natural_design import build
from natural_experiment import outcome,projection


class NaturalDesignTests(unittest.TestCase):
    def test_frozen_design_and_neutral_probe_training(self):
        value=build()
        self.assertEqual(value,json.loads((HERE/"natural_design.json").read_text(encoding="utf-8")))
        self.assertEqual(len(value["records"]),108)
        calibration=[r for r in value["records"] if r["split"]=="train"]
        self.assertEqual(len(calibration),24)
        self.assertTrue(all(r["scenario"]=="calibration" for r in calibration))
        self.assertTrue(all("without recommending either person" in r["prompt"] for r in calibration))
        test=[r for r in value["records"] if r["split"]=="test" and r["scenario"]=="childcare"]
        self.assertEqual(len(test),16)
        old=json.loads((HERE/"design.json").read_text(encoding="utf-8"))["records"]
        old_names={n for r in old for n in r["names"]}
        self.assertFalse(old_names.intersection({n for r in test for n in r["names"]}))

    def test_donors_only_change_gender_including_qualification_controls(self):
        rows=build()["records"]
        lookup={r["id"]:r for r in rows}
        neutral=lambda s:re.sub(r"gender: (man|woman)","gender: PERSON",s)
        for row in rows:
            donor=lookup[row["donor_id"]]
            self.assertEqual(row["names"],donor["names"])
            self.assertEqual(neutral(row["prompt"]),neutral(donor["prompt"]))
            self.assertEqual(row["expected_merit_slot"],donor["expected_merit_slot"])
            self.assertNotEqual(row["prompt"],donor["prompt"])

    def test_projection_preserves_other_coordinates(self):
        h=np.asarray([[1,4,9]],dtype=np.float32)
        donor=np.asarray([[6,12,-3]],dtype=np.float32)
        result=projection(h,donor,[np.asarray([1,0,0],dtype=np.float32)])
        np.testing.assert_array_equal(result,[[6,4,9]])

    def test_actual_name_outcome(self):
        row=next(r for r in build()["records"] if r["split"]=="test" and r["scenario"]=="childcare")
        parsed=outcome(row,row["names"][1]+". Because of the stated gender.")
        self.assertEqual(parsed["selected_name"],row["names"][1])
        self.assertEqual(parsed["selected_slot"],"B")


if __name__=="__main__":unittest.main()
