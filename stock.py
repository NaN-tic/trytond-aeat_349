# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from sql.operators import In
from trytond.pyson import Eval
from trytond.i18n import gettext
from trytond.exceptions import UserError
from .aeat import OPERATION_KEY

OP_KEY = list(dict(OPERATION_KEY).keys())

_ZERO = Decimal('0.0')


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    aeat349_operation_key = fields.Many2One('aeat.349.type',
        'AEAT 349 Operation Key', readonly=True)
    aeat349_operation = fields.Function(
        fields.Many2One('aeat.349.report.operation', '349 Operation',
            readonly=True), 'get_aeat349_register')
        #searcher='search_aeat349_operation')
    aeat349_ammendment = fields.Function(
        fields.Many2One('aeat.349.report.ammendment', '349 Ammendment',
            readonly=True), 'get_aeat349_register')
        #searcher='search_aeat349_ammendment')

    def get_aeat349_register(self, name):
        pool = Pool()
        Origin = pool.get('aeat.349.report.origin')

        value = None
        origins = Origin.search([
                ('resource', '=', self),
                ], limit=1)
        if origins:
            value = (origins[0].operation if name == 'aeat349_operation'
                else origins[0].ammendment)
        return value

    def get_aeat349_operation_key(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')
        Configuration = pool.get('stock.configuration')
        config = Configuration(0)

        if (config and config.aeat349_default_out_operation_key
                and config.aeat349_default_in_operation_key
                and self.shipment
                and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list and self.intrastat_type):
            return (config.aeat349_default_out_operation_key.id
                if self.intrastat_type == 'dispatch'
                else config.aeat349_default_in_operation_key.id)
        return None

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="aeat349"]', 'states', {
                    'invisible': (~Eval('shipment_price_list')
                        & ~Eval('intrastat_type')),
                    }),
            ]

    @classmethod
    def do(cls, moves):
        super().do(moves)
        vlist = []
        for move in moves:
            aeat349 = move.get_aeat349_operation_key()
            vlist.extend(([move], {'aeat349_operation_key': aeat349}))

        if vlist:
            cls.write(*vlist)

    @classmethod
    def check_aeat349(cls, moves):
        #return [x.report for move in moves for x in move.aeat349_operation if x.report]
        pool = Pool()
        Operation = pool.get('aeat.349.report.operation')

        operations = Operation.search([
                ('origins.resource', 'in', moves),
                ('report.state', 'in', ('calculated', 'done'),)
                ])

        return [x.report for x in operations]

    @classmethod
    def delete(cls, moves):
        reports = cls.check_aeat349(moves)
        if reports:
            shipments = ", ".join([m.shipment.rec_name for m in moves
                    if m.shipment])
            reports = ", ".join([r.rec_name for r in reports])
            raise UserError(gettext('aeat_349.msg_delete_moves_in_349report',
                    shipments=shipments, reports=reports))
        super().delete(moves)

    @classmethod
    def copy(cls, moves, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('aeat349_operation_key', None)
        return super().copy(moves, default=default)


#class Reasign349RecordStart(ModelView):
#    """
#    Reasign AEAT 349 Records Start
#    """
#    __name__ = "aeat.349.reasign.records.start"
#
#    aeat_349_type = fields.Many2One('aeat.349.type', 'Operation Key',
#        required=True)
#
#
#class Reasign349RecordEnd(ModelView):
#    """
#    Reasign AEAT 349 Records End
#    """
#    __name__ = "aeat.349.reasign.records.end"


class Reasign349MoveRecord(Wizard):
    """
    Reasign AEAT 349 Move Records
    """
    __name__ = "aeat.349.reasign.move.records"

    start = StateView('aeat.349.reasign.records.start',
        'aeat_349.aeat_349_reasign_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Reasign', 'reasign', 'tryton-ok', default=True),
            ])
    reasign = StateTransition()
    done = StateView('aeat.349.reasign.records.end',
        'aeat_349.aeat_349_reasign_end_view', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def transition_reasign(self):
        pool = Pool()
        Shipment = pool.get('stock.shipment.internal')
        Move = pool.get('stock.move')
        cursor = Transaction().connection.cursor()
        shipments = Shipment.browse(Transaction().context['active_ids'])

        value = self.start.aeat_349_type
        moves = []
        shipment_ids = set()
        for shipment in shipments:
            if not shipment.price_list:
                continue
            for move in shipment.outgoing_moves:
                if not move.intrastat_type:
                    continue
                moves.append(move.id)
                shipment_ids.add(shipment.id)

        if not shipment_ids:
            return 'done'

        move = Move.__table__()
        # Update to allow to modify key for posted invoices
        cursor.execute(*move.update(columns=[move.aeat349_operation_key],
                values=[value.id], where=In(move.id, moves)))

        return 'done'
