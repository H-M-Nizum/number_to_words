import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { formatInteger } from "@web/views/fields/formatters";
import { parseInteger } from "@web/views/fields/parsers";

import { useEffect, useState } from "@odoo/owl";

/**
 * Float / Integer / Monetary field showing its value in words below it.
 *
 * Usage: <field name="amount_total" widget="number_to_words"
 *               options="{'lang': 'bn', 'mode': 'currency'}"/>
 *
 * Options:
 *  - lang: "en" or "bn" (default: module settings / user language)
 *  - mode: "number" (default) or "currency"
 *  - currency_field: currency field name for the currency mode
 *    (default: "currency_id")
 *  - words_only: true to show only the words, not the number
 */
export class NumberToWordsField extends FloatField {
    static template = "number_to_words.NumberToWordsField";
    static props = {
        ...FloatField.props,
        lang: { type: String, optional: true },
        mode: { type: String, optional: true },
        currencyField: { type: String, optional: true },
        wordsOnly: { type: Boolean, optional: true },
    };
    static defaultProps = {
        ...FloatField.defaultProps,
        mode: "number",
        currencyField: "currency_id",
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.wordsState = useState({ text: "" });
        this.requestId = 0;
        useEffect(
            (value, currencyId) => {
                this.updateWords(value, currencyId);
            },
            () => [this.value, this.currencyId]
        );
    }

    get isInteger() {
        return this.props.record.fields[this.props.name].type === "integer";
    }

    get currencyId() {
        if (this.props.mode !== "currency") {
            return false;
        }
        const currency = this.props.record.data[this.props.currencyField];
        return Array.isArray(currency) ? currency[0] : currency?.id || false;
    }

    parse(value) {
        return this.isInteger ? parseInteger(value, { allowOperation: true }) : super.parse(value);
    }

    get formattedValue() {
        if (this.isInteger && this.props.formatNumber) {
            return formatInteger(this.value);
        }
        return super.formattedValue;
    }

    async updateWords(value, currencyId) {
        const requestId = ++this.requestId;
        if (value === false || value === undefined || value === null) {
            this.wordsState.text = "";
            return;
        }
        const text = await this.orm.call("number.to.words", "to_words", [value], {
            lang: this.props.lang || null,
            mode: this.props.mode,
            currency_id: currencyId || null,
        });
        // Ignore outdated answers when the value changed in the meantime.
        if (requestId === this.requestId) {
            this.wordsState.text = text;
        }
    }
}

export const numberToWordsField = {
    ...floatField,
    component: NumberToWordsField,
    displayName: _t("Number to Words"),
    supportedTypes: ["float", "monetary", "integer"],
    supportedOptions: [
        ...floatField.supportedOptions,
        {
            label: _t("Language"),
            name: "lang",
            type: "string",
            help: _t("'en' for English or 'bn' for Bangla. Empty: module settings."),
        },
        {
            label: _t("Mode"),
            name: "mode",
            type: "string",
            help: _t("'number' or 'currency'."),
        },
        {
            label: _t("Currency field"),
            name: "currency_field",
            type: "field",
            availableTypes: ["many2one"],
        },
    ],
    extractProps(fieldInfo, dynamicInfo) {
        const { options } = fieldInfo;
        return {
            ...floatField.extractProps(fieldInfo, dynamicInfo),
            lang: options.lang,
            mode: options.mode || "number",
            currencyField: options.currency_field || "currency_id",
            wordsOnly: !!options.words_only,
        };
    },
};

registry.category("fields").add("number_to_words", numberToWordsField);
