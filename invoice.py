# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSQL, ModelView, Workflow, fields, Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql.operators import In
from sql import Literal
from trytond.i18n import gettext
from trytond.exceptions import UserError
from .aeat import OPERATION_KEY, AMMENDMENT_KEY

OP_KEY = list(dict(OPERATION_KEY).keys())
AM_KEY = list(dict(AMMENDMENT_KEY).keys())


class Type(ModelSQL, ModelView):
    """
    AEAT 349 Type
    Keys types for AEAT 349 Report
    """
    __name__ = 'aeat.349.type'

    operation_key = fields.Selection(OPERATION_KEY + AMMENDMENT_KEY,
        'Operation key', required=True)

    @classmethod
    def __setup__(cls):
        super(Type, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('operation_key_uniq', Unique(t, t.operation_key),
                'Operation key must be unique.')
            ]

    def get_rec_name(self, name):
        opts = self.fields_get('operation_key')['operation_key']['selection']
        for key, value in opts:
            if self.operation_key == key:
                return value
        return self.operation_key


class TypeTax(ModelSQL):
    """
    AEAT 349 Type-Tax Relation
    """
    __name__ = 'aeat.349.type-account.tax'

    aeat_349_type = fields.Many2One('aeat.349.type', 'Operation Key',
        ondelete='CASCADE', required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='CASCADE',
        required=True)


class TypeTaxTemplate(ModelSQL):
    """
    AEAT 349 Type-Tax Template Relation
    """
    __name__ = 'aeat.349.type-account.tax.template'

    aeat_349_type = fields.Many2One('aeat.349.type', 'Operation Key',
        ondelete='CASCADE', required=True)
    tax = fields.Many2One('account.tax.template', 'Tax Template',
        ondelete='CASCADE', required=True)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Module = pool.get('ir.module')
        cursor = Transaction().connection.cursor()
        module_table = Module.__table__()
        sql_table = ModelData.__table__()
        # Meld aeat_349_es into aeat_349
        cursor.execute(*module_table.update(
                columns=[module_table.state],
                values=[Literal('uninstalled')],
                where=module_table.name == Literal('aeat_349_es')
                ))
        cursor.execute(*sql_table.update(
                columns=[sql_table.module],
                values=[module_name],
                where=sql_table.module == Literal('aeat_349_es')))
        super(TypeTaxTemplate, cls).__register__(module_name)


