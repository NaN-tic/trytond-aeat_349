# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    def check_invoice_line_from_consignment(self):
        if hasattr(self, 'stock_moves') and self.stock_moves:
            invoice_country = self.invoice.invoice_address.country
            shipments = {m.shipment for m in self.stock_moves if m.shipment}
            for shipment in shipments:
                shipment_country = shipment.warehouse.address.country
                if shipment_country == invoice_country:
                    return False
        return True

    @fields.depends('taxes', 'invoice_type', 'aeat349_operation_key',
        'invoice', '_parent_invoice.type', 'quantity', 'amount',
        'unit_price')
    def on_change_with_aeat349_operation_key(self):
        result = super().on_change_with_aeat349_operation_key()
        if self.check_invoice_line_from_consignment():
            return result
        return None

    @classmethod
    def get_aeat349_operation_key(cls, line, invoice_type, amount, taxes):
        result = super().get_aeat349_operation_key(line, invoice_type, amount,
            taxes)
        if line.check_invoice_line_from_consignment():
            return result
        return None
