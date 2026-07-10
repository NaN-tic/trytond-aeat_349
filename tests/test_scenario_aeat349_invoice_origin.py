import datetime
import unittest
from decimal import Decimal
from proteus import Model
from trytond.modules.account.tests.tools import create_fiscalyear, create_tax_code
from trytond.modules.account_es.tests.tools import create_chart, create_tax, get_accounts
from trytond.modules.account_invoice.tests.tools import create_payment_term, set_fiscalyear_invoice_sequences
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        config = activate_modules(['aeat_349', 'account_es',
                'account_code_digits'])
        config.skip_warning = True

        year = datetime.date.today().year
        previous_date = datetime.date(year, 1, 15)
        current_date = datetime.date(year, 2, 15)

        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company, today=(datetime.date(year, 1, 1),
                datetime.date(year, 12, 31))))
        fiscalyear.click('create_period')

        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']

        A349Type = Model.get('aeat.349.type')
        operation_key_e, = A349Type.find([('operation_key', '=', 'E')])
        ammendment_key_e, = A349Type.find([('operation_key', '=', 'A-E')])

        tax = create_tax(Decimal('.10'))
        tax.aeat349_operation_keys.append(operation_key_e)
        tax.aeat349_operation_keys.append(ammendment_key_e)
        tax.aeat349_default_out_operation_key = operation_key_e
        tax.aeat349_default_out_ammendment_key = ammendment_key_e
        tax.save()
        create_tax_code(tax, 'base', 'invoice').save()
        create_tax_code(tax, 'tax', 'invoice').save()
        create_tax_code(tax, 'base', 'credit').save()
        create_tax_code(tax, 'tax', 'credit').save()

        Party = Model.get('party.party')
        same_period_party = Party(name='Same Period Party')
        same_period_party.identifiers.new(type='eu_vat', code='ES00000000T')
        same_period_party.save()
        previous_period_party = Party(name='Previous Period Party')
        previous_period_party.identifiers.new(type='eu_vat', code='ES00000001R')
        previous_period_party.save()

        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Account Category')
        account_category.accounting = True
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        template.save()
        product, = template.products

        payment_term = create_payment_term()
        payment_term.save()

        Invoice = Model.get('account.invoice')
        original_previous_period = Invoice()
        original_previous_period.party = previous_period_party
        original_previous_period.payment_term = payment_term
        original_previous_period.invoice_date = previous_date
        for _ in range(5):
            line = original_previous_period.lines.new()
            line.product = product
            line.quantity = 1
            line.unit_price = Decimal('40')
        original_previous_period.click('post')

        original_same_period = Invoice()
        original_same_period.party = same_period_party
        original_same_period.payment_term = payment_term
        original_same_period.invoice_date = current_date
        line = original_same_period.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('40')
        line = original_same_period.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('45')
        original_same_period.click('post')

        same_period_credit = Invoice()
        same_period_credit.party = same_period_party
        same_period_credit.payment_term = payment_term
        same_period_credit.invoice_date = current_date
        line = same_period_credit.lines.new()
        line.product = product
        line.quantity = -1
        line.unit_price = Decimal('40')
        line.origin = original_same_period
        same_period_credit.click('post')

        Report = Model.get('aeat.349.report')
        previous_report = Report()
        previous_report.year = previous_date.year
        previous_report.period = '%02d' % previous_date.month
        previous_report.company_vat = '123456789'
        previous_report.contact_name = 'Guido van Rosum'
        previous_report.contact_phone = '987654321'
        previous_report.representative_vat = '22334455'
        previous_report.click('calculate')

        previous_period_credit = Invoice()
        previous_period_credit.party = previous_period_party
        previous_period_credit.payment_term = payment_term
        previous_period_credit.invoice_date = current_date
        line = previous_period_credit.lines.new()
        line.product = product
        line.quantity = -1
        line.unit_price = Decimal('40')
        line.origin = original_previous_period
        previous_period_credit.click('post')

        report = Report()
        report.year = current_date.year
        report.period = '%02d' % current_date.month
        report.company_vat = '123456789'
        report.contact_name = 'Guido van Rosum'
        report.contact_phone = '987654321'
        report.representative_vat = '22334455'
        report.click('calculate')

        self.assertEqual(len(report.operations), 1)
        operation, = report.operations
        self.assertEqual(operation.party_vat, 'ES00000000T')
        self.assertEqual(operation.base, Decimal('45.00'))
        self.assertEqual(len(operation.origins), 3)

        self.assertEqual(len(report.ammendments), 1)
        ammendment, = report.ammendments
        self.assertEqual(ammendment.party_vat, 'ES00000001R')
        self.assertEqual(ammendment.base, Decimal('40.00'))
        self.assertEqual(ammendment.original_base, Decimal('200.00'))
        self.assertEqual(ammendment.ammendment_fiscalyear_code,
            previous_date.year)
        self.assertEqual(ammendment.ammendment_period,
            '%02d' % previous_date.month)
