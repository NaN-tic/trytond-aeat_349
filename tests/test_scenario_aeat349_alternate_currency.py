import datetime
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account_es.tests.tools import (create_chart, create_tax,
    get_accounts)
from trytond.modules.account.tests.tools import (create_fiscalyear,
    create_tax_code)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
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

        # Imports
        today = datetime.date.today()

        # Install aeat_349 module
        activate_modules(['aeat_349', 'account_es',
                'account_code_digits'])

        # Create company
        usd = get_currency('USD')
        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create AEAT 349
        A349Type = Model.get('aeat.349.type')
        operation_key_e, = A349Type.find([('operation_key', '=', 'E')])
        operation_key_a, = A349Type.find([('operation_key', '=', 'A')])

        # Create tax
        Tax = Model.get('account.tax')
        tax = create_tax(Decimal('.10'))
        tax.aeat349_operation_keys.append(operation_key_e)
        tax.aeat349_operation_keys.append(operation_key_a)
        tax.aeat349_default_out_operation_key = operation_key_e
        tax.aeat349_default_in_operation_key = operation_key_a
        tax.save()
        invoice_base_code = create_tax_code(tax, 'base', 'invoice')
        invoice_base_code.save()
        invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
        invoice_tax_code.save()
        credit_note_base_code = create_tax_code(tax, 'base', 'credit')
        credit_note_base_code.save()
        credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
        credit_note_tax_code.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.identifiers.new(type='eu_vat', code='ES00000000T')
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.supplier_taxes.append(Tax(tax.id))
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('25')
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create out invoice
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = payment_term
        invoice.currency = usd
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal(80)
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('400.00'))
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('20.00'))
        invoice.click('post')

        # Create in invoice
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = party
        invoice.payment_term = payment_term
        invoice.currency = usd
        invoice.invoice_date = today
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('50.0')
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('250.00'))
        line = invoice.lines.new()
        line.account = expense
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal('20.00')
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('20.00'))
        invoice.click('post')

        # Generate 349 Report
        Report = Model.get('aeat.349.report')
        report = Report()
        report.year = today.year
        report.period = "%02d" % (today.month)
        report.company_vat = '123456789'
        report.contact_name = 'Guido van Rosum'
        report.contact_phone = '987654321'
        report.representative_vat = '22334455'
        report.click('calculate')
        self.assertEqual(report.operation_amount, Decimal('1300.00'))
        self.assertEqual(report.ammendment_amount, Decimal('0.0'))
        self.assertEqual(len(report.operations), 2)
        self.assertEqual(len(report.ammendments), 0)

        # Test report is generated correctly
        report.file_
        report.click('process')
        self.assertEqual(bool(report.file_), True)
