# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    number_to_words_language_id = fields.Many2one(
        'number.to.words.language', string="Words Language",
        config_parameter='number_to_words.language_id',
        help="Always write the words in this language. Empty: follow the language of the user.",
    )
    number_to_words_text_case = fields.Selection(
        selection=[
            ('title', "Title Case"),
            ('lower', "lower case"),
            ('upper', "UPPER CASE"),
        ],
        string="English Text Case",
        default='title',
        config_parameter='number_to_words.text_case',
    )
    number_to_words_append_only = fields.Boolean(
        string="Append \"Only\" to Amounts",
        config_parameter='number_to_words.append_only',
    )
    number_to_words_fraction_style = fields.Selection(
        selection=[
            ('words', "In words (… and Fifty Paisa)"),
            ('fraction', "As a fraction (… and 50/100)"),
        ],
        string="Subunit Style",
        default='words',
        config_parameter='number_to_words.fraction_style',
    )
    number_to_words_cheque_style = fields.Boolean(
        string="Cheque Style (*** … ***)",
        config_parameter='number_to_words.cheque_style',
    )
