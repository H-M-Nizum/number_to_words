# Part of Odoo. See LICENSE file for full copyright and licensing details.
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from odoo import api, models
from odoo.exceptions import UserError

try:
    from num2words import CONVERTER_CLASSES, num2words
except ImportError:  # the library is optional in Odoo
    CONVERTER_CLASSES, num2words = {}, None

from ..tools.engine import LanguageData, WordsError

PARAM_PREFIX = 'number_to_words.'





class NumberToWords(models.AbstractModel):
    _name = 'number.to.words'
    _description = 'Number to Words Converter'


    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _get_flag(self, key):
        return self._get_param(key, 'False') in ('True', 'true', '1')

    @api.model
    def _settings_language(self):
        """The language forced in the settings (empty: follow the user)."""
        language_id = self._get_param('language_id', '')
        language = self.env['number.to.words.language'].sudo().browse(int(language_id)) if language_id else None
        return language if language and language.exists() and language.active else None

    @api.model
    def _resolve_language(self, lang=None):
        """The configured language record to write in, or an empty recordset.

        ``lang`` may be a language code ('bn', 'bn_BD'), a language record, or empty: then the language of
        the settings, then the one of the user. When no configured language applies (Spanish, Arabic...)
        the empty result tells ``to_words`` to use the engine of Odoo itself.
        """
        Language = self.env['number.to.words.language'].sudo()
        if isinstance(lang, models.BaseModel):
            return lang.sudo() if lang else Language.browse()
        if lang and lang != 'user':
            return Language.search([('code', 'in', [lang, lang.split('_')[0]])], limit=1)
        forced = self._settings_language()
        if forced:
            return forced
        user_code = (self.env.lang or 'en_US').split('_')[0]
        return Language.search([('code', '=', user_code)], limit=1)

    @api.model
    def _requested_code(self, lang=None):
        """The language code asked for (explicit, else the one of the user)."""
        if isinstance(lang, str) and lang and lang != 'user':
            return lang
        return self.env.lang or 'en_US'

    @api.model
    def _num2words_code(self, code):
        """The code of Odoo's own library for ``code`` (es_MX -> es), or None."""
        if num2words is None:
            return None
        for candidate in (code, code.split('_')[0]):
            if candidate in CONVERTER_CLASSES:
                return candidate
        return None

    @api.model
    def _should_override_currency_text(self):
        """Whether ``res.currency.amount_to_text`` must use this module."""
        if self._settings_language():
            return True
        user_code = (self.env.lang or 'en_US').split('_')[0]
        language = self.env['number.to.words.language'].sudo().search([('code', '=', user_code)], limit=1)
        return bool(language.override_core_amount_text)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def to_words(self, value, lang=None, mode='number', currency_id=None):
        """Convert ``value`` to words.

        :param value: int, float, Decimal or numeric string
        :param lang: code of a configured language (``'en'``, ``'bn'``...); default from the
                     settings, then from the language of the user
        :param mode: ``'number'`` (decimals read digit by digit) or
                     ``'currency'`` (unit and subunit of the currency)
        :param currency_id: id of the ``res.currency`` used in currency mode
        :return: the text, or ``''`` when ``value`` is empty / not a number
        """
        amount = self._to_decimal(value)
        if amount is None:
            return ''
        language = self._resolve_language(lang)
        if not language:
            # no configured language: Odoo's own library writes it (Spanish, Arabic, French...)
            text = self._library_words(amount, self._requested_code(lang), mode, currency_id)
            if text is not None:
                return text
            language = self.env['number.to.words.language'].sudo().search([('code', '=', 'en')], limit=1) or \
                self.env['number.to.words.language'].sudo().search([], limit=1)
        data = LanguageData(language)
        try:
            if mode == 'currency':
                text = self._currency_words(amount, language, data, currency_id)
                if self._get_flag('append_only') and data.only:
                    text += data.separator + data.only
                if self._get_flag('cheque_style'):
                    text = f"*** {text} ***"
            else:
                text = self._number_words(amount, data)
        except WordsError as error:
            raise UserError(str(error)) from error
        return self._apply_case(text, language)

    @api.model
    def amount_to_words(self, amount, currency, lang=None):
        """Shortcut for Python/QWeb callers owning a currency record."""
        return self.to_words(amount, lang=lang, mode='currency', currency_id=currency.id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @api.model
    def _to_decimal(self, value):
        if value is None or value is False or value == '':
            return None
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None
        return amount if amount.is_finite() else None

    @api.model
    def _library_words(self, amount, code, mode, currency_id):
        """Words from the library of Odoo (the same engine as Odoo's own amount in letters), or None
        when the language is not supported."""
        library_code = self._num2words_code(code)
        if not library_code:
            return None
        try:
            if mode == 'currency':
                currency = self.env['res.currency'].browse(currency_id) if currency_id else self.env.company.currency_id
                Lang = self.env['res.lang'].sudo()
                installed = Lang.search([('code', '=', code)], limit=1) or Lang.search(
                    [('code', '=like', code.split('_')[0] + '%')], limit=1)
                # Odoo's own method: the translated names of the currency and the library
                text = currency.with_context(
                    lang=installed.code if installed else self.env.lang, number_to_words_core=True,
                ).amount_to_text(float(amount))
                if self._get_flag('cheque_style'):
                    text = f"*** {text} ***"
                return text
            value = int(amount) if amount == amount.to_integral_value() else float(amount)
            return self._apply_plain_case(num2words(value, lang=library_code))
        except (NotImplementedError, OverflowError, ValueError, TypeError):
            return None

    @api.model
    def _apply_plain_case(self, text):
        case = self._get_param('text_case', 'title')
        return text.upper() if case == 'upper' else text.lower() if case == 'lower' else text.title()

    @api.model
    def _number_words(self, amount, data):
        sign = data.minus + data.separator if amount < 0 and data.minus else ''
        integral, _sep, fractional = format(abs(amount), 'f').partition('.')
        text = data.integer(int(integral))
        fractional = fractional.rstrip('0')
        if fractional:
            text += f"{data.separator}{data.point}{data.separator}{data.read_digits(fractional)}"
        return sign + text

    @api.model
    def _currency_labels(self, currency, language):
        """(unit, subunit) of the currency in the language: configured on the currency."""
        name = currency.sudo().number_to_words_name_ids.filtered(lambda n: n.language_id == language)[:1]
        if name:
            return name.unit, name.subunit or ''
        english = currency.with_context(lang='en_US')
        return english.currency_unit_label or currency.name, english.currency_subunit_label or ''

    @api.model
    def _currency_words(self, amount, language, data, currency_id):
        currency = self.env['res.currency'].browse(currency_id) if currency_id else self.env.company.currency_id
        currency.ensure_one()
        decimal_places = currency.decimal_places
        amount = amount.quantize(Decimal(1).scaleb(-decimal_places), rounding=ROUND_HALF_UP)

        sign = data.minus + data.separator if amount < 0 and data.minus else ''
        integral, _sep, fractional = format(abs(amount), 'f').partition('.')
        unit, subunit = self._currency_labels(currency, language)

        text = f"{data.integer(int(integral))}{data.separator}{unit}".strip()
        if fractional and int(fractional):
            if self._get_param('fraction_style', 'words') == 'fraction':
                sub_text = data.translate_digits(f"{int(fractional)}/{10 ** decimal_places}")
            else:
                sub_text = f"{data.integer(int(fractional))}{data.separator}{subunit}".strip()
            text += f"{data.separator}{data.and_word}{data.separator}{sub_text}" if data.and_word else f"{data.separator}{sub_text}"
        return sign + text

    @api.model
    def _apply_case(self, text, language):
        if not language.apply_text_case:
            return text
        case = self._get_param('text_case', 'title')
        if case == 'upper':
            return text.upper()
        if case == 'lower':
            return text.lower()
        return text
