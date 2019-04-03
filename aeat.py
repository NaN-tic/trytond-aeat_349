# -*- coding: utf-8 -*-
import datetime
import itertools
from decimal import Decimal
import unicodedata
import sys

from retrofix import aeat349
from retrofix.record import Record, write as retrofix_write

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction

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
    ('A', 'A - Intra-Community acquisition'),
    ('T', 'T - Triangular operations'),
    ('S', 'S - Intra-Community services'),
    ('I', 'I - Intra-Community services acquisitions'),
    ('M', 'M - Intra-Community supplies without taxes'),
    ('H', 'H - Intra-Community supplies without taxes delivered '
        'by legal representative'),
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
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear_code = fields.Integer('Fiscal Year Code', required=True,
        depends=['fiscalyear'])
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
    support_type = fields.Selection([
            ('C', 'DVD'),
            ('T', 'Telematics'),
            ], 'Support Type', required=True, states={
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
        help='Must have name and surname.', states={
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

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_support_type():
        return 'T'

    @staticmethod
    def default_type():
        return 'N'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    def get_rec_name(self, name):
        return '%s - %s/%s' % (self.company.rec_name,
            self.fiscalyear.name, self.period)

    def get_currency(self, name):
        return self.company.currency.id

    def get_filename(self, name):
        return 'aeat349-%s-%s.txt' % (
            self.fiscalyear_code, self.period)

    @fields.depends('fiscalyear')
    def on_change_with_fiscalyear_code(self):
        code = None
        if self.fiscalyear:
            code = self.fiscalyear.start_date.year
        return code

    @fields.depends('company')
    def on_change_with_company_vat(self):
        if self.company:
            tax_identifier = self.company.party.tax_identifier
            if tax_identifier and tax_identifier.code.startswith('ES'):
                return tax_identifier.code[2:]

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_names()

    def check_euro(self):
        if self.currency.code != 'EUR':
            raise UserError(gettext('aeat_349.msg_invalid_currency',
                name=self.path,
                ))

    def check_names(self):
        """
        Checks that names are correct (not formed by only one string)
        """
        if self.state != 'done':
            return
        if not self.contact_name or len(self.contact_name.split()) < 2:
            raise UserError(gettext('aeat_349.msg_contact_name',
                name=self.path,
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
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Data = pool.get('aeat.349.record')
        Operation = pool.get('aeat.349.report.operation')

        with Transaction().set_user(0):
            Operation.delete(Operation.search([
                ('report', 'in', [r.id for r in reports])]))

        for report in reports:
            fiscalyear = report.fiscalyear
            multiplier = 1
            period = report.period
            if 'T' in period:
                period = int(period[0]) - 1
                multiplier = 3
                start_month = period * multiplier + 1
            else:
                start_month = int(period) * multiplier

            end_month = start_month + multiplier

            to_create = {}
            for record in Data.search([
                    ('fiscalyear', '=', fiscalyear.id),
                    ('month', '>=', start_month),
                    ('month', '<', end_month)
                    ]):
                key = '%s-%s-%s' % (report.id, record.party_vat,
                    record.operation_key)

                if key in to_create:
                    to_create[key]['base'] += record.base
                    to_create[key]['records'][0][1].append(record.id)
                else:
                    to_create[key] = {
                        'base': record.base,
                        'party_vat': record.party_vat,
                        'party_name': record.party_name,
                        'operation_key': record.operation_key,
                        'report': report.id,
                        'records': [('add', [record.id])],
                    }
        with Transaction().set_user(0, set_context=True):
            Operation.create(list(to_create.values()))

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
                ('fiscalyear', 'DESC'),
                ('period', 'DESC'),
            ], count=True)
        return count + 1

    def create_file(self):
        records = []
        record = Record(aeat349.PRESENTER_HEADER_RECORD)
        record.fiscalyear = str(self.fiscalyear_code)
        record.nif = self.company_vat
        record.presenter_name = self.company.party.name
        record.support_type = self.support_type
        record.contact_phone = self.contact_phone
        record.contact_name = self.contact_name
        try:
            period = int(self.period)
        except ValueError:
            period = '0%s' % self.period[:1]
        record.declaration_number = int('349{}{}{:0>4}'.format(
            self.fiscalyear_code,
            period,
            self.auto_sequence()))
        record.complementary = '' if self.type == 'N' else self.type
        record.replacement = self.previous_number
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
            record.fiscalyear = str(self.fiscalyear_code)
            record.nif = self.company_vat
            records.append(record)
        data = retrofix_write(records)
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
    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))
    records = fields.One2Many('aeat.349.record', 'operation',
        'AEAT 349 Records', readonly=True)

    @fields.depends('report')
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
        return record


class Ammendment(ModelSQL, ModelView):
    """
    AEAT 349 Ammendment
    """
    __name__ = 'aeat.349.report.ammendment'

    company = fields.Many2One('company.company', 'Company', required=True)
    report = fields.Many2One('aeat.349.report', 'AEAT 349 Report')
    party_vat = fields.Char('VAT', size=17)
    party_name = fields.Char('Party Name', size=40)
    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)
    ammendment_fiscalyear_code = fields.Integer('Ammendment Fiscal Year Code')
    ammendment_period = fields.Selection(PERIOD, 'Period', sort=False,
            required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))
    original_base = fields.Numeric('Original Base', digits=(16, 2))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_record(self):
        record = Record(aeat349.AMMENDMENT_RECORD)
        record.party_vat = self.party_vat
        record.party_name = self.party_name
        record.operation_key = self.operation_key
        record.ammendment_fiscalyear = str(self.ammendment_fiscalyear_code)
        record.ammendment_period = self.ammendment_period
        record.base = self.base
        record.original_base = self.original_base
        return record
