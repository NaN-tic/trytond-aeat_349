
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class Aeat349TestCase(CompanyTestMixin, ModuleTestCase):
    'Test Aeat349 module'
    module = 'aeat_349'
    extras = ['account_stock_eu_es']


del ModuleTestCase
