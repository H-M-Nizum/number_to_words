# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Names of the most common currencies in the built-in languages: language code -> ISO code -> (unit, subunit).

They are only a starting point and are plain data (``number.to.words.currency.name``).
"""

CURRENCY_NAMES = {
    'bn': {
        'BDT': ('টাকা', 'পয়সা'),
        'USD': ('ডলার', 'সেন্ট'),
        'EUR': ('ইউরো', 'সেন্ট'),
        'GBP': ('পাউন্ড', 'পেনি'),
        'INR': ('রুপি', 'পয়সা'),
        'PKR': ('রুপি', 'পয়সা'),
        'SAR': ('রিয়াল', 'হালালা'),
        'AED': ('দিরহাম', 'ফিলস'),
        'MYR': ('রিঙ্গিত', 'সেন'),
        'CAD': ('ডলার', 'সেন্ট'),
        'AUD': ('ডলার', 'সেন্ট'),
        'JPY': ('ইয়েন', ''),
    },
    'hi': {
        'INR': ('रुपये', 'पैसे'),
        'USD': ('डॉलर', 'सेंट'),
        'EUR': ('यूरो', 'सेंट'),
        'GBP': ('पाउंड', 'पेंस'),
        'BDT': ('टका', 'पैसे'),
        'PKR': ('रुपये', 'पैसे'),
        'SAR': ('रियाल', 'हलाला'),
        'AED': ('दिरहम', 'फ़िल्स'),
        'CAD': ('डॉलर', 'सेंट'),
        'AUD': ('डॉलर', 'सेंट'),
        'JPY': ('येन', ''),
    },
    'ur': {
        'PKR': ('روپے', 'پیسے'),
        'INR': ('روپے', 'پیسے'),
        'USD': ('ڈالر', 'سینٹ'),
        'EUR': ('یورو', 'سینٹ'),
        'GBP': ('پاؤنڈ', 'پینس'),
        'BDT': ('ٹکا', 'پیسے'),
        'SAR': ('ریال', 'ہلالہ'),
        'AED': ('درہم', 'فلس'),
        'CAD': ('ڈالر', 'سینٹ'),
        'AUD': ('ڈالر', 'سینٹ'),
        'JPY': ('ین', ''),
    },
}


def load_currency_names(env):
    """Give the common currencies a name in each built-in language (never overwrites an existing name)."""
    Name = env['number.to.words.currency.name']
    for code, names in CURRENCY_NAMES.items():
        language = env['number.to.words.language'].with_context(active_test=False).search([('code', '=', code)], limit=1)
        if not language:
            continue
        currencies = env['res.currency'].with_context(active_test=False).search([('name', 'in', list(names))])
        existing = set(Name.search([('language_id', '=', language.id)]).mapped('currency_id').ids)
        Name.create([{
            'currency_id': currency.id, 'language_id': language.id,
            'unit': names[currency.name][0], 'subunit': names[currency.name][1],
        } for currency in currencies if currency.id not in existing])
