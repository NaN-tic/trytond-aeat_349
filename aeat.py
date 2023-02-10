# -*- coding: utf-8 -*-
from decimal import Decimal
import datetime
import itertools
import unicodedata
import sys

from retrofix import aeat349
from retrofix.record import Record, write as retrofix_write

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from sql.functions import Extract

__all__ = ['Report', 'Operation', 'Ammendment']

PERIOD = [
    ('1T', 'First quarter'),
    ('2T', 'Second quarter'),
    ('3T', 'Third quarter'),
    ('4T', 'Fourth quarter'),
    ('01', 'January'),
    ('02', 'February'),
    ('03', 'March'),
    ('04', 'April'),
    ('05', 'May'),
    ('06', 'June'),
    ('07', 'July'),
    ('08', 'August'),
    ('09', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
    ]

OPERATION_KEY = [
    ('E', 'E - Intra-Community supplies'),
    ('M', 'M - Intra-Community supplies without taxes'),
    ('H', 'H - Intra-Community supplies without taxes delivered by legal '
        'representative'),
    ('A', 'A - Intra-Community acquisition'),
    ('T', 'T - Triangular operations'),
    ('S', 'S - Intra-Community services'),
    ('I', 'I - Intra-Community services acquisitions by legal representative'),
    ('R', 'R - Consignment sales agreements transfer'),
    ('D', 'D - Return of goods sended previously from TAI'),
    ('C', 'C - Substitutions of the employer or professional consignee'),
    ]
AMMENDMENT_KEY = [
    ('A-E', 'E - Ammendments Intra-Community supplies'),
    ('A-M', 'M - Ammendments Intra-Community supplies without taxes'),
    ('A-H', 'H - Ammendments Intra-Community supplies without taxes delivered '
        'by legal representative'),
    ('A-A', 'A - Ammendments Intra-Community acquisition'),
    ('A-T', 'T - Ammendments Triangular operations'),
    ('A-S', 'S - Ammendments Intra-Community services'),
    ('A-I', 'I - Ammendments Intra-Community services acquisitions by legal '
        'representative'),
    ('A-R', 'R - Ammendments Consignment sales agreements transfer'),
    ('A-D', 'D - Ammendments Return of goods sended previously from TAI'),
    ('A-C', 'C - Ammendments Substitutions of the employer or professional '
        'consignee'),
    ]

_ZERO = Decimal('0.0')


def remove_accents(unicode_string):
    str_ = str if sys.version_info < (3, 0) else bytes
    unicode_ = str if sys.version_info < (3, 0) else str
    if isinstance(unicode_string, str_):
        unicode_string_bak = unicode_string
        try:
            unicode_string = unicode_string_bak.decode('iso-8859-1')
        except UnicodeDecodeError:
            try:
                unicode_string = unicode_string_bak.decode('utf-8')
            except UnicodeDecodeError:
                return unicode_string_bak

    if not isinstance(unicode_string, unicode_):
        return unicode_string

    unicode_string_nfd = ''.join(
        (c for c in unicodedata.normalize('NFD', unicode_string)
            if (unicodedata.category(c) != 'Mn')
            ))
    # It converts nfd to nfc to allow unicode.decode()
    return unicodedata.normalize('NFC', unicode_string_nfd)


class Report(Workflow, ModelSQL, ModelView):
    """
    AEAT 349 Report
    """
    __name__ = "aeat.349.report"

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    previous_number = fields.Char('Previous Declaration Number', size=13,
        states={
            'readonly': Eval('state') == 'done',
            'invisible': Eval('type') == 'N',
            'required': Eval('type') != 'N',
            }, depends=['state', 'type'])
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number.', states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    year = fields.Integer("Year", required=True)
    company_vat = fields.Char('VAT number', size=9, states={
            'required': True,
            'readonly': Eval('state') == 'done',
            }, depends=['state', 'company'])
    type = fields.Selection([
            ('N', 'Normal'),
            ('C', 'Complementary'),
            ('S', 'Substitutive')
            ], 'Statement Type', required=True, states={
                'readonly': Eval('state') == 'done',
            }, depends=['state'])
    calculation_date = fields.DateTime("Calculation Date", readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    period = fields.Selection(PERIOD, 'Period', sort=False, required=True)
    contact_name = fields.Char('Full Name', size=40,
        help='The first surname, a space, the second surname, a space and the '
        'name, necessarily in this order.', states={
            'required': True,
            'readonly': Eval('state') == 'confirmed',
            }, depends=['state'])
    contact_phone = fields.Char('Phone', size=9, states={
            'required': True,
            'readonly': Eval('state') == 'confirmed',
            }, depends=['state'])
    operations = fields.One2Many('aeat.349.report.operation', 'report',
        'Operations')
    operation_amount = fields.Function(fields.Numeric(
            'Operation Amount', digits=(16, 2)), 'get_totals')
    ammendments = fields.One2Many('aeat.349.report.ammendment', 'report',
        'Ammendments')
    ammendment_amount = fields.Function(fields.Numeric(
            'Ammendment Amount', digits=(16, 2)), 'get_totals')
    file_ = fields.Binary('File', filename='filename', states={
            'invisible': Eval('state') != 'done',
            })
    filename = fields.Function(fields.Char("File Name"),
        'get_filename')

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls._order = [
            ('year', 'DESC'),
            ('id', 'DESC'),
            ]
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['calculated',
                            'cancelled']),
                    },
                'calculate': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'process': {
                    'invisible': ~Eval('state').in_(['calculated']),
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled']),
                    },
                })
        cls._transitions |= set((
                ('draft', 'calculated'),
                ('draft', 'cancelled'),
                ('calculated', 'draft'),
                ('calculated', 'done'),
                ('calculated', 'cancelled'),
                ('done', 'cancelled'),
                ('cancelled', 'draft'),
                ))

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')

        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        fiscalyear_table = FiscalYear.__table__()

        support_type = table.column_exist('support_type')

        super().__register__(module_name)

        if support_type:
            table.drop_column('support_type')

        # migration fiscalyear to year
        if table.column_exist('fiscalyear'):
            query = sql_table.update(columns=[sql_table.year],
                    values=[Extract('YEAR', fiscalyear_table.start_date)],
                    from_=[fiscalyear_table],
                    where=sql_table.fiscalyear == fiscalyear_table.id)
            cursor.execute(*query)
            table.drop_column('fiscalyear')
        if table.column_exist('fiscalyear_code'):
            table.drop_column('fiscalyear_code')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_type():
        return 'N'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_rec_name(self, name):
        return '%s - %s/%s' % (self.company.rec_name,
            self.year, self.period)

    def get_currency(self, name):
        return self.company.currency.id

    def get_filename(self, name):
        return 'aeat349-%s-%s.txt' % (
            self.year, self.period)

    @fields.depends('company')
    def on_change_with_company_vat(self):
        if self.company:
            tax_identifier = self.company.party.tax_identifier
            if tax_identifier and tax_identifier.code.startswith('ES'):
                return tax_identifier.code[2:]

    def pre_validate(self):
        super().pre_validate()
        self.check_year_digits()

    @fields.depends('year')
    def check_year_digits(self):
        if self.year and len(str(self.year)) != 4:
            raise UserError(
                gettext('aeat_303.msg_invalid_year',
                    year=self.year))

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_names()

    def check_euro(self):
        if self.currency.code != 'EUR':
            raise UserError(gettext('aeat_349.msg_invalid_currency',
                name=self.rec_name,
                ))

    def check_names(self):
        """
        Checks that names are correct (not formed by only one string)
        """
        if self.state != 'done':
            return
        if not self.contact_name or len(self.contact_name.split()) < 2:
            raise UserError(gettext('aeat_349.msg_contact_name',
                name=self.rec_name,
                ))

    @classmethod
    def get_totals(cls, reports, names):
        res = {}
        for name in ('operation_count', 'ammendment_count'):
            res[name] = dict.fromkeys([x.id for x in reports], 0)
        for name in ('operation_amount', 'ammendment_amount'):
            res[name] = dict.fromkeys([x.id for x in reports], _ZERO)
        for report in reports:
            res['operation_count'][report.id] = len(report.operations)
            res['operation_amount'][report.id] = (sum([
                        x.base for x in report.operations]) or Decimal('0.0'))
            res['ammendment_count'][report.id] = len(report.ammendments)
            res['ammendment_amount'][report.id] = (sum([
                        x.base for x in report.ammendments]) or Decimal('0.0'))
        for key in list(res.keys()):
            if key not in names:
                del res[key]
        return res

    @classmethod
    def add_349_register(cls, report, to_create, key, line, ammendment=False,
            operations=None):
        pool = Pool()
        Currency = pool.get('currency.currency')
        InvoiceLine = pool.get('account.invoice.line')

        amount = abs(line.amount) if ammendment else line.amount
        if line.invoice.currency != line.invoice.company.currency:
            with Transaction().set_context(
                    date=line.invoice.currency_date):
                amount = Currency.compute(
                    line.invoice.currency, amount,
                    line.invoice.company.currency)
        party_name = line.invoice.party.name[:40]
        party_vat = (line.invoice.party.tax_identifier.code
            if line.invoice.party.tax_identifier else '')

        operation_key = line.aeat349_operation_key.operation_key[-1:]

        # Control if in the same invoice have 2 keys operation and
        # ammendment equals, so that we need the opeartions.
        next_line = False
        if ammendment and not line.origin and operations and key in operations:
            for oline_id in operations[key]['invoice_lines'][0][1]:
                oline = InvoiceLine(oline_id)
                if oline.invoice == line.invoice:
                    operations[key]['base'] -= amount
                    operations[key]['invoice_lines'][0][1].append(line.id)
                    next_line = True
                    break

        if not next_line:
            if key in to_create:
                to_create[key]['base'] += amount
                to_create[key]['invoice_lines'][0][1].append(
                    line.id)
            else:
                to_create[key] = {
                    'report': report.id,
                    'party_vat': party_vat,
                    'party_name': party_name,
                    'operation_key': operation_key,
                    'base': amount,
                    'invoice_lines': [('add', [line.id])],
                }
                if (ammendment and line.origin
                        and isinstance(line.origin, InvoiceLine)):
                    origin = line.origin.aeat349_operation or None
                    if origin:
                        to_create[key]['ammendment_fiscalyear_code'] = (
                            origin.report.year)
                        to_create[key]['ammendment_period'] = (
                            origin.report.period)
                        to_create[key]['original_base'] = origin.base

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        Operation = pool.get('aeat.349.report.operation')
        Ammendment = pool.get('aeat.349.report.ammendment')

        with Transaction().set_user(0):
            Operation.delete(Operation.search([
                ('report', 'in', [r.id for r in reports])]))
            Ammendment.delete(Ammendment.search([
                ('report', 'in', [r.id for r in reports])]))

        for report in reports:
            year = end_year = report.year
            multiplier = 1
            period = report.period
            if 'T' in period:
                period = int(period[0]) - 1
                multiplier = 3
                start_month = period * multiplier + 1
            else:
                start_month = int(period) * multiplier
            end_month = start_month + multiplier
            if end_month > 12:
                end_month = 1
                end_year = year + 1

            start_date = datetime.datetime(year, start_month, 1).date()
            end_date = datetime.datetime(end_year, end_month, 1).date()

            lines = Line.search([
                    ('aeat349_operation_key', '!=', None),
                    ('invoice.accounting_date', '>=', start_date),
                    ('invoice.accounting_date', '<', end_date),
                    ('invoice.company', '=', report.company)])

            lines.extend(Line.search([
                        ('aeat349_operation_key', '!=', None),
                        ('invoice.accounting_date', '=', None),
                        ('invoice.invoice_date', '>=', start_date),
                        ('invoice.invoice_date', '<', end_date),
                        ('invoice.company', '=', report.company)]))

            operation_to_create = {}
            ammendment_to_create = {}
            for line in lines:
                party_vat = (line.invoice.party.tax_identifier.code
                    if line.invoice.party.tax_identifier else ''),
                operation_key = line.aeat349_operation_key.operation_key[-1:]
                key = '%s-%s-%s' % (report.id, party_vat, operation_key)

                if (line.aeat349_operation_key.operation_key in
                        dict(OPERATION_KEY).keys()):
                    cls.add_349_register(report, operation_to_create, key,
                        line, ammendment=False)
                elif (line.aeat349_operation_key.operation_key in
                        dict(AMMENDMENT_KEY).keys()):
                    # Control if in the same invoice have 2 keys operation and
                    # ammendment equals, so that we need the opeartions.
                    cls.add_349_register(report, ammendment_to_create, key,
                        line, ammendment=True, operations=operation_to_create)

        with Transaction().set_user(0, set_context=True):
            Operation.create(list(operation_to_create.values()))
            Ammendment.create(list(ammendment_to_create.values()))

        cls.write(reports, {
                'calculation_date': datetime.datetime.now(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, reports):
        for report in reports:
            report.create_file()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, reports):
        pass

    def auto_sequence(self):
        pool = Pool()
        Report = pool.get('aeat.349.report')

        count = Report.search([
                ('state', '=', 'done'),
                ],
            order=[
                ('year', 'DESC'),
                ('period', 'DESC'),
            ], count=True)
        return count + 1

    def create_file(self):
        records = []
        record = Record(aeat349.PRESENTER_HEADER_RECORD)
        record.year = str(self.year)
        record.nif = self.company_vat
        record.presenter_name = self.company.party.name
        record.contact_phone = self.contact_phone
        record.contact_name = self.contact_name
        try:
            period = int(self.period)
        except ValueError:
            period = '0%s' % self.period[:1]
        record.declaration_number = int('349{}{}{:0>4}'.format(
            self.year,
            period,
            self.auto_sequence()))
        record.complementary = self.type if self.type == 'C' else ''
        record.replacement = self.type if self.type == 'S' else ''
        record.previous_declaration_number = self.previous_number
        record.period = self.period
        record.operation_count = len(self.operations)
        record.operation_amount = self.operation_amount or _ZERO
        record.ammendment_count = len(self.ammendments)
        record.ammendment_amount = self.ammendment_amount or _ZERO
        record.representative_nif = self.representative_vat
        records.append(record)
        for line in itertools.chain(self.operations, self.ammendments):
            record = line.get_record()
            record.year = str(self.year)
            record.nif = self.company_vat
            records.append(record)
        try:
            data = retrofix_write(records)
        except AssertionError as e:
            raise UserError(str(e))
        data = remove_accents(data).upper()
        if isinstance(data, str):
            data = data.encode('iso-8859-1')
        self.file_ = self.__class__.file_.cast(data)
        self.save()


class Operation(ModelSQL, ModelView):
    """
    AEAT 349 Operation
    """
    __name__ = 'aeat.349.report.operation'
    _rec_name = 'party_name'

    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')
    report = fields.Many2One('aeat.349.report', 'AEAT 349 Report',
        required=True)
    party_vat = fields.Char('VAT', size=17)
    party_name = fields.Char('Party Name', size=40)
    operation_key = fields.Selection(OPERATION_KEY + AMMENDMENT_KEY,
        'Operation key', required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))
    invoice_lines = fields.One2Many('account.invoice.line',
        'aeat349_operation', 'Invoice Lines', readonly=True)
    substitution_nif = fields.Char('Substitution VAT', size=17,
        states={
            'invisible': ~(Eval('operation_key') == 'C'),
            'required': Eval('operation_key') == 'C',
            })
    substitution_name = fields.Char('Substitution Name', size=40,
        states={
            'invisible': ~(Eval('operation_key') == 'C'),
            'required': Eval('operation_key') == 'C',
            })

    @fields.depends('report', '_parent_report.company')
    def on_change_with_company(self, name=None):
        return self.report and self.report.company and self.report.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('report.%s' % name,) + tuple(clause[1:])]

    def get_record(self):
        record = Record(aeat349.OPERATOR_RECORD)
        record.party_vat = self.party_vat
        record.party_name = self.party_name
        record.operation_key = self.operation_key
        record.base = self.base or _ZERO
        record.substitution_nif = self.substitution_nif
        record.substitution_name = self.substitution_name
        return record


