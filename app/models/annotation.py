from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.variant import Variant


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    gene_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    clinical_significance: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    variant: Mapped["Variant"] = relationship(
        back_populates="annotation",
    )
