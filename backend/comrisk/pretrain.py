"""Same-domain masked feature reconstruction, inspired by GraphMAE (not a reproduction)."""
import torch
from torch.nn import functional as F


def pretrain(model, graph, epochs=20):
    decoder = torch.nn.Linear(model.classifier.in_features - int(model.use_prior), graph["x"].shape[1] // 2)
    optimizer = torch.optim.AdamW(list(model.parameters()) + list(decoder.parameters()), lr=0.003)
    eligible = torch.where(graph["masks"]["train"])[0]
    width = graph["x"].shape[1] // 2
    history = []
    model.train()
    for epoch in range(epochs):
        chosen = eligible[torch.randperm(len(eligible))[:max(1, len(eligible)//3)]]
        masked = dict(graph)
        masked["x"] = graph["x"].clone()
        masked["x"][chosen, :width] = 0
        masked["x"][chosen, width:] = 1
        predicted = decoder(model.encode(masked))[chosen]
        present = graph["x"][chosen, width:] == 0
        if not present.any():
            continue
        loss = F.mse_loss(predicted[present], graph["x"][chosen, :width][present])
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        history.append(float(loss.detach()))
    return history