class Ammendment(ModelSQL, ModelView):
    """
    AEAT 349 Ammendment
    """
    __name__ = 'aeat.349.report.ammendment'

    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company', searcher='search_company')
    report = fields.Many2One('aeat.349.report', 'AEAT 349 Report',
        required=True)
    party_vat = fields.Char('VAT', size=17)
    party_name = fields.Char('Party Name', size=40)
    operation_key = fields.Selection(OPERATION_KEY + AMMENDMENT_KEY,
        'Operation key', required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))
    invoice_lines = fields.One2Many('account.invoice.line',
        'aeat349_ammendment', 'Invoice Lines', readonly=True)
    ammendment_fiscalyear_code = fields.Integer('Ammendment Fiscal Year Code')
    ammendment_period = fields.Selection([(None, '')] + PERIOD,
        'Ammendment Period', sort=False,
        states={
            'invisible': ~Bool(Eval('ammendment_fiscalyear_code')),
            'required': Bool(Eval('ammendment_fiscalyear_code')),
            })
    original_base = fields.Numeric('Original Base', digits=(16, 2))
    substitution_nif = fields.Char('Substitution VAT', size=17,
        states={
            'invisible': ~(Eval('operation_key') == 'C'),
            'required': Eval('operation_key') == 'C',
            })
    substitution_name = fields.Char('Substitution Name', size=40,
        states={
            'invisible': ~(Eval('operation_key') == 'C'),
            'required': Eval('operation_key') == 'C',
            })

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        if table.column_exist('company'):
            table.drop_column('company')

        super().__register__(module_name)

    @fields.depends('report', '_parent_report.company')
    def on_change_with_company(self, name=None):
        return self.report and self.report.company and self.report.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('report.%s' % name,) + tuple(clause[1:])]

    def get_record(self):
        if not self.ammendment_fiscalyear_code or not self.ammendment_period:
            raise UserError(
                gettext('aeat_349.msg_missing_ammendment_information',
                    party=self.party_name,
                    ))
        record = Record(aeat349.AMMENDMENT_RECORD)
        record.party_vat = self.party_vat
        record.party_name = self.party_name
        record.operation_key = self.operation_key
        record.base = self.base
        record.ammendment_fiscalyear = str(self.ammendment_fiscalyear_code)
        record.ammendment_period = self.ammendment_period
        record.original_base = (self.original_base if self.original_base else
            Decimal(0))
        record.substitution_nif = self.substitution_nif
        record.substitution_name = self.substitution_name
        return record
