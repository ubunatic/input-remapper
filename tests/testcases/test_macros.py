#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


import time
import unittest
import asyncio

from keymapper.dev.macros import parse, _Macro, _extract_params, \
    is_this_a_macro
from keymapper.config import config
from keymapper.state import system_mapping


class TestMacros(unittest.TestCase):
    def setUp(self):
        self.result = []
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        self.result = []

    def handler(self, code, value):
        """Where macros should write codes to."""
        self.result.append((code, value))

    def test_is_this_a_macro(self):
        self.assertTrue(is_this_a_macro('k(1)'))
        self.assertTrue(is_this_a_macro('k(1).k(2)'))
        self.assertTrue(is_this_a_macro('r(1, k(1).k(2))'))

        self.assertFalse(is_this_a_macro('1'))
        self.assertFalse(is_this_a_macro('key_kp1'))
        self.assertFalse(is_this_a_macro('btn_left'))
        self.assertFalse(is_this_a_macro('minus'))
        self.assertFalse(is_this_a_macro('k'))

    def test_extract_params(self):
        def expect(raw, expectation):
            self.assertListEqual(_extract_params(raw), expectation)

        expect('a', ['a'])
        expect('a,b', ['a', 'b'])
        expect('a,b,c', ['a', 'b', 'c'])

        expect('k(a)', ['k(a)'])
        expect('k(a).k(b), k(a)', ['k(a).k(b)', 'k(a)'])
        expect('k(a), k(a).k(b)', ['k(a)', 'k(a).k(b)'])

        expect('r(1, k(a))', ['r(1, k(a))'])
        expect('r(1, k(a)), r(1, k(b))', ['r(1, k(a))', 'r(1, k(b))'])
        expect(
            'r(1, k(a)), r(1, k(b)), r(1, k(c))',
            ['r(1, k(a))', 'r(1, k(b))', 'r(1, k(c))']
        )

        expect('', [''])
        expect(',', ['', ''])
        expect(',,', ['', '', ''])

    def test_set_handler(self):
        macro = parse('r(1, r(1, k(1)))')
        one_code = system_mapping.get('1')
        self.assertSetEqual(macro.get_capabilities(), {one_code})

        self.loop.run_until_complete(macro.run())
        self.assertListEqual(self.result, [])

        macro.set_handler(self.handler)
        self.loop.run_until_complete(macro.run())
        self.assertListEqual(self.result, [(one_code, 1), (one_code, 0)])

    def test_fails(self):
        self.assertIsNone(parse('r(1, a)'))
        self.assertIsNone(parse('r(a, k(b))'))
        self.assertIsNone(parse('m(a, b)'))

    def test_0(self):
        macro = parse('k(1)')
        macro.set_handler(self.handler)
        one_code = system_mapping.get('1')
        self.assertSetEqual(macro.get_capabilities(), {one_code})

        self.loop.run_until_complete(macro.run())
        self.assertListEqual(self.result, [(one_code, 1), (one_code, 0)])
        self.assertEqual(len(macro.child_macros), 0)

    def test_1(self):
        macro = parse('k(1).k(a).k(3)')
        macro.set_handler(self.handler)
        self.assertSetEqual(macro.get_capabilities(), {
            system_mapping.get('1'),
            system_mapping.get('a'),
            system_mapping.get('3')
        })

        self.loop.run_until_complete(macro.run())
        self.assertListEqual(self.result, [
            (system_mapping.get('1'), 1), (system_mapping.get('1'), 0),
            (system_mapping.get('a'), 1), (system_mapping.get('a'), 0),
            (system_mapping.get('3'), 1), (system_mapping.get('3'), 0),
        ])
        self.assertEqual(len(macro.child_macros), 0)

    def test_return_errors(self):
        error = parse('k(1).h(k(a)).k(3)', return_errors=True)
        self.assertIsNone(error)
        error = parse('k(1))', return_errors=True)
        self.assertIn('bracket', error)
        error = parse('k((1)', return_errors=True)
        self.assertIn('bracket', error)
        error = parse('k((1).k)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('k()', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('r(a, k(1))', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('k(1, 1)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('h(1, 1)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('h(h(h(1, 1)))', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('r(1)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('r(1, 1)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('r(k(1), 1)', return_errors=True)
        self.assertIsNotNone(error)
        error = parse('r(1, k(1))', return_errors=True)
        self.assertIsNone(error)

    def test_hold(self):
        macro = parse('k(1).h(k(a)).k(3)')
        macro.set_handler(self.handler)
        self.assertSetEqual(macro.get_capabilities(), {
            system_mapping.get('1'),
            system_mapping.get('a'),
            system_mapping.get('3')
        })

        macro.press_key()
        asyncio.ensure_future(macro.run())
        self.loop.run_until_complete(asyncio.sleep(0.2))
        macro.release_key()
        self.loop.run_until_complete(asyncio.sleep(0.05))

        self.assertEqual(
            self.result[0],
            (system_mapping.get('1'), 1)
        )
        self.assertEqual(
            self.result[-1],
            (system_mapping.get('3'), 0)
        )

        code_a = system_mapping.get('a')
        self.assertGreater(self.result.count((code_a, 1)), 2)

        self.assertEqual(len(macro.child_macros), 1)

    def test_2(self):
        start = time.time()
        repeats = 20

        macro = parse(f'r({repeats}, k(k)).r(1, k(k))')
        macro.set_handler(self.handler)
        k_code = system_mapping.get('k')
        self.assertSetEqual(macro.get_capabilities(), {k_code})

        self.loop.run_until_complete(macro.run())
        keystroke_sleep = config.get('macros.keystroke_sleep_ms')
        sleep_time = 2 * repeats * keystroke_sleep / 1000
        self.assertGreater(time.time() - start, sleep_time * 0.9)
        self.assertLess(time.time() - start, sleep_time * 1.1)

        self.assertListEqual(
            self.result,
            [(k_code, 1), (k_code, 0)] * (repeats + 1)
        )

        self.assertEqual(len(macro.child_macros), 2)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    def test_3(self):
        start = time.time()
        macro = parse('r(3, k(m).w(100))')
        macro.set_handler(self.handler)
        m_code = system_mapping.get('m')
        self.assertSetEqual(macro.get_capabilities(), {m_code})
        self.loop.run_until_complete(macro.run())

        keystroke_time = 6 * config.get('macros.keystroke_sleep_ms')
        total_time = keystroke_time + 300
        total_time /= 1000

        self.assertGreater(time.time() - start, total_time * 0.9)
        self.assertLess(time.time() - start, total_time * 1.1)
        self.assertListEqual(self.result, [
            (m_code, 1), (m_code, 0),
            (m_code, 1), (m_code, 0),
            (m_code, 1), (m_code, 0),
        ])
        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    def test_4(self):
        macro = parse('  r(2,\nk(\nr ).k(minus\n )).k(m)  ')
        macro.set_handler(self.handler)

        r = system_mapping.get('r')
        minus = system_mapping.get('minus')
        m = system_mapping.get('m')

        self.assertSetEqual(macro.get_capabilities(), {r, minus, m})

        self.loop.run_until_complete(macro.run())
        self.assertListEqual(self.result, [
            (r, 1), (r, 0),
            (minus, 1), (minus, 0),
            (r, 1), (r, 0),
            (minus, 1), (minus, 0),
            (m, 1), (m, 0),
        ])
        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 0)

    def test_5(self):
        start = time.time()
        macro = parse('w(200).r(2,m(w,\nr(2,\tk(BtN_LeFt))).w(10).k(k))')
        macro.set_handler(self.handler)

        self.assertEqual(len(macro.child_macros), 1)
        self.assertEqual(len(macro.child_macros[0].child_macros), 1)

        w = system_mapping.get('w')
        left = system_mapping.get('bTn_lEfT')
        k = system_mapping.get('k')

        self.assertSetEqual(macro.get_capabilities(), {w, left, k})

        self.loop.run_until_complete(macro.run())

        num_pauses = 8 + 6 + 4
        keystroke_time = num_pauses * config.get('macros.keystroke_sleep_ms')
        wait_time = 220
        total_time = (keystroke_time + wait_time) / 1000

        self.assertLess(time.time() - start, total_time * 1.1)
        self.assertGreater(time.time() - start, total_time * 0.9)
        expected = [(w, 1)]
        expected += [(left, 1), (left, 0)] * 2
        expected += [(w, 0)]
        expected += [(k, 1), (k, 0)]
        expected *= 2
        self.assertListEqual(self.result, expected)

    def test_6(self):
        # does nothing without .run
        macro = parse('k(a).r(3, k(b))')
        macro.set_handler(self.handler)
        self.assertIsInstance(macro, _Macro)
        self.assertListEqual(self.result, [])


if __name__ == '__main__':
    unittest.main()
