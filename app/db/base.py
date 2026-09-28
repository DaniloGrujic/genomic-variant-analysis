from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so they are registered in Base.metadata.
from app.models.annotation_file import AnnotationFile  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.variant import Variant  # noqa: F401
from app.models.vcf_file import VCFFile  # noqa: F401
