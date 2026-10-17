"""Stable padding and probability-loss contracts for batched decision computation."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch

SPEC = importlib.util.spec_from_file_location(
    "jevforge_batch", Path(__file__).parents[1] / "jevforge_batch.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def encoding(prompt):
    nodes = [
        SimpleNamespace(parent=-1, token=-1, depth=0, legal=[4, 6]),
        SimpleNamespace(parent=0, token=4, depth=1, legal=[5]),
        SimpleNamespace(parent=1, token=5, depth=2, legal=[]),
        SimpleNamespace(parent=0, token=6, depth=1, legal=[5]),
        SimpleNamespace(parent=3, token=5, depth=2, legal=[]),
    ]
    trie = SimpleNamespace(nodes=nodes, paths=[[1, 2], [3, 4]], internal=lambda: [0, 1, 3])
    return SimpleNamespace(prompt_ids=prompt, reply_start_pos=max(0, len(prompt) - 3), trie=trie)


class TinyAttention(torch.nn.Module):
    def __init__(self):
        super().__init__()
        torch.manual_seed(4)
        self.embedding = torch.nn.Embedding(16, 8)
        self.head = torch.nn.Linear(8, 16)

    def forward(self, input_ids, attention_mask, position_ids, logits_to_keep, use_cache):
        hidden = self.embedding(input_ids) + position_ids[..., None] * 0.1
        scores = hidden @ hidden.transpose(-1, -2) / 8**0.5 + attention_mask[:, 0]
        context = scores.softmax(-1) @ hidden
        return SimpleNamespace(logits=self.head(context[:, logits_to_keep]))


class BatchContracts(unittest.TestCase):
    def test_padding_does_not_change_scores(self):
        model = TinyAttention().eval()
        examples = [encoding([1, 2]), encoding([2, 3, 7, 8, 9, 1])]
        together = module.tree_batch_forward(model, examples, 0)
        for index, example in enumerate(examples):
            alone = module.tree_batch_forward(model, [example], 0)
            torch.testing.assert_close(together.node[index], alone.node[0])
            torch.testing.assert_close(together.reply_start[index], alone.reply_start[0])

    def test_topk_tail_is_kl_of_coarsened_distribution(self):
        torch.manual_seed(42)
        for vocab in (16, 128):
            ref = torch.randn(3, vocab, dtype=torch.float64).log_softmax(-1)
            cur = torch.randn(3, vocab, dtype=torch.float64).log_softmax(-1)
            got = module.topk_tail_batch(ref, cur, vocab)
            indices = ref.topk(min(vocab, 64), -1).indices
            p, q = ref.exp().gather(-1, indices), cur.exp().gather(-1, indices)
            if vocab > 64:
                p = torch.cat([p, 1 - p.sum(-1, keepdim=True)], -1)
                q = torch.cat([q, 1 - q.sum(-1, keepdim=True)], -1)
            expected = (p * (p.log() - q.log())).sum(-1)
            torch.testing.assert_close(got, expected, atol=1e-10, rtol=1e-10)

    def test_batch_loss_has_finite_gradients(self):
        import random

        torch.manual_seed(3)
        logits = torch.randn(2, 5, 128, requires_grad=True)
        reply = torch.randn(2, 128, requires_grad=True)
        current = module.BatchLogProbs(logits.log_softmax(-1), reply.log_softmax(-1))
        reference = module.BatchLogProbs(
            torch.randn(2, 5, 128).log_softmax(-1), torch.randn(2, 128).log_softmax(-1)
        )
        loss = module.jev_loss_batch(current, reference, [encoding([1, 2])] * 2,
                                     [0, 1], random.Random(42))
        loss["loss"].mean().backward()
        self.assertTrue(torch.isfinite(logits.grad).all())
        self.assertTrue(torch.isfinite(reply.grad).all())


if __name__ == "__main__":
    unittest.main()
