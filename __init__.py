#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from .aeat import *
from .invoice import *


def register():
    Pool.register(
        Report,
        Operation,
        Ammendment,
        Type,
        TypeTaxTemplate,
        TypeTax,
        Record,
        TaxTemplate,
        Tax,
        Invoice,
        InvoiceLine,
        Recalculate349RecordStart,
        Recalculate349RecordEnd,
        Reasign349RecordStart,
        Reasign349RecordEnd,
        module='aeat_349', type_='model')
    Pool.register(
        Recalculate349Record,
        Reasign349Record,
        module='aeat_349', type_='wizard')
