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
                'sale', 'purchase'])
        config.skip_warning = True

        today = datetime.date.today()
        year = today.year
        period = '%02d' % today.month

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

        purchase_tax = create_tax(Decimal('.10'))
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
        template.salable = True
        template.purchasable = True
        template.list_price = Decimal('40')
        template.cost_price = Decimal('25')
        template.account_category = account_category
        template.save()
        product, = template.products

        payment_term = create_payment_term()
        payment_term.save()

        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        line = sale.lines.new()
        line.product = product
        line.quantity = 5
        sale.click('quote')
        sale.click('confirm')
        sale_invoice, = sale.invoices
        sale_invoice.invoice_date = today
        sale_invoice.click('post')

        return_sale = Wizard('sale.return_sale', [sale])
        return_sale.execute('return_')
        returned_sale, = Sale.find([
                ('origin', '=', sale),
                ('state', '=', 'draft'),
                ], limit=1)
        returned_sale_line, = [l for l in returned_sale.lines if l.product]
        returned_sale_line.quantity = Decimal('-1')
        returned_sale.click('quote')
        returned_sale.click('confirm')
        sale_credit_invoice, = returned_sale.invoices
        sale_credit_invoice.invoice_date = today
        sale_credit_invoice.click('post')

        Purchase = Model.get('purchase.purchase')
        purchase = Purchase()
        purchase.party = supplier
        purchase.payment_term = payment_term
        line = purchase.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('25')
        purchase.click('quote')
        purchase.click('confirm')
        purchase_invoice, = purchase.invoices
        purchase_invoice.invoice_date = today
        purchase_invoice.click('post')

        return_purchase = Wizard('purchase.return_purchase', [purchase])
        return_purchase.execute('return_')
        returned_purchase, = Purchase.find([
                ('origin', '=', purchase),
                ('state', '=', 'draft'),
                ], limit=1)
        returned_purchase_line, = [l for l in returned_purchase.lines if l.product]
        returned_purchase_line.quantity = Decimal('-1')
        returned_purchase.click('quote')
        returned_purchase.click('confirm')
        purchase_credit_invoice, = returned_purchase.invoices
        purchase_credit_invoice.invoice_date = today
        purchase_credit_invoice.click('post')

        Report = Model.get('aeat.349.report')
        report = Report()
        report.year = year
        report.period = period
        report.company_vat = '123456789'
        report.contact_name = 'Guido van Rosum'
        report.contact_phone = '987654321'
        report.representative_vat = '22334455'
        report.click('calculate')

        self.assertEqual(len(report.ammendments), 0)
        self.assertEqual(len(report.operations), 2)
        self.assertEqual(sorted(o.base for o in report.operations), [
                Decimal('100.00'), Decimal('160.00')])
        self.assertEqual(sorted(len(o.origins) for o in report.operations),
            [2, 2])
