# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSQL, ModelView, Workflow, fields, Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql.operators import In, Concat
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
            ])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ])
    aeat349_default_out_ammendment_key = fields.Many2One('aeat.349.type',
        'Default Out Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ])
    aeat349_default_in_ammendment_key = fields.Many2One('aeat.349.type',
        'Default In Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ])

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
            ])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', OP_KEY),
            ])
    aeat349_default_out_ammendment_key = fields.Many2One('aeat.349.type',
        'Default Out Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ])
    aeat349_default_in_ammendment_key = fields.Many2One('aeat.349.type',
        'Default In Ammendment Key',
        domain=[
            ('id', 'in', Eval('aeat349_operation_keys', [])),
            ('operation_key', 'in', AM_KEY),
            ])


STATES = {
    'invisible': Eval('type') != 'line',
    }

# TODO: Remove from databse the aeat_349_record table


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    aeat349_available_keys = fields.Function(fields.Many2Many('aeat.349.type',
        None, None, 'AEAT 349 Available Keys',
        states=STATES),
        'on_change_with_aeat349_available_keys')
    aeat349_operation_key = fields.Many2One('aeat.349.type',
        'AEAT 349 Operation Key',
        states=STATES, depends=DEPENDS + ['aeat349_available_keys', 'taxes',
            'invoice_type', 'product'],
        domain=[('id', 'in', Eval('aeat349_available_keys', []))],)
    aeat349_operation = fields.Function(
        fields.Many2One('aeat.349.report.operation', '349 Operation',
            readonly=True), 'get_aeat349_resource')
    aeat349_ammendment = fields.Function(
        fields.Many2One('aeat.349.report.ammendment', '349 Ammendment',
            readonly=True), 'get_aeat349_resource')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude |= {'aeat349_operation',
            'aeat349_ammendment'}

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Origin = pool.get('aeat.349.report.origin')
        sql_table = cls.__table__()
        origin = Origin.__table__()

        super().__register__(module_name)
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)

        if table.column_exist('aeat349_operation'):
            cursor.execute(*origin.insert(
                    columns=[
                        origin.operation,
                        origin.ammendment,
                        origin.resource],
                    values=sql_table.select(
                        sql_table.aeat349_operation,
                        sql_table.aeat349_ammendment,
                        Concat(cls.__name__ + ',', sql_table.id),
                        where=((sql_table.aeat349_operation != None)
                            | (sql_table.aeat349_ammendment != None)))))
            table.drop_column('aeat349_operation')
            table.drop_column('aeat349_ammendment')

    def get_aeat349_resource(self, name):
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
        pool = Pool()
        Line = pool.get('account.invoice.line')

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

        return Line.get_aeat349_operation_key(self, type_, self.amount, self.taxes)

    @classmethod
    def get_aeat349_operation_key(cls, line, invoice_type, amount, taxes):
        direction = 'in' if invoice_type == 'in' else 'out'
        type_ = 'operation' if amount >= Decimal(0) else 'ammendment'
        for tax in taxes:
            name = 'aeat349_default_%s_%s_key' % (direction, type_)
            value = getattr(tax, name)
            if value:
                return value.id

    @classmethod
    def create(cls, vlist):
        Taxes = Pool().get('account.tax')

        invoice_lines = super().create(vlist)

        to_save = []
        for line in invoice_lines:
            if line.type != 'line':
                continue
            if not line.aeat349_operation_key and line.taxes:
                invoice_type = line.invoice_type
                if not invoice_type and line.invoice:
                    invoice_type = line.invoice.type
                taxes_ids = [x.id for x in line.taxes]
                with Transaction().set_user(0):
                    taxes = Taxes.browse(taxes_ids)
                amount = (Decimal(str(line.quantity or 0))
                    * Decimal(str(line.unit_price or 0)))
                line.aeat349_operation_key = cls.get_aeat349_operation_key(
                    line, invoice_type, amount, taxes)
                to_save.append(line)
        if to_save:
            cls.save(to_save)
        return invoice_lines

    @classmethod
    def check_aeat349(cls, lines):
        pool = Pool()
        Operation = pool.get('aeat.349.report.operation')
        Ammendment = pool.get('aeat.349.report.ammendment')

        operations = Operation.search([
                ('origins.resource', 'in', lines),
                ('report.state', 'in', ('calculated', 'done'),)
                ])
        ammendments = Ammendment.search([
                ('origins.resource', 'in', lines),
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

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('aeat349_ammendment', None)
        default.setdefault('aeat349_operation', None)
        return super().copy(lines, default=default)


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

    @fields.depends('base_price')
    def on_change_with_aeat349_operation_key(self):
        return super(InvoiceLineDisccount, self
            ).on_change_with_aeat349_operation_key()
