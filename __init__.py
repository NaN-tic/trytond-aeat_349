#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from .aeat import *


def register():
    Pool.register(
        Report,
        Operation,
        Ammendment,
        module='aeat_349', type_='model')
