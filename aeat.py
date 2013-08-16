import datetime
import itertools
from decimal import Decimal
from retrofix import aeat349
import retrofix

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval

__all__ = ['Report', 'Operation', 'Ammendment']

PERIOD = [
    ('1T','First quarter'),
    ('2T','Second quarter'),
    ('3T','Third quarter'),
    ('4T','Fourth quarter'),
    ('01','January'),
    ('02','February'),
    ('03','March'),
    ('04','April'),
    ('05','May'),
    ('06','June'),
    ('07','July'),
    ('08','August'),
    ('09','September'),
    ('10','October'),
    ('11','November'),
    ('12','December'),
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
            }, depends=['state'])
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number.', states={
            'required': Eval('state') == 'calculated',
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear_code = fields.Integer('Fiscal Year Code',
        on_change_with=['fiscalyear'], required=True)
    company_vat = fields.Char('VAT number', size=9, states={
            'required': Eval('state') == 'calculated',
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    type = fields.Selection([
            ('N','Normal'),
            ('C','Complementary'),
            ('S','Substitutive')
            ], 'Statement Type', required=True, states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    support_type = fields.Selection([
            ('C','DVD'),
            ('T','Telematics'),
            ], 'Support Type', required=True, states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    calculation_date = fields.DateTime("Calculation Date")
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    period = fields.Selection(PERIOD, 'Period', sort=False, required=True)
    contact_name = fields.Char('Full Name', size=40,
        help='Must have name and surname.', states={
            'required': Eval('state') == 'calculated',
            'readonly': Eval('state') == 'confirmed',
            }, depends=['state'])
    contact_phone = fields.Char('Phone', size=9, states={
            'required': Eval('state') == 'calculated',
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
    file_ = fields.Binary('File', states={
            'invisible': Eval('state') != 'done',
            })

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls._error_messages.update({
                'contact_name': ('Contact name in report "%s" must contain '
                    'name and surname'),
                'missing_country_vat': ('Missing country or VAT information '
                    'in Invoice Record "%(record)s" in report "%(report)s".'),
                'negative_amounts': ('Negative amounts are not valid in Party '
                    'Record "%(record)s" in report "%(report)s"'),
                'invalid_currency': ('Currency in AEAT 340 report "%s" must be '
                    'Euro.')
                })
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

    def get_rec_name(self, name):
        return '%s - %s/%s' % (self.company.rec_name,
            self.fiscalyear.name, self.period)

    def get_currency(self, name):
        return self.company.currency.id

    def on_change_with_fiscalyear_code(self):
        code = self.fiscalyear.code if self.fiscalyear else None
        if code:
            try:
                code = int(code)
            except ValueError:
                code = None
        return code

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_names()

    def check_euro(self):
        if self.currency.code != 'EUR':
            self.raise_user_error('invalid_currency', self.rec_name)

    def check_names(self):
        """
        Checks that names are correct (not formed by only one string)
        """
        if self.state != 'done':
            return
        if not self.contact_name or len(self.contact_name.split()) < 2:
            self.raise_user_error('contact_name', self.rec_name)

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
        for key in res.keys():
            if key not in names:
                del res[key]
        return res

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
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

    def create_file(self):
        records = []
        record = retrofix.Record(aeat349.PRESENTER_HEADER_RECORD)
        record.fiscalyear = str(self.fiscalyear_code)
        record.nif = self.company_vat
        #record.presenter_name = 
        record.support_type = self.support_type
        record.contact_phone = self.contact_phone
        record.contact_name = self.contact_name
        #record.declaration_number = 
        #record.complementary = 
        #record.replacement = 
        record.previous_declaration_number = self.previous_number
        record.period = self.period
        record.operation_count = len(self.operations)
        record.operation_amount = self.operation_amount
        record.ammendment_count = len(self.ammendments)
        record.ammendment_amount = self.ammendment_amount
        #record.representative_nif = 
        records.append(record)
        for line in itertools.chain(self.operations, self.ammendments):
            record = line.get_record()
            record.fiscalyear = str(self.fiscalyear_code)
            record.nif = self.company_vat
            records.append(record)
        data = retrofix.record.write(records)
        data = data.encode('iso-8859-1')
        self.file_ = buffer(data)
        self.save()


class Operation(ModelSQL, ModelView):
    """
    AEAT 349 Operation
    """
    __name__ = 'aeat.349.report.operation'
    _rec_name = 'party_name'

    report = fields.Many2One('aeat.349.report', 'AEAT 349 Report')
    party_vat = fields.Char('VAT', size=17)
    party_name = fields.Char('Party Name', size=40)
    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))

    def get_record(self):
        record = retrofix.Record(aeat349.OPERATOR_RECORD)
        record.party_vat = self.party_vat
        record.party_name = self.party_name
        record.operation_key = self.operation_key
        record.base = self.base
        return record


class Ammendment(ModelSQL, ModelView):
    """
    AEAT 349 Ammendment
    """
    __name__ = 'aeat.349.report.ammendment'

    report = fields.Many2One('aeat.349.report', 'AEAT 349 Report')
    party_vat = fields.Char('VAT', size=17, on_change_with=[
            'party_vat', 'country'])
    party_name = fields.Char('Party Name', size=40)
    operation_key = fields.Selection(OPERATION_KEY, 'Operation key',
        required=True)
    ammendment_fiscalyear_code = fields.Integer('Ammendment Fiscal Year Code')
    ammendment_period = fields.Selection(PERIOD, 'Period', sort=False,
            required=True)
    base = fields.Numeric('Base Operation Amount', digits=(16, 2))
    original_base = fields.Numeric('Original Base', digits=(16, 2))

    def get_record(self):
        record = retrofix.Record(aeat349.AMMENDMENT_RECORD)
        record.party_vat = self.country.code.upper()
        record.party_name = self.party_name
        record.operation_key = self.operation_key
        record.ammendment_fiscalyear = self.ammendment_fiscalyear_code
        record.ammendment_period = self.ammendment_period
        record.base = self.base
        record.original_base = self.original_base
        return record
