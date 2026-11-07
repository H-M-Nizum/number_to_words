# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


DEFAULT_PARAMS = {
    'language_id': '',
    'text_case': 'title',
    'append_only': 'False',
    'fraction_style': 'words',
    'cheque_style': 'False',
}


def reset_settings(env):
    """Tests must not depend on the settings of the database they run in."""
    for key, value in DEFAULT_PARAMS.items():
        env['ir.config_parameter'].sudo().set_param(f'number_to_words.{key}', value)


@tagged('post_install', '-at_install')
class TestNumberToWords(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['number.to.words']
        cls.params = cls.env['ir.config_parameter'].sudo()
        reset_settings(cls.env)
        cls.english = cls.env.ref('number_to_words.lang_en')
        cls.bangla = cls.env.ref('number_to_words.lang_bn')

    # ---- the engine reads the configuration -------------------------------
    def test_english_international(self):
        cases = {
            0: 'Zero',
            7: 'Seven',
            13: 'Thirteen',
            21: 'Twenty-One',
            100: 'One Hundred',
            101: 'One Hundred One',
            1234: 'One Thousand Two Hundred Thirty-Four',
            100000: 'One Hundred Thousand',
            1000000: 'One Million',
            1000000000: 'One Billion',
            12345678: 'Twelve Million Three Hundred Forty-Five Thousand Six Hundred Seventy-Eight',
        }
        for number, expected in cases.items():
            self.assertEqual(self.service.to_words(number, lang='en'), expected, number)

    def test_english_south_asian(self):
        self.english.system_id = self.env.ref('number_to_words.system_en_south_asian')
        cases = {
            99999: 'Ninety-Nine Thousand Nine Hundred Ninety-Nine',
            100000: 'One Lakh',
            10000000: 'One Crore',
            12345678: 'One Crore Twenty-Three Lakh Forty-Five Thousand Six Hundred Seventy-Eight',
            1000000000: 'One Arab',
        }
        for number, expected in cases.items():
            self.assertEqual(self.service.to_words(number, lang='en'), expected, number)

    def test_bangla(self):
        cases = {
            0: 'শূন্য',
            5: 'পাঁচ',
            25: 'পঁচিশ',
            99: 'নিরানব্বই',
            100: 'এক শত',
            1234: 'এক হাজার দুই শত চৌত্রিশ',
            100000: 'এক লক্ষ',
            10000000: 'এক কোটি',
            12345678: 'এক কোটি তেইশ লক্ষ পঁয়তাল্লিশ হাজার ছয় শত আটাত্তর',
            1000000000: 'এক শত কোটি',
        }
        for number, expected in cases.items():
            self.assertEqual(self.service.to_words(number, lang='bn'), expected, number)

    def test_bangla_table_is_complete(self):
        self.assertEqual(self.bangla.number_count, 100)
        self.assertEqual(len(set(self.bangla.number_ids.mapped('word'))), 100)
        self.assertFalse(self.bangla._words_missing())

    # ---- service ------------------------------------------------------
    def test_number_mode(self):
        self.assertEqual(self.service.to_words(12.34, lang='en'), 'Twelve Point Three Four')
        self.assertEqual(self.service.to_words(12.34, lang='bn'), 'বারো দশমিক তিন চার')
        self.assertEqual(self.service.to_words(12.0, lang='en'), 'Twelve')
        self.assertEqual(self.service.to_words(-5, lang='en'), 'Minus Five')
        self.assertEqual(self.service.to_words('42', lang='bn'), 'বিয়াল্লিশ')

    def test_empty_and_invalid_values(self):
        for value in (False, None, '', 'abc', float('nan')):
            self.assertEqual(self.service.to_words(value), '')

    def test_currency_mode(self):
        bdt = self.env.ref('base.BDT')
        self.assertEqual(
            self.service.to_words(150.5, lang='en', mode='currency', currency_id=bdt.id),
            'One Hundred Fifty Taka and Fifty Paisa',
        )
        self.assertEqual(
            self.service.to_words(150.5, lang='bn', mode='currency', currency_id=bdt.id),
            'এক শত পঞ্চাশ টাকা এবং পঞ্চাশ পয়সা',
        )
        self.assertEqual(
            self.service.to_words(100, lang='bn', mode='currency', currency_id=bdt.id),
            'এক শত টাকা',
        )

    def test_currency_rounding(self):
        bdt = self.env.ref('base.BDT')
        self.assertEqual(
            self.service.to_words(0.999, lang='en', mode='currency', currency_id=bdt.id),
            'One Taka',
        )

    def test_settings(self):
        bdt = self.env.ref('base.BDT')
        self.english.system_id = self.env.ref('number_to_words.system_en_south_asian')
        self.params.set_param('number_to_words.text_case', 'upper')
        self.params.set_param('number_to_words.append_only', 'True')
        self.assertEqual(
            self.service.to_words(100000, lang='en', mode='currency', currency_id=bdt.id),
            'ONE LAKH TAKA ONLY',
        )
        self.assertEqual(
            self.service.to_words(100000, lang='bn', mode='currency', currency_id=bdt.id),
            'এক লক্ষ টাকা মাত্র',
        )

    def test_currency_amount_to_text_override(self):
        bdt = self.env.ref('base.BDT')
        self.params.set_param('number_to_words.language_id', str(self.bangla.id))
        self.assertEqual(bdt.amount_to_text(25), 'পঁচিশ টাকা')
        self.params.set_param('number_to_words.language_id', '')
        # Core behaviour is untouched with default settings.
        self.assertEqual(bdt.amount_to_text(25), bdt.with_context(lang='en_US').amount_to_text(25))

    def test_the_language_follows_the_user_then_the_settings(self):
        Lang = self.env['res.lang'].with_context(active_test=False)
        bengali = Lang.search([('code', '=', 'bn_BD')]) or Lang.create({
            'name': "Bengali", 'code': 'bn_BD', 'iso_code': 'bn', 'url_code': 'bn_BD', 'active': True})
        bengali.active = True
        self.assertEqual(self.service.with_context(lang='bn_BD')._resolve_language(), self.bangla)
        self.assertEqual(self.service.with_context(lang='en_US')._resolve_language(), self.english)
        self.params.set_param('number_to_words.language_id', str(self.bangla.id))
        self.assertEqual(self.service.with_context(lang='en_US')._resolve_language(), self.bangla)
        self.assertEqual(self.service._resolve_language('en'), self.english)  # an explicit language wins

    # ---- nothing is written in the code ---------------------------------
    def test_a_normal_user_can_use_the_words_but_not_the_rules(self):
        from odoo.exceptions import AccessError
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': "Words user", 'login': "words_user", 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        usd = self.env.ref('base.USD')
        as_user = self.service.with_user(user)
        self.assertEqual(as_user.to_words(23, lang='en'), 'Twenty-Three')
        self.assertEqual(as_user.to_words(2.5, lang='bn', mode='currency', currency_id=usd.id),
                         'দুই ডলার এবং পঞ্চাশ সেন্ট')
        self.params.set_param('number_to_words.language_id', str(self.bangla.id))
        self.assertEqual(usd.with_user(user).amount_to_text(5), 'পাঁচ ডলার')
        for model in ('number.to.words.rule', 'number.to.words.anchor'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(user).search([])
        with self.assertRaises(AccessError):
            self.env['number.to.words.rule'].with_user(user).create({'name': "no"})

    # ---- more languages: built in (Hindi, Urdu) and automatic (Odoo's own library) ----
    def test_hindi_and_urdu_are_built_in(self):
        self.assertEqual(self.service.to_words(125, lang='hi'), 'एक सौ पच्चीस')
        self.assertEqual(self.service.to_words(12345678, lang='hi'),
                         'एक करोड़ तेईस लाख पैंतालीस हज़ार छह सौ अठहत्तर')
        self.assertEqual(self.service.to_words(12.5, lang='hi'), 'बारह दशमलव पाँच')
        self.assertEqual(self.service.to_words(125, lang='ur'), 'ایک سو پچیس')
        self.assertEqual(self.service.to_words(12345678, lang='ur'),
                         'ایک کروڑ تئیس لاکھ پینتالیس ہزار چھ سو اٹھہتر')
        for code in ('hi', 'ur'):
            language = self.env['number.to.words.language'].search([('code', '=', code)])
            self.assertEqual(language.number_count, 100, code)
            self.assertFalse(language._words_missing(), code)
            self.assertTrue(language.system_id, code)
        inr = self.env.ref('base.INR')
        self.assertEqual(self.service.to_words(125.5, lang='hi', mode='currency', currency_id=inr.id),
                         'एक सौ पच्चीस रुपये और पचास पैसे')
        self.assertEqual(self.service.to_words(125.5, lang='ur', mode='currency', currency_id=inr.id),
                         'ایک سو پچیس روپے اور پچاس پیسے')

    def test_other_languages_use_the_library_of_odoo(self):
        self.env['res.lang']._activate_lang('es_ES')
        self.assertEqual(self.service.to_words(23, lang='es'), 'Veintitrés')
        self.assertEqual(self.service.to_words(-23, lang='es').lower(), 'menos veintitrés')
        self.assertIn('punto', self.service.to_words(12.5, lang='es').lower())
        arabic = self.service.to_words(5, lang='ar')
        self.assertTrue(arabic and any('\u0600' <= char <= '\u06ff' for char in arabic), arabic)
        # the language of the user, without any setting
        self.assertEqual(self.service.with_context(lang='es_ES').to_words(23), 'Veintitrés')
        # amounts: the same engine as Odoo's own amount in letters
        usd = self.env.ref('base.USD')
        self.assertTrue(
            self.service.to_words(25, lang='es', mode='currency', currency_id=usd.id).startswith('Veinticinco'))

    def test_a_forced_language_does_not_hide_an_explicit_other_language(self):
        self.env['res.lang']._activate_lang('es_ES')
        usd = self.env.ref('base.USD')
        self.params.set_param('number_to_words.language_id', str(self.bangla.id))
        self.assertEqual(self.service.to_words(23, lang='es'), 'Veintitrés')
        self.assertTrue(
            self.service.to_words(25, lang='es', mode='currency', currency_id=usd.id).startswith('Veinticinco'))
        self.assertEqual(self.service.to_words(23, lang='en'), 'Twenty-Three')

    def test_an_unsupported_language_falls_back_to_english(self):
        self.assertEqual(self.service.to_words(23, lang='zh'), 'Twenty-Three')       # not in the library
        self.assertEqual(self.service.to_words(23, lang='xx'), 'Twenty-Three')

    def test_without_the_library_english_is_used(self):
        with patch('odoo.addons.number_to_words.models.number_to_words.num2words', None), \
                patch('odoo.addons.number_to_words.models.number_to_words.CONVERTER_CLASSES', {}):
            self.assertEqual(self.service.to_words(23, lang='es'), 'Twenty-Three')

    def test_every_language_has_a_default_numbering_system(self):
        self.assertEqual(self.english.system_id, self.env.ref('number_to_words.system_en_international'))
        self.assertEqual(self.bangla.system_id, self.env.ref('number_to_words.system_bn'))

    def test_a_word_can_be_changed_by_configuration(self):
        self.english.number_ids.filtered(lambda n: n.value == 7).word = 'Sept'
        self.english.word_point = 'Dot'
        self.assertEqual(self.service.to_words(7.5, lang='en'), 'Sept Dot Five')

    def test_a_scale_can_be_added_by_configuration(self):
        international = self.env.ref('number_to_words.system_en_international')
        self.env['number.to.words.scale'].create({
            'system_id': international.id, 'exponent': 4, 'word': 'Myriad', 'joiner': ' ',
        })
        self.assertEqual(self.service.to_words(30000, lang='en'), 'Three Myriad')

    def test_the_joiners_and_the_separator_are_configuration(self):
        self.english.tens_joiner = ' '
        self.assertEqual(self.service.to_words(21, lang='en'), 'Twenty One')
        self.english.separator = ', '
        self.assertEqual(self.service.to_words(1234, lang='en'), 'One Thousand, Two Hundred, Thirty Four')

    def test_a_new_language_needs_no_code(self):
        words = {0: 'zilch', 1: 'un', 2: 'du', 3: 'tri', 4: 'kvar', 5: 'kvin', 6: 'ses', 7: 'sep', 8: 'ok', 9: 'nau',
                 10: 'dek', 20: 'dudek'}
        language = self.env['number.to.words.language'].create({
            'name': "Test language", 'code': 'zz', 'word_minus': 'mal', 'word_point': 'komo', 'word_and': 'kaj',
            'tens_joiner': '_', 'digits': 'ABCDEFGHIJ',
            'number_ids': [(0, 0, {'value': value, 'word': word}) for value, word in words.items()],
        })
        system = self.env['number.to.words.system'].create({
            'name': "Test", 'language_id': language.id,
            'scale_ids': [(0, 0, {'exponent': 2, 'word': 'cent', 'joiner': ' '}),
                          (0, 0, {'exponent': 3, 'word': 'mil', 'joiner': '-'})],
        })
        language.system_id = system
        service = self.service
        self.assertEqual(service.to_words(0, lang='zz'), 'zilch')
        self.assertEqual(service.to_words(23, lang='zz'), 'dudek_tri')
        self.assertEqual(service.to_words(-5, lang='zz'), 'mal kvin')
        self.assertEqual(service.to_words(1.25, lang='zz'), 'un komo du kvin')
        self.assertEqual(service.to_words(2000, lang='zz'), 'du-mil')
        self.assertEqual(service.to_words(305, lang='zz'), 'tri cent kvin')
        self.params.set_param('number_to_words.fraction_style', 'fraction')
        usd = self.env.ref('base.USD')
        self.env['number.to.words.currency.name'].create(
            {'currency_id': usd.id, 'language_id': language.id, 'unit': 'dolaro', 'subunit': 'cendo'})
        self.assertEqual(
            service.to_words(2.5, lang='zz', mode='currency', currency_id=usd.id), 'du dolaro kaj FA/BAA')

    def test_a_missing_word_is_explained(self):
        language = self.env['number.to.words.language'].create({
            'name': "Poor", 'code': 'pp',
            'number_ids': [(0, 0, {'value': value, 'word': str(value)}) for value in range(10)],
        })
        language.system_id = self.env['number.to.words.system'].create({'name': "None", 'language_id': language.id})
        with self.assertRaisesRegex(Exception, "no word for 25"):
            self.service.to_words(25, lang='pp')

    def test_the_words_of_a_language_are_checked(self):
        with self.assertRaises(Exception):
            self.env['number.to.words.language'].create({'name': "Bad", 'code': 'bd', 'digits': '123'})
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception):
            self.env['number.to.words.language'].create({'name': "Twin", 'code': 'en'})

@tagged('post_install', '-at_install')
class TestNumberToWordsOptions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['number.to.words']
        cls.params = cls.env['ir.config_parameter'].sudo()
        reset_settings(cls.env)
        cls.bdt = cls.env.ref('base.BDT')

    def test_bangla_currency_names_are_editable(self):
        usd = self.env.ref('base.USD')
        self.assertEqual(
            self.service.to_words(2.5, lang='bn', mode='currency', currency_id=usd.id),
            'দুই ডলার এবং পঞ্চাশ সেন্ট',
        )
        usd.number_to_words_name_ids.filtered(lambda n: n.language_id.code == 'bn').unit = 'মার্কিন ডলার'
        self.assertEqual(
            self.service.to_words(1, lang='bn', mode='currency', currency_id=usd.id), 'এক মার্কিন ডলার')

    def test_bangla_hundreds_style(self):
        self.env.ref('number_to_words.lang_bn').system_id = self.env.ref('number_to_words.system_bn_sho')
        self.assertEqual(self.service.to_words(125, lang='bn'), 'একশো পঁচিশ')
        self.assertEqual(self.service.to_words(1200, lang='bn'), 'এক হাজার দুইশো')

    def test_fraction_and_cheque_style(self):
        self.params.set_param('number_to_words.fraction_style', 'fraction')
        self.params.set_param('number_to_words.cheque_style', 'True')
        self.assertEqual(
            self.service.to_words(10.5, lang='en', mode='currency', currency_id=self.bdt.id),
            '*** Ten Taka and 50/100 ***',
        )
        self.assertEqual(
            self.service.to_words(10.5, lang='bn', mode='currency', currency_id=self.bdt.id),
            '*** দশ টাকা এবং ৫০/১০০ ***',
        )

    def test_report_rule(self):
        view = self.env['ir.ui.view'].create({
            'name': 'ntw.test.report',
            'type': 'qweb',
            'key': 'number_to_words.ntw_test_report',
            'arch': '<t t-name="number_to_words.ntw_test_report"><div class="page"><span id="anchor"/></div></t>',
        })
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Partner report",
            'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report',
            'report_view_id': view.id,
            'record_var': 'o',
            'line_ids': [(0, 0, {
                'target': 'report',
                'field_id': field('color').id,
                'mode': 'number',
                'language_id': self.env.ref('number_to_words.lang_bn').id,
                'xpath_expr': "//span[@id='anchor']",
            })],
        })
        self.assertTrue(rule.report_view_ids)
        partner = self.env['res.partner'].create({'name': "Words", 'color': 3})
        html = self.env['ir.qweb']._render('number_to_words.ntw_test_report', {'o': partner})
        self.assertIn('তিন', str(html))
        with self.assertRaises(Exception):
            rule.line_ids.xpath_expr = "//nothing"


