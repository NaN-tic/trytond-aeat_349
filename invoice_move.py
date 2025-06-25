# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('_parent_invoice.invoice_address', 'stock_moves')
    def check_invoice_line_from_consignment(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        if self.invoice is not None and getattr(self, 'stock_moves', None):
            invoice_country = self.invoice.invoice_address.country
            moves = self.stock_moves
            aeat349_moves = any(m.aeat349_operation_key for m in moves)
            if aeat349_moves:
                shipments = {m.shipment for m in moves
                    if m.shipment and isinstance(m.shipment, ShipmentInternal)}
                for shipment in shipments:
                    if (shipment.warehouse is None
                            or shipment.warehouse.address is None):
                        continue
                    shipment_country = shipment.warehouse.address.country
                    if shipment_country == invoice_country:
                        return False
        return True

    @fields.depends('taxes', 'invoice_type', 'aeat349_operation_key',
        'invoice', '_parent_invoice.type', 'quantity', 'amount',
        'unit_price', methods=['check_invoice_line_from_consignment'])
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
