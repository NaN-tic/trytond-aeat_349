from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from sql.operators import In
from .aeat import OPERATION_KEY

__all__ = ['Type', 'TypeTax', 'TypeTaxTemplate', 'Record', 'TaxTemplate',
    'Tax', 'Invoice', 'InvoiceLine', 'Recalculate349RecordStart',
    'Recalculate349RecordEnd', 'Recalculate349Record', 'Reasign349RecordStart',
    'Reasign349RecordEnd', 'Reasign349Record']

__metaclass__ = PoolMeta


class Type(ModelSQL, ModelView):
    """
    AEAT 349 Type

    Keys types for AEAT 349 Report
    """
    __name__ = 'aeat.349.type'
    _rec_name = 'operation_key'

    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)

    @classmethod
    def __setup__(cls):
        super(Type, cls).__setup__()
        cls._sql_constraints += [
            ('operation_key_uniq', 'unique (operation_key)',
                'unique_operation_key')
            ]
        cls._error_messages.update({
                'unique_operation_key': 'Operation key must be unique.',
                })


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

        res['aeat349_operation_keys'] = []
        if tax and len(tax.aeat_349_operation_keys) > 0:
            res['aeat349_operation_keys'].append(['unlink_all'])
        if len(self.aeat349_operation_keys) > 0:
            ids = [c.id for c in self.aeat349_operation_keys]
            res['aeat349_operation_keys'].append(['set', ids])
        for direction in ('in', 'out'):
            field = "aeat349_default_%s_operation_key" % (direction)
            if not tax or getattr(tax, field) != getattr(self, field):
                value = getattr(self, field)
                if value:
                    res[field] = getattr(self, field).id
                else:
                    res[field] = None
        return res


class Tax:
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


class InvoiceLine:
    __name__ = 'account.invoice.line'
    aeat349_available_keys = fields.Function(fields.One2Many('aeat.349.type',
        None, 'AEAT 349 Available Keys', on_change_with=['taxes', 'product'],
        depends=['taxes', 'product']), 'on_change_with_aeat349_available_keys')
    aeat349_operation_key = fields.Many2One('aeat.349.type',
        'AEAT 349 Operation Key', on_change_with=['taxes', 'invoice_type',
            'aeat349_operation_key', '_parent_invoice.type', 'product'],
        depends=['aeat349_available_keys', 'taxes', 'invoice_type', 'product'],
        domain=[('id', 'in', Eval('aeat349_available_keys', []))],)

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()

    def on_change_product(self):
        Taxes = Pool().get('account.tax')
        res = super(InvoiceLine, self).on_change_product()
        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        if 'taxes' in res:
            res['aeat349_operation_key'] = self.get_aeat349_operation_key(
                        type_, Taxes.browse(res['taxes']))
        return res

    def on_change_with_aeat349_available_keys(self, name=None):
        keys = []
        for tax in self.taxes:
            keys.extend([k.id for k in tax.aeat349_operation_keys])
        return list(set(keys))

    def on_change_with_aeat349_operation_key(self):
        if self.aeat349_operation_key:
            return self.aeat349_operation_key.id

        if self.invoice and self.invoice.type:
            type_ = self.invoice.type
        elif self.invoice_type:
            type_ = self.invoice_type
        if not type_:
            return

        return self.get_aeat349_operation_key(type_, self.taxes)

    @classmethod
    def get_aeat349_operation_key(cls, invoice_type, taxes):
        type_ = 'in' if invoice_type[0:2] == 'in' else 'out'
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
            if not vals.get('aeat349_operation_key') and vals.get('taxes'):
                invoice_type = vals.get('invoice_type')
                if not invoice_type and vals.get('invoice'):
                    invoice = Invoice(vals.get('invoice'))
                    invoice_type = invoice.type
                taxes_ids = []
                for key, value in vals.get('taxes'):
                    if key in ['add', 'set']:
                        taxes_ids.extend(value)

                vals['aeat349_operation_key'] = cls.get_aeat349_operation_key(
                    invoice_type, Taxes.browse(taxes_ids))
        return super(InvoiceLine, cls).create(vlist)


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def create_aeat349_records(cls, invoices):
        Record = Pool().get('aeat.349.record')
        to_create = {}
        for invoice in invoices:
            if not invoice.move:
                continue
            for line in invoice.lines:
                if line.aeat349_operation_key:
                    operation_key = line.aeat349_operation_key.operation_key
                    key = "%d-%s" % (invoice.id, operation_key)
                    if key in to_create:
                        to_create[key]['base'] += line.amount
                    else:
                        to_create[key] = {
                                'company': invoice.company.id,
                                'fiscalyear': invoice.move.period.fiscalyear,
                                'month': invoice.invoice_date.month,
                                'party_name': invoice.party.rec_name,
                                'party_vat': invoice.party.vat_code,
                                'base': line.amount,
                                'operation_key': operation_key,
                                'invoice': invoice.id,
                        }

        with Transaction().set_user(0, set_context=True):
            Record.delete(Record.search([('invoice', 'in',
                            [i.id for i in invoices])]))
            Record.create(to_create.values())

    @classmethod
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        cls.create_aeat349_records(invoices)


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
        cursor = Transaction().cursor
        invoices = Invoice.browse(Transaction().context['active_ids'])

        value = self.start.aeat_349_type
        lines = []
        invoice_ids = set()
        for invoice in invoices:
            for line in invoice.lines:
                if value in line.aeat349_available_keys:
                    lines.append(line.id)
                    invoice_ids.add(invoice.id)

        line = Line.__table__()
        #Update to allow to modify key for posted invoices
        cursor.execute(*line.update(columns=[line.aeat349_operation_key],
                values=[value.id], where=In(line.id, lines)))

        invoices = Invoice.browse(list(invoices))
        Invoice.create_aeat349_records(invoices)

        return 'done'
