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
from trytond.model.exceptions import ValidationError
from trytond.transaction import Transaction
from sql.functions import Extract

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

_ZERO = Decimal(0)


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
            })
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    previous_number = fields.Char('Previous Declaration Number', size=13,
        states={
            'readonly': Eval('state') == 'done',
            'invisible': Eval('type') == 'N',
            'required': Eval('type') != 'N',
            })
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number.', states={
            'readonly': Eval('state') == 'done',
            })
    year = fields.Integer("Year", required=True)
    company_vat = fields.Char('VAT number', size=9, states={
            'required': True,
            'readonly': Eval('state') == 'done',
            })
    type = fields.Selection([
            ('N', 'Normal'),
            ('C', 'Complementary'),
            ('S', 'Substitutive')
            ], 'Statement Type', required=True, states={
                'readonly': Eval('state') == 'done',
            })
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
            })
    contact_phone = fields.Char('Phone', size=9, states={
            'required': True,
            'readonly': Eval('state') == 'confirmed',
            })
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
            if tax_identifier and tax_identifier.es_country() == 'ES':
                return tax_identifier.es_code()

    def pre_validate(self):
        super().pre_validate()
        self.check_year_digits()

    @fields.depends('year')
    def check_year_digits(self):
        if self.year and len(str(self.year)) != 4:
            raise ValidationError(
                gettext('aeat_349.msg_invalid_year',
                    year=self.year))

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()
            report.check_names()

    def check_euro(self):
        if self.currency.code != 'EUR':
            raise ValidationError(gettext('aeat_349.msg_invalid_currency',
                name=self.rec_name,
                ))

    def check_names(self):
        """
        Checks that names are correct (not formed by only one string)
        """
        if self.state != 'done':
            return
        if not self.contact_name or len(self.contact_name.split()) < 2:
            raise ValidationError(gettext('aeat_349.msg_contact_name',
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
                        x.base or Decimal(0) for x in report.operations]) or Decimal(0))
            res['ammendment_count'][report.id] = len(report.ammendments)
            res['ammendment_amount'][report.id] = (sum([
                        x.base or Decimal(0) for x in report.ammendments]) or Decimal(0))
        for key in list(res.keys()):
            if key not in names:
                del res[key]
        return res

    @staticmethod
    def _get_pool_model(name):
        try:
            return Pool().get(name)
        except KeyError:
            return None

    @staticmethod
    def _line_lot_key(line):
        moves = getattr(line, 'stock_moves', ()) or ()
        lots = sorted({move.lot.id for move in moves
                if getattr(move, 'lot', None)})
        return tuple(lots)

    @classmethod
    def _quantities_match(cls, line, origin_line):
        Uom = cls._get_pool_model('product.uom')
        quantity = abs(line.quantity or 0)
        origin_quantity = abs(origin_line.quantity or 0)
        if (Uom and getattr(line, 'unit', None)
                and getattr(origin_line, 'unit', None)
                and line.unit != origin_line.unit):
            origin_quantity = Uom.compute_qty(
                origin_line.unit, origin_quantity, line.unit, round=False)
        return abs(origin_quantity - quantity) < 1e-10

    @classmethod
    def _match_origin_invoice_line(cls, report, line, candidates,
            used_origin_lines):
        report_key = report.id
        used_for_report = used_origin_lines.setdefault(report_key, set())

        lot_key = cls._line_lot_key(line)
        exact_matches = []
        for candidate in candidates:
            if candidate.id in used_for_report:
                continue
            if candidate.product != line.product:
                continue
            if not cls._quantities_match(line, candidate):
                continue
            candidate_lot_key = cls._line_lot_key(candidate)
            if (lot_key or candidate_lot_key) and candidate_lot_key != lot_key:
                continue
            exact_matches.append(candidate)

        if not exact_matches:
            return None

        unit_price_matches = [c for c in exact_matches
            if c.unit_price == line.unit_price]
        matched = (unit_price_matches or exact_matches)[0]
        used_for_report.add(matched.id)
        return matched

    @classmethod
    def _get_indirect_origin_invoice_line(cls, report, line,
            used_origin_lines):
        Sale = cls._get_pool_model('sale.sale')
        SaleLine = cls._get_pool_model('sale.line')
        Purchase = cls._get_pool_model('purchase.purchase')
        PurchaseLine = cls._get_pool_model('purchase.line')

        origin = line.origin
        is_sale_origin = bool(SaleLine and Sale and isinstance(origin, SaleLine))
        is_purchase_origin = bool(PurchaseLine and Purchase
            and isinstance(origin, PurchaseLine))
        if is_sale_origin:
            order = origin.sale
        elif is_purchase_origin:
            order = origin.purchase
        else:
            return None

        original_order = getattr(order, 'origin', None)
        if not original_order:
            return None
        if is_sale_origin and (not Sale or not isinstance(original_order, Sale)):
            return None
        if (is_purchase_origin
                and (not Purchase or not isinstance(original_order, Purchase))):
            return None

        candidates = []
        for order_line in original_order.lines:
            if order_line.type != 'line':
                continue
            if order_line.product != line.product:
                continue
            for invoice_line in order_line.invoice_lines:
                if (invoice_line.type != 'line'
                        or not getattr(invoice_line, 'invoice', None)):
                    continue
                candidates.append(invoice_line)
        return cls._match_origin_invoice_line(
            report, line, candidates, used_origin_lines)

    @classmethod
    def _get_invoice_origin_invoice_line(cls, report, line,
            used_origin_lines):
        origin = line.origin
        for invoice_line in origin.lines:
            if invoice_line.type != 'line':
                continue
            if invoice_line.aeat349_operation:
                return invoice_line
        return None

    @classmethod
    def get_origin_invoice_line(cls, report, line, used_origin_lines):
        Invoice = Pool().get('account.invoice')
        InvoiceLine = Pool().get('account.invoice.line')
        if isinstance(line.origin, InvoiceLine):
            return line.origin
        if isinstance(line.origin, Invoice):
            return cls._get_invoice_origin_invoice_line(
                report, line, used_origin_lines)
        return cls._get_indirect_origin_invoice_line(
            report, line, used_origin_lines)

    @classmethod
    def add_349_register(cls, report, to_create, key, line, ammendment=False,
            operations=None, used_origin_lines=None):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Origin = pool.get('aeat.349.report.origin')

        aeat349_origin = Origin()
        aeat349_origin.resource = line
        aeat349_origin.save()

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

        operation_key = line.aeat349_operation_key.operation_key
        origin_invoice_line = cls.get_origin_invoice_line(
            report, line, used_origin_lines or {})
        origin_operation = None
        if ammendment and origin_invoice_line:
            origin_operation = origin_invoice_line.aeat349_operation or None

        # Control if in the same invoice have 2 keys: operation and ammendment,
        # or have credit note invoices where the date is in the same period as
        # the original invoice, so they have to be all operations, not
        # ammendment.
        next_line = False
        operation_key_match = '%s-%s-%s' % (
            report.id, party_vat, operation_key[2:])
        if ammendment and operations and operation_key_match in operations:
            key = operation_key_match
            start_date, end_date = cls.get_period_dates(report)
            if (not origin_invoice_line
                    or (origin_invoice_line.invoice
                        and start_date <= origin_invoice_line.invoice.invoice_date\
                        <= end_date)):
                origin_aux = Origin()
                origin_aux.resource = line
                origin_aux.save()
                operations[key]['base'] -= amount
                operations[key]['origins'][0][1].append(origin_aux.id)
                next_line = True

        if not next_line:
            if key in to_create:
                to_create[key]['base'] += amount
                to_create[key]['origins'][0][1].append(
                    aeat349_origin.id)
                if origin_operation:
                    to_create[key]['original_base'] += origin_operation.base
            else:
                to_create[key] = {
                    'report': report.id,
                    'party_vat': party_vat,
                    'party_name': party_name,
                    'operation_key': operation_key,
                    'base': amount,
                    'origins': [('add', [aeat349_origin.id])],
                }
                if origin_operation:
                    ammendment_year = origin_operation.report.year
                    ammendment_period = origin_operation.report.period
                    year = report.year
                    period = report.period
                    if (ammendment_year != year or
                            (ammendment_year == year
                                and ammendment_period != period)):
                        to_create[key]['ammendment_fiscalyear_code'] = (
                            ammendment_year)
                        to_create[key]['ammendment_period'] = (
                            ammendment_period)
                    to_create[key]['original_base'] = origin_operation.base

    def calculate_operations_ammendments(self, start_date, end_date,
            operation_to_create, ammendment_to_create, used_origin_lines):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        Report = pool.get('aeat.349.report')

        # Dividing the search is more efficiency than use a single search
        # with an 'or' in the domain.
        lines = Line.search([
                ('invoice.company', '=', self.company),
                ('invoice.state', 'in', {'posted', 'paid'}),
                ('aeat349_operation_key', '!=', None),
                ('invoice.accounting_date', '>=', start_date),
                ('invoice.accounting_date', '<', end_date)])

        lines.extend(Line.search([
                    ('invoice.company', '=', self.company),
                    ('invoice.state', 'in', {'posted', 'paid'}),
                    ('aeat349_operation_key', '!=', None),
                    ('invoice.accounting_date', '=', None),
                    ('invoice.invoice_date', '>=', start_date),
                    ('invoice.invoice_date', '<', end_date)]))

        for line in sorted(lines, key=lambda line: line.amount, reverse=True):
            party_vat = (line.invoice.party.tax_identifier.code
                if line.invoice.party.tax_identifier else '')
            operation_key = line.aeat349_operation_key.operation_key
            key = '%s-%s-%s' % (self.id, party_vat, operation_key)

            if (line.aeat349_operation_key.operation_key in
                    dict(OPERATION_KEY).keys()):
                Report.add_349_register(self, operation_to_create, key,
                    line, ammendment=False,
                    used_origin_lines=used_origin_lines)
            elif (line.aeat349_operation_key.operation_key in
                    dict(AMMENDMENT_KEY).keys()):
                # Control if in the same invoice have 2 keys operation and
                # ammendment equals, so that we need the opeartions.
                Report.add_349_register(self, ammendment_to_create, key,
                    line, ammendment=True, operations=operation_to_create,
                    used_origin_lines=used_origin_lines)
    @classmethod
    def get_period_dates(cls, report):
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

        return start_date, end_date

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Operation = pool.get('aeat.349.report.operation')
        Ammendment = pool.get('aeat.349.report.ammendment')

        with Transaction().set_user(0):
            Operation.delete(Operation.search([
                ('report', 'in', [r.id for r in reports])]))
            Ammendment.delete(Ammendment.search([
                ('report', 'in', [r.id for r in reports])]))

        operation_to_create = {}
        ammendment_to_create = {}
        used_origin_lines = {}
        for report in reports:
            start_date, end_date = cls.get_period_dates(report)

            report.calculate_operations_ammendments(start_date, end_date,
                operation_to_create, ammendment_to_create,
                used_origin_lines)

        operation_to_create = {
            key: values for key, values in operation_to_create.items()
            if values['base'] != _ZERO}
        ammendment_to_create = {
            key: values for key, values in ammendment_to_create.items()
            if values['base'] != _ZERO}

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
            period = '%02d' % period
        except ValueError:
            period = '0%s' % self.period[0]
        # It must be a number of 13 digits, and the first three must be '349'.
        # So need to ensure to have 13 digits, beacsue in retrofix if not
        # arrive 13 digits if ill with 0 from left and the number became
        # differnt as expected by AEAT.
        # DIGITS:
        #    349 (3)
        #    year (4)
        #    period (2)
        #    sequence (4)
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
            data = data.encode('iso-8859-1', errors='ignore')
        self.file_ = self.__class__.file_.cast(data)
        self.save()


