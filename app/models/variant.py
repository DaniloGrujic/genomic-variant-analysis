from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.annotation import Annotation
    from app.models.vcf_file import VCFFile


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    vcf_file_id: Mapped[int] = mapped_column(
        ForeignKey("vcf_files.id", ondelete="CASCADE"),
        nullable=False,
    )

    chromosome: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    variant_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    quality: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    reference: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    alternate: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    allele_frequency: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    vcf_file: Mapped["VCFFile"] = relationship(
        back_populates="variants",
    )

    annotation: Mapped["Annotation | None"] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
        uselist=False,
    )
