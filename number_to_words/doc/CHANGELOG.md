# Changelog

## 19.0.1.0.0 — first release
* Many languages: English, Bangla, Hindi and Urdu are built in; Spanish, Arabic, French, German, Portuguese, Russian,
  Turkish, Indonesian, Japanese, Korean and about 40 more are written automatically (Odoo's own `num2words` engine)
  in the language of the user.
* Amount in words for any model, any integer, float or monetary field, on forms and PDF reports.
* Display Rules: choose the model, the field, where it is shown (form view or PDF report) and the position;
  rules can be switched on and off with one click.
* PDF reports: the place is chosen from a list written in plain words (no XPath); it works for reports built from
  several templates and for several layouts of the same report.
* `number_to_words` field widget, Python / QWeb service `env['number.to.words'].to_words(...)`.
* Bangla and English for Odoo's own "amount in letters" (invoices, checks) when the user's language is Bangla.
* Settings: language, text case, "Only / মাত্র", subunit style, cheque style.
* English and Bangla words, scales and currency names are built in; no external Python dependency.