@tagged('post_install', '-at_install')
class TestNumberToWordsRuleForm(TransactionCase):

    def test_report_choice_is_filtered_by_model(self):
        from odoo.tests import Form
        report = self.env.ref('base.report_irmodeloverview_action', raise_if_not_found=False) \
            or self.env['ir.actions.report'].search([('report_name', '=', 'base.report_irmodeloverview')], limit=1)
        self.assertTrue(report)
        form = Form(self.env['number.to.words.rule'])
        form.name = "Model overview"
        form.model_id = self.env['ir.model']._get(report.model)
        form.target = 'report'
        form.report_id = report
        self.assertTrue(form.report_view_id)
        self.assertTrue(form.report_view_id.key.startswith(report.report_name))
        self.assertTrue(form.record_var.isidentifier())  # guessed from the template
        # only the reports of the chosen model are proposed
        domain = self.env['number.to.words.rule']._fields['report_id'].domain
        self.assertIn('model_name', domain)

    def test_each_show_in_keeps_its_own_lines(self):
        from odoo.tests import Form
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        view = self.env['ir.ui.view'].create({
            'name': 'ntw.test.own', 'type': 'qweb', 'key': 'number_to_words.ntw_test_own',
            'arch': '<t t-name="number_to_words.ntw_test_own"><div><span id="anchor"/></div></t>',
        })
        rule = self.env['number.to.words.rule'].create({
            'name': "Partner",
            'model_id': self.env['ir.model']._get('res.partner').id,
            'line_ids': [
                (0, 0, {'field_id': field('color').id, 'anchor_field_id': field('name').id, 'mode': 'number'}),
                (0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                        'xpath_expr': "//span[@id='anchor']"}),
            ],
        })
        self.assertEqual(len(rule.form_line_ids), 1)
        self.assertEqual(len(rule.report_line_ids), 1)
        rule.report_view_id = view
        with Form(rule) as form:
            form.target = 'report'
            self.assertEqual(len(form.report_line_ids), 1)
            self.assertEqual(len(form.form_line_ids), 1)  # kept aside
            form.target = 'form'
            self.assertEqual(len(form.form_line_ids), 1)
        self.assertEqual(rule.view_id.type, 'form')
        rule.target = 'report'
        self.assertFalse(rule.view_id)
        self.assertEqual(rule.report_view_ids.type, 'qweb')
        self.assertIn("anchor", rule.report_view_ids.arch_base)
        self.assertEqual(len(rule.form_line_ids), 1)

    def test_changing_the_report_keeps_the_lines(self):
        from odoo.tests import Form
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Partner",
            'model_id': self.env['ir.model']._get('res.partner').id,
            'line_ids': [(0, 0, {'field_id': field('color').id, 'anchor_field_id': field('name').id, 'mode': 'number'})],
        })
        report = self.env['ir.actions.report'].search([('report_name', '=', 'base.report_irmodeloverview')], limit=1)
        with Form(rule) as form:
            form.target = 'report'
            form.report_id = report
            form.target = 'form'
            self.assertEqual(len(form.form_line_ids), 1)

    def test_switching_an_existing_rule_between_form_and_report(self):
        view = self.env['ir.ui.view'].create({
            'name': 'ntw.test.switch', 'type': 'qweb', 'key': 'number_to_words.ntw_test_switch',
            'arch': '<t t-name="number_to_words.ntw_test_switch"><div><span id="anchor"/></div></t>',
        })
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Switch",
            'model_id': self.env['ir.model']._get('res.partner').id,
            'line_ids': [
                (0, 0, {'field_id': field('color').id, 'anchor_field_id': field('name').id, 'mode': 'number'}),
                (0, 0, {'target': 'report', 'field_id': field('color').id, 'xpath_expr': "//span[@id='anchor']",
                        'mode': 'number'}),
            ],
        })
        self.assertEqual(rule.view_id.type, 'form')
        rule.write({'target': 'report', 'report_view_id': view.id})
        self.assertEqual(rule.report_view_ids.type, 'qweb')
        self.assertFalse(rule.view_id)
        rule.write({'target': 'form'})
        self.assertEqual(rule.view_id.type, 'form')
        self.assertFalse(rule.report_view_ids)
        self.assertEqual(rule.view_id.model, 'res.partner')


