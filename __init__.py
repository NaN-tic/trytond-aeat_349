# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import aeat
from . import invoice


def register():
    Pool.register(
        aeat.Report,
        aeat.Operation,
        aeat.Ammendment,
        invoice.Type,
        invoice.TypeTaxTemplate,
        invoice.TypeTax,
        invoice.Record,
        invoice.TaxTemplate,
        invoice.Tax,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.Recalculate349RecordStart,
        invoice.Recalculate349RecordEnd,
        invoice.Reasign349RecordStart,
        invoice.Reasign349RecordEnd,
        module='aeat_349', type_='model')
    Pool.register(
        invoice.Recalculate349Record,
        invoice.Reasign349Record,
        module='aeat_349', type_='wizard')
