# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    number_to_words_name_ids = fields.One2many(
        'number.to.words.currency.name', 'currency_id', string="Names in Words",
        help="How the currency is called in each language, e.g. Taka / Paisa or টাকা / পয়সা.",
    )

    def amount_to_text(self, amount):
        """Add the configured languages to the core amount in words.

        Every Odoo feature relying on this method (invoice "amount in
        letters", check printing, ...) benefits from it. When no configured
        language applies, the core behaviour is kept untouched.
        """
        self.ensure_one()
        service = self.env['number.to.words']
        if not self.env.context.get('number_to_words_core') and service._should_override_currency_text():
            return service.to_words(amount, mode='currency', currency_id=self.id)
        return super().amount_to_text(amount)