class ReportOrigin(ModelSQL, ModelView):
    """
    AEAT 349 Operation/Ammendment Origin
    """
    __name__ = 'aeat.349.report.origin'

    operation = fields.Many2One('aeat.349.report.operation',
        '349 Operation', readonly=True, ondelete='CASCADE')
    ammendment = fields.Many2One('aeat.349.report.ammendment',
        '349 Ammendment', readonly=True, ondelete='CASCADE')
    resource = fields.Reference('Resource', selection='get_resource',
        readonly=True)

    @classmethod
    def get_resource(cls):
        'Return list of Model names for resource Reference'
        return [(None, ''), ('account.invoice.line', 'Invoice Line')]


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
    origins = fields.One2Many('aeat.349.report.origin', 'operation',
        'Origins', readonly=True)
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
    origins = fields.One2Many('aeat.349.report.origin', 'ammendment',
        'Origins', readonly=True)
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
        record = Record(aeat349.AMMENDMENT_RECORD)
        record.party_vat = self.party_vat
        record.party_name = self.party_name
        record.operation_key = self.operation_key[-1:]
        record.base = self.base
        record.ammendment_fiscalyear = (str(self.ammendment_fiscalyear_code)
            if self.ammendment_fiscalyear_code else '')
        record.ammendment_period = self.ammendment_period or ''
        record.original_base = (self.original_base if self.original_base else
            Decimal(0))
        record.substitution_nif = self.substitution_nif
        record.substitution_name = self.substitution_name
        return record
