# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.company.model import CompanyValueMixin
from .invoice import OP_KEY


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    aeat349_default_out_operation_key = fields.MultiValue(
        fields.Many2One('aeat.349.type', 'Default Out Operation Key',
        domain=[
            ('operation_key', 'in', OP_KEY),
            ]))
    aeat349_default_in_operation_key = fields.MultiValue(
        fields.Many2One('aeat.349.type', 'Default In Operation Key',
        domain=[
            ('operation_key', 'in', OP_KEY),
            ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in ('aeat349_default_in_operation_key',
                'aeat349_default_out_operation_key'):
            return pool.get('stock.configuration.aeat349')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationAEAT349(ModelSQL, CompanyValueMixin):
    "Stock Configuration AEAT 349"
    __name__ = 'stock.configuration.aeat349'

    aeat349_default_out_operation_key = fields.Many2One('aeat.349.type',
        'Default Out Operation Key',
        domain=[
            ('operation_key', 'in', OP_KEY),
            ])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[
            ('operation_key', 'in', OP_KEY),
            ])
