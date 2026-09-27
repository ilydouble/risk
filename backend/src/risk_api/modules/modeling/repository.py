from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.modules.modeling.model import ModelingDataset, ModelingExperiment


class ModelingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_dataset(self, dataset: ModelingDataset) -> None:
        self.session.add(dataset)
        await self.session.commit()

    async def dataset(self, dataset_id: str, owner_id: str) -> ModelingDataset | None:
        return await self.session.scalar(
            select(ModelingDataset).where(
                ModelingDataset.id == dataset_id, ModelingDataset.owner_id == owner_id
            )
        )

    async def datasets(self, owner_id: str) -> list[ModelingDataset]:
        rows = await self.session.scalars(
            select(ModelingDataset)
            .where(ModelingDataset.owner_id == owner_id)
            .order_by(ModelingDataset.created_at.desc(), ModelingDataset.id)
        )
        return list(rows)

    async def save_dataset(self, dataset: ModelingDataset) -> None:
        await self.session.commit()

    async def add_experiment(self, experiment: ModelingExperiment) -> None:
        self.session.add(experiment)
        await self.session.commit()

    async def experiment(self, experiment_id: str, owner_id: str) -> ModelingExperiment | None:
        return await self.session.scalar(
            select(ModelingExperiment).where(
                ModelingExperiment.id == experiment_id,
                ModelingExperiment.owner_id == owner_id,
            )
        )

    async def experiments(self, owner_id: str) -> list[ModelingExperiment]:
        rows = await self.session.scalars(
            select(ModelingExperiment)
            .where(ModelingExperiment.owner_id == owner_id)
            .order_by(ModelingExperiment.created_at.desc(), ModelingExperiment.id)
        )
        return list(rows)
