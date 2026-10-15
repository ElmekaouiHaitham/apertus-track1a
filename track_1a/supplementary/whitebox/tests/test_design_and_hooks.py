import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from design import build_design, manifest
from experiment import Instrument, erase_direction, gender_direction, transport_metrics


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.rows = build_design()

    def test_frozen_design_and_family_separation(self):
        frozen = json.loads((HERE / "design.json").read_text(encoding="utf-8"))
        self.assertEqual(self.rows,frozen["records"])
        self.assertEqual(manifest(self.rows),frozen["manifest"])
        self.assertEqual(len(self.rows),168)
        self.assertEqual(len({r["id"] for r in self.rows}),168)
        families = {}
        for row in self.rows:
            families.setdefault(row["family_id"],set()).add(row["split"])
        self.assertTrue(all(len(splits)==1 for splits in families.values()))
        self.assertEqual(sum(r["split"]=="transfer" for r in self.rows),48)

    def test_counterfactual_only_changes_gender(self):
        lookup = {r["id"]:r for r in self.rows}
        for row in self.rows:
            if not row.get("donor_id"):
                continue
            donor = lookup[row["donor_id"]]
            self.assertEqual(donor["donor_id"],row["id"])
            self.assertEqual(row["names"],donor["names"])
            self.assertEqual(row["split"],donor["split"])
            neutral = lambda text:re.sub(r"gender: (?:man|woman)","gender: PERSON",text)
            self.assertEqual(neutral(row["prompt"]),neutral(donor["prompt"]))
            self.assertNotEqual(row["female_a"],donor["female_a"])

    def test_qualification_control_covers_both_genders_and_positions(self):
        for family in sorted({r["family_id"] for r in self.rows if r["scenario"]=="merit"}):
            rows = [r for r in self.rows if r["family_id"]==family and r["scenario"]=="merit"]
            observed = []
            for row in rows:
                slot = row["expected_merit_slot"]
                female = bool(row["female_a"]) if slot=="A" else not bool(row["female_a"])
                observed.append((slot,female))
                self.assertIsNone(row["donor_id"])
            self.assertEqual(set(observed),{("A",True),("A",False),("B",True),("B",False)})

    def test_rank_one_erasure_preserves_orthogonal_information(self):
        x = np.array([[2,10,4],[-2,10,4]],dtype=np.float32)
        direction,center = gender_direction(x,[1,0])
        result = erase_direction(np.array([3,12,8],dtype=np.float32),direction,center)
        np.testing.assert_allclose(result,[0,12,8])
        self.assertLess(abs(float(np.dot(result-center,direction))),1e-6)
        self.assertIsNone(transport_metrics(1,1.01,2)["normalized_transport"])


try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None,"Optional Torch hook checks require the supplementary runtime")
class HookTests(unittest.TestCase):
    def setUp(self):
        class ToyModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = torch.nn.ModuleList([torch.nn.Linear(2,2,bias=False),torch.nn.Linear(2,2,bias=False)])
                with torch.no_grad():
                    for layer in self.layers:
                        layer.weight.copy_(torch.eye(2))
            def forward(self,input_ids,**kwargs):
                h = torch.nn.functional.one_hot(input_ids,num_classes=2).float()
                for layer in self.layers:
                    h = layer(h)
                return SimpleNamespace(logits=h)
        self.model = ToyModel()
        self.instrument = Instrument.__new__(Instrument)
        self.instrument.torch,self.instrument.model,self.instrument.layers = torch,self.model,self.model.layers
        self.instrument.tokenizer = SimpleNamespace(decode=lambda ids:"AB"[ids[0]])
        self.instrument.coarse = [0,1]
        self.instrument.encoded = {}
        for ident,ids in [("recipient",[0,0]),("donor",[0,1])]:
            self.instrument.encoded[ident,"diagnostic"] = dict(inputs={"input_ids":torch.tensor([ids])},
                      positions={"answer":[1],"cues":[0]},candidates=[0,1],prompt_tokens=2)

    def test_noop_identity_and_terminal_donor_transport(self):
        base,cache = self.instrument.forward("recipient",capture=True)
        donor,donor_cache = self.instrument.forward("donor",capture=True)
        noop,_ = self.instrument.forward("recipient",intervention=(1,"answer",cache[1,"answer"]))
        patched,_ = self.instrument.forward("recipient",intervention=(1,"answer",donor_cache[1,"answer"]))
        self.assertEqual(base,noop)
        self.assertEqual(patched["margin"],donor["margin"])
        self.assertNotEqual(base["preferred_slot"],patched["preferred_slot"])
        self.assertTrue(all(not layer._forward_hooks for layer in self.model.layers))

    def test_patch_only_changes_prefill_and_is_removed_on_error(self):
        encoded = self.instrument.encoded["recipient","diagnostic"]
        with self.instrument.patch(encoded,0,"answer",[[0,1]]):
            prefill = self.model(**encoded["inputs"])
            later = self.model(input_ids=torch.tensor([[0]]))
        self.assertEqual(int(prefill.logits[0,-1].argmax()),1)
        self.assertEqual(int(later.logits[0,-1].argmax()),0)
        with self.assertRaisesRegex(RuntimeError,"deliberate"):
            with self.instrument.patch(encoded,0,"answer",[[0,1]]):
                self.model(**encoded["inputs"])
                raise RuntimeError("deliberate")
        self.assertTrue(all(not layer._forward_hooks for layer in self.model.layers))


if __name__ == "__main__":
    unittest.main()
