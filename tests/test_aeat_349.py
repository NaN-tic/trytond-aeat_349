# This file is part of the aeat_349 module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class Aeat349TestCase(ModuleTestCase):
    'Test Aeat 349 module'
    module = 'aeat_349'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        Aeat349TestCase))
    return suite