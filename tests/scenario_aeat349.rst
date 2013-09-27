================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice::

    >>> Module = Model.get('ir.module.module')
    >>> aeat_349_module, = Module.find(
    ...     [('name', '=', 'aeat_349')])
    >>> Module.install([aeat_349_module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> account_tax, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Tax'),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create tax::

    >>> TaxCode = Model.get('account.tax.code')
    >>> Tax = Model.get('account.tax')
    >>> tax = Tax()
    >>> tax.name = 'Tax'
    >>> tax.description = 'Tax'
    >>> tax.type = 'percentage'
    >>> tax.rate = Decimal('.10')
    >>> tax.invoice_account = account_tax
    >>> tax.credit_note_account = account_tax
    >>> invoice_base_code = TaxCode(name='invoice base')
    >>> invoice_base_code.save()
    >>> tax.invoice_base_code = invoice_base_code
    >>> invoice_tax_code = TaxCode(name='invoice tax')
    >>> invoice_tax_code.save()
    >>> tax.invoice_tax_code = invoice_tax_code
    >>> credit_note_base_code = TaxCode(name='credit note base')
    >>> credit_note_base_code.save()
    >>> tax.credit_note_base_code = credit_note_base_code
    >>> credit_note_tax_code = TaxCode(name='credit note tax')
    >>> credit_note_tax_code.save()
    >>> tax.credit_note_tax_code = credit_note_tax_code
    >>> Type = Model.get('aeat.349.type')
    >>> etype = Type()
    >>> etype.operation_key = 'E'
    >>> etype.save()
    >>> atype = Type()
    >>> atype.operation_key = 'A'
    >>> atype.save()
    >>> ttype = Type()
    >>> ttype.operation_key = 'T'
    >>> ttype.save()
    >>> stype = Type()
    >>> stype.operation_key = 'S'
    >>> stype.save()
    >>> itype = Type()
    >>> itype.operation_key = 'I'
    >>> itype.save()
    >>> mtype = Type()
    >>> mtype.operation_key = 'M'
    >>> mtype.save()
    >>> htype = Type()
    >>> htype.operation_key = 'H'
    >>> htype.save()
    >>> tax.aeat349_operation_keys.extend([etype, atype, stype, itype, mtype, htype])
    >>> tax.aeat349_default_in_operation_key = atype
    >>> tax.aeat349_default_out_operation_key = stype
    >>> tax.save()
    >>> tax.reload()
    >>> len(tax.aeat349_operation_keys) == 6
    True
    >>> tax.aeat349_default_in_operation_key == atype
    True
    >>> tax.aeat349_default_out_operation_key == stype
    True

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party', vat_number='00000000T')
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
    >>> tax = Tax(1)
    >>> template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Term')
    >>> payment_term_line = PaymentTermLine(type='percent', days=20,
    ...     percentage=Decimal(50))
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term_line = PaymentTermLine(type='remainder', days=40)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create out invoice::

    >>> Record = Model.get('aeat.349.record')
    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> len(line.taxes) == 1
    True
    >>> line.aeat349_operation_key == stype
    True
    >>> line.amount == Decimal(200)
    True
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount == Decimal(20)
    True
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> len(line.taxes) == 0
    True
    >>> line.account = revenue
    >>> line.description = 'Test 2'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(40)
    >>> tax = Tax(1)
    >>> line.taxes.append(tax)
    >>> line.aeat349_operation_key == stype
    True
    >>> line.aeat349_operation_key = etype
    >>> line.aeat349_operation_key == etype
    True
    >>> line.amount == Decimal(40)
    True
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> (rec1, rec2) = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name == 'Party'
    True
    >>> rec1.party_vat == '00000000T'
    True
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key == 'S'
    True
    >>> rec1.base == Decimal(200)
    True
    >>> rec2.operation_key == 'E'
    True
    >>> rec2.base == Decimal(40)
    True

Create in invoice::

    >>> invoice = Invoice()
    >>> invoice.type = 'in_invoice'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> len(line.taxes) == 1
    True
    >>> line.aeat349_operation_key == atype
    True
    >>> line.amount == Decimal(125)
    True
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = expense
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> line.aeat349_operation_key == None
    True
    >>> line.amount == Decimal(20)
    True
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> len(line.taxes) == 0
    True
    >>> line.account = expense
    >>> line.description = 'Test 2'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(40)
    >>> tax = Tax(1)
    >>> line.taxes.append(tax)
    >>> line.aeat349_operation_key == atype
    True
    >>> line.aeat349_operation_key = itype
    >>> line.aeat349_operation_key == itype
    True
    >>> line.amount == Decimal(40)
    True
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> (rec1, rec2) = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name == 'Party'
    True
    >>> rec1.party_vat == '00000000T'
    True
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key == 'I'
    True
    >>> rec1.base == Decimal(40)
    True
    >>> rec2.operation_key == 'A'
    True
    >>> rec2.base == Decimal(125)
    True

Generate 349 Report::

    >>> Report = Model.get('aeat.349.report')
    >>> report = Report()
    >>> report.fiscalyear_code = 2013
    >>> report.period = "%02d" % (today.month)
    >>> report.company_vat = '123456789'
    >>> report.contact_name = 'Guido van Rosum'
    >>> report.contact_phone = '987654321'
    >>> report.representative_vat = '22334455'
    >>> report.save()
    >>> Report.calculate([report.id], config.context)
    >>> report.reload()
    >>> report.operation_amount == Decimal(405)
    True
    >>> report.ammendment_amount == Decimal(0)
    True
    >>> len(report.operations) == 4
    True
    >>> len(report.ammendments) == 0
    True
