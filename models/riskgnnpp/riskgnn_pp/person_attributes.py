"""Encode raw person attributes and aggregate unique person-company memberships."""

import torch
from torch import nn


class PersonAttributeMeanEncoder(nn.Module):
    def __init__(self, features: int, output_dim: int):
        super().__init__()
        self.features = features
        self.encoder = nn.Sequential(
            nn.Linear(features, 32), nn.GELU(), nn.Linear(32, output_dim, bias=False)
        )

    def forward(
        self, attributes: object, edges: object, companies: int
    ) -> torch.Tensor:
        if attributes is None or edges is None:
            raise ValueError("Person attributes and person-company edges are required")
        parameter = self.encoder[0].weight
        x = torch.as_tensor(attributes, dtype=parameter.dtype, device=parameter.device)
        membership = torch.as_tensor(edges, device=parameter.device)
        if x.ndim != 2 or x.shape[1] != self.features or not torch.isfinite(x).all():
            raise ValueError("Invalid person attribute matrix")
        if membership.ndim != 2 or membership.shape[1] != 2:
            raise ValueError("Membership must contain [person_id, company_id] pairs")
        if membership.dtype not in (torch.int32, torch.int64):
            raise ValueError("Membership identities must be integers")
        membership = torch.unique(membership.to(torch.long), dim=0)
        if len(membership) and (
            membership.min() < 0
            or membership[:, 0].max() >= len(x)
            or membership[:, 1].max() >= companies
        ):
            raise ValueError("Person/company identity outside attribute namespace")
        encoded = self.encoder(x)
        pooled = encoded.new_zeros((companies, encoded.shape[1]))
        pooled.index_add_(0, membership[:, 1], encoded[membership[:, 0]])
        counts = torch.bincount(membership[:, 1], minlength=companies)
        # Empty neighborhoods contribute exactly zero, including when the encoder has a bias.
        return pooled / counts.clamp_min(1).to(pooled.dtype).unsqueeze(1)
