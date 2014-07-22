#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends, doctest_dropdb


class Aeat349TestCase(unittest.TestCase):
    '''
    Test AEAT 349 module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('aeat_349')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('aeat_349')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            Aeat349TestCase))
    suite.addTests(doctest.DocFileSuite('scenario_aeat349.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    suite.addTests(doctest.DocFileSuite(
            'scenario_aeat349_alternate_currency.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