class TaxTemplate(ModelSQL, ModelView):
    'Account Tax Template'
    __name__ = 'account.tax.template'
    aeat349_operation_keys = fields.Many2Many(
        'aeat.349.type-account.tax.template', 'tax', 'aeat_349_type',
        'Available Operation Keys')
    aeat349_default_out_operation_key = fields.Many2One('aeat.349.type',
        'Default Out Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_out_ammendment_key = fields.Many2One('aeat.349.type',
        'Default Out Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_in_ammendment_key = fields.Many2One('aeat.349.type',
        'Default In Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ], depends=['aeat349_operation_keys'])

    def _get_tax_value(self, tax=None):
        res = super(TaxTemplate, self)._get_tax_value(tax)

        old_ids = set()
        new_ids = set()
        if tax and len(tax.aeat349_operation_keys) > 0:
            old_ids = set([c.id for c in tax.aeat349_operation_keys])
        if len(self.aeat349_operation_keys) > 0:
            new_ids = set([c.id for c in self.aeat349_operation_keys])
            for direction in ('in', 'out'):
                for type_ in ('operation', 'ammendment'):
                    field = "aeat349_default_%s_%s_key" % (direction, type_)
                    if not tax or getattr(tax, field) != getattr(self, field):
                        value = getattr(self, field)
                        if value and value.id in new_ids:
                            res[field] = value.id
                        else:
                            res[field] = None
        else:
            if tax and tax.aeat349_default_in_operation_key:
                res['aeat349_default_in_operation_key'] = None
            if tax and tax.aeat349_default_out_operation_key:
                res['aeat349_default_out_operation_key'] = None
            if tax and tax.aeat349_default_in_ammendment_key:
                res['aeat349_default_in_ammendment_key'] = None
            if tax and tax.aeat349_default_out_ammendment_key:
                res['aeat349_default_out_ammendment_key'] = None
        if old_ids or new_ids:
            key = 'aeat349_operation_keys'
            res[key] = []
            to_remove = old_ids - new_ids
            if to_remove:
                res[key].append(['remove', list(to_remove)])
            to_add = new_ids - old_ids
            if to_add:
                res[key].append(['add', list(to_add)])
            if not res[key]:
                del res[key]
        return res


class Tax(metaclass=PoolMeta):
    __name__ = 'account.tax'

    aeat349_operation_keys = fields.Many2Many('aeat.349.type-account.tax',
        'tax', 'aeat_349_type', 'Available Operation Keys')
    aeat349_default_out_operation_key = fields.Many2One('aeat.349.type',
        'Default Out Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_out_ammendment_key = fields.Many2One('aeat.349.type',
        'Default Out Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ], depends=['aeat349_operation_keys'])
    aeat349_default_in_ammendment_key = fields.Many2One('aeat.349.type',
        'Default In Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ], depends=['aeat349_operation_keys'])


STATES = {
    'invisible': Eval('type') != 'line',
    }
DEPENDS = ['type']

# TODO: Remove from databse the aeat_349_record table


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    aeat349_available_keys = fields.Function(fields.Many2Many('aeat.349.type',
        None, None, 'AEAT 349 Available Keys',
        states=STATES, depends=DEPENDS + ['taxes', 'product']),
        'on_change_with_aeat349_available_keys')
    aeat349_operation_key = fields.Many2One('aeat.349.type',
        'AEAT 349 Operation Key',
        states=STATES, depends=DEPENDS + ['aeat349_available_keys', 'taxes',
            'invoice_type', 'product'],
        domain=[('id', 'in', Eval('aeat349_available_keys', []))],)
    aeat349_operation = fields.Many2One('aeat.349.report.operation',
        '349 Operation', readonly=True)
    aeat349_ammendment = fields.Many2One('aeat.349.report.ammendment',
        '349 Ammendment', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude |= {'aeat349_operation',
            'aeat349_ammendment'}

    def _has_aeat349_operation_keys(self):
        # in case not has taxes or not has aeat 349, operation_key is None
        return all([tax.aeat349_operation_keys not in [(), [], None]
            for tax in self.taxes])

    @fields.depends('taxes')
    def on_change_taxes(self):
        try:
            super(InvoiceLine, self).on_change_taxes()
        except AttributeError:
            pass

        if not self.taxes or not self._has_aeat349_operation_keys():
            self.aeat349_operation_key = None

    @fields.depends('taxes', 'product')
    def on_change_with_aeat349_available_keys(self, name=None):
        if self._has_aeat349_operation_keys():
            return list(set([k.id for tax in self.taxes
                for k in tax.aeat349_operation_keys]))
        return []

    @fields.depends('taxes', 'invoice_type', 'aeat349_operation_key',
        'invoice', '_parent_invoice.type', 'quantity', 'amount',
        'unit_price')
    def on_change_with_aeat349_operation_key(self):
        if not self.taxes or not self._has_aeat349_operation_keys():
            return
        if not self.amount:
            return
        if self.aeat349_operation_key:
            return self.aeat349_operation_key.id
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        else:
            return

        return self.get_aeat349_operation_key(type_, self.amount, self.taxes)

    @classmethod
    def get_aeat349_operation_key(cls, invoice_type, amount, taxes):
        direction = 'in' if invoice_type == 'in' else 'out'
        type_ = 'operation' if amount >= Decimal('0.0') else 'ammendment'
        for tax in taxes:
            name = 'aeat349_default_%s_%s_key' % (direction, type_)
            value = getattr(tax, name)
            if value:
                return value.id

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        Taxes = Pool().get('account.tax')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if vals.get('type', 'line') != 'line':
                continue
            if not vals.get('aeat349_operation_key') and vals.get('taxes'):
                invoice_type = vals.get('invoice_type')
                if not invoice_type and vals.get('invoice'):
                    invoice = Invoice(vals.get('invoice'))
                    invoice_type = invoice.type
                taxes_ids = []
                for key, value in vals.get('taxes'):
                    if key == 'add':
                        taxes_ids.extend(value)
                with Transaction().set_user(0):
                    taxes = Taxes.browse(taxes_ids)
                amount = (Decimal(str(vals.get('quantity') or 0))
                    * Decimal(str(vals.get('unit_price') or 0)))
                vals['aeat349_operation_key'] = cls.get_aeat349_operation_key(
                    invoice_type, amount, taxes)
        return super(InvoiceLine, cls).create(vlist)

    @classmethod
    def check_aeat349(cls, lines):
        pool = Pool()
        Operation = pool.get('aeat.349.report.operation')
        Ammendment = pool.get('aeat.349.report.ammendment')

        operations = Operation.search([
                ('invoice_lines', 'in', lines),
                ('report.state', 'in', ('calculated', 'done'),)
                ])
        ammendments = Ammendment.search([
                ('invoice_lines', 'in', lines),
                ('report.state', 'in', ('calculated', 'done'),)
                ])

        return [x.report for x in operations + ammendments]

    @classmethod
    def delete(cls, lines):
        reports = cls.check_aeat349(lines)
        if reports:
            invoices = ", ".join([l.invoice.rec_name for l in lines
                    if l.invoice])
            reports = ", ".join([r.rec_name for r in reports])
            raise UserError(gettext('aeat_349.msg_delete_lines_in_349report',
                    invoices=invoices, reports=reports))
        super().delete(lines)

    def _credit(self):
        pool = Pool()
        AEAT349Type = pool.get('aeat.349.type')

        line = super(InvoiceLine, self)._credit()
        if self.aeat349_operation:
            aeat349_ammendment, = AEAT349Type.search([
                ('operation_key', '=', 'A-%s' % (
                    self.aeat349_operation.operation_key)),
            ])
            line.aeat349_operation_key = aeat349_ammendment.id
        return line


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def draft(cls, invoices):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        super(Invoice, cls).draft(invoices)

        lines = [l for i in invoices for l in i.lines]
        reports = Line.check_aeat349(lines)
        if reports:
            invoices_name = ", ".join([l.invoice.rec_name for l in lines
                    if l.invoice])
            reports = ", ".join([r.rec_name for r in reports])
            raise UserError(gettext('aeat_349.msg_delete_lines_in_349report',
                    invoices=invoices_name,
                    reports=reports
                    ))

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, invoices):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        super(Invoice, cls).cancel(invoices)

        if not Transaction().context.get('credit_wizard'):
            lines = [l for i in invoices for l in i.lines]
            reports = Line.check_aeat349(lines)

            if reports:
                invoices_name = ", ".join([l.invoice.rec_name for l in lines
                        if l.invoice])
                reports = ", ".join([r.rec_name for r in reports])
                raise UserError(
                    gettext('aeat_349.msg_delete_lines_in_349report',
                        invoices=invoices_name,
                        reports=reports
                    ))


class Reasign349RecordStart(ModelView):
    """
    Reasign AEAT 349 Records Start
    """
    __name__ = "aeat.349.reasign.records.start"

    aeat_349_type = fields.Many2One('aeat.349.type', 'Operation Key',
        required=True)


class Reasign349RecordEnd(ModelView):
    """
    Reasign AEAT 349 Records End
    """
    __name__ = "aeat.349.reasign.records.end"


class Reasign349Record(Wizard):
    """
    Reasign AEAT 349 Records
    """
    __name__ = "aeat.349.reasign.records"
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
        Invoice = Pool().get('account.invoice')
        Line = Pool().get('account.invoice.line')
        cursor = Transaction().connection.cursor()
        invoices = Invoice.browse(Transaction().context['active_ids'])

        value = self.start.aeat_349_type
        lines = []
        invoice_ids = set()
        for invoice in invoices:
            for line in invoice.lines:
                if value in line.aeat349_available_keys:
                    lines.append(line.id)
                    invoice_ids.add(invoice.id)

        if not invoice_ids:
            return 'done'

        line = Line.__table__()
        # Update to allow to modify key for posted invoices
        cursor.execute(*line.update(columns=[line.aeat349_operation_key],
                values=[value.id], where=In(line.id, lines)))

        return 'done'


class CreditInvoice(metaclass=PoolMeta):
    __name__ = 'account.invoice.credit'

    def do_credit(self, action):
        with Transaction().set_context(credit_wizard=True):
            return super(CreditInvoice, self).do_credit(action)


class InvoiceLineDisccount(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @fields.depends('gross_unit_price')
    def on_change_with_aeat349_operation_key(self):
        return super(InvoiceLineDisccount, self
            ).on_change_with_aeat349_operation_key()
