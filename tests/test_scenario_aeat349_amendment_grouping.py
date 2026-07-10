import datetime
import unittest
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from proteus import Model, Wizard
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

        previous_date = datetime.date.today() + relativedelta(day=15)
        current_date = previous_date + relativedelta(months=1)
        year = previous_date.year

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
        party = Party(name='Party')
        party.identifiers.new(type='eu_vat', code='ES00000000T')
        party.save()

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
        original_invoice = Invoice(type='out')
        original_invoice.party = party
        original_invoice.payment_term = payment_term
        original_invoice.invoice_date = previous_date
        line = original_invoice.lines.new()
        line.product = product
        line.unit_price = Decimal('40')
        line.quantity = 5
        original_invoice.click('post')
        original_line, = [l for l in original_invoice.lines if l.product]

        Report = Model.get('aeat.349.report')
        previous_report = Report()
        previous_report.year = previous_date.year
        previous_report.period = '%02d' % previous_date.month
        previous_report.company_vat = '123456789'
        previous_report.contact_name = 'Guido van Rosum'
        previous_report.contact_phone = '987654321'
        previous_report.representative_vat = '22334455'
        previous_report.click('calculate')
        self.assertEqual(len(previous_report.operations), 1)
        original_operation, = previous_report.operations
        self.assertEqual(original_operation.base, Decimal('200.00'))

        for quantity in (Decimal('1'), Decimal('2')):
            credit = Wizard('account.invoice.credit', [original_invoice])
            credit.form.with_refund = False
            credit.form.invoice_date = current_date
            credit.execute('credit')
            credit_invoice, = Invoice.find([
                    ('lines.origin', '=', original_line),
                    ('invoice_date', '=', current_date),
                    ('state', '=', 'draft'),
                    ], order=[('id', 'DESC')], limit=1)
            credit_line, = [l for l in credit_invoice.lines if l.product]
            credit_line.quantity = -quantity
            credit_invoice.click('post')

        report = Report()
        report.year = current_date.year
        report.period = '%02d' % current_date.month
        report.company_vat = '123456789'
        report.contact_name = 'Guido van Rosum'
        report.contact_phone = '987654321'
        report.representative_vat = '22334455'
        report.click('calculate')

        self.assertEqual(len(report.operations), 0)
        self.assertEqual(len(report.ammendments), 1)
        ammendment, = report.ammendments
        self.assertEqual(ammendment.base, Decimal('120.00'))
        self.assertEqual(ammendment.original_base, Decimal('400.00'))
        self.assertEqual(ammendment.ammendment_fiscalyear_code,
            previous_date.year)
        self.assertEqual(ammendment.ammendment_period,
            '%02d' % previous_date.month)
        self.assertEqual(len(ammendment.origins), 2)
