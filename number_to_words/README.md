# Amount in Words (English & Bangla) — Odoo 19

Convert integers, decimals and currency amounts to words on any model, field or report.
One single module: it knows no model or field, you choose them in *Display Rules*. English, Bangla, Hindi and Urdu are built in; Spanish, Arabic, French, German and about 40 more languages are written automatically in the language of the user.

## Install
Copy the module folder into your addons path, update the apps list and install
`number_to_words`. It is a single module that works for every model: there is nothing to install per app.

## Configure
* **Amount in Words → Settings**: language, text case, "Only", subunit style, cheque style.
* **Amount in Words → Display Rules**: one rule per model (form view or PDF report),
  one line per numeric field with its anchor and position.

## Python / QWeb API
```python
self.env['number.to.words'].to_words(150.5, lang='bn', mode='currency', currency_id=cur.id)
```
* `mode='number'`: `12.34` → "Twelve Point Three Four"
* `mode='currency'`: unit and subunit of the currency
* In QWeb: `<span t-out="env['number.to.words'].to_words(o.amount_total, mode='currency', currency_id=o.currency_id.id)"/>`

## Field widget
```xml
<field name="amount_total" widget="number_to_words"
       options="{'mode': 'currency', 'lang': 'bn', 'words_only': True}"/>
```

## Tests
`odoo-bin -d <db> -i number_to_words --test-tags /number_to_words --stop-after-init`

## License
LGPL-3. See the `LICENSE` file. Author: H.M.Nizum.
