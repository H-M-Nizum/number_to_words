# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools.names import GENERATED_VIEW_PREFIX


class NumberToWordsRule(models.Model):
    _name = 'number.to.words.rule'
    _description = 'Amount in Words Display Rule'
    _order = 'model_id, sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        'ir.model', string="Model", required=True, ondelete='cascade',
        domain=[('transient', '=', False)],
        help="Model whose form view shows the words.",
    )
    model_name = fields.Char(related='model_id.model', string="Model Name")
    target = fields.Selection(
        [('form', "Form view (on screen)"), ('report', "PDF report / QWeb template")],
        string="Show In", default='form', required=True,
    )
    base_view_id = fields.Many2one(
        'ir.ui.view', string="Form View",
        compute='_compute_base_view_id', store=True, readonly=False, ondelete='cascade',
        domain="[('model', '=', model_name), ('type', '=', 'form'), ('mode', '=', 'primary')]",
    )
    report_id = fields.Many2one(
        'ir.actions.report', string="Report", ondelete='set null',
        domain="[('model', '=', model_name), ('report_type', 'in', ['qweb-pdf', 'qweb-html'])]",
        help="The printed report of the model, e.g. Quotation / Order.",
    )
    report_name = fields.Char(related='report_id.report_name', string="Report Name")
    report_view_id = fields.Many2one(
        'ir.ui.view', string="Report Template", ondelete='cascade',
        domain="[('type', '=', 'qweb'), ('inherit_id', '=', False), ('key', '=like', (report_name or '') + '%')]",
        help="The QWeb template of the report that contains the content, "
             "usually the one ending with _document.",
    )
    record_var = fields.Char(
        string="Record Variable", compute='_compute_record_var', store=True, readonly=False,
        help="Name of the variable holding the record in the template ('doc', 'o', 'product'...). "
             "It is detected from the report template.",
    )
    form_field_names = fields.Json(
        string="Fields of the Form", compute='_compute_form_field_names',
        help="Names of the fields displayed in the chosen form view (the places offered to the lines).",
    )
    line_ids = fields.One2many('number.to.words.rule.line', 'rule_id', string="All Lines", copy=True)
    # Each "Show In" choice has its own lines, so switching never loses anything.
    form_line_ids = fields.One2many(
        'number.to.words.rule.line', 'rule_id', string="Form Fields",
        domain=[('target', '=', 'form')], context={'default_target': 'form'},
    )
    report_line_ids = fields.One2many(
        'number.to.words.rule.line', 'rule_id', string="Report Fields",
        domain=[('target', '=', 'report')], context={'default_target': 'report'},
    )
    view_id = fields.Many2one('ir.ui.view', string="Generated View", readonly=True, copy=False, ondelete='set null')
    report_view_ids = fields.Many2many(
        'ir.ui.view', 'number_to_words_rule_view_rel', 'rule_id', 'view_id',
        string="Generated Report Views", readonly=True, copy=False,
        help="One change per report template the lines are placed in.",
    )

    # ------------------------------------------------------------------
    @api.model
    def _default_form_view(self, model_name):
        return self.env['ir.ui.view'].search([
            ('model', '=', model_name), ('type', '=', 'form'), ('mode', '=', 'primary'),
        ], order='priority, id', limit=1)

    @api.depends('model_id', 'target')
    def _compute_base_view_id(self):
        for rule in self:
            if rule.target == 'form' and rule.model_id:
                rule.base_view_id = self._default_form_view(rule.model_id.model)
            else:
                rule.base_view_id = False

    @api.depends('base_view_id', 'model_id')
    def _compute_form_field_names(self):
        for rule in self:
            names = []
            if rule.base_view_id and rule.model_id and rule.model_id.model in self.env:
                combined = self.env[rule.model_id.model].get_view(rule.base_view_id.id, 'form')['arch']
                tree = etree.fromstring(combined)
                # the words inserted by our own rules are not places to choose
                for node in tree.xpath("//field[@widget='number_to_words']"):
                    node.getparent().remove(node)
                # fields hidden in the form are not places the words could be seen next to
                names = sorted({
                    node.get('name') for node in tree.xpath('//field')
                    if node.get('name') and node.get('invisible') not in ('1', 'True', 'true')
                })
            rule.form_field_names = names

    @api.constrains('target', 'base_view_id', 'report_view_id', 'record_var')
    def _check_target(self):
        for rule in self:
            if rule.target == 'form' and not rule.base_view_id:
                raise ValidationError(self.env._("Please choose the form view."))
            if rule.target == 'report':
                if not rule.report_view_id:
                    raise ValidationError(self.env._("Please choose the report template."))
                if not (rule.record_var or '').isidentifier():
                    raise ValidationError(self.env._("The record variable must be a valid name, e.g. doc or o."))

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.form_line_ids = [(5, 0, 0)]
        self.report_line_ids = [(5, 0, 0)]

    @api.onchange('report_id')
    def _onchange_report_id(self):
        """Pick the template holding the content of the chosen report."""
        self.report_view_id = False
        if self.report_id:
            Views = self.env['ir.ui.view']
            name = self.report_id.report_name
            self.report_view_id = (
                Views.search([('key', '=', name + '_document'), ('inherit_id', '=', False)], limit=1)
                or Views.search([('key', '=', name), ('inherit_id', '=', False)], limit=1)
            )

    @api.depends('report_view_id')
    def _compute_record_var(self):
        Anchor = self.env['number.to.words.anchor']
        for rule in self:
            rule.record_var = Anchor._guess_record_var(rule.report_view_id) if rule.report_view_id else 'doc'

    @api.onchange('report_view_id')
    def _onchange_report_view_id_places(self):
        """Places belong to one report: lines placed in another report choose again."""
        for line in self.report_line_ids:
            if line.report_anchor_id and line.report_anchor_id.view_id != self.report_view_id:
                line.report_anchor_id = False
                line.xpath_expr = False

    @api.onchange('model_id')
    def _onchange_model_reset_report(self):
        self.report_id = self.report_view_id = False

    @api.constrains('model_id', 'line_ids')
    def _check_lines_belong_to_model(self):
        for rule in self:
            for line in rule.line_ids:
                for field in (line.field_id | line.anchor_field_id | line.currency_field_id):
                    if field.model_id != rule.model_id:
                        raise ValidationError(self.env._(
                            "The field %(field)s does not belong to the model %(model)s.",
                            field=field.name, model=rule.model_id.model))

    def _active_lines(self):
        """The lines of the chosen "Show In" (the other ones are kept aside)."""
        self.ensure_one()
        return self.line_ids.filtered(lambda line: line.target == self.target)

    # ------------------------------------------------------------------
    # Generated inherited view
    # ------------------------------------------------------------------
    def _build_arch(self):
        self.ensure_one()
        lines = self._active_lines().sorted(lambda line: (line.sequence, line.id))
        # Several "after" lines on the same anchor are inserted right after
        # the anchor, so they must be emitted in reverse to keep their order.
        ordered = [line for line in lines if line.position == 'before']
        ordered += [line for line in reversed(lines) if line.position == 'after']
        data = etree.Element('data')
        for line in ordered:
            xpath = etree.SubElement(
                data, 'xpath', expr=f"//field[@name='{line.anchor_field_id.name}']", position=line.position,
            )
            etree.SubElement(xpath, 'field', name=line.field_id.name, widget='number_to_words',
                             nolabel='1', readonly='1', options=repr(line._get_widget_options()))
        return etree.tostring(data, encoding='unicode')

    def _build_report_arch(self, lines):
        lines = lines.sorted(lambda line: (line.sequence, line.id))
        ordered = [line for line in lines if line.position == 'before']
        ordered += [line for line in reversed(lines) if line.position == 'after']
        data = etree.Element('data')
        for line in ordered:
            xpath = etree.SubElement(data, 'xpath', expr=line.xpath_expr, position=line.position)
            block = etree.SubElement(xpath, 'div', {'class': 'number-to-words text-muted fst-italic'})
            etree.SubElement(block, 'span', {'t-out': line._get_report_expression(self.record_var)})
        return etree.tostring(data, encoding='unicode')

    def _check_report_anchors(self):
        Anchor = self.env['number.to.words.anchor']
        for rule in self:
            trees = {}
            for line in rule._active_lines():
                place = line.report_anchor_id
                if place and place.view_id != rule.report_view_id:
                    raise ValidationError(self.env._(
                        "The place \"%(place)s\" does not belong to the report %(report)s. "
                        "Choose the place again.",
                        place=place.name, report=rule.report_view_id.display_name))
                for template in line._get_templates():
                    if template not in trees:
                        trees[template] = Anchor._template_tree(template)
                    try:
                        found = trees[template].xpath(line.xpath_expr)
                    except etree.XPathError:
                        found = None
                    if not found:
                        raise ValidationError(self.env._(
                            "The place %(place)s was not found in the report template %(view)s.",
                            place=place.name or line.xpath_expr, view=template.display_name))

    def _check_anchors_in_view(self):
        for rule in self.filtered(lambda r: r.target == 'form'):
            if not rule._active_lines():
                continue
            combined = self.env[rule.model_id.model].get_view(rule.base_view_id.id, 'form')['arch']
            tree = etree.fromstring(combined)
            for line in rule._active_lines():
                if not tree.xpath(f"//field[@name='{line.anchor_field_id.name}']"):
                    raise ValidationError(self.env._(
                        "The field %(field)s is not displayed in the form view %(view)s. "
                        "Pick a field that is visible on that form.",
                        field=line.anchor_field_id.name, view=rule.base_view_id.display_name))

    def _sync_report_views(self):
        """One generated change per template the report lines are placed in."""
        View = self.env['ir.ui.view'].sudo()
        for rule in self:
            rule.view_id.sudo().unlink()
            groups = {}
            for line in rule._active_lines().sorted(lambda line: (line.sequence, line.id)):
                for template in line._get_templates():
                    groups[template] = groups.get(template, line.browse()) | line
            # inactive generated views must be found again when the rule is switched on
            all_views = rule.with_context(active_test=False).report_view_ids.sudo()
            existing = {view.inherit_id: view for view in all_views}
            keep = View
            for template, lines in groups.items():
                vals = {
                    'name': f"{GENERATED_VIEW_PREFIX}{rule.id}.{template.id}",
                    'model': False,
                    'type': 'qweb',
                    'mode': 'extension',
                    'inherit_id': template.id,
                    'arch_base': rule._build_report_arch(lines),
                    'active': rule.active,
                }
                view = existing.get(template)
                if view:
                    view.write(vals)
                else:
                    view = View.create(vals)
                    rule.report_view_ids = [(4, view.id)]
                keep |= view
            (all_views - keep).unlink()

    def _sync_view(self):
        View = self.env['ir.ui.view'].sudo()
        for rule in self:
            if rule.target == 'report':
                rule._sync_report_views()
                continue
            rule.with_context(active_test=False).report_view_ids.sudo().unlink()
            if not rule._active_lines():
                rule.view_id.sudo().unlink()
                continue
            vals = {
                'name': f"{GENERATED_VIEW_PREFIX}{rule.id}",
                'model': rule.model_id.model,
                'type': 'form',
                'mode': 'extension',
                'inherit_id': rule.base_view_id.id,
                'arch_base': rule._build_arch(),
                'active': rule.active,
            }
            if rule.view_id:
                rule.view_id.sudo().write(vals)
            else:
                rule.view_id = View.create(vals)

    def _refresh(self):
        # a rule that is switched off is not checked: it only has to stop showing its words
        active_rules = self.filtered('active')
        active_rules._check_anchors_in_view()
        active_rules._check_report_anchors_for_reports()
        self._sync_view()

    def _check_report_anchors_for_reports(self):
        self.filtered(lambda r: r.target == 'report')._check_report_anchors()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('target', 'form') == 'form' and not vals.get('base_view_id') and vals.get('model_id'):
                model_name = self.env['ir.model'].browse(vals['model_id']).model
                vals['base_view_id'] = self._default_form_view(model_name).id
        rules = super().create(vals_list)
        rules._refresh()
        return rules

    def write(self, vals):
        res = super().write(vals)
        self._refresh()
        return res

    def unlink(self):
        self.view_id.sudo().unlink()
        self.with_context(active_test=False).report_view_ids.sudo().unlink()
        return super().unlink()


