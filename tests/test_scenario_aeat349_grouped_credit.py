import datetime
import unittest
from decimal import Decimal

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
        config = activate_modules([
                'aeat_349', 'account_es', 'account_code_digits',
                'account_tax_non_deductible'])
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
        expense = accounts['expense']

        A349Type = Model.get('aeat.349.type')
        operation_key_e, = A349Type.find([('operation_key', '=', 'E')])
        ammendment_key_e, = A349Type.find([('operation_key', '=', 'A-E')])
        operation_key_a, = A349Type.find([('operation_key', '=', 'A')])
        ammendment_key_a, = A349Type.find([('operation_key', '=', 'A-A')])

        sale_tax = create_tax(Decimal('.10'))
        sale_tax.aeat349_operation_keys.append(operation_key_e)
        sale_tax.aeat349_operation_keys.append(ammendment_key_e)
        sale_tax.aeat349_default_out_operation_key = operation_key_e
        sale_tax.aeat349_default_out_ammendment_key = ammendment_key_e
        sale_tax.save()
        create_tax_code(sale_tax, 'base', 'invoice').save()
        create_tax_code(sale_tax, 'tax', 'invoice').save()
        create_tax_code(sale_tax, 'base', 'credit').save()
        create_tax_code(sale_tax, 'tax', 'credit').save()

        purchase_tax = create_tax(Decimal('.21'))
        purchase_tax.non_deductible = True
        purchase_tax.aeat349_operation_keys.append(operation_key_a)
        purchase_tax.aeat349_operation_keys.append(ammendment_key_a)
        purchase_tax.aeat349_default_in_operation_key = operation_key_a
        purchase_tax.aeat349_default_in_ammendment_key = ammendment_key_a
        purchase_tax.save()
        create_tax_code(purchase_tax, 'base', 'invoice').save()
        create_tax_code(purchase_tax, 'tax', 'invoice').save()
        create_tax_code(purchase_tax, 'base', 'credit').save()
        create_tax_code(purchase_tax, 'tax', 'credit').save()

        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.identifiers.new(type='eu_vat', code='ESB65247983')
        customer.save()
        supplier = Party(name='Supplier')
        supplier.identifiers.new(type='eu_vat', code='ESB65247983')
        supplier.save()

        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Account Category')
        account_category.accounting = True
        account_category.account_revenue = revenue
        account_category.account_expense = expense
        account_category.customer_taxes.append(sale_tax)
        account_category.supplier_taxes.append(purchase_tax)
        account_category.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'service'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        template.save()
        product, = template.products

        payment_term = create_payment_term()
        payment_term.save()

        Invoice = Model.get('account.invoice')
        out_invoice = Invoice(type='out')
        out_invoice.party = customer
        out_invoice.payment_term = payment_term
        out_invoice.invoice_date = current_date
        line = out_invoice.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('40')
        line = out_invoice.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('45')
        line = out_invoice.lines.new()
        line.type = 'comment'
        line.description = 'Comment'
        out_invoice.click('post')

        credit = Wizard('account.invoice.credit', [out_invoice])
        credit.form.with_refund = False
        credit.form.invoice_date = current_date
        credit.form.group_lines = True
        credit.execute('credit')
        grouped_credit, = Invoice.find([
                ('type', '=', 'out'),
                ('total_amount', '<', 0),
                ('party', '=', customer.id),
                ], order=[('id', 'DESC')], limit=1)
        grouped_credit.click('post')
        grouped_lines = [l for l in grouped_credit.lines if l.type == 'line']
        self.assertEqual(len(grouped_credit.lines), 1)
        self.assertEqual(len(grouped_lines), 1)
        self.assertEqual(grouped_lines[0].origin, out_invoice)
        self.assertEqual(grouped_credit.untaxed_amount, Decimal('-85.00'))
        self.assertEqual(grouped_credit.tax_amount, Decimal('-8.50'))

        Report = Model.get('aeat.349.report')
        same_period_report = Report()
        same_period_report.year = current_date.year
        same_period_report.period = '%02d' % current_date.month
        same_period_report.company_vat = '123456789'
        same_period_report.contact_name = 'Guido van Rosum'
        same_period_report.contact_phone = '987654321'
        same_period_report.representative_vat = '22334455'
        same_period_report.click('calculate')
        self.assertEqual(len(same_period_report.operations), 0)
        self.assertEqual(len(same_period_report.ammendments), 0)

        in_invoice = Invoice(type='in')
        in_invoice.party = supplier
        in_invoice.payment_term = payment_term
        in_invoice.invoice_date = previous_date
        line = in_invoice.lines.new()
        line.product = product
        line.quantity = 1
        line.unit_price = Decimal('100')
        line = in_invoice.lines.new()
        line.type = 'comment'
        line.description = 'Comment'
        in_invoice.click('post')

        previous_report = Report()
        previous_report.year = previous_date.year
        previous_report.period = '%02d' % previous_date.month
        previous_report.company_vat = '123456789'
        previous_report.contact_name = 'Guido van Rosum'
        previous_report.contact_phone = '987654321'
        previous_report.representative_vat = '22334455'
        previous_report.click('calculate')

        supplier_credit = Wizard('account.invoice.credit', [in_invoice])
        supplier_credit.form.invoice_date = current_date
        supplier_credit.form.group_lines = True
        supplier_credit.execute('credit')
        grouped_supplier_credit, = Invoice.find([
                ('type', '=', 'in'),
                ('total_amount', '<', 0),
                ('party', '=', supplier.id),
                ], order=[('id', 'DESC')], limit=1)
        grouped_supplier_credit.click('post')
        supplier_lines = [l for l in grouped_supplier_credit.lines if l.type == 'line']
        self.assertEqual(len(grouped_supplier_credit.lines), 1)
        self.assertEqual(len(supplier_lines), 1)
        self.assertEqual(supplier_lines[0].origin, in_invoice)
        self.assertEqual(grouped_supplier_credit.taxes, [])
        self.assertEqual(grouped_supplier_credit.total_amount, Decimal('-121.00'))

        current_report = Report()
        current_report.year = current_date.year
        current_report.period = '%02d' % current_date.month
        current_report.company_vat = '123456789'
        current_report.contact_name = 'Guido van Rosum'
        current_report.contact_phone = '987654321'
        current_report.representative_vat = '22334455'
        current_report.click('calculate')
        self.assertEqual(len(current_report.operations), 0)
        self.assertEqual(len(current_report.ammendments), 1)
        ammendment, = current_report.ammendments
        self.assertEqual(ammendment.base, Decimal('121.00'))
        self.assertEqual(ammendment.original_base, Decimal('121.00'))
