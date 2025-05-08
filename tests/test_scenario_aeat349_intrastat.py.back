import datetime
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 create_tax_code, get_accounts)
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
        config = activate_modules(['aeat_349', 'account_es', 'account_stock_eu_es'])

        # Create countries
        Country = Model.get('country.country')
        Organization = Model.get('country.organization')
        europe, = Organization.find([('code', '=', 'EU')])
        belgium = Country(name="Belgium", code='BE')
        belgium.subdivisions.new(name="Flemish Region",
                                               intrastat_code='1',
                                               type='region')
        belgium.subdivisions.new(name="Walloon Region",
                                               intrastat_code='2',
                                               type='region')
        belgium.save()
        flemish, walloon = belgium.subdivisions
        belgium.subdivisions.new(name="Liège",
                                               type='province',
                                               parent=walloon)
        belgium.save()
        liege, = [s for s in belgium.subdivisions if s.parent == walloon]
        france = Country(name="France", code='FR')
        france.save()
        china = Country(name="China", code='CN')
        china.save()
        europe.members.new(country=belgium)
        europe.members.new(country=france)
        europe.save()

        # Create company
        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()
        self.assertEqual(company.intrastat, True)
        company_address, = company.party.addresses
        company_address.country = belgium
        company_address.subdivision = liege
        company_address.save()

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

        # Create suppliers
        Party = Model.get('party.party')
        customer_be = Party(name="Customer BE")
        address, = customer_be.addresses
        address.country = belgium
        customer_be.save()
        supplier_fr = Party(name="Supplier FR")
        address, = supplier_fr.addresses
        address.country = france
        identifier = supplier_fr.identifiers.new(type='eu_vat')
        identifier.code = "FR40303265045"
        supplier_fr.save()
        customer_fr = Party(name="Customer FR")
        identifier = customer_fr.identifiers.new(type='eu_vat')
        identifier.code = "FR40303265045"
        address_fr, = customer_fr.addresses
        address_fr.country = france
        customer_fr.save()
        address_fr.save()

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
        ProductTemplate = Model.get('product.template')
        ProductUom = Model.get('product.uom')
        TariffCode = Model.get('customs.tariff.code')
        unit, = ProductUom.find([('name', '=', "Unit")])
        kg, = ProductUom.find([('name', '=', "Kilogram")])
        tariff_code = TariffCode(code="9403 10 51")
        tariff_code.description = "Desks"
        tariff_code.intrastat_uom = unit
        tariff_code.save()
        template = ProductTemplate(name="Desk")
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('40')
        template.cost_price = Decimal('25')
        template.account_category = account_category
        _ = template.tariff_codes.new(tariff_code=tariff_code)
        template.weight = 3
        template.weight_uom = kg
        template.country_of_origin = china
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create out invoice
        Invoice = Model.get('account.invoice')
        invoice = Invoice()
        invoice.party = customer_fr
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.unit_price = Decimal(40)
        line.quantity = 5
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('200.00'))
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('20.00'))
        invoice.click('post')

        # Create out credit note
        invoice = Invoice()
        invoice.party = customer_fr
        invoice.payment_term = payment_term
        line = invoice.lines.new()
        line.product = product
        line.quantity = -1
        line.unit_price = Decimal(40)
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('-40.00'))
        line = invoice.lines.new()
        line.account = revenue
        line.description = 'Test'
        line.quantity = -1
        line.unit_price = Decimal(20)
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('-20.00'))
        invoice.click('post')

        # Create in invoice
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = supplier_fr
        invoice.payment_term = payment_term
        invoice.invoice_date = today
        line = invoice.lines.new()
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal(25)
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('125.00'))
        line = invoice.lines.new()
        line.account = expense
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('20.00'))
        invoice.click('post')

        # Create in credit note
        invoice = Invoice()
        invoice.type = 'in'
        invoice.party = supplier_fr
        invoice.payment_term = payment_term
        invoice.invoice_date = today
        line = invoice.lines.new()
        line.product = product
        line.quantity = -1
        line.unit_price = Decimal(25)
        self.assertEqual(len(line.taxes), 1)
        self.assertEqual(line.amount, Decimal('-25.00'))
        line = invoice.lines.new()
        line.account = expense
        line.description = 'Test'
        line.quantity = -1
        line.unit_price = Decimal(20)
        self.assertEqual(line.aeat349_operation_key, None)
        self.assertEqual(line.amount, Decimal('-20.00'))
        invoice.click('post')

        # Set default aet 349 Shipment vlues
        Configuration = Model.get('stock.configuration')
        configuration = Configuration(0)
        configuration.aeat349_default_out_operation_key = operation_key_e
        configuration.aeat349_default_in_operation_key = operation_key_a
        configuration.save()

        ShipmentInternal = Model.get('stock.shipment.internal')
        StockLocation = Model.get('stock.location')
        PriceList = Model.get('product.price_list')

        # Get stock locations
        warehouse_loc, = StockLocation.find([('code', '=', 'WH')])
        warehouse_loc.address = company_address
        warehouse_loc.save()

        # Create consignment stock locations
        warehouse_consignment_id, = StockLocation.copy([warehouse_loc],
            config.context)
        warehouse_consignment = StockLocation(warehouse_consignment_id)
        warehouse_consignment.name = 'Consignment'
        warehouse_consignment.address = address_fr
        warehouse_consignment.save()

        # Create a price List
        price_list = PriceList(name='Retail')
        price_list_line = price_list.lines.new()
        price_list_line.quantity = 1
        price_list_line.product = product
        price_list_line.formula = '100.00'
        price_list_line = price_list.lines.new()
        price_list_line.formula = 'cost_price'
        price_list.save()

        # Move product from consignment location setting the price list
        shipment = ShipmentInternal()
        shipment.from_location = warehouse_loc.storage_location
        shipment.to_location = warehouse_consignment.storage_location
        shipment.price_list = price_list
        move = shipment.moves.new()
        move.from_location = shipment.from_location
        move.to_location = shipment.to_location
        move.product = product
        move.quantity = 10
        # move.currency = eur
        shipment.click('wait')
        shipment.click('assign_force')
        shipment.click('ship')
        shipment.click('do')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.incoming_moves
        move.intrastat_type
        move, = shipment.outgoing_moves
        self.assertEqual(move.intrastat_type, 'dispatch')
        self.assertEqual(move.aeat349_operation_key, operation_key_e)

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
        self.assertEqual(report.operation_amount, Decimal('1325.00'))
        self.assertEqual(report.ammendment_amount, Decimal('0.0'))
        self.assertEqual(len(report.operations), 2)
        self.assertEqual(len(report.ammendments), 0)

        # Test report is generated correctly
        report.file_
        report.click('process')
        self.assertEqual(bool(report.file_), True)
