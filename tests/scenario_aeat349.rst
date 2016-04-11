================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from.trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice::

    >>> Module = Model.get('ir.module')
    >>> aeat_349_module, = Module.find(
    ...     [('name', '=', 'aeat_349')])
    >>> aeat_349_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')


Create company::

    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=eur)
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']

Create tax::

    >>> Tax = Model.get('account.tax')
    >>> AeatType = Model.get('aeat.349.type')
    >>> a_key, = AeatType.find([('operation_key', '=', 'A')])
    >>> e_key, = AeatType.find([('operation_key', '=', 'E')])
    >>> tax = set_tax_code(create_tax(Decimal('.10')))
    >>> tax.aeat349_operation_keys.extend([a_key, e_key])
    >>> tax.aeat349_default_out_operation_key = e_key
    >>> tax.aeat349_default_in_operation_key = a_key
    >>> tax.save()
    >>> invoice_base_code = tax.invoice_base_code
    >>> invoice_tax_code = tax.invoice_tax_code
    >>> credit_note_base_code = tax.credit_note_base_code
    >>> credit_note_tax_code = tax.credit_note_tax_code

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> identifier = party.identifiers.new(type='eu_vat',
    ...     code='ES00000000T')
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> tax, = Tax.find([])
    >>> template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create out invoice::

    >>> Record = Model.get('aeat.349.record')
    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal(40)
    >>> line.quantity = 5
    >>> len(line.taxes)
    1
    >>> line.aeat349_operation_key.operation_key
    u'E'
    >>> line.amount
    Decimal('200.00')
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount
    Decimal('20.00')
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    u'Party'
    >>> rec1.party_vat
    u'ES00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    u'E'
    >>> rec1.base
    Decimal('200.00')

Create out credit note::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = -1
    >>> line.unit_price = Decimal(40)
    >>> len(line.taxes)
    1
    >>> line.aeat349_operation_key.operation_key
    u'E'
    >>> line.amount
    Decimal('-40.00')
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = -1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount
    Decimal('-20.00')
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    u'Party'
    >>> rec1.party_vat
    u'ES00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    u'E'
    >>> rec1.base
    Decimal('-40.00')

Create in invoice::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal(25)
    >>> len(line.taxes)
    1
    >>> line.aeat349_operation_key.operation_key
    u'A'
    >>> line.amount
    Decimal('125.00')
    >>> line = invoice.lines.new()
    >>> line.account = expense
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount
    Decimal('20.00')
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    u'Party'
    >>> rec1.party_vat
    u'ES00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    u'A'
    >>> rec1.base
    Decimal('125.00')

Create in credit note::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = -1
    >>> line.unit_price = Decimal(25)
    >>> len(line.taxes)
    1
    >>> line.aeat349_operation_key.operation_key
    u'A'
    >>> line.amount
    Decimal('-25.00')
    >>> line = invoice.lines.new()
    >>> line.account = expense
    >>> line.description = 'Test'
    >>> line.quantity = -1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount
    Decimal('-20.00')
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    u'Party'
    >>> rec1.party_vat
    u'ES00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    u'A'
    >>> rec1.base
    Decimal('-25.00')


Generate 349 Report::

    >>> Report = Model.get('aeat.349.report')
    >>> report = Report()
    >>> report.fiscalyear_code = 2013
    >>> report.period = "%02d" % (today.month)
    >>> report.company_vat = '123456789'
    >>> report.contact_name = 'Guido van Rosum'
    >>> report.contact_phone = '987654321'
    >>> report.representative_vat = '22334455'
    >>> report.click('calculate')
    >>> report.operation_amount
    Decimal('260.00')
    >>> report.ammendment_amount
    Decimal('0.0')
    >>> len(report.operations)
    2
    >>> len(report.ammendments)
    0
