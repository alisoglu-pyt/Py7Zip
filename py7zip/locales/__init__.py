"""Additional language packs."""

from .az import TRANSLATIONS as AZ
from .de import TRANSLATIONS as DE
from .es import TRANSLATIONS as ES
from .fr import TRANSLATIONS as FR
from .ko import TRANSLATIONS as KO
from .pt import TRANSLATIONS as PT
from .tk import TRANSLATIONS as TK
from .zh import TRANSLATIONS as ZH

EXTRA_TRANSLATIONS = {
    "de": DE,
    "fr": FR,
    "es": ES,
    "pt": PT,
    "zh": ZH,
    "ko": KO,
    "az": AZ,
    "tk": TK,
}

__all__ = ["EXTRA_TRANSLATIONS"]
