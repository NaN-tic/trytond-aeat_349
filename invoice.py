from trytond.model import ModelSQL, ModelView, fields, Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql.operators import In
from sql import Literal
from .aeat import OPERATION_KEY

__all__ = ['Type', 'TypeTax', 'TypeTaxTemplate', 'Record', 'TaxTemplate',
    'Tax', 'Invoice', 'InvoiceLine', 'Recalculate349RecordStart',
    'Recalculate349RecordEnd', 'Recalculate349Record', 'Reasign349RecordStart',
    'Reasign349RecordEnd', 'Reasign349Record']


class Type(ModelSQL, ModelView):
    """
    AEAT 349 Type

    Keys types for AEAT 349 Report
    """
    __name__ = 'aeat.349.type'

    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)

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
        ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='CASCADE',
        select=True, required=True)


class TypeTaxTemplate(ModelSQL):
    """
    AEAT 349 Type-Tax Template Relation
    """
    __name__ = 'aeat.349.type-account.tax.template'

    aeat_349_type = fields.Many2One('aeat.349.type', 'Operation Key',
        ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax.template', 'Tax Template',
        ondelete='CASCADE', select=True, required=True)

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


class Record(ModelSQL, ModelView):
    """
    AEAT 349 Record

    Calculated on invoice creation to generate temporal
    data for reports. Aggregated on aeat349 calculation.
    """
    __name__ = 'aeat.349.record'

    company = fields.Many2One('company.company', 'Company', required=True,
        readonly=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, readonly=True)
    month = fields.Integer('Month', readonly=True)
    party_vat = fields.Char('VAT', size=17, readonly=True)
    party_name = fields.Char('Party Name', size=40, readonly=True)
    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True, readonly=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2),
        readonly=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', readonly=True)
    operation = fields.Many2One('aeat.349.report.operation', 'Operation',
        readonly=True)


class TaxTemplate(ModelSQL, ModelView):
    'Account Tax Template'
    __name__ = 'account.tax.template'
    aeat349_operation_keys = fields.Many2Many(
        'aeat.349.type-account.tax.template', 'tax', 'aeat_349_type',
        'Available Operation Keys')
    aeat349_default_out_operation_key = fields.Many2One('aeat.349.type',
        'Default Out Operation Key',
        domain=[('id', 'in', Eval('aeat349_operation_keys', []))],
        depends=['aeat349_operation_keys'])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[('id', 'in', Eval('aeat349_operation_keys', []))],
        depends=['aeat349_operation_keys'])

    def _get_tax_value(self, tax=None):
        res = super(TaxTemplate, self)._get_tax_value(tax)

        old_ids = set()
        new_ids = set()
        if tax and len(tax.aeat349_operation_keys) > 0:
            old_ids = set([c.id for c in tax.aeat349_operation_keys])
        if len(self.aeat349_operation_keys) > 0:
            new_ids = set([c.id for c in self.aeat349_operation_keys])
            for direction in ('in', 'out'):
                field = "aeat349_default_%s_operation_key" % (direction)
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
        domain=[('id', 'in', Eval('aeat349_operation_keys', []))],
        depends=['aeat349_operation_keys'])
    aeat349_default_in_operation_key = fields.Many2One('aeat.349.type',
        'Default In Operation Key',
        domain=[('id', 'in', Eval('aeat349_operation_keys', []))],
        depends=['aeat349_operation_keys'])


STATES = {
    'invisible': Eval('type') != 'line',
    }
