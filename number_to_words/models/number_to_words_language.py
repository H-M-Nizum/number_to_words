# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class NumberToWordsLanguage(models.Model):
    """A language the numbers can be written in. Everything the engine says comes
    from here: nothing is written in the code."""
    _name = 'number.to.words.language'
    _description = 'Amount in Words Language'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Short code of the language, e.g. en, bn, hi. It is matched with the language of the user "
             "(en_US -> en) and used in the widget and report options.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # -- words that glue the number together ------------------------------
    word_minus = fields.Char(string="Negative", help="Written before a negative number, e.g. Minus.")
    word_point = fields.Char(string="Decimal Point", help="Written between the integer and the decimals, e.g. Point.")
    word_and = fields.Char(string="And", help="Written between the amount and the subunit, e.g. and.")
    word_only = fields.Char(string="Only", help="Written at the end of an amount when \"Append Only\" is on, e.g. Only.")
    separator = fields.Char(
        string="Word Separator", default=' ', trim=False,
        help="Written between the parts of a number. Usually a space.",
    )
    tens_joiner = fields.Char(
        string="Tens Joiner", default=' ', trim=False,
        help="Written between tens and units when the number is not in the word table, "
             "e.g. a hyphen in Twenty-One.",
    )
    digits = fields.Char(
        string="Digits", size=10,
        help="The ten digits of the language, from 0 to 9 (e.g. ০১২৩৪৫৬৭৮৯), used when a fraction like 50/100 "
             "is written with figures. Empty: the usual digits.",
    )
    apply_text_case = fields.Boolean(
        string="Use the Text Case Setting",
        help="Apply the Title / lower / UPPER case of the settings to this language.",
    )
    override_core_amount_text = fields.Boolean(
        string="Use for Odoo's Amount in Letters",
        help="Invoices, checks and every feature using Odoo's own \"amount in letters\" write the amount "
             "with this language when it is the language of the user.",
    )

    system_id = fields.Many2one(
        'number.to.words.system', string="Numbering System", domain="[('language_id', '=', id)]",
        help="The way big numbers are written (scales like thousand, lakh, crore).",
    )
    number_ids = fields.One2many('number.to.words.number', 'language_id', string="Number Words", copy=True)
    system_ids = fields.One2many('number.to.words.system', 'language_id', string="Numbering Systems")
    number_count = fields.Integer(compute='_compute_number_count')

    _code_unique = models.Constraint('unique(code)', "Each language needs its own code.")

    @api.depends('number_ids')
    def _compute_number_count(self):
        for language in self:
            language.number_count = len(language.number_ids)

    @api.constrains('number_ids', 'digits')
    def _check_digits(self):
        for language in self:
            if language.digits and len(language.digits) != 10:
                raise ValidationError(self.env._("The digits of a language must be exactly ten characters."))

    def _words_missing(self):
        """Values from 0 to 9 that have no word yet (they are needed to read decimals)."""
        self.ensure_one()
        return [value for value in range(10) if value not in set(self.number_ids.mapped('value'))]


class NumberToWordsNumber(models.Model):
    _name = 'number.to.words.number'
    _description = 'Amount in Words Number Word'
    _order = 'language_id, value'

    language_id = fields.Many2one('number.to.words.language', required=True, ondelete='cascade', index=True)
    value = fields.Integer(required=True, help="The number, e.g. 7, 13 or 40.")
    word = fields.Char(required=True, translate=False, help="How the number is written, e.g. Seven.")

    _value_unique = models.Constraint(
        'unique(language_id, value)', "This number already has a word in this language.")

    @api.constrains('value')
    def _check_value(self):
        for number in self:
            if number.value < 0:
                raise ValidationError(self.env._("Only positive numbers have a word."))


class NumberToWordsSystem(models.Model):
    _name = 'number.to.words.system'
    _description = 'Amount in Words Numbering System'
    _order = 'language_id, sequence, id'

    name = fields.Char(required=True, translate=True)
    language_id = fields.Many2one('number.to.words.language', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    scale_ids = fields.One2many('number.to.words.scale', 'system_id', string="Scales", copy=True)


class NumberToWordsScale(models.Model):
    """"Hundred", "Thousand", "Lakh"...: the word written after a quantity."""
    _name = 'number.to.words.scale'
    _description = 'Amount in Words Scale'
    _order = 'system_id, exponent'

    system_id = fields.Many2one('number.to.words.system', required=True, ondelete='cascade', index=True)
    exponent = fields.Integer(
        string="Power of Ten", required=True,
        help="2 for a hundred, 3 for a thousand, 5 for a lakh, 7 for a crore, 6 for a million...",
    )
    value = fields.Char(string="Value", compute='_compute_value')
    word = fields.Char(required=True, help="The word, e.g. Thousand.")
    joiner = fields.Char(
        string="Joiner", default=' ', trim=False,
        help="Written between the quantity and the word: a space (One Thousand) or nothing (একশো).",
    )

    _exponent_unique = models.Constraint(
        'unique(system_id, exponent)', "This scale already exists in this numbering system.")

    @api.depends('exponent')
    def _compute_value(self):
        for scale in self:
            scale.value = f"{10 ** scale.exponent:,}" if 0 < scale.exponent < 60 else ''

    @api.constrains('exponent')
    def _check_exponent(self):
        for scale in self:
            if not 0 < scale.exponent < 60:
                raise ValidationError(self.env._("The power of ten must be between 1 and 59."))


class NumberToWordsCurrencyName(models.Model):
    """How a currency is called in a language."""
    _name = 'number.to.words.currency.name'
    _description = 'Amount in Words Currency Name'
    _order = 'currency_id, language_id'

    currency_id = fields.Many2one('res.currency', required=True, ondelete='cascade', index=True)
    language_id = fields.Many2one('number.to.words.language', required=True, ondelete='cascade', index=True)
    unit = fields.Char(string="Unit", required=True, help="e.g. Taka or টাকা.")
    subunit = fields.Char(string="Subunit", help="e.g. Paisa or পয়সা.")

    _currency_language_unique = models.Constraint(
        'unique(currency_id, language_id)', "This currency already has a name in this language.")
