"""Shared epoch/optimization loop for research CLI and workbench model CLI."""

import time

import torch


def optimize_batch(model, optimizer, criterion, scores, labels):
    loss = criterion(scores, labels)
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 0.25)
    optimizer.step()
    return loss.item()


def run_epochs(
    model,
    optimizer,
    scheduler,
    criterion,
    epochs,
    batches,
    forward,
    on_epoch,
    on_batch=None,
):
    # Data preparation, batching and evaluation are model-side policies supplied by
    # the calling research profile. The service does not implement this loop.
    for epoch in range(epochs):
        started = time.time()
        model.train()
        total, count = 0.0, 0
        for batch in batches(epoch):
            if on_batch is not None:
                on_batch(count)
            scores, labels = forward(epoch, batch)
            total += optimize_batch(model, optimizer, criterion, scores, labels)
            count += 1
        scheduler.step()
        on_epoch(epoch, total / max(count, 1), count, time.time() - started)
