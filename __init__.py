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
        invoice.TaxTemplate,
        invoice.Tax,
        invoice.Invoice,
        invoice.InvoiceLine,
        invoice.Reasign349RecordStart,
        invoice.Reasign349RecordEnd,
        module='aeat_349', type_='model')
    Pool.register(
        invoice.Reasign349Record,
        invoice.CreditInvoice,
        module='aeat_349', type_='wizard')
    Pool.register(
        invoice.InvoiceLineDisccount,
        module='aeat_349', type_='model', depends=['account_invoice_discount'])
