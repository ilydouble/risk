"""Batched tree attention and the unchanged LLM-as-Jev objective for shared suffix tries."""

from dataclasses import dataclass

import torch


@dataclass
class BatchLogProbs:
    node: torch.Tensor
    reply_start: torch.Tensor


def trie_signature(enc):
    return ([(n.parent, n.token, n.depth) for n in enc.trie.nodes], enc.trie.paths)


def tree_batch_forward(model, encodings, pad_token_id):
    if not encodings:
        raise ValueError("Empty batch")
    first = encodings[0]
    if any(trie_signature(e) != trie_signature(first) for e in encodings):
        raise ValueError("A batch must share candidate tokenization and trie layout")
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    nodes = first.trie.nodes
    prefix = max(len(e.prompt_ids) for e in encodings)
    length, count = prefix + len(nodes) - 1, len(encodings)
    ids, positions, reply_positions = [], [], []
    for enc in encodings:
        p = len(enc.prompt_ids)
        padding = prefix - p
        ids.append([pad_token_id] * padding + enc.prompt_ids + [n.token for n in nodes[1:]])
        positions.append([0] * padding + list(range(p)) + [p - 1 + n.depth for n in nodes[1:]])
        reply_positions.append(padding + enc.reply_start_pos)
    allowed = torch.tril(torch.ones(length, length, dtype=torch.bool, device=device))
    allowed = allowed[None, None].expand(count, 1, length, length).clone()
    for i, enc in enumerate(encodings):
        padding = prefix - len(enc.prompt_ids)
        allowed[i, :, :, :padding] = False
        # Padding queries never contribute to outputs; their diagonal avoids all-masked rows.
        if padding:
            pad = torch.arange(padding, device=device)
            allowed[i, 0, pad, pad] = True
        for j in range(1, len(nodes)):
            row = prefix + j - 1
            allowed[i, 0, row] = False
            allowed[i, 0, row, padding:prefix] = True
            ancestor = j
            while ancestor > 0:
                allowed[i, 0, row, prefix + ancestor - 1] = True
                ancestor = nodes[ancestor].parent
    mask = torch.zeros(count, 1, length, length, dtype=dtype, device=device)
    mask.masked_fill_(~allowed, torch.finfo(dtype).min)
    node_positions = [prefix - 1] + [prefix + i - 1 for i in range(1, len(nodes))]
    keep = sorted(set(node_positions + reply_positions))
    lookup = {position: i for i, position in enumerate(keep)}
    output = model(
        input_ids=torch.tensor(ids, device=device), attention_mask=mask,
        position_ids=torch.tensor(positions, device=device),
        logits_to_keep=torch.tensor(keep, device=device), use_cache=False,
    )
    logp = torch.log_softmax(output.logits.float(), dim=-1)
    return BatchLogProbs(
        logp[:, [lookup[p] for p in node_positions]],
        logp[torch.arange(count, device=device), [lookup[p] for p in reply_positions]],
    )


def candidate_scores_batch(logp, enc):
    values = []
    for path in enc.trie.paths:
        value = logp.node.new_zeros(logp.node.shape[0])
        for index in path:
            node = enc.trie.nodes[index]
            value = value + logp.node[:, node.parent, node.token]
        values.append(value)
    return torch.stack(values, dim=-1)


def topk_tail_batch(reference, current, finite_count):
    k = min(64, finite_count)
    indices = reference.topk(k, dim=-1).indices
    keep = torch.zeros_like(reference, dtype=torch.bool).scatter_(-1, indices, True)
    ref_top, cur_top = reference.gather(-1, indices), current.gather(-1, indices)
    divergence = (ref_top.exp() * (ref_top - cur_top)).sum(-1)
    if k < finite_count:
        ref_tail = torch.logsumexp(reference.masked_fill(keep, -torch.inf), dim=-1)
        cur_tail = torch.logsumexp(current.masked_fill(keep, -torch.inf), dim=-1)
        divergence = divergence + ref_tail.exp() * (ref_tail - cur_tail)
    return divergence.clamp(min=0)


def jev_loss_batch(current, reference, encodings, gold, rng, lam=1.0):
    enc = encodings[0]
    if any(trie_signature(e) != trie_signature(enc) for e in encodings):
        raise ValueError("Loss requires a shared suffix trie")
    batch, _, vocab = current.node.shape
    if len(gold) != batch:
        raise ValueError("Gold labels must align with batch rows")
    device = current.node.device
    internal = enc.trie.internal()
    weights = []
    for label in gold:
        gold_nodes = [enc.trie.nodes[v].parent for v in enc.trie.paths[label]]
        others = [v for v in internal if v not in set(gold_nodes)]
        off = rng.sample(others, min(3, len(others)))
        row = [0.0] * len(enc.trie.nodes)
        for node in gold_nodes:
            row[node] = (0.5 if off else 1.0) / len(gold_nodes)
        for node in off:
            row[node] += 0.5 / len(off)
        weights.append(row)
    weights = torch.tensor(weights, device=device, dtype=current.node.dtype)
    mass, outside = current.node.new_zeros(batch), current.node.new_zeros(batch)
    legal_mass = {}
    root_delta = None
    for node in internal:
        legal = enc.trie.nodes[node].legal
        cur, ref = current.node[:, node], reference.node[:, node]
        cur_mass, ref_mass = torch.logsumexp(cur[:, legal], -1), torch.logsumexp(ref[:, legal], -1)
        illegal_mask = torch.zeros(vocab, dtype=torch.bool, device=device)
        illegal_mask[legal] = True
        cur_illegal, ref_illegal = cur.masked_fill(illegal_mask, -torch.inf), ref.masked_fill(
            illegal_mask, -torch.inf
        )
        cur_rest, ref_rest = torch.logsumexp(cur_illegal, -1), torch.logsumexp(ref_illegal, -1)
        bernoulli = (ref_mass.exp() * (ref_mass - cur_mass)
                     + ref_rest.exp() * (ref_rest - cur_rest)).clamp(min=0)
        divergence = topk_tail_batch(
            ref_illegal - ref_rest[:, None], cur_illegal - cur_rest[:, None], vocab - len(legal)
        )
        mass = mass + weights[:, node] * bernoulli
        outside = outside + weights[:, node] * divergence
        legal_mass[node] = cur_mass
        if node == 0:
            root_delta = cur_mass - ref_mass
    logq = []
    for path in enc.trie.paths:
        value = current.node.new_zeros(batch)
        for index in path:
            node = enc.trie.nodes[index]
            value = value + current.node[:, node.parent, node.token] - legal_mass[node.parent]
        logq.append(value)
    gold_tensor = torch.tensor(gold, device=device)
    tree = -torch.stack(logq, -1).gather(-1, gold_tensor[:, None]).squeeze(-1)
    leaves = torch.tensor([enc.trie.paths[k][-1] for k in gold], device=device)
    rows = torch.arange(batch, device=device)
    position = 0.5 * topk_tail_batch(reference.reply_start, current.reply_start, vocab)
    position = position + 0.5 * topk_tail_batch(
        reference.node[rows, leaves], current.node[rows, leaves], vocab
    )
    return {
        "loss": tree + lam * (mass + outside + position), "tree": tree,
        "mass": mass, "out": outside, "pos": position, "root_delta": root_delta,
    }
