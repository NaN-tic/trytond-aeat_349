# -*- coding: utf-8 -*-
from trytond.pool import Pool, PoolMeta
from.aeat import OPERATION_KEY


class Report(metaclass=PoolMeta):
    __name__ = "aeat.349.report"

    @classmethod
    def add_349_move_register(cls, report, to_create, key, move,
            party_vat, party_name):
        pool = Pool()
        Origin = pool.get('aeat.349.report.origin')

        amount = move.intrastat_value
        operation_key = move.aeat349_operation_key.operation_key[-1:]

        origin = Origin()
        origin.resource = move
        origin.save()

        if key in to_create:
            to_create[key]['base'] += amount
            to_create[key]['origins'][0][1].append(
                origin.id)
        else:
            to_create[key] = {
                'report': report.id,
                'party_vat': party_vat,
                'party_name': party_name,
                'operation_key': operation_key,
                'base': amount,
                'origins': [('add', [origin.id])],
                }

    def calculate_operations_ammendments(self, start_date, end_date,
            operation_to_create, ammendment_to_create):
        pool = Pool()
        Move = pool.get('stock.move')
        Report = pool.get('aeat.349.report')

        super().calculate_operations_ammendments(start_date, end_date,
            operation_to_create, ammendment_to_create)

        moves = Move.search([
                ('state', '=', 'done'),
                ('aeat349_operation_key', '!=', None),
                ('effective_date', '>=', start_date),
                ('effective_date', '<', end_date),
                ('shipment_price_list', '!=', None),
                ('shipment.company', '=', self.company, 'stock.shipment.internal'),
                ])

        for move in moves:
            party_vat = party_name = ''
            if move.intrastat_type == 'dispatch':
                if (move.shipment.to_warehouse
                        and move.shipment.to_warehouse.address
                        and move.shipment.to_warehouse.address.party):
                    party_vat = (move.shipment.to_warehouse.address.party.
                        tax_identifier.code)
                    party_name = (move.shipment.to_warehouse.address.party.
                        name)
            elif move.intrastat_type == 'arribal':
                if (move.shipment.warehouse
                        and move.shipment.warehouse.address
                        and move.shipment.warehouse.address.party):
                    party_vat = (move.shipment.warehouse.address.party.
                        tax_identifier.code)
                    party_name = (move.shipment.warehouse.address.party.
                        name)
            operation_key = move.aeat349_operation_key.operation_key[-1:]
            key = '%s-%s-%s' % (self.id, party_vat, operation_key)

            if (move.aeat349_operation_key.operation_key in
                    dict(OPERATION_KEY).keys()):
                Report.add_349_move_register(self, operation_to_create, key,
                    move, party_vat, party_name)


class ReportOrigin(metaclass=PoolMeta):
    __name__ = 'aeat.349.report.origin'

    @classmethod
    def get_resource(cls):
        result = super().get_resource()
        result.append(('stock.move', 'Move'))
        return result
