from .io import AnnotationLoader
from .io.htk_lab import HTKAnnotationLoader
from .io.textgrid import TGTAnnotationLoader

__all__ = ["AnnotationLoader", "HTKAnnotationLoader", "TGTAnnotationLoader"]
