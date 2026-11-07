# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Generic number to words engine.

It knows no word at all: everything comes from the configuration of a language
(the words of the numbers, the scales of a numbering system and the small words
that glue them), see ``number.to.words.language``.
"""


class WordsError(Exception):
    """The configuration of the language cannot write the number."""


class LanguageData:
    """The configuration of a language, read once and used for many numbers."""

    def __init__(self, language, system=None):
        system = system or language.system_id or language.system_ids[:1]
        self.name = language.name
        self.numbers = {number.value: number.word for number in language.number_ids}
        self.separator = language.separator if language.separator is not False else ' '
        self.tens_joiner = language.tens_joiner if language.tens_joiner is not False else ' '
        self.minus = language.word_minus or ''
        self.point = language.word_point or ''
        self.and_word = language.word_and or ''
        self.only = language.word_only or ''
        self.digits = language.digits or '0123456789'
        # biggest scale first: (value, word, joiner)
        self.scales = sorted(
            ((10 ** scale.exponent, scale.word, scale.joiner if scale.joiner is not False else ' ')
             for scale in system.scale_ids),
            reverse=True,
        )

    def integer(self, number):
        """The words of a non-negative integer."""
        if number < 0:
            raise ValueError("integer expects a non-negative integer")
        if number in self.numbers:
            return self.numbers[number]
        for value, word, joiner in self.scales:
            if number >= value:
                quantity, rest = divmod(number, value)
                text = self.integer(quantity) + joiner + word
                return text + self.separator + self.integer(rest) if rest else text
        # no scale fits: tens and units, e.g. twenty-one
        tens, unit = (number // 10) * 10, number % 10
        if number < 100 and tens in self.numbers and unit in self.numbers:
            return self.numbers[tens] + self.tens_joiner + self.numbers[unit]
        raise WordsError(
            f"{self.name} has no word for {number}: add it in the number words or add the scale it needs.")

    def read_digits(self, digits):
        """Read digit by digit: '34' -> 'Three Four'."""
        return self.separator.join(self.integer(int(digit)) for digit in digits)

    def translate_digits(self, text):
        """Write the figures of ``text`` with the digits of the language."""
        return str(text).translate(str.maketrans('0123456789', self.digits))
