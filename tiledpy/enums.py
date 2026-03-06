from enum import Enum


class OFFSET(Enum):
    LEFT_TOP       =   (0, 0)
    MIDDLE_TOP     =   (0.5, 0)
    RIGHT_TOP      =   (1, 0)
    LEFT_MIDDLE    =   (0, 0.5)
    CENTER         =   (0.5, 0.5)
    RIGHT_MIDDLE   =   (1, 0.5)
    LEFT_BOTTOM    =   (0, 1)
    MIDDLE_BOTTOM  =   (0.5, 1)
    RIGHT_BOTTOM   =   (1, 1)