class NumberToWordsRuleLine(models.Model):
    _name = 'number.to.words.rule.line'
    _description = 'Amount in Words Display Rule Line'
    _order = 'sequence, id'

    rule_id = fields.Many2one('number.to.words.rule', required=True, ondelete='cascade', index=True)
    target = fields.Selection(
        [('form', "Form view"), ('report', "PDF report")], default='form', required=True,
        help="Which kind of rule this line belongs to.",
    )
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        'ir.model.fields', string="Number Field", required=True, ondelete='cascade',
        help="The numeric field converted to words.",
    )
    mode = fields.Selection(
        [('currency', "Currency amount"), ('number', "Plain number")],
        default='currency', required=True,
    )
    currency_field_id = fields.Many2one(
        'ir.model.fields', string="Currency Field", ondelete='set null',
        help="Leave empty to use the 'currency_id' field of the model.",
    )
    language_id = fields.Many2one(
        'number.to.words.language', string="Language", ondelete='set null',
        help="Language of the words. Empty: the language of the settings, then of the user.",
    )
    anchor_field_id = fields.Many2one(
        'ir.model.fields', string="Place Next To", ondelete='cascade',
        help="A field displayed in the form view. The words are placed next to it.",
    )
    report_anchor_id = fields.Many2one(
        'number.to.words.anchor', string="Place in the Report", ondelete='set null',
        help="Report only: the part of the report the words are placed next to.",
    )
    xpath_expr = fields.Char(
        string="XPath", compute='_compute_xpath_expr', store=True, readonly=False,
        help="Advanced: where to place the words in the report, filled in from the chosen place.",
    )
    position = fields.Selection(
        [('after', "After"), ('before', "Before")],
        default='after', required=True,
    )

    def _get_widget_options(self):
        self.ensure_one()
        options = {'words_only': True, 'mode': self.mode}
        if self.language_id:
            options['lang'] = self.language_id.code
        if self.mode == 'currency' and self.currency_field_id:
            options['currency_field'] = self.currency_field_id.name
        return options

    @api.depends('report_anchor_id')
    def _compute_xpath_expr(self):
        for line in self:
            if line.report_anchor_id:
                line.xpath_expr = line.report_anchor_id.xpath

    @api.constrains('anchor_field_id', 'xpath_expr', 'target')
    def _check_anchor_or_xpath(self):
        for line in self:
            if line.target == 'form' and not line.anchor_field_id:
                raise ValidationError(self.env._("Choose the field the words are placed next to."))
            if line.target == 'report' and not line.xpath_expr:
                raise ValidationError(self.env._("Choose the place of the report the words are placed next to."))

    def _get_templates(self):
        """The report templates this line is placed in."""
        self.ensure_one()
        return self.report_anchor_id.template_ids or self.rule_id.report_view_id

    def _get_report_expression(self, record_var):
        """QWeb expression computing the words of this line."""
        self.ensure_one()
        args = [f"{record_var}.{self.field_id.name}", f"mode={self.mode!r}"]
        if self.language_id:
            args.append(f"lang={self.language_id.code!r}")
        if self.mode == 'currency':
            currency = self.currency_field_id.name or 'currency_id'
            args.append(f"currency_id={record_var}.{currency}.id")
        return f"env['number.to.words'].to_words({', '.join(args)})"

    def _refresh_rules(self):
        self.rule_id._refresh()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._refresh_rules()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._refresh_rules()
        return res

    def unlink(self):
        rules = self.rule_id
        res = super().unlink()
        rules._sync_view()
        return res