@tagged('post_install', '-at_install')
class TestNumberToWordsPlaces(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reset_settings(cls.env)
        cls.view = cls.env['ir.ui.view'].create({
            'name': 'ntw.test.places',
            'type': 'qweb',
            'key': 'number_to_words.ntw_test_places',
            'arch': '''<t t-name="number_to_words.ntw_test_places"><div class="page">
                <h2>Order Overview</h2>
                <table><thead><tr><th>Quantity</th><th><span>Price</span></th></tr></thead>
                <tbody><tr><td><span t-field="doc.color"/></td></tr></tbody></table>
                <div name="totals"><span t-out="doc.name"/></div>
                <span t-field="doc.parent_id.name"/>
                <div name="grand_total_box" id="grand_total_box"><span t-out="doc.display_name.lower()"/></div>
                <table><tbody t-foreach="doc.child_ids" t-as="line"><tr name="line_row"><td>
                    <span t-field="line.name"/></td></tr></tbody></table>
            </div></t>''',
        })
        cls.Anchor = cls.env['number.to.words.anchor']

    def test_places_are_described_in_plain_words(self):
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        names = self.Anchor.search([('view_id', '=', self.view.id)]).mapped('name')
        self.assertIn("Title: Order Overview", names)
        self.assertIn("Column: Quantity", names)
        self.assertIn("Column: Price", names)
        self.assertIn("Block: totals", names)
        self.assertIn("Value: Name", names)
        # the technical expression is replaced by the label of the field
        color = self.env['ir.model.fields']._get('res.partner', 'color').field_description
        self.assertIn(f"Field: {color}", names)

    def test_places_are_cached_and_refreshed(self):
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        ids = self.Anchor.search([('view_id', '=', self.view.id)]).ids
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        self.assertEqual(self.Anchor.search([('view_id', '=', self.view.id)]).ids, ids)
        self.view.arch_base = self.view.arch_base.replace('Order Overview', 'Overview')
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        names = self.Anchor.search([('view_id', '=', self.view.id)]).mapped('name')
        self.assertIn("Title: Overview", names)
        self.assertNotIn("Title: Order Overview", names)

    def test_dropdown_search_prepares_the_places(self):
        found = self.Anchor.with_context(
            ntw_view_id=self.view.id, ntw_model='res.partner', ntw_var='doc',
        ).name_search('Column')
        self.assertEqual({name for _id, name in found}, {"Column: Quantity", "Column: Price"})

    def test_line_gets_its_xpath_from_the_chosen_place(self):
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', self.view.id), ('name', '=', "Block: totals")])
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Places",
            'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report',
            'report_view_id': self.view.id,
            'line_ids': [(0, 0, {
                'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                'report_anchor_id': place.id,
            })],
        })
        self.assertEqual(rule.line_ids.xpath_expr, "//div[@name='totals']")
        partner = self.env['res.partner'].create({'name': "P", 'color': 4})
        html = self.env['ir.qweb']._render('number_to_words.ntw_test_places', {'doc': partner})
        self.assertIn('Four', str(html))
        # our own insertion never shows up as a place to choose
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        self.assertFalse(self.Anchor.search([('view_id', '=', self.view.id), ('name', 'ilike', 'number-to-words')]))


    def test_places_follow_called_templates(self):
        wrapper = self.env['ir.ui.view'].create({
            'name': 'ntw.test.wrapper', 'type': 'qweb', 'key': 'number_to_words.ntw_test_wrapper',
            'arch': '<t t-name="number_to_words.ntw_test_wrapper"><div class="page">'
                    '<t t-call="number_to_words.ntw_test_places"/></div></t>',
        })
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        places = self.Anchor.search([('view_id', '=', wrapper.id)])
        self.assertIn("Block: totals", places.mapped('name'))
        self.assertEqual(places.mapped('template_ids'), self.view)
        self.assertEqual(self.Anchor._guess_record_var(wrapper), 'doc')

        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        place = places.filtered(lambda p: p.name == "Block: totals")
        rule = self.env['number.to.words.rule'].create({
            'name': "Wrapped", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        # the change is attached to the template that holds the place, not to the wrapper
        self.assertEqual(rule.report_view_ids.inherit_id, self.view)
        partner = self.env['res.partner'].create({'name': "P", 'color': 2})
        html = self.env['ir.qweb']._render('number_to_words.ntw_test_wrapper', {'doc': partner})
        self.assertIn('Two', str(html))


    def test_only_displayed_fields_are_offered_next_to_a_form_field(self):
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Offered", 'model_id': self.env['ir.model']._get('res.partner').id,
            'line_ids': [(0, 0, {'field_id': field('id').id,
                                 'anchor_field_id': field('name').id, 'mode': 'number'})],
        })
        names = rule.form_field_names
        self.assertIn('name', names)
        # shown only by our own rule, or not shown at all: not places to choose
        self.assertNotIn('id', names)
        self.assertNotIn('email_normalized', names)
        self.assertNotIn('active_lang_count', names)  # invisible technical field
        self.assertEqual(names, sorted(set(names)))


    def test_places_are_readable_and_document_level(self):
        self.Anchor._ensure_places(self.view, 'res.partner', 'doc')
        names = self.Anchor.search([('view_id', '=', self.view.id)]).mapped('name')
        related = self.env['ir.model.fields']._get('res.partner', 'parent_id').field_description
        name = self.env['ir.model.fields']._get('res.partner', 'name').field_description
        self.assertIn(f"Field: {related} › {name}", names)       # chain written with real labels
        self.assertIn("Block: grand total box", names)           # readable block name
        self.assertFalse([n for n in names if 'line' in n.lower().split()], names)  # inside a loop
        self.assertFalse([n for n in names if '(' in n])          # no method calls
        self.assertNotIn("Block: line row", names)
        self.assertEqual(len(names), len(set(names)))             # no duplicated place


    def _layouts(self):
        """Two layouts of the same report that share the same places."""
        View = self.env['ir.ui.view']
        layouts = View
        for index in (1, 2):
            layouts |= View.create({
                'name': f'ntw.test.layout{index}', 'type': 'qweb', 'key': f'number_to_words.ntw_test_layout{index}',
                'arch': f'<t t-name="number_to_words.ntw_test_layout{index}"><div class="page">'
                        '<h2>Label</h2><span t-field="doc.name"/></div></t>',
            })
        wrapper = View.create({
            'name': 'ntw.test.layouts', 'type': 'qweb', 'key': 'number_to_words.ntw_test_layouts',
            'arch': '<t t-name="number_to_words.ntw_test_layouts"><div>'
                    '<t t-if="layout == 1" t-call="number_to_words.ntw_test_layout1"/>'
                    '<t t-if="layout == 2" t-call="number_to_words.ntw_test_layout2"/></div></t>',
        })
        return wrapper, layouts

    def test_a_place_shared_by_several_layouts_is_one_place_for_all(self):
        wrapper, layouts = self._layouts()
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', wrapper.id), ('name', 'ilike', 'Field:')])
        self.assertEqual(len(place), 1)
        self.assertEqual(place.template_ids, layouts)
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Layouts", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        self.assertEqual(rule.report_view_ids.mapped('inherit_id'), layouts)  # one change per layout
        partner = self.env['res.partner'].create({'name': "P", 'color': 5})
        for layout in (1, 2):
            html = self.env['ir.qweb']._render('number_to_words.ntw_test_layouts', {'doc': partner, 'layout': layout})
            self.assertIn('Five', str(html), layout)

    def test_a_place_of_another_report_is_refused_and_cleared(self):
        from odoo.tests import Form
        wrapper, layouts = self._layouts()
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', wrapper.id), ('name', 'ilike', 'Field:')])
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Other", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        # the report is changed afterwards: the place no longer belongs to it
        with self.assertRaises(Exception):
            rule.report_view_id = self.view
        # in the form, the place is cleared so the user chooses it again
        report = self.env['ir.actions.report'].create({
            'name': "Test places", 'model': 'res.partner', 'report_type': 'qweb-html',
            'report_name': 'number_to_words.ntw_test_places',
        })
        with self.assertRaisesRegex(AssertionError, "report_anchor_id.*required"):
            with Form(rule) as form:
                form.report_id = report
                self.assertEqual(form.report_view_id, self.view)
                form.report_line_ids.edit(0)  # the cleared place must be chosen again

    def test_upgrade_replaces_places_of_another_report(self):
        from ..tools.maintenance import repoint_report_lines
        wrapper, layouts = self._layouts()
        other = self.env['ir.ui.view'].create({
            'name': 'ntw.test.other', 'type': 'qweb', 'key': 'number_to_words.ntw_test_other',
            'arch': '<t t-name="number_to_words.ntw_test_other"><div><span t-field="doc.email"/></div></t>',
        })
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', wrapper.id), ('name', 'ilike', 'Field:')])
        rule = self.env['number.to.words.rule'].create({
            'name': "Upgrade", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        self.assertTrue(rule.report_view_ids)
        # the report of the rule is changed behind the scenes (old data): the place is not part of it
        self.env.cr.execute("UPDATE number_to_words_rule SET report_view_id = %s WHERE id = %s", (other.id, rule.id))
        rule.invalidate_recordset()
        repoint_report_lines(self.env)
        self.assertFalse(rule.report_view_ids)           # nothing keeps pointing at the other report
        self.assertFalse(rule.line_ids.report_anchor_id)  # the user chooses the place again
        self.assertFalse(rule.line_ids.xpath_expr)


    def test_a_rule_can_be_switched_off_and_on(self):
        wrapper, layouts = self._layouts()
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', wrapper.id), ('name', 'ilike', 'Field:')])
        report_rule = self.env['number.to.words.rule'].create({
            'name': "Toggle report", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        form_rule = self.env['number.to.words.rule'].create({
            'name': "Toggle form", 'model_id': self.env['ir.model']._get('res.partner').id,
            'line_ids': [(0, 0, {'field_id': field('color').id, 'anchor_field_id': field('name').id,
                                 'mode': 'number'})],
        })
        partner = self.env['res.partner'].create({'name': "P", 'color': 5})
        render = lambda layout: str(self.env['ir.qweb']._render(
            'number_to_words.ntw_test_layouts', {'doc': partner, 'layout': layout}))
        views = report_rule.report_view_ids
        self.assertEqual(len(views), 2)
        self.assertIn('Five', render(1))

        report_rule.active = False
        form_rule.active = False
        self.assertFalse(report_rule.with_context(active_test=False).report_view_ids.filtered('active'))
        self.assertFalse(form_rule.view_id.active)
        self.assertNotIn('Five', render(1))                      # the words are gone from the report
        self.assertNotIn('number_to_words', self.env['res.partner'].get_view(form_rule.base_view_id.id, 'form')['arch'])

        report_rule.active = True
        form_rule.active = True
        self.assertEqual(report_rule.report_view_ids, views)     # the same views came back: no duplicate
        self.assertTrue(form_rule.view_id.active)
        self.assertIn('Five', render(1))
        self.assertIn('number_to_words', self.env['res.partner'].get_view(form_rule.base_view_id.id, 'form')['arch'])

    def test_a_broken_rule_can_still_be_switched_off(self):
        wrapper, layouts = self._layouts()
        other = self.env['ir.ui.view'].create({
            'name': 'ntw.test.other2', 'type': 'qweb', 'key': 'number_to_words.ntw_test_other2',
            'arch': '<t t-name="number_to_words.ntw_test_other2"><div/></t>',
        })
        self.Anchor._ensure_places(wrapper, 'res.partner', 'doc')
        place = self.Anchor.search([('view_id', '=', wrapper.id), ('name', 'ilike', 'Field:')])
        field = lambda name: self.env['ir.model.fields']._get('res.partner', name)
        rule = self.env['number.to.words.rule'].create({
            'name': "Broken", 'model_id': self.env['ir.model']._get('res.partner').id,
            'target': 'report', 'report_view_id': wrapper.id,
            'line_ids': [(0, 0, {'target': 'report', 'field_id': field('color').id, 'mode': 'number',
                                 'report_anchor_id': place.id})],
        })
        self.env.cr.execute("UPDATE number_to_words_rule SET report_view_id = %s WHERE id = %s", (other.id, rule.id))
        rule.invalidate_recordset()
        rule.active = False                      # switching off never fails
        self.assertFalse(rule.active)
        with self.assertRaises(Exception):       # switching on checks the rule again
            rule.active = True