DEPENDS = ['type']


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

    @fields.depends('invoice', 'taxes')
    def on_change_product(self):
        Taxes = Pool().get('account.tax')

        super(InvoiceLine, self).on_change_product()
        type_ = None
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        self.aeat349_operation_key = None
        if type_ and self.taxes:
            with Transaction().set_user(0):
                taxes = Taxes.browse(self.taxes)
            self.aeat349_operation_key = self.get_aeat349_operation_key(
                        type_, taxes)

    @fields.depends('taxes', 'product')
    def on_change_with_aeat349_available_keys(self, name=None):
        keys = []
        for tax in self.taxes:
            keys.extend([k.id for k in tax.aeat349_operation_keys])
        return list(set(keys))

    @fields.depends('taxes', 'invoice_type', 'aeat349_operation_key',
        '_parent_invoice.type', 'product', 'invoice')
    def on_change_with_aeat349_operation_key(self):
        if self.aeat349_operation_key:
            return self.aeat349_operation_key.id

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        else:
            return

        return self.get_aeat349_operation_key(type_, self.taxes)

    @classmethod
    def get_aeat349_operation_key(cls, invoice_type, taxes):
        type_ = 'in' if invoice_type == 'in' else 'out'
        for tax in taxes:
            name = 'aeat349_default_%s_operation_key' % type_
            value = getattr(tax, name)
            if value:
                return value.id

    @classmethod
    def create(cls, vlist):
        Invoice = Pool().get('account.invoice')
        Taxes = Pool().get('account.tax')
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
                vals['aeat349_operation_key'] = cls.get_aeat349_operation_key(
                    invoice_type, taxes)
        return super(InvoiceLine, cls).create(vlist)


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def create_aeat349_records(cls, invoices):
        pool = Pool()
        Record = pool.get('aeat.349.record')
        Currency = pool.get('currency.currency')
        to_create = {}
        for invoice in invoices:
            if not invoice.move or invoice.state == 'cancel':
                continue
            for line in invoice.lines:
                if line.type != 'line':
                    continue
                if line.aeat349_operation_key:
                    operation_key = line.aeat349_operation_key.operation_key
                    key = "%d-%s" % (invoice.id, operation_key)
                    amount = line.amount
                    if invoice.currency != invoice.company.currency:
                        with Transaction().set_context(
                                date=invoice.currency_date):
                            amount = Currency.compute(
                                invoice.currency, amount,
                                invoice.company.currency)
                    if key in to_create:
                        to_create[key]['base'] += amount
                    else:
                        month = (invoice.accounting_date.month
                             if invoice.accounting_date
                             else invoice.invoice_date.month)
                        to_create[key] = {
                            'company': invoice.company.id,
                            'fiscalyear': invoice.move.period.fiscalyear,
                            'month': month,
                            'party_name': invoice.party.name[:40],
                            'party_vat': (invoice.party.tax_identifier.code
                                if invoice.party.tax_identifier else ''),
                            'base': amount,
                            'operation_key': operation_key,
                            'invoice': invoice.id,
                            }

        with Transaction().set_user(0, set_context=True):
            Record.delete(Record.search([('invoice', 'in',
                            [i.id for i in invoices])]))
            Record.create(list(to_create.values()))

    @classmethod
    def draft(cls, invoices):
        pool = Pool()
        Record = pool.get('aeat.349.record')
        super(Invoice, cls).draft(invoices)
        with Transaction().set_user(0, set_context=True):
            Record.delete(Record.search([('invoice', 'in',
                            [i.id for i in invoices])]))

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        cls.create_aeat349_records(invoices)

    @classmethod
    def cancel(cls, invoices):
        pool = Pool()
        Record = pool.get('aeat.349.record')
        super(Invoice, cls).cancel(invoices)
        with Transaction().set_user(0, set_context=True):
            Record.delete(Record.search([('invoice', 'in',
                            [i.id for i in invoices])]))


class Recalculate349RecordStart(ModelView):
    """
    Recalculate AEAT 349 Records Start
    """
    __name__ = "aeat.349.recalculate.records.start"


class Recalculate349RecordEnd(ModelView):
    """
    Recalculate AEAT 349 Records End
    """
    __name__ = "aeat.349.recalculate.records.end"


class Recalculate349Record(Wizard):
    """
    Recalculate AEAT 349 Records
    """
    __name__ = "aeat.349.recalculate.records"
    start = StateView('aeat.349.recalculate.records.start',
        'aeat_349.aeat_349_recalculate_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Calculate', 'calculate', 'tryton-ok', default=True),
            ])
    calculate = StateTransition()
    done = StateView('aeat.349.recalculate.records.end',
        'aeat_349.aeat_349_recalculate_end_view', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    def transition_calculate(self):
        Invoice = Pool().get('account.invoice')
        invoices = Invoice.browse(Transaction().context['active_ids'])
        Invoice.create_aeat349_records(invoices)
        return 'done'


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

        invoices = Invoice.browse(list(invoices))
        Invoice.create_aeat349_records(invoices)

        return 'done'
